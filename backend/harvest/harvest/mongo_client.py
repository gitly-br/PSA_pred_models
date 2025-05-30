from __future__ import annotations
from typing import Iterable, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from harvest.constants import (
    DEFAULT_MONGO_URI,
    DEFAULT_MONGO_DB,
    DEFAULT_TTL_DAYS,
    window_to_timedelta,
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
        window_minutes: int,
        ttl_days: int | None = None,
    ):
        # UNIQUE on (dedup_key, bucket_ts)
        await collection.create_index(
            [(dedup_key, 1), ("bucket_ts", 1)],
            unique=True,
            name="dedup_idx",
            background=True,
        )

        # TTL on dt_request
        expire_after = (ttl_days or DEFAULT_TTL_DAYS) * 86400
        await collection.create_index(
            [("dt_request", 1)],
            name="ttl_idx",
            expireAfterSeconds=expire_after,
            background=True,
        )

    # ------------------------------------------------------------------ #
    async def insert_many_safe(
        self, collection, docs: Iterable[dict[str, Any]]
    ) -> tuple[int, int]:
        """Returns (inserted, skipped)."""
        inserted = skipped = 0
        for doc in docs:
            try:
                await collection.insert_one(doc)
                inserted += 1
            except DuplicateKeyError:
                skipped += 1
        return inserted, skipped

    async def close(self):
        self.client.close()
