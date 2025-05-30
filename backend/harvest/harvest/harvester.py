from __future__ import annotations
from collections import defaultdict
from typing import Mapping, Iterable, Any

from harvest.utils import bucketize
from harvest.constants import (
    DEFAULT_TTL_DAYS,
    window_to_timedelta,
)
from harvest.mongo_client import MongoClientWrapper
from harvest.config_loader import SourceConfig
from harvest.sources.api_source import ApiSource
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
        self.sources: list[SourceBase] = [self._build_source(c) for c in self.configs]

    def _build_source(self, cfg: SourceConfig) -> SourceBase:
        if cfg.type == "api":
            return ApiSource(cfg, city=cfg.city)
        raise NotImplementedError(cfg.type)

    # ------------------------------------------------------------------ #
    async def run_all(self) -> Mapping[str, dict[str, int]]:
        """
        Returns {source_id: {"inserted": X, "skipped": Y, "failed": 0/1}}
        """
        summary: dict[str, dict[str, int]] = defaultdict(
            lambda: {"inserted": 0, "skipped": 0, "failed": 0}
        )

        for src in self.sources:
            try:
                docs = await src.harvest()
                coll = await self.mongo.get_collection(src.name, self.city)
                await self.mongo.ensure_indexes(
                    coll,
                    dedup_key=src.config.dedup_key,
                    window_minutes=src.config.dedup_window_minutes,
                    ttl_days=src.config.ttl_days,
                )
                ins, skip = await self.mongo.insert_many_safe(coll, docs)
                summary[src.name]["inserted"] += ins
                summary[src.name]["skipped"] += skip
            except HarvestError as exc:
                summary[src.name]["failed"] = 1
                print(f"⚠️  {src.name} failed: {exc}")

        return summary
