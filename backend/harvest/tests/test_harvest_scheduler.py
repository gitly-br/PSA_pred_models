from __future__ import annotations

from datetime import datetime

import pytz

from harvest.scheduler import _seconds_until_next_hour


def test_seconds_until_next_hour_at_30_minutes():
    tz = pytz.timezone("America/Sao_Paulo")
    now = tz.localize(datetime(2024, 10, 14, 14, 30, 0))
    seconds = _seconds_until_next_hour(now)
    assert seconds == 1800.0


def test_seconds_until_next_hour_at_59_minutes():
    tz = pytz.timezone("America/Sao_Paulo")
    now = tz.localize(datetime(2024, 10, 14, 14, 59, 0))
    seconds = _seconds_until_next_hour(now)
    assert seconds == 60.0


def test_seconds_until_next_hour_at_top_of_hour():
    tz = pytz.timezone("America/Sao_Paulo")
    now = tz.localize(datetime(2024, 10, 14, 14, 0, 0))
    seconds = _seconds_until_next_hour(now)
    assert seconds == 3600.0


def test_seconds_until_next_hour_handles_naive_datetime():
    now = datetime(2024, 10, 14, 14, 30, 0)
    seconds = _seconds_until_next_hour(now)
    assert seconds == 1800.0
