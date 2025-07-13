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

import argparse
from .logger import configure_logging, get_logger


if __name__ == "__main__":
    main()

async def main():
    """
    Main function to run the flood prediction.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    args = parser.parse_args()
    
    # Configure logging before importing other modules
    configure_logging(debug=args.debug)
    logger = get_logger(__name__)

    logger.info("Starting floodcast job")
    # Step 1: Fetch all model configurations
    models_config = await get_models_config()

    # Step 2: Check if inference is needed
    inference_writer = InferenceWriter()
    models_to_run = await inference_writer.check_inference_needed(models_config)

    if not models_to_run:
        logger.warning("No new inference needed. Exiting...")
        return

    # Step 3: Load forecasts for unique sources
    forecast_loader = ForecastLoader(models_to_run)
    forecasts = await forecast_loader.load_forecasts()

    # Step 4: Run predictions for all models
    model_predictor = ModelPredictor(models_to_run, forecasts)
    all_predictions = await model_predictor.run_predictions()

    # Step 5: Write inference results to MongoDB
    await inference_writer.write_inference_object(all_predictions)
    logger.info("is done")


if __name__ == "__main__":
    asyncio.run(main())


def main_sync():
    """Synchronous entry point for setup.py."""
    asyncio.run(main())

