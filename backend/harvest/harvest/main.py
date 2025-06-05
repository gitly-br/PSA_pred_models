import asyncio
import logging
from harvest.mongo_client import MongoClientWrapper
from harvest.harvester import Harvester

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    mongo = MongoClientWrapper(
        uri="mongodb://localhost:27017",
        config_db_name="harvest_config",
        data_db_name="harvest_data",
    )

    try:
        harvester = Harvester(mongo=mongo)

        summary = await harvester.harvest()

        print("\n=== HARVEST SUMMARY ===")
        for src_type, counters in summary.items():
            print(f"{src_type}: inserted={counters['inserted']}, skipped={counters['skipped']}, failed={counters['failed']}")
    except Exception as e:
        logging.error(f"Unexpected error in main: {e}")
    finally:
        await mongo.close()

if __name__ == "__main__":
    asyncio.run(main())
