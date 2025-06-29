import asyncio
import pandas as pd
import gdown
import joblib
import os
# Import custom transformers
from .custom_transformers import WindowAgg, DropColumnsTransformer

from .mongo_loader import get_models_config, get_latest_hourly_data


async def grab_from_gdrive(file_id, filename):

  url = f"https://drive.google.com/uc?id={file_id}"
  output = os.path.join('.', filename)
  if not(os.path.isfile(output)):
    gdown.download(url, output=output, quiet=True)


async def main():
    """
    Main function to run the flood prediction.
    """
    # Step 1: Fetch all model configurations
    models_config = await get_models_config()

    for model_config in models_config:
        model_name = model_config.get("name", "unknown_model")
        source_collection = model_config.get("source")
        pipeline_file_id = model_config.get("files", {}).get("pipeline")

        if not source_collection or not pipeline_file_id:
            print(f"Skipping model {model_name}: Missing source collection or pipeline file ID.")
            continue

        print(f"\nProcessing model: {model_name}")

        # Step 2: Fetch the latest raw hourly data from MongoDB for the specific source
        try:
            hourly_forecast = await get_latest_hourly_data(source_collection)
            hourly_df = pd.DataFrame(hourly_forecast)
        except RuntimeError as e:
            print(f"Error fetching data for {model_name}: {e}")
            continue

        # Step 3: Download and load the feature engineering pipeline
        pipeline_filename = f"pipeline_{model_name}.joblib"
        await grab_from_gdrive(pipeline_file_id, pipeline_filename)
        
        if not os.path.exists(pipeline_filename):
            print(f"Error: Pipeline file {pipeline_filename} not downloaded for model {model_name}.")
            continue

        try:
            pipeline = joblib.load(pipeline_filename)
        except Exception as e:
            print(f"Error loading pipeline for {model_name}: {e}")
            continue

        # Step 4: Run the pipeline and make prediction
        print(f"Running pipeline for {model_name}...")
        try:
            prediction = pipeline.predict(hourly_df)[0]
            print(f"Prediction for {model_name}: {prediction}")
        except Exception as e:
            print(f"Error during prediction for {model_name}: {e}")
            continue

        # Clean up the downloaded pipeline file
        os.remove(pipeline_filename)
        print(f"Cleaned up {pipeline_filename}")


if __name__ == "__main__":
    asyncio.run(main())
