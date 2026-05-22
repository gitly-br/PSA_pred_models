from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
from datetime import date, datetime, time, timedelta
from pathlib import Path

import polars as pl

from harvest.mongo_client import MongoClientWrapper

from .bootstrap_api_data import bootstrap_api_data, _load_station_bacias
from .minio_client import MinioClientWrapper, MinioSettings


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MONGO_URI = "mongodb://psa:psa@localhost:16521/?authSource=admin"


async def bootstrap_local_weather(
    cemaden_source: Path,
    forecast_source: Path,
    station_bacias_path: Path | None = None,
    historic_prefix: str = "weather/cemaden/",
    forecast_prefix: str = "weather/openweather/forecast/",
    start_date: date = date(2025, 1, 1),
    end_date: date = date(2025, 2, 28),
    workers: int = 2,
) -> dict[str, int]:
    minio = MinioClientWrapper(
        MinioSettings(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:19000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "psa"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "psa12345"),
            bucket=os.getenv("MINIO_BUCKET", "psa"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )
    )
    mongo = MongoClientWrapper(
        uri=os.getenv("MONGO_URI", DEFAULT_MONGO_URI),
        config_db_name="api_data",
        data_db_name="api_data",
    )
    station_bacias = _load_station_bacias(station_bacias_path) if station_bacias_path else {}
    point_bacias = _load_point_bacias(forecast_source)

    try:
        minio.ensure_bucket()
        minio.delete_prefix(historic_prefix)
        minio.delete_prefix(forecast_prefix)
        semaphore = asyncio.Semaphore(max(1, workers))

        with tempfile.TemporaryDirectory() as tmp_dir:
            staged_dir = Path(tmp_dir)

            async def _stage_and_upload(source_file: Path, prefix: str) -> None:
                async with semaphore:
                    if not source_file.exists():
                        return
                    staged_file = await asyncio.to_thread(
                        _filter_parquet_to_window,
                        source_file,
                        start_date,
                        end_date,
                        staged_dir,
                    )
                    await asyncio.to_thread(
                        minio.upload_file,
                        staged_file,
                        f"{prefix.rstrip('/')}/{staged_file.name}",
                    )

            async def _upload_monthly(source_file: Path, prefix: str) -> None:
                async with semaphore:
                    if not source_file.exists():
                        return
                    await asyncio.to_thread(
                        minio.upload_file,
                        source_file,
                        f"{prefix.rstrip('/')}/{source_file.name}",
                    )

            if cemaden_source.is_dir():
                cemaden_files = sorted(cemaden_source.glob("cemaden_*.parquet"))
                cemaden_files = [f for f in cemaden_files if _file_month_in_range(f.name, "", start_date, end_date)]
                await asyncio.gather(*(
                    _upload_monthly(f, historic_prefix) for f in cemaden_files
                ))
            else:
                await _stage_and_upload(cemaden_source, historic_prefix)

            forecast_files = _forecast_files(forecast_source)
            if forecast_source.is_dir():
                forecast_files = [f for f in forecast_files if _file_month_in_range(f.name, "", start_date, end_date)]
            if forecast_files:
                await asyncio.gather(*(
                    _stage_and_upload(f, forecast_prefix) for f in forecast_files
                ))

        await mongo.get_data_collection("forecast").delete_many({})

        counters = await bootstrap_api_data(
            minio=minio,
            mongo=mongo,
            station_bacias=station_bacias,
            historic_prefix=historic_prefix,
            forecast_prefix=forecast_prefix,
            point_bacias=point_bacias,
            workers=workers,
        )
        return counters
    finally:
        await mongo.close()


def _file_month_in_range(filename: str, prefix: str, start_date: date, end_date: date) -> bool:
    import re

    stem = filename.replace(prefix, "").replace(".parquet", "")
    m = re.search(r"(\d{4})_(\d{2})", stem)
    if not m:
        return True
    file_date = date(int(m.group(1)), int(m.group(2)), 1)
    month_end = date(file_date.year, file_date.month, 28) + timedelta(days=4)
    month_end = month_end.replace(day=1) - timedelta(days=1)
    return file_date <= end_date and month_end >= start_date


def _filter_parquet_to_year(source_file: Path, year: int, output_dir: Path) -> Path:
    frame = pl.read_parquet(source_file)
    if "dt" in frame.columns:
        frame = frame.filter(pl.col("dt").dt.year() == year)
    elif "slice_dt" in frame.columns:
        frame = frame.filter(pl.col("slice_dt").dt.year() == year)
    elif "forecast_dt" in frame.columns:
        frame = frame.filter(pl.col("forecast_dt").dt.year() == year)

    output_dir.mkdir(parents=True, exist_ok=True)
    staged_path = output_dir / f"{source_file.stem}_{year}.parquet"
    frame.write_parquet(staged_path)
    return staged_path


def _forecast_files(forecast_source: Path) -> list[Path]:
    if forecast_source.is_dir():
        monthly = sorted(forecast_source.glob("openmeteo_*.parquet"))
        if monthly:
            return monthly
        return sorted(forecast_source.glob("pt_*.parquet"))
    return [forecast_source]


def _load_point_bacias(forecast_source: Path) -> dict[str, list[str]]:
    if not forecast_source.is_dir():
        return {}
    index_path = forecast_source / "index.json"
    if not index_path.exists():
        return {}
    import json

    index = json.loads(index_path.read_text(encoding="utf-8"))
    point_bacias: dict[str, list[str]] = {}
    for bacia, points in index.items():
        for point in points:
            point_id = f"{point['lat']}_{point['lon']}"
            point_bacias.setdefault(point_id, []).append(bacia)
    return {point_id: sorted(set(bacias)) for point_id, bacias in point_bacias.items()}


def _filter_parquet_to_window(source_file: Path, start_date: date, end_date: date, output_dir: Path) -> Path:
    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date + timedelta(days=1), time.min)
    scan = pl.scan_parquet(source_file)
    schema = scan.collect_schema()
    frame = None
    for column in ("dt", "forecast_dt", "slice_dt"):
        if column in schema.names():
            frame = (
                scan
                .filter((pl.col(column) >= start_dt) & (pl.col(column) < end_dt))
                .collect()
            )
            break

    if frame is None:
        frame = pl.read_parquet(source_file)

    output_dir.mkdir(parents=True, exist_ok=True)
    staged_path = output_dir / f"{source_file.stem}_{start_date.isoformat()}_{end_date.isoformat()}.parquet"
    frame.write_parquet(staged_path)
    return staged_path


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MinIO with local parquets and bootstrap api_data")
    parser.add_argument("--cemaden-dir", default=str((REPO_ROOT / "notebooks/dados/weather/monthly/historic")))
    parser.add_argument("--forecast-dir", default=str((REPO_ROOT / "notebooks/dados/weather/monthly/forecast")))
    parser.add_argument("--station-bacias", default=None)
    parser.add_argument("--historic-prefix", default="weather/cemaden/")
    parser.add_argument("--forecast-prefix", default="weather/openweather/forecast/")
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2026-05-31")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    counters = await bootstrap_local_weather(
        cemaden_source=Path(args.cemaden_dir).resolve(),
        forecast_source=Path(args.forecast_dir).resolve(),
        station_bacias_path=Path(args.station_bacias).resolve() if args.station_bacias else None,
        historic_prefix=args.historic_prefix,
        forecast_prefix=args.forecast_prefix,
        start_date=date.fromisoformat(args.start_date),
        end_date=date.fromisoformat(args.end_date),
        workers=args.workers,
    )
    print(counters)


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
