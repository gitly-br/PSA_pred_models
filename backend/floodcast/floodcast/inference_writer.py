import os
from datetime import datetime
import pytz
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

FEATURE_DICT = {
    "rain": "precipitação",
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
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = "floodcast_db"
        self.collection_name = "inference"

    def _calculate_distribution(self, rain_distribution: dict, proba: float) -> dict:
        distribution = {}
        value_total = rain_distribution["today"]["total"]
        value_night = rain_distribution["today"]["night"]
        value_morning = rain_distribution["today"]["morning"]
        value_afternoon = rain_distribution["today"]["afternoon"]
        value_evening = rain_distribution["today"]["evening"]
        distribution["night"] = (value_night / value_total) * proba
        distribution["morning"] = (value_morning / value_total) * proba
        distribution["afternoon"] = (value_afternoon / value_total) * proba
        distribution["evening"] = (value_evening / value_total) * proba
        return distribution

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
        return f"O modelo deu mais importância para a {agg_translated} de {feature_translated} entre {start}h e {end}h"

    def _get_current_rounded_hour(self) -> datetime:
        now_utc = datetime.now(pytz.utc)
        return now_utc.replace(minute=0, second=0, microsecond=0)

    async def _build_inference_object(self, all_predictions: list[dict]) -> dict:
        if not all_predictions:
            raise ValueError("--- No predictions provided to build inference object.")

        # Assuming all predictions belong to the same region for a single inference object
        # This can be refined if multi-region inference objects are needed later.
        top_level_region = all_predictions[0].get("region", "unknown_region")
        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        dt_inference = datetime.now(sao_paulo_tz)
        dt_key = datetime(dt_inference.year, dt_inference.month, dt_inference.day, tzinfo=sao_paulo_tz)

        results_by_day_and_subregion = defaultdict(lambda: defaultdict(lambda: {"predicts": [], "probas": [], "shaps": [], "models": {}}))

        for pred in all_predictions:
            day = pred.get("day")
            if not day:
                raise ValueError("--- Prediction object missing 'day' key.")
            subregion = pred.get("subregion", "unknown_subregion")
            model_name = pred.get("model_name", "unknown_model")
            predict_value = pred.get("predict")
            proba_value = pred.get("proba")
            shap_explanation = pred.get("shap_explanation")
            rain_distribution = pred.get("rain_distribution")

            # Store individual model results
            model_result = {"predict": predict_value}
            model_result["shap"] = shap_explanation
            if proba_value is not None:
                model_result["proba"] = proba_value
            results_by_day_and_subregion[day][subregion]["models"][model_name] = model_result

            # Collect for subregion aggregation
            results_by_day_and_subregion[day][subregion]["predicts"].append(predict_value)
            if shap_explanation is not None:
                results_by_day_and_subregion[day][subregion]["shaps"].append(shap_explanation)
            if proba_value is not None:
                results_by_day_and_subregion[day][subregion]["probas"].append(proba_value)

        # Finalize results for each subregion and 'all'
        final_results_by_day = defaultdict(dict)
        for day, subregions_data in results_by_day_and_subregion.items():
            for subregion, data in subregions_data.items():
                subregion_predict = int(sum(data["predicts"]) / len(data["predicts"])) if data["predicts"] else 0
                subregion_proba = sum(data["probas"]) / len(data["probas"]) if data["probas"] else None
                # TODO: Isso aqui esta porco!! Arrumar para uma logica decente depois
                subregion_shap = data["shaps"][0]

                if rain_distribution.get(day).get("total") < 3.5:
                    explanation = "Não há precipitação significativa prevista para o período"
                    rain_today = {"night": 0, "morning": 0, "afternoon": 0, "evening": 0}
                    subregion_proba = 0
                    subregion_predict = 0
                elif subregion_predict == 0:
                    explanation = "Há previsão de chuva, mas o modelo não detectou nenhuma condição preocupante na previsão."
                    rain_today = {"night": 0, "morning": 0, "afternoon": 0, "evening": 0}
                else:
                    explanation = self._get_explanation(subregion_shap)
                    rain_today = self._calculate_distribution(rain_distribution, subregion_proba)
                
                final_results_by_day[day][subregion] = {
                    "predict": subregion_predict,
                    "proba": subregion_proba,
                    "explanation": explanation,
                    "rain_today": rain_today,
                    "models": data["models"]
                }
            
            # Coercion logic for 'all' model
            all_model_result = final_results_by_day[day].get("all")
            if all_model_result and all_model_result["predict"] == 0:
                all_explanation = all_model_result["explanation"]
                all_proba = all_model_result["proba"]
                all_rain_today = {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0}

                for subregion, result in final_results_by_day[day].items():
                    if subregion != "all":
                        result["predict"] = 0
                        result["proba"] *= all_proba 
                        result["explanation"] = all_explanation
                        result["rain_today"] = all_rain_today
        
        inference_object = {
            "obj_version": "0.2",
            "dt_inference": dt_inference,
            "dt_key": dt_key,
            "region": top_level_region,
            "timezone": "America/Sao_Paulo",
            "timezone_offset": int(dt_inference.utcoffset().total_seconds()),
            "results": final_results_by_day
        }
        return inference_object

    async def write_inference_object(self, all_predictions: list[dict]):
        inference_object = await self._build_inference_object(all_predictions)
        dt_key = inference_object["dt_key"]
        region = inference_object["region"]

        client = AsyncIOMotorClient(self.mongo_uri)
        collection = client[self.db_name][self.collection_name]

        # Check for duplicates for the current day and region
        existing_record = await collection.find_one({
            "dt_key": dt_key,
            "region": region
        })

        if existing_record:
            print(f"**** Inference record for {region} on {dt_key.date()} already exists. Skipping write.")
        else:
            try:
                await collection.insert_one(inference_object)
                print(f"++++ Successfully wrote inference record for {region} on {dt_key.date()} to MongoDB.")
            except Exception as e:
                print(f"---- Error writing inference record to MongoDB: {e}")
