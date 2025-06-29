import asyncio

# Import custom transformers
from .custom_transformers import WindowAgg, DropColumnsTransformer

from .mongo_loader import get_models_config
from .forecast_loader import ForecastLoader
from .model_predictor import ModelPredictor


async def main():
    """
    Main function to run the flood prediction.
    """
    # Step 1: Fetch all model configurations
    models_config = await get_models_config()

    # Step 2: Load forecasts for unique sources
    forecast_loader = ForecastLoader(models_config)
    forecasts = await forecast_loader.load_forecasts()

    # Step 3: Run predictions for all models
    model_predictor = ModelPredictor(models_config, forecasts)
    await model_predictor.run_predictions()


if __name__ == "__main__":
    asyncio.run(main())
