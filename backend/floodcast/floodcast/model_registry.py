from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient


MONGO_URI = os.getenv("MONGO_URI", "mongodb://psa:psa@localhost:16521/?authSource=admin")
DB_NAME = "floodcast"
COLLECTION_NAME = "models"


@dataclass(frozen=True)
class ChampionModelSpec:
    name: str
    bacia: str
    artifact_uri: str
    features: list[str]
    thresholds: dict[str, float]
    station_ids: list[str]
    modeling_family: str = "psa_v7_ordinal"
    obj_version: str = "0.3"


def _normalize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    bacia = str(doc.get("bacia") or doc.get("region") or doc.get("subregion") or doc.get("name") or "unknown")
    name = str(doc.get("name") or f"champion_{bacia}")
    return {
        "name": name,
        "bacia": bacia,
        "region": str(doc.get("region") or bacia),
        "subregion": str(doc.get("subregion") or bacia),
        "artifact_uri": str(doc.get("artifact_uri") or ""),
        "features": list(doc.get("features") or []),
        "thresholds": dict(doc.get("thresholds") or {}),
        "station_ids": list(doc.get("station_ids") or []),
        "modeling_family": str(doc.get("modeling_family") or "psa_v7_ordinal"),
        "obj_version": str(doc.get("obj_version") or "0.3"),
        "calibration": doc.get("calibration"),
        "calibration_metrics": doc.get("calibration_metrics"),
    }


async def upsert_model_spec(spec: ChampionModelSpec) -> None:
    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]
    await collection.update_one(
        {"name": spec.name, "bacia": spec.bacia},
        {
            "$set": {
                "name": spec.name,
                "bacia": spec.bacia,
                "region": spec.bacia,
                "subregion": spec.bacia,
                "artifact_uri": spec.artifact_uri,
                "features": spec.features,
                "thresholds": spec.thresholds,
                "station_ids": spec.station_ids,
                "modeling_family": spec.modeling_family,
                "obj_version": spec.obj_version,
                "is_champion": True,
                "active": True,
                "created_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )
    client.close()


async def get_active_models() -> list[dict[str, Any]]:
    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]
    docs = []
    async for doc in collection.find({"is_champion": True, "active": True}):
        docs.append(_normalize_doc(doc))
    client.close()
    return docs
