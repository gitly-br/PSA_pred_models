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

    async def _get_rain_distribution(self, df):
        distribution = {"today": {}, "tomorrow": {}}
        distribution["today"]["total"] = df.iloc[:24].rain.sum()
        distribution["tomorrow"]["total"] = df.iloc[24:48].rain.sum()
        distribution["today"]["night"] = df.iloc[:6].rain.sum()
        distribution["today"]["morning"] = df.iloc[6:12].rain.sum()
        distribution["today"]["afternoon"] = df.iloc[12:18].rain.sum()
        distribution["today"]["evening"] = df.iloc[18:24].rain.sum()
        distribution["tomorrow"]["night"] = df.iloc[24:30].rain.sum()
        distribution["tomorrow"]["morning"] = df.iloc[30:36].rain.sum()
        distribution["tomorrow"]["afternoon"] = df.iloc[36:42].rain.sum()
        distribution["tomorrow"]["evening"] = df.iloc[42:48].rain.sum()
        return distribution

    async def _process_single_model(self, model_config: dict) -> dict | None:
        model_name = model_config.get("name", "unknown_model")
        region = model_config.get("region", "unknown_region")
        subregion = model_config.get("subregion", "unknown_subregion")
        source_collection = model_config.get("source")
        pipeline_file_id = model_config.get("files", {}).get("pipeline")
        explainer_file_id = model_config.get("files", {}).get("explainer")

        if not source_collection or not pipeline_file_id:
            print(f"---- Skipping model {model_name}: Missing source collection or pipeline file ID.")
            return None

        print(f"==== Processing model: {region}/{subregion}/{model_name}")

        if source_collection not in self.forecasts:
            print(f"---- Skipping model {model_name}: Forecast data not available for source {source_collection}.")
            return None

        hourly_df = self.forecasts[source_collection]
        rain_distribution = await self._get_rain_distribution(hourly_df)

        # Download and load the pipeline
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

        # Download and load the explainer
        explainer_filename = f"explainer_{region}_{subregion}_{model_name}.joblib"
        try:
            await grab_from_gdrive(explainer_file_id, explainer_filename)
            if not os.path.exists(explainer_filename):
                print(f"---- Error: Explainer file {explainer_filename} not downloaded for model {region}/{subregion}/{model_name}.")
                return None

            explainer = joblib.load(explainer_filename)
        except Exception as e:
            print(f"---- Error loading explainer for {region}/{subregion}/{model_name}: {e}")
            return None

        try:
            prediction_value = int(pipeline.predict(hourly_df)[0])
            proba_value = None
            if hasattr(pipeline, 'predict_proba'):
                proba_value = float(pipeline.predict_proba(hourly_df)[0][1]) # Probability of the positive class
                print(f"++++ Prediction for {region}/{subregion}/{model_name}: {prediction_value} (Proba: {proba_value:.2f})")
            else:
                print(f"**** Prediction for {region}/{subregion}/{model_name}: {prediction_value}")
            hourly_agg = pipeline.named_steps["aggregator"].transform(hourly_df)
            hourly_pp = pipeline.named_steps["dt_dropper"].transform(hourly_agg)
            shap_values = explainer.shap_values(hourly_pp)
            column_names = hourly_pp.columns
            shap_converted = [float(x) for x in shap_values[0]]
            explainer_values = sorted(list(zip(column_names, shap_converted)), key=lambda x: x[1], reverse=True)
            result = {
                "model_name": model_name,
                "region": region,
                "subregion": subregion,
                "predict": prediction_value,
                "shap_explanation": explainer_values,
                "rain_distribution": rain_distribution,
                "day": model_config.get("day")
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
