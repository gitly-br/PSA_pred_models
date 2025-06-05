"""
Simple CLI entry point for the Harvester module.

This script:
  1. Instantiates a MongoClientWrapper pointing to your MongoDB instance.
  2. Creates a Harvester using that Mongo client.
  3. Runs the Harvester to read all registered sources and persist data.
  4. Uses a default TTL of 7 days for all indexes (config can override per-source).
"""

import asyncio
import logging
import os

from harvest.mongo_client import MongoClientWrapper
from harvest.harvester import Harvester

# Default constants
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_CONFIG_DB = "harvest_config"
DEFAULT_DATA_DB = "harvest_data"
DEFAULT_TTL_DAYS = 7


async def main():
    # Configure basic logging to show INFO and above.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s"
    )
    logger = logging.getLogger(__name__)

    # Read environment variables or fall back to defaults
    mongo_uri = os.getenv("MONGO_URI", DEFAULT_MONGO_URI)
    config_db_name = os.getenv("CONFIG_DB_NAME", DEFAULT_CONFIG_DB)
    data_db_name = os.getenv("DATA_DB_NAME", DEFAULT_DATA_DB)
    ttl_days = int(os.getenv("DEFAULT_TTL_DAYS", DEFAULT_TTL_DAYS))

    logger.info("Starting Harvester CLI")
    logger.info(f"Mongo URI: {mongo_uri}")
    logger.info(f"Config DB: {config_db_name}, Data DB: {data_db_name}")
    logger.info(f"Default TTL: {ttl_days} days")

    # 1) Instantiate MongoClientWrapper
    mongo = MongoClientWrapper(
        uri=mongo_uri,
        config_db_name=config_db_name,
        data_db_name=data_db_name
    )

    try:
        # 2) Instantiate the Harvester
        harvester = Harvester(mongo=mongo)

        # 3) Run the harvest process
        summary = await harvester.harvest()

        # 4) Print a human-readable summary of results
        print("\n=== HARVEST SUMMARY ===")
        for src_type, counters in summary.items():
            inserted = counters.get("inserted", 0)
            skipped = counters.get("skipped", 0)
            failed = counters.get("failed", 0)
            print(f"{src_type}: inserted={inserted}, skipped={skipped}, failed={failed}")

    except Exception as e:
        logger.error(f"Unexpected error during harvesting: {e}")
    finally:
        # Always close the Mongo client on exit
        await mongo.close()


if __name__ == "__main__":
    asyncio.run(main())
