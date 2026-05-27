from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

import pytz

from harvest.mongo_client import MongoClientWrapper
from harvest.harvester import Harvester


def _seconds_until_next_hour(now: datetime | None = None) -> float:
    tz = pytz.timezone("America/Sao_Paulo")
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = tz.localize(current)
    next_hour = (current + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return max(0.0, (next_hour - current).total_seconds())


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        return logger
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s HARVEST-SCHEDULER %(message)s")
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    return logger


async def run_harvest(mongo: MongoClientWrapper, logger: logging.Logger) -> None:
    harvester = Harvester(mongo=mongo)
    summary = await harvester.harvest()
    for src_type, counters in summary.items():
        inserted = counters.get("inserted", 0)
        skipped = counters.get("skipped", 0)
        failed = counters.get("failed", 0)
        logger.info(f"{src_type}: inserted={inserted}, skipped={skipped}, failed={failed}")


async def run_scheduler(
    interval_seconds: int,
    debug: bool = False,
    top_of_hour: bool = False,
    run_immediately: bool = True,
) -> None:
    logger = setup_logger(__name__, logging.DEBUG if debug else logging.INFO)

    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    config_db_name = os.getenv("CONFIG_DB_NAME", "harvest_config")
    data_db_name = os.getenv("DATA_DB_NAME", "harvest_data")

    mongo = MongoClientWrapper(
        uri=mongo_uri,
        config_db_name=config_db_name,
        data_db_name=data_db_name,
    )

    try:
        if top_of_hour:
            wait = _seconds_until_next_hour()
            logger.info(f"Waiting {wait:.0f}s until next hour")
            await asyncio.sleep(wait)

        first = True
        while True:
            if first and not run_immediately:
                first = False
            else:
                logger.info("Starting harvest cycle")
                try:
                    await run_harvest(mongo, logger)
                except Exception as exc:
                    logger.error(f"Harvest failed: {exc}")
                first = False

            await asyncio.sleep(max(1, interval_seconds))
    finally:
        await mongo.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run Harvest periodically")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--top-of-hour", action="store_true")
    parser.add_argument("--run-immediately", action="store_true", default=False)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    await run_scheduler(
        interval_seconds=args.interval_seconds,
        debug=args.debug,
        top_of_hour=args.top_of_hour,
        run_immediately=args.run_immediately,
    )


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
