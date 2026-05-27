from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable

import httpx
from httpx import HTTPStatusError

from harvest.sources.source_base import SourceBase, HarvestError


class OpenMeteoSource(SourceBase):
    """
    Concrete implementation of SourceBase for the Open-Meteo Forecast API.

    Fetches hourly forecast data for multiple grid points and normalizes
    them into api_data.forecast documents.
    """

    target = "api_data.forecast"

    def __init__(self, src_config, timeout: int = 60) -> None:
        super().__init__(src_config, timeout)
        self._point_bacias = self._load_point_mapping()

    def _load_point_mapping(self) -> dict[str, list[str]]:
        """
        Load point-to-bacias mapping from openmeteo_grid_points.json.
        Returns dict mapping point_id (LAT_LON) -> list of bacias.
        """
        index_path = Path(__file__).parent.parent / "openmeteo_grid_points.json"
        if not index_path.exists():
            return {}

        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)

        point_bacias: dict[str, list[str]] = {}
        for bacia, points in data.items():
            for pt in points:
                point_id = f"{pt['lat']}_{pt['lon']}"
                if point_id not in point_bacias:
                    point_bacias[point_id] = []
                if bacia not in point_bacias[point_id]:
                    point_bacias[point_id].append(bacia)

        return point_bacias

    def _get_unique_points(self) -> list[tuple[float, float, str]]:
        """Get unique (lat, lon, point_id) tuples for all grid points."""
        seen = set()
        points = []
        for point_id, bacias in self._point_bacias.items():
            if point_id in seen:
                continue
            seen.add(point_id)
            lat_str, lon_str = point_id.split("_")
            points.append((float(lat_str), float(lon_str), point_id))
        return points

    async def _fetch_point(
        self,
        client: httpx.AsyncClient,
        lat: float,
        lon: float,
        point_id: str,
    ) -> dict[str, Any] | None:
        """Fetch forecast data for a single grid point."""
        base_url = self.src_config.url
        hourly_vars = self.src_config.args.get(
            "hourly",
            "precipitation,rain,temperature_2m,relative_humidity_2m,wind_speed_10m,pressure_msl"
        )
        timezone = self.src_config.args.get("timezone", "America/Sao_Paulo")
        forecast_days = self.src_config.args.get("forecast_days", 2)

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": hourly_vars,
            "timezone": timezone,
            "forecast_days": forecast_days,
        }

        try:
            resp = await client.get(base_url, params=params)
            resp.raise_for_status()
        except (HTTPStatusError, httpx.RequestError, Exception):
            return None

        return resp.json()

    async def harvest(self) -> Iterable[dict[str, Any]]:
        """
        Fetch hourly forecasts for all grid points and normalize to
        api_data.forecast documents.

        Raises:
            HarvestError: if no points are configured or all requests fail.
        """
        points = self._get_unique_points()
        if not points:
            raise HarvestError("No grid points configured for Open-Meteo")

        loaded_at = dt.datetime.now(dt.timezone.utc)
        dt_request = dt.datetime.now(dt.timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )

        documents: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for lat, lon, point_id in points:
                data = await self._fetch_point(client, lat, lon, point_id)
                if not data:
                    continue

                hourly = data.get("hourly", {})
                times = hourly.get("time", [])
                if not times:
                    continue

                bacias = self._point_bacias.get(point_id, [])

                hourly_data = []
                for i, time_str in enumerate(times):
                    dt_value = dt.datetime.fromisoformat(time_str)
                    if dt_value.tzinfo is None:
                        dt_value = dt_value.replace(tzinfo=dt.timezone.utc)

                    hourly_data.append({
                        "dt": dt_value,
                        "latitude": lat,
                        "longitude": lon,
                        "temperature": hourly.get("temperature_2m", [None] * len(times))[i],
                        "humidity": hourly.get("relative_humidity_2m", [None] * len(times))[i],
                        "wind_speed": hourly.get("wind_speed_10m", [None] * len(times))[i],
                        "pressure": hourly.get("pressure_msl", [None] * len(times))[i],
                        "rain": hourly.get("rain", [0.0] * len(times))[i] or 0.0,
                        "precipitation_mm": hourly.get("precipitation", [0.0] * len(times))[i] or 0.0,
                    })

                documents.append({
                    "provider": "openmeteo",
                    "point_id": point_id,
                    "bacia": bacias[0] if bacias else None,
                    "bacias": bacias,
                    "dt_request": dt_request,
                    "timezone": "UTC",
                    "hourly": hourly_data,
                    "loaded_at": loaded_at,
                    "latitude": lat,
                    "longitude": lon,
                })

                await asyncio.sleep(1)

        if not documents:
            raise HarvestError("Failed to fetch any Open-Meteo data")

        return documents
