import asyncio
import sys

# Import custom transformers
from floodcast import custom_transformers
from floodcast.custom_transformers import WindowAgg, DropColumnsTransformer
sys.modules['__main__'] = custom_transformers


from .mongo_loader import get_models_config
from .forecast_loader import ForecastLoader
from .model_predictor import ModelPredictor
from .inference_writer import InferenceWriter


async def main():
    """
    Main function to run the flood prediction.
    """
    # Step 1: Fetch all model configurations
    print("========= Fetching models ========")
    models_config = await get_models_config()

    # Step 2: Check if inference is needed
    print("\n\n========= Checking if inference is needed ========")
    inference_writer = InferenceWriter()
    models_to_run = await inference_writer.check_inference_needed(models_config)

    if not models_to_run:
        print("\n\n========= No new inferences needed. Exiting. ========")
        return

    # Step 3: Load forecasts for unique sources
    print("\n\n========= Fetching forecasts ========")
    forecast_loader = ForecastLoader(models_to_run)
    forecasts = await forecast_loader.load_forecasts()

    # Step 4: Run predictions for all models
    print("\n\n========= Running predicitons ========")
    model_predictor = ModelPredictor(models_to_run, forecasts)
    all_predictions = await model_predictor.run_predictions()

    # Step 5: Write inference results to MongoDB
    print("\n\n========= Writing inferences ========")
    await inference_writer.write_inference_object(all_predictions)


if __name__ == "__main__":
    asyncio.run(main())


def main_sync():
    """Synchronous entry point for setup.py."""
    asyncio.run(main())

