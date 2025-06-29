import joblib
import os
import gdown
import pandas as pd

async def grab_from_gdrive(file_id, filename):
  url = f"https://drive.google.com/uc?id={file_id}"
  output = os.path.join('.', filename)
  if not(os.path.isfile(output)):
    gdown.download(url, output=output, quiet=True)

class ModelPredictor:
    def __init__(self, models_config: list, forecasts: dict[str, pd.DataFrame]):
        self.models_config = models_config
        self.forecasts = forecasts

    async def run_predictions(self):
        print("\nRunning predictions for all models...")
        for model_config in self.models_config:
            model_name = model_config.get("name", "unknown_model")
            source_collection = model_config.get("source")
            pipeline_file_id = model_config.get("files", {}).get("pipeline")

            if not source_collection or not pipeline_file_id:
                print(f"Skipping model {model_name}: Missing source collection or pipeline file ID.")
                continue

            print(f"\nProcessing model: {model_name}")

            if source_collection not in self.forecasts:
                print(f"Skipping model {model_name}: Forecast data not available for source {source_collection}.")
                continue

            hourly_df = self.forecasts[source_collection]

            # Download and load the feature engineering pipeline
            pipeline_filename = f"pipeline_{model_name}.joblib"
            try:
                await grab_from_gdrive(pipeline_file_id, pipeline_filename)
                
                if not os.path.exists(pipeline_filename):
                    print(f"Error: Pipeline file {pipeline_filename} not downloaded for model {model_name}.")
                    continue

                pipeline = joblib.load(pipeline_filename)
            except Exception as e:
                print(f"Error loading pipeline for {model_name}: {e}")
                continue

            # Run the pipeline and make prediction
            print(f"Running pipeline for {model_name}...")
            try:
                prediction = int(pipeline.predict(hourly_df)[0])
                if hasattr(pipeline, 'predict_proba'):
                    proba = pipeline.predict_proba(hourly_df)[0][1] # Probability of the positive class
                    print(f"Prediction for {model_name}: {prediction} (Proba: {proba:.4f})")
                else:
                    print(f"Prediction for {model_name}: {prediction}")
            except Exception as e:
                print(f"Error during prediction for {model_name}: {e}")
                continue

            # Clean up the downloaded pipeline file
            os.remove(pipeline_filename)
            print(f"Cleaned up {pipeline_filename}")
