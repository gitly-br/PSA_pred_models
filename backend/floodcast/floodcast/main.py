import argparse
import asyncio
from datetime import datetime
import sys

from floodcast import custom_transformers

from .runner import run_floodcast

sys.modules["__main__"] = custom_transformers


async def main():
    """
    Main function to run the flood prediction.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--date', type=str, help='Date for inference in YYYY-MM-DD format')
    args = parser.parse_args()

    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")
            return

    await run_floodcast(target_date=target_date, debug=args.debug)


def main_sync():
    """Synchronous entry point for setup.py."""
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
