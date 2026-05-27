from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

import polars as pl
from pymongo import UpdateOne

from harvest.mongo_client import MongoClientWrapper
from .minio_client import MinioClientWrapper, MinioSettings


DEFAULT_HISTORIC_PREFIX = "weather/cemaden/"
DEFAULT_FORECAST_PREFIX = "weather/openmeteo/forecast/"
DEFAULT_MONGO_URI = "mongodb://psa:psa@localhost:16521/?authSource=admin"
HISTORIC_QUERY_INDEXES = (
    ([("bacia", 1), ("dt", 1)], "historic_bacia_dt_idx"),
    ([("bacias", 1), ("dt", 1)], "historic_bacias_dt_idx"),
    ([("station_id", 1), ("dt", 1)], "historic_station_id_dt_idx"),
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _to_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return None


def _load_station_bacias(path: str | None) -> dict[str, list[str]]:
    if not path:
        return {}
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    station_map: dict[str, list[str]] = defaultdict(list)
    for bacia, station_ids in data.items():
        for station_id in station_ids:
            station_map[str(station_id)].append(str(bacia))
    return {station_id: sorted(set(bacias)) for station_id, bacias in station_map.items()}


def _load_parquet_bytes(raw: bytes) -> pl.DataFrame:
    return pl.read_parquet(BytesIO(raw))


def _build_historic_documents(
    frame: pl.DataFrame,
    source_file: str,
    station_bacias: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    station_bacias = station_bacias or {}
    loaded_at = _utc_now()
    documents: list[dict[str, Any]] = []

    for row in frame.to_dicts():
        station_id = str(row.get("codEstacao") or row.get("station_id") or "unknown")
        bacias = station_bacias.get(station_id, [])
        documents.append(
            {
                "provider": "cemaden",
                "station_id": station_id,
                "station_name": row.get("nomeEstacao") or row.get("station_name"),
                "municipio": row.get("municipio"),
                "bacias": bacias,
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "dt": _to_utc_datetime(row.get("dt")),
                "precipitation_mm": row.get("valor_mm") or row.get("precipitation_mm") or 0.0,
                "source_file": source_file,
                "loaded_at": loaded_at,
            }
        )

    return documents


def _build_forecast_documents(
    frame: pl.DataFrame,
    source_file: str,
    point_bacias: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    loaded_at = _utc_now()
    rows = frame.to_dicts()
    if not rows:
        return []

    grouped: dict[tuple[Any, Any], list[dict[str, Any]]] = defaultdict(list)
    has_slice_dt = "slice_dt" in frame.columns and "forecast_dt" in frame.columns
    point_bacias = point_bacias or {}

    for row in rows:
        if has_slice_dt:
            dt_request = _to_utc_datetime(row.get("slice_dt"))
            dt_value = _to_utc_datetime(row.get("forecast_dt"))
            point_id = f"{row.get('lat')}_{row.get('lon')}"
            key = (dt_request, point_id)
        else:
            dt_value = _to_utc_datetime(row.get("dt"))
            point_id = f"{row.get('latitude')}_{row.get('longitude')}"
            dt_request = datetime(dt_value.year, dt_value.month, dt_value.day, tzinfo=timezone.utc) if dt_value else None
            key = (dt_request, point_id)

        grouped[key].append(
            {
                "dt": dt_value,
                "latitude": row.get("lat") or row.get("latitude"),
                "longitude": row.get("lon") or row.get("longitude"),
                "temperature": row.get("temperature") or row.get("temperature_c") or row.get("temp"),
                "dew_point": row.get("dew_point"),
                "pressure": row.get("pressure") or row.get("pressure_hpa"),
                "humidity": row.get("humidity") or row.get("humidity_pct"),
                "wind_speed": row.get("wind_speed") or row.get("wind_speed_kmh"),
                "rain": row.get("rain") or row.get("rain_mm") or row.get("precipitation_mm") or 0.0,
                "precipitation_mm": row.get("precipitation_mm") or row.get("rain_mm") or row.get("rain") or 0.0,
            }
        )

    documents: list[dict[str, Any]] = []
    for key, hourly in grouped.items():
        dt_request, point_id = key
        hourly = sorted(hourly, key=lambda item: item["dt"] or datetime.min.replace(tzinfo=timezone.utc))
        first = hourly[0] if hourly else {}
        bacias = point_bacias.get(point_id, [])
        if not bacias and not Path(source_file).stem.startswith("pt_"):
            bacias = [Path(source_file).stem]
        documents.append(
            {
                "provider": "openmeteo",
                "point_id": point_id,
                "bacias": bacias,
                "dt_request": dt_request,
                "timezone": "UTC",
                "hourly": hourly,
                "source_file": source_file,
                "loaded_at": loaded_at,
                "latitude": first.get("latitude"),
                "longitude": first.get("longitude"),
            }
        )

    return documents


async def _upsert_many(collection, documents: list[dict[str, Any]], index_fields: list[tuple[str, int]]) -> int:
    if not documents:
        return 0
    operations = [
        UpdateOne({field: doc.get(field) for field, _ in index_fields}, {"$set": doc}, upsert=True)
        for doc in documents
    ]
    result = await collection.bulk_write(operations, ordered=False)
    return result.upserted_count + result.modified_count


async def ensure_api_data_indexes(historic_collection, forecast_collection) -> None:
    await historic_collection.create_index(
        [("provider", 1), ("station_id", 1), ("dt", 1)],
        unique=True,
    )
    for keys, name in HISTORIC_QUERY_INDEXES:
        await historic_collection.create_index(keys, name=name, background=True)
    await forecast_collection.create_index(
        [("provider", 1), ("point_id", 1), ("dt_request", 1)],
        unique=True,
    )


async def bootstrap_api_data(
    minio: MinioClientWrapper,
    mongo: MongoClientWrapper,
    station_bacias: dict[str, list[str]] | None = None,
    point_bacias: dict[str, list[str]] | None = None,
    historic_prefix: str = DEFAULT_HISTORIC_PREFIX,
    forecast_prefix: str = DEFAULT_FORECAST_PREFIX,
    workers: int = 4,
) -> dict[str, int]:
    station_bacias = station_bacias or {}
    point_bacias = point_bacias or {}
    minio.ensure_bucket()

    historic_collection = mongo.get_data_collection("historic")
    forecast_collection = mongo.get_data_collection("forecast")

    await ensure_api_data_indexes(historic_collection, forecast_collection)

    counters = {"historic": 0, "forecast": 0}

    semaphore = asyncio.Semaphore(max(1, workers))

    async def _process_object(
        object_name: str,
        collection,
        builder,
        builder_kwargs: dict[str, Any],
        index_fields: list[tuple[str, int]],
    ) -> int:
        async with semaphore:
            raw_bytes = await asyncio.to_thread(minio.get_object_bytes, object_name)
            frame = await asyncio.to_thread(_load_parquet_bytes, raw_bytes)
            documents = await asyncio.to_thread(builder, frame, object_name, **builder_kwargs)
            return await _upsert_many(collection, documents, index_fields)

    historic_objects = [
        object_name
        for object_name in minio.list_objects(historic_prefix)
        if object_name.endswith(".parquet")
    ]
    if historic_objects:
        historic_counts = await asyncio.gather(*(
            _process_object(
                object_name,
                historic_collection,
                _build_historic_documents,
                {"station_bacias": station_bacias},
                [("provider", 1), ("station_id", 1), ("dt", 1)],
            )
            for object_name in historic_objects
        ))
        counters["historic"] += sum(historic_counts)

    forecast_objects = [
        object_name
        for object_name in minio.list_objects(forecast_prefix)
        if object_name.endswith(".parquet")
    ]
    if forecast_objects:
        forecast_counts = await asyncio.gather(*(
            _process_object(
                object_name,
                forecast_collection,
                _build_forecast_documents,
                {"point_bacias": point_bacias},
                [("provider", 1), ("point_id", 1), ("dt_request", 1)],
            )
            for object_name in forecast_objects
        ))
        counters["forecast"] += sum(forecast_counts)

    return counters


async def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap api_data collections from MinIO")
    parser.add_argument("--station-bacias", help="Path to estacoes_bacia.json", default=None)
    parser.add_argument("--historic-prefix", default=DEFAULT_HISTORIC_PREFIX)
    parser.add_argument("--forecast-prefix", default=DEFAULT_FORECAST_PREFIX)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    mongo = MongoClientWrapper(
        uri=os.getenv("MONGO_URI", DEFAULT_MONGO_URI),
        config_db_name="api_data",
        data_db_name="api_data",
    )
    minio = MinioClientWrapper(
        MinioSettings(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:19000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "psa"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "psa12345"),
            bucket=os.getenv("MINIO_BUCKET", "psa"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )
    )

    try:
        station_bacias = _load_station_bacias(args.station_bacias)
        counters = await bootstrap_api_data(
            minio=minio,
            mongo=mongo,
            station_bacias=station_bacias,
            historic_prefix=args.historic_prefix,
            forecast_prefix=args.forecast_prefix,
            workers=args.workers,
        )
        print(json.dumps(counters, ensure_ascii=False))
    finally:
        await mongo.close()


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
