from __future__ import annotations

import asyncio
from datetime import datetime

import motor.motor_asyncio

import floodcast.model_registry as model_registry


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._docs:
            raise StopAsyncIteration
        return self._docs.pop(0)


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.find_query = None
        self.update_calls = []

    async def update_one(self, flt, update, upsert=False):
        self.update_calls.append((flt, update, upsert))

    def find(self, query):
        self.find_query = query
        filtered = [doc for doc in self.docs if all(doc.get(key) == value for key, value in query.items())]
        return _FakeCursor(filtered)


class _FakeDB:
    def __init__(self, collection):
        self.collection = collection

    def __getitem__(self, name):
        return self.collection


class _FakeClient:
    def __init__(self, collection):
        self.collection = collection
        self.closed = False

    def __getitem__(self, name):
        return _FakeDB(self.collection)

    def close(self):
        self.closed = True


def test_get_active_models_returns_normalized_champion_docs(monkeypatch):
    async def run():
        collection = _FakeCollection(
            [
                {
                    "bacia": "guarara",
                    "artifact_uri": "file:///tmp/champion.joblib",
                    "features": ["api_070"],
                    "thresholds": {"1": 0.2, "2": 0.03},
                    "station_ids": ["st-1"],
                    "is_champion": True,
                    "active": True,
                },
                {
                    "bacia": "ignored",
                    "artifact_uri": "file:///tmp/ignored.joblib",
                    "features": [],
                    "is_champion": True,
                    "active": False,
                },
            ]
        )
        client = _FakeClient(collection)
        monkeypatch.setattr(motor.motor_asyncio, "AsyncIOMotorClient", lambda *args, **kwargs: client)

        docs = await model_registry.get_active_models()

        return collection, docs

    collection, docs = asyncio.run(run())

    assert collection.find_query == {"is_champion": True, "active": True}
    assert len(docs) == 1
    assert docs[0]["name"] == "champion_guarara"
    assert docs[0]["region"] == "guarara"
    assert docs[0]["subregion"] == "guarara"
    assert docs[0]["artifact_uri"] == "file:///tmp/champion.joblib"
    assert docs[0]["features"] == ["api_070"]
    assert docs[0]["thresholds"] == {"1": 0.2, "2": 0.1}


def test_upsert_model_spec_persists_champion_flags(monkeypatch):
    async def run():
        collection = _FakeCollection()
        client = _FakeClient(collection)
        monkeypatch.setattr(motor.motor_asyncio, "AsyncIOMotorClient", lambda *args, **kwargs: client)

        spec = model_registry.ChampionModelSpec(
            name="champion_guarara",
            bacia="guarara",
            artifact_uri="minio://psa/models/champion_guarara.joblib",
            features=["api_070", "api_085"],
            thresholds={"1": 0.2, "2": 0.04},
            station_ids=["st-1"],
        )

        await model_registry.upsert_model_spec(spec)
        return collection, client, spec

    collection, client, spec = asyncio.run(run())

    assert client.closed is True
    assert len(collection.update_calls) == 1
    flt, update, upsert = collection.update_calls[0]
    assert flt == {"name": "champion_guarara", "bacia": "guarara"}
    assert upsert is True
    assert update["$set"]["region"] == "guarara"
    assert update["$set"]["subregion"] == "guarara"
    assert update["$set"]["artifact_uri"] == spec.artifact_uri
    assert update["$set"]["thresholds"] == {"1": 0.2, "2": 0.1}
    assert update["$set"]["is_champion"] is True
    assert update["$set"]["active"] is True
    assert isinstance(update["$set"]["created_at"], datetime)
