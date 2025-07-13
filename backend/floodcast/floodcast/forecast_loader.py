import pandas as pd
from .mongo_loader import get_latest_hourly_data
from .logger import get_logger

logger = get_logger(__name__)

class ForecastLoader:
    def __init__(self, models_config: list):
        self.models_config = models_config
        self.unique_sources = self._get_unique_sources()

    def _get_unique_sources(self) -> set:
        sources = set()
        for model_config in self.models_config:
            source = model_config.get("source")
            if source:
                sources.add(source)
        return sources

    async def load_forecasts(self) -> dict[str, pd.DataFrame]:
        forecasts = {}
        for source in self.unique_sources:
            try:
                hourly_forecast_list = await get_latest_hourly_data(source)
                forecasts[source] = pd.DataFrame(hourly_forecast_list)
                logger.debug(f"Successfully loaded forecast for source: {source}")
            except RuntimeError as e:
                logger.error(f"Error loading forecast for source {source}: {e}")
            except Exception as e:
                logger.error(f"An unexpected error occurred while loading forecast for source {source}: {e}")
        return forecasts
