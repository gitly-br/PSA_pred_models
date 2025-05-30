"""Stage 1 orchestrator: sequentially calls each Source and returns counts."""
from __future__ import annotations
from collections import defaultdict
from typing import Iterable, Mapping

from .config_loader import SourceConfig
from .sources.api_source import ApiSource
from .sources.source_base import SourceBase


class Harvester:
    def __init__(self, configs: Iterable[SourceConfig], city: str) -> None:
        self.city = city
        # keep only configs for the requested city
        self.configs = [c for c in configs if c.city == city]
        self.sources: list[SourceBase] = [
            self._build_source(c) for c in self.configs
        ]

    # --------------------------------------------------------------------- #
    def _build_source(self, cfg: SourceConfig) -> SourceBase:
        if cfg.type == "api":
            return ApiSource(cfg, city=cfg.city)
        raise NotImplementedError(f"Unknown source type {cfg.type!r}")

    # --------------------------------------------------------------------- #
    async def run_all(self) -> Mapping[str, int]:
        """Return {source_id: num_docs_harvested}."""
        from itertools import zip_longest

        counts = defaultdict(int)
        for src in self.sources:
            docs = await src.harvest()
            counts[src.name] += len(list(docs))
        return counts
