from __future__ import annotations

from harvest.sources.source_base import SourceBase, HarvestError
from harvest.mongo_client import MongoClientWrapper
from harvest.config_loader import ConfigLoader
from harvest.sources.openweather_source import OpenWeatherSource
from harvest.config_loader import SourceConfig
from harvest.utils import slugify

from typing import Iterable


class Harvester:
    """
    Harvester loads all configured sources and handles the data harvesting.

    On initialization:
      - It prepares a Mongo client (MongoClientWrapper)
      - It loads all source configurations using ConfigLoader
      - It builds a list of concrete SourceBase instances (e.g.,
        OpenWeatherSource)

    Methods:
      - harvest(): iterates over all sources, calls their harvest method,
        inserts the result into the MongoDB collection named by type and region.

    Example collections:
      - "openweather_sao_paulo"
      - "openweather_santo_andre_tam_central" (if subregion exists)

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
        """
        Loads all source configurations from MongoDB.
        """
        loader = ConfigLoader(self.mongo)
        configs = await loader.load()
        return configs

    def _build_source(self, cfg: SourceConfig) -> SourceBase:
        """
        Maps a SourceConfig to its concrete SourceBase implementation.
        """
        if cfg.type == "openweather":
            return OpenWeatherSource(cfg)
        raise NotImplementedError(
            f"Source type '{cfg.type}' is not implemented."
        )

    # ------------------------------------------------------------------ #
    async def harvest(self) -> dict[str, dict[str, int]]:
        """
        Harvests data from all sources and inserts into appropriate MongoDB
        collections.

        Returns:
            A dictionary summarizing the number of inserted, skipped, and
            failed operations per source type.
        """
        if not self._loaded_configs:
            all_cfgs = await self._build_configs()
            self._loaded_configs = all_cfgs
            self.sources = [self._build_source(c) for c in self._loaded_configs]

        summary: dict[str, dict[str, int]] = {}
        default_counters: dict[str, int] = {
            "inserted": 0, 
            "skipped": 0, 
            "failed": 0
        }

        for src in self.sources:
            region_slug = slugify(f"{src.region} {src.subregion}")
            coll_name = f"{src.type}_{region_slug}"

            if src.type not in summary:
                summary[src.type] = default_counters.copy()

            try:
                payload = await src.harvest()
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
                summary[src.type]["failed"] += 1
                print(f"⚠️  {src.type} failed: {exc}")
                continue

        return summary
