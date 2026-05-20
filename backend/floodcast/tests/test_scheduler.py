from __future__ import annotations

from datetime import datetime

import pytz

from floodcast.scheduler import _seconds_until_next_hour


def test_seconds_until_next_hour():
    tz = pytz.timezone("America/Sao_Paulo")
    now = tz.localize(datetime(2025, 5, 20, 10, 15, 30))
    assert _seconds_until_next_hour(now) == 2670.0
