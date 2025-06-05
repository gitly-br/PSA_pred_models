from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Iterable

from harvest.config_loader import SourceConfig


class HarvestError(Exception):
    """Raised when a Source fails to fetch or process data."""


class SourceBase(ABC):
    """
    Abstract base class for all data sources.

    Any concrete source must inherit from this class and implement the
    `harvest()` method, which should return an iterable of dictionaries
    (even if it's a list with a single item).
    """

    def __init__(self, src_config: SourceConfig, timeout: int = 30) -> None:
        """
        Args:
            src_config (SourceConfig): Configuration object for this source.
            timeout (int): Request timeout in seconds (default: 30s).
        """
        self.timeout = timeout
        self.src_config = src_config

    @property
    def type(self) -> str:
        """Convenience property to get the source type (same as
        src_config.type)."""
        return self.src_config.type

    @property
    def region(self) -> str:
        """Convenience property to get the source type (same as
        src_config.type)."""
        return self.src_config.region_name

    @abstractmethod
    async def harvest(self) -> Iterable[dict[str, Any]]:
        """
        Fetch payloads (can be empty).

        Should return an iterable of dictionaries, where each dictionary
        represents a "data package" (for example, parsed JSON enriched with
        fields like dt_request, region_name, and type). Even if there is only
        one payload, wrap it in a list or other iterable.

        Raises:
            HarvestError: if the source fails to fetch or process data.
        """
