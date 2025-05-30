from __future__ import annotations
import datetime as dt
from typing import Any

import httpx
from httpx import HTTPStatusError

from harvest.sources.source_base import SourceBase, HarvestError
from harvest.constants import OPENWX_KEY_ENV
import os


class OpenWeatherSource(SourceBase):
    async def harvest(self) -> dict[str, Any]:
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
                raise HarvestError(f"""
                                   HTTP {exc.response.status_code} 
                                   for {self.name}
                                   """) from exc

        payload = resp.json()
        dt_request = dt.datetime.now(dt.timezone.utc).replace(minute=0,
                                                              second=0,
                                                              microsecond=0)

        doc = {
            "city": self.city,
            "source": self.type,
            "dt_request": dt_request,
            "forecasts": payload["list"]
        }

        return doc
