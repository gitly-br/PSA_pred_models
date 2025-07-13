"""
Simple CLI entry point for the Harvester module.

This script:
  1. Instantiates a MongoClientWrapper pointing to your MongoDB instance.
  2. Creates a Harvester using that Mongo client.
  3. Runs the Harvester to read all registered sources and persist data.
  4. Uses a default TTL of 7 days for all indexes (unless overridden by each
  source’s config).

Logging configuration:
  - INFO and below → stdout
  - ERROR and above → stderr
"""

import asyncio
import logging
import os
import sys
import argparse

from harvest.mongo_client import MongoClientWrapper
from harvest.harvester import Harvester

# Default constants
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_CONFIG_DB = "harvest_config"
DEFAULT_DATA_DB = "harvest_data"
DEFAULT_TTL_DAYS = 60


def setup_logger(name, log_file=None, level=logging.INFO):
    """Set up logger with custom formatting"""

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter("%(asctime)s %(levelname)-8s HARVEST %(message)s")

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


async def main():
    # 1) Configure CLI arguments
    parser = argparse.ArgumentParser(description="Harvest data from various sources.")
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    # 2) Configure logging
    log_level = logging.DEBUG if args.debug else logging.INFO
    logger = setup_logger(__name__, "app.log", level=log_level)


    # 3) Read environment variables or default values
    mongo_uri = os.getenv("MONGO_URI", DEFAULT_MONGO_URI)
    config_db_name = os.getenv("CONFIG_DB_NAME", DEFAULT_CONFIG_DB)
    data_db_name = os.getenv("DATA_DB_NAME", DEFAULT_DATA_DB)
    ttl_days = int(os.getenv("DEFAULT_TTL_DAYS", DEFAULT_TTL_DAYS))

    logger.info("Starting harvest job")
    logger.debug(f"Mongo URI: {mongo_uri}")
    logger.debug(f"Config DB: {config_db_name}, Data DB: {data_db_name}")
    logger.debug(f"Default TTL: {ttl_days} days")

    # 4) Instantiate MongoClientWrapper
    mongo = MongoClientWrapper(
        uri=mongo_uri,
        config_db_name=config_db_name,
        data_db_name=data_db_name,
    )

    try:
        # 5) Instantiate the Harvester
        harvester = Harvester(mongo=mongo)

        # 6) Run the harvest process
        summary = await harvester.harvest()

        for src_type, counters in summary.items():
            inserted = counters.get("inserted", 0)
            skipped = counters.get("skipped", 0)
            failed = counters.get("failed", 0)
            logger.debug(
                (f"{src_type.upper()}: inserted={inserted},"
                 f"  skipped={skipped}, failed={failed}")
            )
        if skipped > 0:
            logger.warning(f"{src_type.upper()} had {skipped} skips")
        if failed > 0:
            logger.error(f"{src_type.upper()} had {failed} failures")
        else:
            logger.info(f"{src_type.upper()} is done")

    except Exception as e:
        # This goes to stderr because level=ERROR
        logger.error(f"Unexpected error during harvesting: {e}")
    finally:
        # Always close the Mongo client on exit
        await mongo.close()


if __name__ == "__main__":
    asyncio.run(main())


def main_sync():
    """Synchronous entry point for setup.py."""
    import asyncio
    asyncio.run(main())
