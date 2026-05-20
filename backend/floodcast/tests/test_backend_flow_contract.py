from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
SENTRY_SOURCE = ROOT / "backend" / "sentry" / "source"
if str(SENTRY_SOURCE) not in sys.path:
    sys.path.insert(0, str(SENTRY_SOURCE))

import floodcast.runner as runner_module
import floodcast.weather_repository as weather_repository_module
from floodcast.minio_weather_fallback import WeatherDataUnavailableError

from app.sanic_blueprints.region import region as region_module


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
        self.find_queries = []

    def find(self, query):
        self.find_queries.append(query)
        return _FakeCursor(self.docs)


class _FakeDB:
    def __init__(self, historic, forecast):
        self._collections = {
            "historic": historic,
            "forecast": forecast,
        }

    def __getitem__(self, name):
        return self._collections[name]


class _FakeClient:
    def __init__(self, historic, forecast):
        self._db = _FakeDB(historic, forecast)

    def __getitem__(self, name):
        return self._db

    def close(self):
        return None


class _FakeRepoFallback:
    def __init__(self, historic_docs=None, forecast_error: Exception | None = None):
        self.historic_docs = list(historic_docs or [])
        self.forecast_error = forecast_error

    def fetch_historic_documents(self, bacia, start_date, end_date):
        return list(self.historic_docs)

    def fetch_forecast_documents(self, bacia, target_date):
        if self.forecast_error:
            raise self.forecast_error
        return []


@pytest.mark.parametrize(
    "method_name,fallback,expected",
    [
        (
            "fetch_historic_documents",
            _FakeRepoFallback(
                historic_docs=[{"bacia": "guarara", "dt": datetime(2025, 2, 1), "precipitation_mm": 4.2}]
            ),
            [{"bacia": "guarara", "dt": datetime(2025, 2, 1), "precipitation_mm": 4.2}],
        ),
        (
            "fetch_forecast_documents",
            _FakeRepoFallback(forecast_error=WeatherDataUnavailableError("Sem dados de forecast em parquet para guarara")),
            WeatherDataUnavailableError,
        ),
    ],
)
def test_weather_repository_uses_parquet_or_raises(monkeypatch, method_name, fallback, expected):
    async def run():
        historic = _FakeCollection([])
        forecast = _FakeCollection([])
        fake_client = _FakeClient(historic, forecast)
        monkeypatch.setattr(weather_repository_module, "AsyncIOMotorClient", lambda *args, **kwargs: fake_client)

        repo = weather_repository_module.WeatherDataRepository()
        monkeypatch.setattr(repo, "_get_minio_fallback", lambda: fallback)

        method = getattr(repo, method_name)
        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                if method_name == "fetch_historic_documents":
                    await method("guarara", datetime(2025, 2, 1).date(), datetime(2025, 2, 2).date())
                else:
                    await method("guarara", datetime(2025, 2, 1).date())
        else:
            if method_name == "fetch_historic_documents":
                return await method("guarara", datetime(2025, 2, 1).date(), datetime(2025, 2, 2).date())
            return await method("guarara", datetime(2025, 2, 1).date())

    result = asyncio.run(run())
    if not (isinstance(expected, type) and issubclass(expected, Exception)):
        assert result == expected


@pytest.mark.parametrize(
    "initial_lookup,followup_lookup,trigger_ok,expected_status,expected_payload,trigger_count",
    [
        (
            {
                "results": {"2025-02-04": {"guarara": {"predict": 2}, "all": {"predict": 2}}},
                "dt_key": datetime(2025, 2, 4),
                "_id": "cached-1",
            },
            None,
            True,
            200,
            {"predict": 2},
            0,
        ),
        (
            None,
            {
                "results": {"2025-02-04": {"guarara": {"predict": 3}, "all": {"predict": 3}}},
                "dt_key": datetime(2025, 2, 4),
                "_id": "generated-1",
            },
            True,
            200,
            {"predict": 3},
            1,
        ),
    ],
)
def test_region_route_returns_cached_inference_or_triggers_floodcast(monkeypatch, initial_lookup, followup_lookup, trigger_ok, expected_status, expected_payload, trigger_count):
    async def run():
        lookups = [initial_lookup]
        if followup_lookup is not None:
            lookups.append(followup_lookup)

        trigger_calls = []

        async def fake_lookup(collection, target_date, target_hour=None):
            if lookups:
                return lookups.pop(0)
            return None

        async def fake_trigger(target_date):
            trigger_calls.append(target_date)
            return trigger_ok, ""

        monkeypatch.setattr(region_module, "_get_municipal_inference", fake_lookup)
        monkeypatch.setattr(region_module, "_trigger_floodcast", fake_trigger)

        request = SimpleNamespace(
            args={},
            app=SimpleNamespace(ctx=SimpleNamespace(db=SimpleNamespace(inference=object()))),
        )

        response = await region_module.get_region_inference(request, "guarara")
        payload = json.loads(response.body)
        return response.status, payload, len(trigger_calls)

    status, payload, got_trigger_count = asyncio.run(run())

    assert status == expected_status
    assert payload == expected_payload
    assert got_trigger_count == trigger_count
