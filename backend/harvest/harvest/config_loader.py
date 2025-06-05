from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import asyncio

@dataclass(slots=True, frozen=True)
class SourceConfig:
    """
    Data class representing the configuration for a single data source.
    """
    type: str
    region_name: str
    ttl_days: int
    url: str
    args: dict[str, Any]

class ConfigLoader:
    """
    Loader class for fetching and validating source configurations from MongoDB.

    Args:
        config_client (MongoClientWrapper): A wrapper around the MongoDB client
        to access configuration collections.

    Methods:
        load() -> list[SourceConfig]:
            Load and validate all sources, returning a list of SourceConfig
            instances.
    """
    def __init__(self, config_client: MongoClientWrapper) -> None:
        self._config_client = config_client

    async def _get_sources(self) -> list[dict[str, Any]]:
        """Load all source configurations from the sources collection."""
        coll = self._config_client.get_config_collection("sources")
        cursor = coll.find({})
        return [doc async for doc in cursor]

    async def _get_types(self) -> dict[str, dict[str, Any]]:
        """Load all source types into a dictionary keyed by type name."""
        coll = self._config_client.get_config_collection("source_types")
        cursor = coll.find({})
        type_dict = {}
        async for doc in cursor:
            type_name = doc.get("type")
            if type_name:
                type_dict[type_name] = doc
        return type_dict

    async def load(self) -> list[SourceConfig]:
        """
        Load and validate all sources from the database.

        Returns:
            list[SourceConfig]: A list of validated SourceConfig objects.
        """
        source_list = await self._get_sources()
        type_dict = await self._get_types()

        out: list[SourceConfig] = []

        for src in source_list:
            src_type = src.get("type")
            type_definition = type_dict.get(src_type)

            if not type_definition:
                print(f"""
                      Warning: Type definition for '{src_type}' not found.
                      Skipping source '{src.get('region_name')}'.""")
                continue

            required_args = type_definition.get("required_args", [])
            url = type_definition.get("url")
            args = src.get("args", {})

            missing_args = [arg for arg in required_args if arg not in args]
            if missing_args:
                print(f"""
                      Warning: Source '{src.get('region_name')}' is missing
                      required args {missing_args}. Skipping.""")
                continue

            out.append(
                SourceConfig(
                    type=src_type,
                    region_name=src.get("region_name"),
                    ttl_days=src.get("ttl_days"),
                    url=url,
                    args=args,
                )
            )

        return out
