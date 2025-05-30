"""Stage 1 dummy implementation: returns a single fake doc."""
from __future__ import annotations
import datetime as _dt
from typing import Any, Iterable

from harvest.sources.source_base import SourceBase


class ApiSource(SourceBase):
    async def harvest(self) -> Iterable[dict[str, Any]]:
        # Stage 1: no real HTTP call—just dummy data
        now = _dt.datetime.now(_dt.timezone.utc).isoformat()
        return [{"city": self.city, "source": self.name, "ts": now, "dummy": True}]
