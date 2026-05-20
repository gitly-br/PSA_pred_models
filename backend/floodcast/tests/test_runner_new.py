from __future__ import annotations

import asyncio
from datetime import datetime

import floodcast.runner as runner_module


class _FakeModel:
    features = ["api_070", "api_085", "api_095"]

    def predict(self, X):
        return [2]

    def predict_proba(self, X):
        return [[0.1, 0.2, 0.6, 0.1]]

    def alarm_level(self, X):
        return [3]


class _FakeRepo:
    async def fetch_historic_documents(self, bacia, start_date, end_date):
        return [
            {
                "provider": "cemaden",
                "station_id": "st-1",
                "bacia": bacia,
                "bacias": [bacia],
                "dt": datetime(2025, 2, 3, 12, 0),
                "precipitation_mm": 1.0,
            }
        ]

    async def fetch_forecast_documents(self, bacia, target_date):
        return [
            {
                "provider": "openmeteo",
                "point_id": "p1",
                "bacia": bacia,
                "bacias": [bacia],
                "dt_request": datetime(2025, 2, 4, 3, 0),
                "hourly": [{"rain": 1.0}, {"rain": 2.0}],
            }
        ]

    async def summarize_forecast(self, bacia, target_date):
        return {"point_count": 2, "total_mm": 10.0, "max_point_total_mm": 6.0, "min_point_total_mm": 4.0}

    async def close(self):
        return None


class _FakeWriter:
    def __init__(self, target_date=None):
        self.target_date = target_date
        self.passed_predictions = None

    async def check_inference_needed(self, models_config):
        return models_config

    async def write_inference_object(self, all_predictions, region_errors=None):
        self.passed_predictions = all_predictions


def test_run_floodcast_uses_registry_and_assembler(monkeypatch):
    async def run():
        fake_writer = _FakeWriter()

        async def fake_get_active_models():
            return [
                {
                    "name": "champion_guarara",
                    "bacia": "guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "artifact_uri": "/tmp/champion.joblib",
                    "features": _FakeModel.features,
                }
            ]

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: _FakeModel())
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _FakeRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        result = await runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False)
        return result, fake_writer

    result, fake_writer = asyncio.run(run())

    assert result is True
    assert fake_writer.passed_predictions is not None
    assert fake_writer.passed_predictions[0]["model_name"] == "champion_guarara"
    assert fake_writer.passed_predictions[0]["predict"] == 2
    assert fake_writer.passed_predictions[0]["severity"] == 3


def test_run_floodcast_raises_when_all_data_missing(monkeypatch):
    async def run():
        async def fake_get_active_models():
            return [
                {
                    "name": "champion_guarara",
                    "bacia": "guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "artifact_uri": "/tmp/champion.joblib",
                    "features": _FakeModel.features,
                }
            ]

        class _EmptyRepo:
            async def fetch_historic_documents(self, bacia, start_date, end_date):
                return []

            async def fetch_forecast_documents(self, bacia, target_date):
                return []

            async def summarize_forecast(self, bacia, target_date):
                return {"point_count": 0, "total_mm": 0.0, "max_point_total_mm": 0.0, "min_point_total_mm": 0.0}

            async def close(self):
                return None

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: _FakeModel())
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _EmptyRepo())

        return await runner_module.run_floodcast(target_date=datetime(2024, 3, 12), debug=False)

    try:
        asyncio.run(run())
        assert False, "should have raised DataAvailabilityError"
    except runner_module.DataAvailabilityError as exc:
        assert "historico" in str(exc) and "forecast" in str(exc)
