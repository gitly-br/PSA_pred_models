from datetime import datetime
import pytz
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

FEATURE_DICT = {
    "rain": "chuva",
    "temp": "temperatura",
    "wind_speed": "velocidade do vento",
    "dew_point": "ponto de orvalho"
}

AGG_DICT = {
    "sum": "quantidade acumulada",
    "delta": "variação"
}

class InferenceWriter:
    def __init__(self):
        self.mongo_uri = "mongodb://host.docker.internal:27017"
        self.db_name = "floodcast_db"
        self.collection_name = "inference"

    def _get_explanation(self, shap_values: list[tuple]) -> str:
        most_important_feature = shap_values[0][0]
        split_feature_name = most_important_feature.split("_")
        agg, start, end = split_feature_name[-3::1]
        feature = "_".join(split_feature_name[:-3])
        if feature in FEATURE_DICT:
            feature_translated = FEATURE_DICT[feature]
        else:
            feature_translated = feature
        if agg in AGG_DICT:
            agg_translated = AGG_DICT[agg]
        else:
            agg_translated = agg
        return f"O modelo detectou uma {agg_translated} de {feature_translated} anormal entre {start}h e {end}h"

    def _get_current_rounded_hour(self) -> datetime:
        now_utc = datetime.now(pytz.utc)
        return now_utc.replace(minute=0, second=0, microsecond=0)

    async def _build_inference_object(self, all_predictions: list[dict]) -> dict:
        if not all_predictions:
            raise ValueError("--- No predictions provided to build inference object.")

        # Assuming all predictions belong to the same region for a single inference object
        # This can be refined if multi-region inference objects are needed later.
        top_level_region = all_predictions[0].get("region", "unknown_region")
        dt_inference = self._get_current_rounded_hour()

        results_by_subregion = defaultdict(lambda: {"predicts": [], "probas": [], "shaps": [], "models": {}})

        for pred in all_predictions:
            subregion = pred.get("subregion", "unknown_subregion")
            model_name = pred.get("model_name", "unknown_model")
            predict_value = pred.get("predict")
            proba_value = pred.get("proba")
            shap_explanation = pred.get("shap_explanation")

            # Store individual model results
            model_result = {"predict": predict_value}
            model_result["shap"] = shap_explanation
            if proba_value is not None:
                model_result["proba"] = proba_value
            results_by_subregion[subregion]["models"][model_name] = model_result

            # Collect for subregion aggregation
            results_by_subregion[subregion]["predicts"].append(predict_value)
            if shap_explanation is not None:
                results_by_subregion[subregion]["shaps"].append(shap_explanation)
            if proba_value is not None:
                results_by_subregion[subregion]["probas"].append(proba_value)

        # Finalize results for each subregion and 'all'
        final_results = {}
        for subregion, data in results_by_subregion.items():
            subregion_predict = int(sum(data["predicts"]) / len(data["predicts"])) if data["predicts"] else 0
            subregion_proba = sum(data["probas"]) / len(data["probas"]) if data["probas"] else None
            # TODO: Isso aqui esta porco!! Arrumar para uma logica decente depois
            subregion_shap = data["shaps"][0]

            if subregion_predict == 0:
                # explanation = "Há previsão de chuva, mas o modelo não detectou nenhuma condição preocupante na previsão."
                explanation = self._get_explanation(subregion_shap)
            else:
                explanation = self._get_explanation(subregion_shap)
            
            final_results[subregion] = {
                "predict": subregion_predict,
                "proba": subregion_proba,
                "explanation": explanation,
                "models": data["models"]
            }
        
        inference_object = {
            "obj_version": "0.2",
            "dt_inference": dt_inference,
            "region": top_level_region,
            "results": final_results
        }
        return inference_object

    async def write_inference_object(self, all_predictions: list[dict]):
        inference_object = await self._build_inference_object(all_predictions)
        dt_inference_hour = inference_object["dt_inference"]
        region = inference_object["region"]

        client = AsyncIOMotorClient(self.mongo_uri)
        collection = client[self.db_name][self.collection_name]

        # Check for duplicates for the current hour and region
        existing_record = await collection.find_one({
            "dt_inference": dt_inference_hour,
            "region": region
        })

        if existing_record:
            print(f"**** Inference record for {region} at {dt_inference_hour} already exists. Skipping write.")
        else:
            try:
                await collection.insert_one(inference_object)
                print(f"++++ Successfully wrote inference record for {region} at {dt_inference_hour} to MongoDB.")
            except Exception as e:
                print(f"---- Error writing inference record to MongoDB: {e}")
