"""Abstract contract for every harvest source."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Iterable


class HarvestError(Exception):
    """Raised by a Source when it cannot fetch data."""


class SourceBase(ABC):
    """All concrete sources must implement this interface."""

    def __init__(self, config, *, city: str, region: str = "all") -> None:
        self.config = config
        self.city = city
        self.region = region

    @property
    def type(self) -> str:  # convenience
        return self.config.type

    # ──────────────────────────────────────────────────────────────
    @abstractmethod
    async def harvest(self) -> Iterable[dict[str, Any]]:
        """Fetch raw docs (may be zero length)."""
