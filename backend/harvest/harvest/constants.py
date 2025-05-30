"""Central defaults & environment keys."""
from datetime import timedelta

MONGO_URI_ENV = "MONGO_URI"
MONGO_DB_ENV = "MONGO_DB_NAME"
OPENWX_KEY_ENV = "OPENWEATHER_API_KEY"

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_MONGO_DB = "harvest_raw"
DEFAULT_TTL_DAYS = 7

# For dedup window: 0 → exact-match only
DEFAULT_DEDUP_WINDOW_MIN = 0

# Convert minutes window → timedelta
def window_to_timedelta(minutes: int) -> timedelta:
    return timedelta(minutes=minutes)
