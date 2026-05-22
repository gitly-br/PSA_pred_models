from __future__ import annotations

import os
from datetime import date, datetime, time, timedelta
from typing import Any

import pytz

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ModuleNotFoundError:
    class AsyncIOMotorClient:  # pragma: no cover - import-time fallback only
        def __init__(self, *args, **kwargs):
            raise ModuleNotFoundError("motor is not installed")

from .minio_weather_fallback import MinIOWeatherFallback


MONGO_URI = os.getenv("MONGO_URI", "mongodb://psa:psa@localhost:16521/?authSource=admin")
DB_NAME = "api_data"
COLLECTION_NAME = "historic"
FORECAST_COLLECTION_NAME = "forecast"
TZ_NAME = "America/Sao_Paulo"


class WeatherDataRepository:
    def __init__(self, mongo_uri: str | None = None, db_name: str = DB_NAME):
        self.client = AsyncIOMotorClient(mongo_uri or MONGO_URI, tz_aware=True)
        self.collection = self.client[db_name][COLLECTION_NAME]
        self.tz = pytz.timezone(TZ_NAME)
        self._minio_fallback: MinIOWeatherFallback | None = None

    def _get_minio_fallback(self) -> MinIOWeatherFallback:
        if self._minio_fallback is None:
            self._minio_fallback = MinIOWeatherFallback()
        return self._minio_fallback

    def _to_utc_bounds(self, start_date: date, end_date: date) -> tuple[datetime, datetime]:
        start_local = self.tz.localize(datetime.combine(start_date, time.min))
        end_local = self.tz.localize(datetime.combine(end_date, time.min))
        return start_local.astimezone(pytz.utc), end_local.astimezone(pytz.utc)

    async def fetch_historic_documents(
        self,
        bacia: str,
        start_date: date,
        end_date: date,
        station_ids: list[str] | None = None,
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        start_utc, end_utc = self._to_utc_bounds(start_date, end_date)
        query = {"dt": {"$gte": start_utc, "$lt": end_utc}}
        if station_ids:
            query["station_id"] = {"$in": station_ids}
        else:
            query["$or"] = [{"bacia": bacia}, {"bacias": bacia}]

        projection = None
        if fields is not None:
            projection = {f: 1 for f in fields}
            projection["_id"] = 0

        docs: list[dict[str, Any]] = []
        async for doc in self.collection.find(query, projection=projection):
            if station_ids and not doc.get("bacia") and not doc.get("bacias"):
                doc = dict(doc)
                doc["bacia"] = bacia
                doc["bacias"] = [bacia]
            docs.append(doc)

        # Fallback to MinIO if MongoDB has no data for this period
        if not docs:
            docs = self._get_minio_fallback().fetch_historic_documents(
                bacia, start_date, end_date, fields=fields,
            )

        return docs

    async def fetch_forecast_documents(self, bacia: str, target_date: date) -> list[dict[str, Any]]:
        start_utc, end_utc = self._to_utc_bounds(target_date, target_date + timedelta(days=1))
        query = {
            "dt_request": {"$gte": start_utc, "$lt": end_utc},
            "$or": [{"bacia": bacia}, {"bacias": bacia}],
        }
        docs: list[dict[str, Any]] = []
        collection = self.client[DB_NAME][FORECAST_COLLECTION_NAME]
        async for doc in collection.find(query):
            docs.append(doc)

        # Fallback to MinIO if MongoDB has no forecast for this date
        if not docs:
            docs = self._get_minio_fallback().fetch_forecast_documents(bacia, target_date)

        return docs

    async def summarize_forecast(self, bacia: str, target_date: date) -> dict[str, float | int]:
        docs = await self.fetch_forecast_documents(bacia, target_date)
        return self.summarize_forecast_documents(docs)

    @staticmethod
    def summarize_forecast_documents(docs: list[dict[str, Any]]) -> dict[str, Any]:
        tz = pytz.timezone(TZ_NAME)
        point_totals: list[float] = []
        rain_by_period = {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0}
        for doc in docs:
            hourly = doc.get("hourly") or []
            total = 0.0
            for index, hour in enumerate(hourly):
                rain = float(hour.get("rain") or hour.get("precipitation_mm") or 0.0)
                total += rain
                dt_value = hour.get("dt")
                local_hour = index
                if isinstance(dt_value, datetime):
                    if dt_value.tzinfo is None:
                        dt_value = pytz.utc.localize(dt_value)
                    local_hour = dt_value.astimezone(tz).hour
                if local_hour < 6:
                    rain_by_period["night"] += rain
                elif local_hour < 12:
                    rain_by_period["morning"] += rain
                elif local_hour < 18:
                    rain_by_period["afternoon"] += rain
                else:
                    rain_by_period["evening"] += rain
            point_totals.append(total)

        return {
            "point_count": len(point_totals),
            "total_mm": float(sum(point_totals)),
            "max_point_total_mm": float(max(point_totals)) if point_totals else 0.0,
            "min_point_total_mm": float(min(point_totals)) if point_totals else 0.0,
            "rain_by_period_mm": {key: float(value) for key, value in rain_by_period.items()},
        }

    async def close(self) -> None:
        self.client.close()
