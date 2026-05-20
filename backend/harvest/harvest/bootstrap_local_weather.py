from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from harvest.mongo_client import MongoClientWrapper

from .bootstrap_api_data import bootstrap_api_data
from .minio_client import MinioClientWrapper, MinioSettings


REPO_ROOT = Path(__file__).resolve().parents[3]


async def bootstrap_local_weather(
    cemaden_file: Path,
    forecast_file: Path,
    historic_prefix: str = "weather/cemaden/",
    forecast_prefix: str = "weather/openweather/forecast/",
) -> dict[str, int]:
    minio = MinioClientWrapper(
        MinioSettings(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:19000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "psa"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "psa"),
            bucket=os.getenv("MINIO_BUCKET", "psa"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )
    )
    mongo = MongoClientWrapper(
        uri=os.getenv("MONGO_URI"),
        config_db_name="api_data",
        data_db_name="api_data",
    )

    try:
        minio.ensure_bucket()
        if cemaden_file.exists():
            minio.upload_file(cemaden_file, f"{historic_prefix.rstrip('/')}/{cemaden_file.name}")
        if forecast_file.exists():
            minio.upload_file(forecast_file, f"{forecast_prefix.rstrip('/')}/{forecast_file.name}")

        return await bootstrap_api_data(
            minio=minio,
            mongo=mongo,
            historic_prefix=historic_prefix,
            forecast_prefix=forecast_prefix,
        )
    finally:
        await mongo.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MinIO with local parquets and bootstrap api_data")
    parser.add_argument("--cemaden-file", default=str((REPO_ROOT / "notebooks/dados/cemaden_abcd.parquet")))
    parser.add_argument("--forecast-file", default=str((REPO_ROOT / "notebooks/dados/weather/openweather_forecast_history.parquet")))
    parser.add_argument("--historic-prefix", default="weather/cemaden/")
    parser.add_argument("--forecast-prefix", default="weather/openweather/forecast/")
    args = parser.parse_args()

    counters = await bootstrap_local_weather(
        cemaden_file=Path(args.cemaden_file).resolve(),
        forecast_file=Path(args.forecast_file).resolve(),
        historic_prefix=args.historic_prefix,
        forecast_prefix=args.forecast_prefix,
    )
    print(counters)


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
