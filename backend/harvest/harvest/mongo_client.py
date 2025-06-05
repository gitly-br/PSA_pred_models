from __future__ import annotations
from typing import Any
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError, OperationFailure

DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_CONFIG_DB = "harvest_config"
DEFAULT_DATA_DB = "harvest_data"
DEFAULT_TTL_DAYS = 7  # fallback TTL

class MongoClientWrapper:
    """
    MongoDB client wrapper for managing access to configuration and data
    databases.

    Args:
        uri (str, optional): The MongoDB connection URI.
        config_db_name (str, optional): The name of the configuration database.
        data_db_name (str, optional): The name of the data database.

    Attributes:
        config_db: The MongoDB database instance for configurations.
        data_db: The MongoDB database instance for data.

    Methods:
        get_config_collection(collection_name: str):
            Get a collection from the configuration database.
        get_data_collection(collection_name: str):
            Get a collection from the data database.
        ensure_indexes(collection, dedup_key: str, ttl_days: int | None = None):
            Create a unique index on a deduplication key and a TTL index on
            'dt_request'.
        insert_one_safe(collection, payload: dict[str, Any]) -> int:
            Safely insert a document, returning 1 if a duplicate key error
            occurs.
        close():
            Close the MongoDB client connection.
    """

    def __init__(
        self,
        uri: str | None = None,
        config_db_name: str | None = None,
        data_db_name: str | None = None,
    ):
        self.client = AsyncIOMotorClient(uri or DEFAULT_MONGO_URI, tz_aware=True)
        self.config_db = self.client[config_db_name or DEFAULT_CONFIG_DB]
        self.data_db = self.client[data_db_name or DEFAULT_DATA_DB]

    def get_config_collection(self, collection_name: str):
        """Get a collection from the configuration database."""
        return self.config_db[collection_name]

    def get_data_collection(self, collection_name: str):
        """Get a collection from the data database."""
        return self.data_db[collection_name]

    async def ensure_indexes(
        self,
        collection,
        dedup_key: str,
        ttl_days: int | None = None,
    ):
        """Create unique and TTL indexes on the collection."""
        expire_after = (ttl_days or DEFAULT_TTL_DAYS) * 86400

        unique_index_name = f"{dedup_key}_unique_idx"
        try:
            await collection.create_index(
                [(dedup_key, 1)],
                unique=True,
                name=unique_index_name,
                background=True,
            )
        except OperationFailure as exc:
            msg = str(exc).lower()
            if "index already exists" in msg or "indexoptionsconflict" in msg:
                pass
            else:
                raise

        ttl_index_name = "dt_request_ttl_idx"
        try:
            await collection.create_index(
                [("dt_request", 1)],
                expireAfterSeconds=expire_after,
                name=ttl_index_name,
                background=True,
            )
        except OperationFailure as exc:
            msg = str(exc).lower()
            if "index already exists" in msg or "indexoptionsconflict" in msg:
                pass
            else:
                raise

    async def insert_one_safe(self, collection, payload: dict[str, Any]) -> int:
        """Safely insert a document, ignoring duplicate key errors."""
        try:
            await collection.insert_one(payload)
        except DuplicateKeyError:
            return 1
        return 0

    async def close(self):
        """Close the MongoDB client connection."""
        self.client.close()
