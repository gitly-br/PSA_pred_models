from __future__ import annotations
import datetime as dt
from typing import Any, Iterable
import os

import httpx
from httpx import HTTPStatusError

from harvest.sources.source_base import SourceBase, HarvestError


class OpenWeatherSource(SourceBase):
    """
    Concrete implementation of SourceBase for the OpenWeather API.

    It expects `self.src_config.url` to be the base URL (e.g.,
    "https://api.openweathermap.org/data/2.5/weather"),
    and `self.src_config.args` to contain all query parameters except `appid`
    (which is retrieved from an environment variable).
    """

    async def harvest(self) -> dict[str, Any]:
        """
        Build the query string from src_config.args plus the API key, make a
        GET request to the OpenWeather URL, and return a dictionary (parsed
        JSON), enriched with `dt_request`, `region_name`, and `type`.

        Raises:
            HarvestError: if the API key is missing or an HTTP/network error
            occurs.
        """
        # 1) Retrieve the API key from environment variables
        key = os.getenv("OPENWEATHER_API_KEY")
        if not key:
            raise HarvestError("OPENWEATHER_API_KEY not set")

        # 2) Build the full URL with query parameters
        base_url = self.src_config.url
        params = {"appid": key}
        for arg_name, arg_value in self.src_config.args.items():
            if arg_value is not None:
                params[arg_name] = arg_value

        # 3) Make the HTTP GET request
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(base_url, params=params)
                resp.raise_for_status()
            except HTTPStatusError as exc:
                # Transform HTTP errors (4xx, 5xx) into HarvestError
                raise HarvestError(
                    (
                        f"HTTP {exc.response.status_code}"
                        f" for source '{self.type}', region '{self.region}'"
                        f" message: '{exc.response.json().get("message")}'"
                    )
                ) from exc
            except httpx.RequestError as exc:
                # Transform network/timeout errors into HarvestError
                raise HarvestError(
                    f"Network error for '{self.type}': {exc}"
                ) from exc

        # 4) Prepare the final payload
        payload: dict[str, Any] = resp.json()
        for hourly_forecast in payload.get("hourly"):
            if "rain" in hourly_forecast:
                hourly_forecast["rain"] = hourly_forecast["rain"]["1h"]
            else:
                hourly_forecast["rain"] = 0
        mandatory = ["lat", "lon", "timezone", "hourly"]
        missing = [field for field in mandatory if field not in payload]
        if missing:
            raise HarvestError(
                f"Missing mandatory field(s) {missing} in response"
            )
        dt_request = dt.datetime.now(dt.timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        payload["dt_request"] = dt_request
        payload["region"] = self.region
        payload["subregion"] = self.subregion
        payload["type"] = self.type

        # 5) Return dict
        return payload
