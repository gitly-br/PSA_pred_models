import joblib
import os
import gdown
import pandas as pd
import asyncio

async def grab_from_gdrive(file_id, filename):
  url = f"https://drive.google.com/uc?id={file_id}"
  output = os.path.join('.', filename)
  if not(os.path.isfile(output)):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, lambda: gdown.download(url, output=output, quiet=True))

class ModelPredictor:
    def __init__(self, models_config: list, forecasts: dict[str, pd.DataFrame]):
        self.models_config = models_config
        self.forecasts = forecasts

    async def _process_single_model(self, model_config: dict) -> dict | None:
        model_name = model_config.get("name", "unknown_model")
        region = model_config.get("region", "unknown_region")
        subregion = model_config.get("subregion", "unknown_subregion")
        source_collection = model_config.get("source")
        pipeline_file_id = model_config.get("files", {}).get("pipeline")

        if not source_collection or not pipeline_file_id:
            print(f"---- Skipping model {model_name}: Missing source collection or pipeline file ID.")
            return None

        print(f"==== Processing model: {region}/{subregion}/{model_name}")

        if source_collection not in self.forecasts:
            print(f"---- Skipping model {model_name}: Forecast data not available for source {source_collection}.")
            return None

        hourly_df = self.forecasts[source_collection]

        # Download and load the feature engineering pipeline
        pipeline_filename = f"pipeline_{region}_{subregion}_{model_name}.joblib"
        try:
            await grab_from_gdrive(pipeline_file_id, pipeline_filename)
            if not os.path.exists(pipeline_filename):
                print(f"---- Error: Pipeline file {pipeline_filename} not downloaded for model {model_name}.")
                return None

            pipeline = joblib.load(pipeline_filename)
        except Exception as e:
            print(f"---- Error loading pipeline for {model_name}: {e}")
            return None

        try:
            prediction_value = int(pipeline.predict(hourly_df)[0])
            proba_value = None
            if hasattr(pipeline, 'predict_proba'):
                proba_value = float(pipeline.predict_proba(hourly_df)[0][1]) # Probability of the positive class
                print(f"++++ Prediction for {region}/{subregion}/{model_name}: {prediction_value} (Proba: {proba_value:.2f})")
            else:
                print(f"**** Prediction for {region}/{subregion}/{model_name}: {prediction_value}")
            
            result = {
                "model_name": model_name,
                "region": region,
                "subregion": subregion,
                "predict": prediction_value
            }
            if proba_value is not None:
                result["proba"] = proba_value
            return result

        except Exception as e:
            print(f"---- Error during prediction for {region}/{subregion}/{model_name}: {e}")
            return None

        finally:
            # Clean up the downloaded pipeline file
            if os.path.exists(pipeline_filename):
                os.remove(pipeline_filename)
                print(f"**** Cleaned up {pipeline_filename}")

    async def run_predictions(self) -> list[dict]:
        tasks = [self._process_single_model(model_config) for model_config in self.models_config]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
