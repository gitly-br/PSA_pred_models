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

from harvest.mongo_client import MongoClientWrapper
from harvest.harvester import Harvester

# Default constants
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_CONFIG_DB = "harvest_config"
DEFAULT_DATA_DB = "harvest_data"
DEFAULT_TTL_DAYS = 60


def configure_logging():
    """
    Configure two handlers:
      - stdout_handler: handles INFO, DEBUG, and WARNING (level < ERROR) → sys.stdout
      - stderr_handler: handles ERROR and CRITICAL (level >= ERROR) → sys.stderr
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)  # capture all levels, handlers will filter

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Handler for INFO and below → stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.addFilter(lambda record: record.levelno < logging.ERROR)
    stdout_handler.setFormatter(formatter)

    # Handler for WARNING and above → stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)
    stderr_handler.setFormatter(formatter)

    # Clear any existing handlers, then add ours
    root_logger.handlers.clear()
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)


async def main():
    # 1) Configure logging
    configure_logging()
    logger = logging.getLogger(__name__)

    # 2) Read environment variables or default values
    mongo_uri = os.getenv("MONGO_URI", DEFAULT_MONGO_URI)
    config_db_name = os.getenv("CONFIG_DB_NAME", DEFAULT_CONFIG_DB)
    data_db_name = os.getenv("DATA_DB_NAME", DEFAULT_DATA_DB)
    ttl_days = int(os.getenv("DEFAULT_TTL_DAYS", DEFAULT_TTL_DAYS))

    logger.info("Starting Harvester CLI")
    logger.info(f"Mongo URI: {mongo_uri}")
    logger.info(f"Config DB: {config_db_name}, Data DB: {data_db_name}")
    logger.info(f"Default TTL: {ttl_days} days")

    # 3) Instantiate MongoClientWrapper
    mongo = MongoClientWrapper(
        uri=mongo_uri,
        config_db_name=config_db_name,
        data_db_name=data_db_name,
    )

    try:
        # 4) Instantiate the Harvester
        harvester = Harvester(mongo=mongo)

        # 5) Run the harvest process
        summary = await harvester.harvest()

        for src_type, counters in summary.items():
            inserted = counters.get("inserted", 0)
            skipped = counters.get("skipped", 0)
            failed = counters.get("failed", 0)
            logger.info(
                (f"SUMMARY: {src_type}: inserted={inserted},"
                 f"  skipped={skipped}, failed={failed}")
            )
        if skipped > 0:
            logger.warning(f"{src_type} had {skipped} skips")
        if failed > 0:
            logger.error(f"{src_type} had {failed} failures")

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
