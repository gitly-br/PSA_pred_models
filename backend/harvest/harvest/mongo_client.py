from __future__ import annotations
from typing import Iterable, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from harvest.constants import (
    DEFAULT_MONGO_URI,
    DEFAULT_MONGO_DB,
    DEFAULT_TTL_DAYS,
)
from .utils import slugify_city

class MongoClientWrapper:
    def __init__(self, uri: str | None = None, db_name: str | None = None):
        self.client = AsyncIOMotorClient(uri or DEFAULT_MONGO_URI, tz_aware=True)
        self.db = self.client[db_name or DEFAULT_MONGO_DB]

    # ------------------------------------------------------------------ #
    async def get_collection(self, source_id: str, city: str):
        coll_name = f"{source_id}_{slugify_city(city)}_raw"
        return self.db[coll_name]

    # ------------------------------------------------------------------ #
    async def ensure_indexes(
        self,
        collection,
        dedup_key: str,
        ttl_days: int | None = None,
    ):
        # UNIQUE on (dedup_key, bucket_ts)
        expire_after = (ttl_days or DEFAULT_TTL_DAYS) * 86400
        await collection.create_index(
            [(dedup_key, 1)],
            unique=True,
            name="dt_idx",
            expireAfterSeconds=expire_after,
            background=True,
        )

    # ------------------------------------------------------------------ #
    async def insert_one_safe(
        self, collection, payload: dict[str, Any]
    ) -> int:
        """Returns 0 (success)/1 (failure)."""
        try:
            await collection.insert_one(payload)
        except DuplicateKeyError:
            return 1
        return 0

    async def close(self):
        self.client.close()
