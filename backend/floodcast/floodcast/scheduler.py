from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta

import pytz


def _seconds_until_next_hour(now: datetime | None = None) -> float:
    tz = pytz.timezone("America/Sao_Paulo")
    current = now or datetime.now(tz)
    if current.tzinfo is None:
        current = tz.localize(current)
    next_hour = (current + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return max(0.0, (next_hour - current).total_seconds())


async def run_scheduler(
    interval_seconds: int,
    debug: bool = False,
    top_of_hour: bool = False,
    run_immediately: bool = True,
) -> None:
    from .runner import run_floodcast

    if top_of_hour:
        await asyncio.sleep(_seconds_until_next_hour())

    first = True
    while True:
        if first and not run_immediately:
            first = False
        else:
            await run_floodcast(debug=debug)
            first = False

        await asyncio.sleep(max(1, interval_seconds))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run Floodcast periodically")
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
