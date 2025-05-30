#!/usr/bin/env python3
"""Harvest CLI – Stage 2."""
from __future__ import annotations
import argparse
import asyncio
from dotenv import load_dotenv
import os
from pprint import pprint

from harvest.utils import resolve_config
from harvest.config_loader import ConfigLoader
from harvest.mongo_client import MongoClientWrapper
from harvest.harvester import Harvester
from harvest.constants import MONGO_URI_ENV, MONGO_DB_ENV, DEFAULT_MONGO_URI, DEFAULT_MONGO_DB


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run harvest for one city.")
    p.add_argument("--city", required=True, help="City name (exactly as in config)")
    p.add_argument("--config", help="Path to YAML configs (default sample_configs.yml)")
    return p.parse_args()


async def main() -> None:
    load_dotenv()  # pick up .env values

    args = parse_args()
    cfg_path = resolve_config(args.config)

    configs = ConfigLoader(cfg_path).load()

    mongo_uri = os.getenv(MONGO_URI_ENV, DEFAULT_MONGO_URI)
    mongo_db = os.getenv(MONGO_DB_ENV, DEFAULT_MONGO_DB)

    mongo = MongoClientWrapper(uri=mongo_uri, db_name=mongo_db)
    harv = Harvester(configs, city=args.city, mongo=mongo)

    summary = await harv.run_all()
    await mongo.close()

    print(f"\nHarvest summary for {args.city}")
    pprint(summary)


if __name__ == "__main__":
    asyncio.run(main())
