from __future__ import annotations

import logging
from typing import Any

from pymongo import UpdateOne

from harvest.sources.source_base import SourceBase, HarvestError
from harvest.mongo_client import MongoClientWrapper
from harvest.config_loader import ConfigLoader
from harvest.sources.openweather_source import OpenWeatherSource
from harvest.sources.defesa_civil_source import DefesaCivilSource
from harvest.sources.openmeteo_source import OpenMeteoSource
from harvest.config_loader import SourceConfig
from harvest.utils import slugify

logger = logging.getLogger(__name__)


HISTORIC_INDEXES = (
    ([("provider", 1), ("station_id", 1), ("dt", 1)], "historic_provider_station_dt_idx"),
    ([("bacia", 1), ("dt", 1)], "historic_bacia_dt_idx"),
    ([("bacias", 1), ("dt", 1)], "historic_bacias_dt_idx"),
    ([("station_id", 1), ("dt", 1)], "historic_station_id_dt_idx"),
)

FORECAST_INDEXES = (
    ([("provider", 1), ("point_id", 1), ("dt_request", 1)], "forecast_provider_point_dt_idx"),
)


class Harvester:
    """
    Harvester loads all configured sources and handles the data harvesting.

    On initialization:
      - It prepares a Mongo client (MongoClientWrapper)
      - It loads all source configurations using ConfigLoader
      - It builds a list of concrete SourceBase instances

    Methods:
      - harvest(): iterates over all sources, calls their harvest method,
        inserts the result into the appropriate MongoDB collection.

    Summary of harvest() result:
      {
        "openweather": {"inserted": 10, "skipped": 2, "failed": 1},
        ...
      }
    """

    def __init__(self, mongo: MongoClientWrapper) -> None:
        self.mongo = mongo
        self._loaded_configs: list[SourceConfig] = []
        self.sources: list[SourceBase] = []

    async def _build_configs(self) -> list[SourceConfig]:
        loader = ConfigLoader(self.mongo)
        configs = await loader.load()
        return configs

    def _build_source(self, cfg: SourceConfig) -> SourceBase:
        if cfg.type == "openweather":
            return OpenWeatherSource(cfg)
        if cfg.type == "defesa_civil":
            return DefesaCivilSource(cfg)
        if cfg.type == "openmeteo":
            return OpenMeteoSource(cfg)
        raise NotImplementedError(
            f"Source type '{cfg.type}' is not implemented."
        )

    async def _ensure_api_data_indexes(self, target: str) -> None:
        if target == "api_data.historic":
            coll = self.mongo.get_data_collection("historic")
            for keys, name in HISTORIC_INDEXES:
                unique = name == "historic_provider_station_dt_idx"
                await coll.create_index(keys, name=name, unique=unique, background=True)
        elif target == "api_data.forecast":
            coll = self.mongo.get_data_collection("forecast")
            for keys, name in FORECAST_INDEXES:
                await coll.create_index(keys, name=name, unique=True, background=True)

    async def _upsert_historic(self, documents: list[dict[str, Any]]) -> int:
        if not documents:
            return 0
        coll = self.mongo.get_data_collection("historic")
        await self._ensure_api_data_indexes("api_data.historic")
        operations = [
            UpdateOne(
                {"provider": doc["provider"], "station_id": doc["station_id"], "dt": doc["dt"]},
                {"$set": doc},
                upsert=True,
            )
            for doc in documents
        ]
        result = await coll.bulk_write(operations, ordered=False)
        return result.upserted_count + result.modified_count

    async def _upsert_forecast(self, documents: list[dict[str, Any]]) -> int:
        if not documents:
            return 0
        coll = self.mongo.get_data_collection("forecast")
        await self._ensure_api_data_indexes("api_data.forecast")
        operations = [
            UpdateOne(
                {"provider": doc["provider"], "point_id": doc["point_id"], "dt_request": doc["dt_request"]},
                {"$set": doc},
                upsert=True,
            )
            for doc in documents
        ]
        result = await coll.bulk_write(operations, ordered=False)
        return result.upserted_count + result.modified_count

    async def harvest(self) -> dict[str, dict[str, int]]:
        if not self._loaded_configs:
            all_cfgs = await self._build_configs()
            self._loaded_configs = all_cfgs
            self.sources = [self._build_source(c) for c in self._loaded_configs]

        summary: dict[str, dict[str, int]] = {}
        default_counters: dict[str, int] = {
            "inserted": 0,
            "skipped": 0,
            "failed": 0,
        }

        for src in self.sources:
            if src.type not in summary:
                summary[src.type] = default_counters.copy()

            try:
                payload = await src.harvest()
                target = getattr(src, "target", None)

                if target == "api_data.historic":
                    count = await self._upsert_historic(list(payload))
                    summary[src.type]["inserted"] += count
                elif target == "api_data.forecast":
                    count = await self._upsert_forecast(list(payload))
                    summary[src.type]["inserted"] += count
                else:
                    region_slug = slugify(f"{src.region} {src.subregion}")
                    coll_name = f"{src.type}_{region_slug}"
                    coll = self.mongo.get_data_collection(coll_name)
                    await self.mongo.ensure_indexes(
                        coll,
                        dedup_key="dt_request",
                        ttl_days=src.src_config.ttl_days,
                    )
                    is_duplicate = await self.mongo.insert_one_safe(coll, payload)
                    if is_duplicate:
                        summary[src.type]["skipped"] += 1
                    else:
                        summary[src.type]["inserted"] += 1

            except HarvestError as exc:
                logger.debug(f"HarvestError for {src.type}: {exc}")
                summary[src.type]["failed"] += 1
                continue

        return summary
