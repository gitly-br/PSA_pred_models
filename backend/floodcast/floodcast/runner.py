from __future__ import annotations

from datetime import datetime

from .forecast_loader import ForecastLoader
from .inference_writer import InferenceWriter
from .logger import configure_logging, get_logger
from .model_predictor import ModelPredictor
from .mongo_loader import get_models_config


async def run_floodcast(target_date: datetime | None = None, debug: bool = False) -> bool:
    configure_logging(debug=debug)
    logger = get_logger(__name__)

    logger.info("Starting floodcast job for date: %s", target_date.strftime("%Y-%m-%d") if target_date else "today")
    models_config = await get_models_config()

    inference_writer = InferenceWriter(target_date=target_date)
    models_to_run = await inference_writer.check_inference_needed(models_config)

    if not models_to_run:
        logger.warning("No new inference needed. Exiting...")
        return False

    forecast_loader = ForecastLoader(models_to_run, target_date=target_date)
    forecasts = await forecast_loader.load_forecasts()

    model_predictor = ModelPredictor(models_to_run, forecasts)
    all_predictions = await model_predictor.run_predictions()

    await inference_writer.write_inference_object(all_predictions)
    logger.info("is done")
    return True
