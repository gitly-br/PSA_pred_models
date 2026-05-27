from __future__ import annotations

import argparse
import asyncio
import os

from harvest.mongo_client import MongoClientWrapper


SOURCE_TYPES = [
    {
        "type": "openweather",
        "url": "https://api.openweathermap.org/data/3.0/onecall",
        "required_args": ["lat", "lon", "units"],
        "target": None,
    },
    {
        "type": "defesa_civil",
        "url": "https://santo-andre-api-app-acta-campo.mitraonline.com.br/api/v1/iot/consultar/leitura-estacoes",
        "required_args": ["periodicidade"],
        "target": "api_data.historic",
    },
    {
        "type": "openmeteo",
        "url": "https://api.open-meteo.com/v1/forecast",
        "required_args": ["hourly", "timezone", "forecast_days"],
        "target": "api_data.forecast",
    },
]

SOURCES = [
    {
        "type": "openweather",
        "region": "santo_andre",
        "subregion": "all",
        "ttl_days": 30,
        "args": {
            "lat": -23.66,
            "lon": -46.54,
            "units": "metric",
        },
    },
    {
        "type": "defesa_civil",
        "region": "santo_andre",
        "subregion": "all",
        "ttl_days": 365,
        "args": {
            "periodicidade": 60,
        },
    },
    {
        "type": "openmeteo",
        "region": "santo_andre",
        "subregion": "all",
        "ttl_days": 30,
        "args": {
            "hourly": "precipitation,rain,temperature_2m,relative_humidity_2m,wind_speed_10m,pressure_msl",
            "timezone": "America/Sao_Paulo",
            "forecast_days": 2,
        },
    },
]


async def seed_harvest_config(mongo: MongoClientWrapper) -> dict[str, int]:
    source_types_coll = mongo.get_config_collection("source_types")
    sources_coll = mongo.get_config_collection("sources")

    await source_types_coll.delete_many({})
    await sources_coll.delete_many({})

    st_result = await source_types_coll.insert_many(SOURCE_TYPES)
    src_result = await sources_coll.insert_many(SOURCES)

    return {
        "source_types": len(st_result.inserted_ids),
        "sources": len(src_result.inserted_ids),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed harvest_config collections")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    config_db_name = os.getenv("CONFIG_DB_NAME", "harvest_config")

    mongo = MongoClientWrapper(
        uri=mongo_uri,
        config_db_name=config_db_name,
        data_db_name=config_db_name,
    )

    try:
        result = await seed_harvest_config(mongo)
        print(f"Seeded: {result}")
    finally:
        await mongo.close()


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
