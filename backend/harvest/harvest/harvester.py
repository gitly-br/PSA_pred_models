from __future__ import annotations
from collections import defaultdict
from typing import Mapping, Iterable, Any

from harvest.utils import bucketize
from harvest.constants import DEFAULT_TTL_DAYS
from harvest.mongo_client import MongoClientWrapper
from harvest.config_loader import SourceConfig
from harvest.sources.openweather_source import OpenWeatherSource
from harvest.sources.source_base import SourceBase, HarvestError


class Harvester:
    def __init__(
        self,
        configs: Iterable[SourceConfig],
        city: str,
        mongo: MongoClientWrapper,
    ) -> None:
        self.city = city
        self.mongo = mongo
        self.configs = [c for c in configs if c.city == city]
        self.sources: list[SourceBase] = [
            self._build_source(c) for c in self.configs
        ]

    def _build_source(self, cfg: SourceConfig) -> SourceBase:
        if cfg.type == "openweather":
            return OpenWeatherSource(cfg, city=cfg.city)
        raise NotImplementedError(cfg.type)

    # ------------------------------------------------------------------ #
    async def run_all(self) -> dict[str, str]:
        """
        Returns {source_id: {"inserted": X, "skipped": Y, "failed": 0/1}}
        """

        summary = {}
        for src in self.sources:
            try:
                payload = await src.harvest()
                coll = await self.mongo.get_collection(src.type, self.city)
                await self.mongo.ensure_indexes(
                    coll,
                    dedup_key="dt",
                    ttl_days=src.config.ttl_days,
                )
                result = await self.mongo.insert_one_safe(coll, payload)
                if result:
                    summary[src.type] = "skipped"
                else: 
                    summary[src.type] = "inserted"
            except HarvestError as exc:
                summary[src.type]["failed"] = 1
                print(f"⚠️  {src.type} failed: {exc}")

        return summary
