import asyncio

# Import custom transformers
from .custom_transformers import WindowAgg, DropColumnsTransformer

from .mongo_loader import get_models_config
from .forecast_loader import ForecastLoader
from .model_predictor import ModelPredictor
from .inference_writer import InferenceWriter


async def main():
    """
    Main function to run the flood prediction.
    """
    # Step 1: Fetch all model configurations
    print("========= Fetching models =========")
    models_config = await get_models_config()

    # Step 2: Load forecasts for unique sources
    print("\n\n========= Fetching forecasts =========")
    forecast_loader = ForecastLoader(models_config)
    forecasts = await forecast_loader.load_forecasts()

    # Step 3: Run predictions for all models
    print("\n\n========= Running predicitons =========")
    model_predictor = ModelPredictor(models_config, forecasts)
    all_predictions = await model_predictor.run_predictions()

    # Step 4: Write inference results to MongoDB
    print("\n\n========= Writing inferences =========")
    inference_writer = InferenceWriter()
    await inference_writer.write_inference_object(all_predictions)


if __name__ == "__main__":
    asyncio.run(main())
