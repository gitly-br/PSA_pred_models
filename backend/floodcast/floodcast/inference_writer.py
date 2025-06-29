from datetime import datetime
import pytz
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict

class InferenceWriter:
    def __init__(self):
        self.mongo_uri = "mongodb://host.docker.internal:27017"
        self.db_name = "floodcast_db"
        self.collection_name = "inference"

    def _get_current_rounded_hour(self) -> datetime:
        now_utc = datetime.now(pytz.utc)
        return now_utc.replace(minute=0, second=0, microsecond=0)

    async def _build_inference_object(self, all_predictions: list[dict]) -> dict:
        if not all_predictions:
            raise ValueError("No predictions provided to build inference object.")

        # Assuming all predictions belong to the same region for a single inference object
        # This can be refined if multi-region inference objects are needed later.
        top_level_region = all_predictions[0].get("region", "unknown_region")
        dt_inference = self._get_current_rounded_hour()

        results_by_subregion = defaultdict(lambda: {"predicts": [], "probas": [], "models": {}})
        all_region_predicts = []
        all_region_probas = []

        for pred in all_predictions:
            subregion = pred.get("subregion", "unknown_subregion")
            model_name = pred.get("model_name", "unknown_model")
            predict_value = pred.get("predict")
            proba_value = pred.get("proba")

            # Store individual model results
            model_result = {"predict": predict_value}
            if proba_value is not None:
                model_result["proba"] = proba_value
            results_by_subregion[subregion]["models"][model_name] = model_result

            # Collect for subregion aggregation
            results_by_subregion[subregion]["predicts"].append(predict_value)
            if proba_value is not None:
                results_by_subregion[subregion]["probas"].append(proba_value)
            
            # Collect for 'all' region aggregation
            all_region_predicts.append(predict_value)
            if proba_value is not None:
                all_region_probas.append(proba_value)

        # Finalize results for each subregion and 'all'
        final_results = {}
        for subregion, data in results_by_subregion.items():
            subregion_predict = int(sum(data["predicts"]) / len(data["predicts"])) if data["predicts"] else 0
            subregion_proba = sum(data["probas"]) / len(data["probas"]) if data["probas"] else None
            
            final_results[subregion] = {
                "predict": subregion_predict,
                "proba": subregion_proba,
                "models": data["models"]
            }
        
        # Add 'all' region aggregation
        all_predict = int(sum(all_region_predicts) / len(all_region_predicts)) if all_region_predicts else 0
        all_proba = sum(all_region_probas) / len(all_region_probas) if all_region_probas else None
        
        final_results["all"] = {
            "predict": all_predict,
            "proba": all_proba,
            "models": {model_name: data["models"][model_name] for subregion, data in results_by_subregion.items() for model_name in data["models"]}
        }

        inference_object = {
            "obj_version": "0.1",
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
            print(f"Inference record for {region} at {dt_inference_hour} already exists. Skipping write.")
        else:
            try:
                await collection.insert_one(inference_object)
                print(f"Successfully wrote inference record for {region} at {dt_inference_hour} to MongoDB.")
            except Exception as e:
                print(f"Error writing inference record to MongoDB: {e}")
