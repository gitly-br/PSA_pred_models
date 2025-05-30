from __future__ import annotations
import datetime as dt
from typing import Any, Iterable

import httpx
from httpx import HTTPStatusError

from harvest.sources.source_base import SourceBase, HarvestError
from harvest.constants import OPENWX_KEY_ENV
from harvest.utils import bucketize
import os


class ApiSource(SourceBase):
    async def harvest(self) -> Iterable[dict[str, Any]]:
        key = os.getenv(OPENWX_KEY_ENV)
        if not key:
            raise HarvestError("OPENWEATHER_API_KEY not set")

        lat = self.config.params["lat"]
        lon = self.config.params["lon"]
        url = (
            "https://api.openweathermap.org/data/2.5/forecast"
            f"?lat={lat}&lon={lon}&appid={key}&units=metric"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
            except HTTPStatusError as exc:
                raise HarvestError(f"HTTP {exc.response.status_code} for {self.name}") from exc

        payload = resp.json()
        dt_request = dt.datetime.now(dt.timezone.utc)
        bucket_ts = bucketize(
            dt_request, dt.timedelta(minutes=self.config.dedup_window_minutes)
        )

        docs = []
        for entry in payload["list"]:
            doc = {
                **entry,
                "city": self.city,
                "source": self.name,
                "dt_request": dt_request,
                "bucket_ts": bucket_ts,
            }
            docs.append(doc)
        return docs
