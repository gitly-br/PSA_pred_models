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


class _FakeRobustModel:
    all_feature_order = ["api_070", "api_085", "api_095"]

    def predict(self, X):
        raise AssertionError("predict() should not be used for robust champion")

    def predict_severity(self, bacia, X):
        assert bacia == "guarara"
        return [3]

    def risk_score(self, bacia, X):
        assert bacia == "guarara"
        return [0.87]


class _FakeRobustContractModel:
    features = [
        "api_070",
        "acum_dia_lag1",
        "om_precip_sum_h24",
        "comp_pancada",
    ]

    def __init__(self):
        self.received_frame = None

    def predict_severity(self, bacia, X):
        assert bacia == "guarara"
        self.received_frame = X
        assert list(X.columns) == self.features
        assert float(X.iloc[0]["acum_dia_lag1"]) == 0.0
        assert float(X.iloc[0]["om_precip_sum_h24"]) == 0.0
        assert float(X.iloc[0]["comp_pancada"]) == 0.0
        return [2]

    def risk_score(self, bacia, X):
        assert bacia == "guarara"
        return [0.5]


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

    def summarize_forecast_documents(self, docs):
        return {"point_count": len(docs), "total_mm": 10.0, "max_point_total_mm": 6.0, "min_point_total_mm": 4.0}

    async def close(self):
        return None


class _FakeWriter:
    def __init__(self, target_date=None):
        self.target_date = target_date
        self.passed_predictions = None
        self.passed_region_errors = None

    async def check_inference_needed(self, models_config):
        return models_config

    async def write_inference_object(self, all_predictions, region_errors=None):
        self.passed_predictions = all_predictions
        self.passed_region_errors = region_errors


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
    assert len(fake_writer.passed_predictions) == 1
    assert fake_writer.passed_predictions[0]["model_name"] == "champion_guarara"
    assert fake_writer.passed_predictions[0]["predict"] == 2
    assert fake_writer.passed_predictions[0]["severity"] == 3


def test_run_floodcast_reuses_prefetched_documents(monkeypatch):
    calls = {"historic": 0, "forecast": 0}

    class _CountingRepo(_FakeRepo):
        async def fetch_historic_documents(self, bacia, start_date, end_date):
            calls["historic"] += 1
            return await super().fetch_historic_documents(bacia, start_date, end_date)

        async def fetch_forecast_documents(self, bacia, target_date):
            calls["forecast"] += 1
            return await super().fetch_forecast_documents(bacia, target_date)

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
                    "station_ids": ["st-1"],
                }
            ]

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: _FakeModel())
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _CountingRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        result = await runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False)
        return result, fake_writer

    result, fake_writer = asyncio.run(run())

    assert result is True
    assert calls["historic"] == 1
    assert calls["forecast"] == 1
    assert fake_writer.passed_region_errors == {}


def test_run_floodcast_keeps_multiple_regions_separate(monkeypatch):
    async def run():
        fake_writer = _FakeWriter()

        async def fake_get_active_models():
            return [
                {
                    "name": "champion_guarara",
                    "bacia": "guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "artifact_uri": "/tmp/champion-guarara.joblib",
                    "features": _FakeModel.features,
                },
                {
                    "name": "champion_meninos",
                    "bacia": "meninos",
                    "region": "meninos",
                    "subregion": "meninos",
                    "artifact_uri": "/tmp/champion-meninos.joblib",
                    "features": _FakeModel.features,
                },
            ]

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: _FakeModel())
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _FakeRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        result = await runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False)
        return result, fake_writer

    result, fake_writer = asyncio.run(run())

    assert result is True
    assert len(fake_writer.passed_predictions) == 2
    assert {pred["bacia"] for pred in fake_writer.passed_predictions} == {"guarara", "meninos"}
    assert {pred["model_name"] for pred in fake_writer.passed_predictions} == {
        "champion_guarara",
        "champion_meninos",
    }
    assert fake_writer.passed_region_errors == {}


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
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: _FakeWriter())

        return await runner_module.run_floodcast(target_date=datetime(2024, 3, 12), debug=False)

    try:
        asyncio.run(run())
        assert False, "should have raised DataAvailabilityError"
    except runner_module.DataAvailabilityError as exc:
        assert "historico" in str(exc) and "forecast" in str(exc)


def test_run_floodcast_supports_robust_model_interface(monkeypatch):
    async def run():
        fake_writer = _FakeWriter()

        async def fake_get_active_models():
            return [
                {
                    "name": "champion_robust_guarara",
                    "bacia": "guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "artifact_uri": "/tmp/champion-robust.joblib",
                }
            ]

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: _FakeRobustModel())
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _FakeRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        result = await runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False)
        return result, fake_writer

    result, fake_writer = asyncio.run(run())

    assert result is True
    assert fake_writer.passed_predictions is not None
    assert fake_writer.passed_predictions[0]["model_name"] == "champion_robust_guarara"
    assert fake_writer.passed_predictions[0]["predict"] == 3
    assert fake_writer.passed_predictions[0]["severity"] == 3
    assert fake_writer.passed_predictions[0]["raw_proba"] == 0.87


def test_run_floodcast_fills_missing_contract_columns(monkeypatch):
    async def run():
        fake_writer = _FakeWriter()
        model = _FakeRobustContractModel()

        async def fake_get_active_models():
            return [
                {
                    "name": "champion_robust_guarara",
                    "bacia": "guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "artifact_uri": "/tmp/champion-robust.joblib",
                    "features": model.features,
                }
            ]

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: model)
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _FakeRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        result = await runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False)
        return result, fake_writer, model

    result, fake_writer, model = asyncio.run(run())

    assert result is True
    assert model.received_frame is not None
    assert fake_writer.passed_predictions[0]["predict"] == 2
    assert fake_writer.passed_predictions[0]["raw_proba"] == 0.5
    assert fake_writer.passed_predictions[0]["proba"] == 0.5


def test_display_probability_keeps_api_contract_0_to_1():
    assert runner_module._display_probability(0.83, threshold=None) == 0.83
    assert runner_module._display_probability(0.83, threshold=0.2) == 0.83
    assert runner_module._display_probability(0.83, threshold=0.2, calibrated_proba=0.42) == 0.42
    assert runner_module._display_probability(1.5, threshold=None) == 1.0


def test_run_floodcast_processes_bacias_in_parallel(monkeypatch):
    concurrency = {"max": 0, "current": 0}

    class _ConcurrentRepo(_FakeRepo):
        async def fetch_historic_documents(self, bacia, start_date, end_date):
            concurrency["current"] += 1
            concurrency["max"] = max(concurrency["max"], concurrency["current"])
            await asyncio.sleep(0.05)
            concurrency["current"] -= 1
            return await super().fetch_historic_documents(bacia, start_date, end_date)

        async def fetch_forecast_documents(self, bacia, target_date):
            concurrency["current"] += 1
            concurrency["max"] = max(concurrency["max"], concurrency["current"])
            await asyncio.sleep(0.05)
            concurrency["current"] -= 1
            return await super().fetch_forecast_documents(bacia, target_date)

    async def run():
        fake_writer = _FakeWriter()

        async def fake_get_active_models():
            return [
                {
                    "name": f"champion_{b}",
                    "bacia": b,
                    "region": b,
                    "subregion": b,
                    "artifact_uri": f"/tmp/champion-{b}.joblib",
                    "features": _FakeModel.features,
                }
                for b in ("guarara", "meninos", "oratorio", "tamanduatei")
            ]

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: _FakeModel())
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _ConcurrentRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        result = await runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False)
        return result, fake_writer

    result, fake_writer = asyncio.run(run())

    assert result is True
    assert len(fake_writer.passed_predictions) == 4
    assert {pred["bacia"] for pred in fake_writer.passed_predictions} == {
        "guarara", "meninos", "oratorio", "tamanduatei"
    }
    assert concurrency["max"] >= 2, f"expected parallel execution, max concurrency was {concurrency['max']}"
    assert fake_writer.passed_region_errors == {}


def test_run_floodcast_fetches_historic_and_forecast_in_parallel(monkeypatch):
    async def run():
        fake_writer = _FakeWriter()
        started_historic = asyncio.Event()
        started_forecast = asyncio.Event()
        release = asyncio.Event()

        class _OverlappingRepo(_FakeRepo):
            async def fetch_historic_documents(self, bacia, start_date, end_date):
                started_historic.set()
                await release.wait()
                return await super().fetch_historic_documents(bacia, start_date, end_date)

            async def fetch_forecast_documents(self, bacia, target_date):
                started_forecast.set()
                await release.wait()
                return await super().fetch_forecast_documents(bacia, target_date)

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
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _OverlappingRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        task = asyncio.create_task(runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False))
        await asyncio.wait_for(started_historic.wait(), timeout=1.0)
        await asyncio.wait_for(started_forecast.wait(), timeout=1.0)
        release.set()
        result = await asyncio.wait_for(task, timeout=1.0)
        return result, fake_writer

    result, fake_writer = asyncio.run(run())

    assert result is True
    assert fake_writer.passed_region_errors == {}


class _FakeRiskModelWithComponents:
    all_feature_order = ["api_070", "api_085", "api_095"]

    def predict_severity(self, bacia, X):
        return [3]

    def risk_score(self, bacia, X):
        return [0.95]  # alto se usado diretamente

    def compute_risk_components(self, bacia, X):
        return {"perigoso_any": 0.35, "pancada": 0.20, "prolongada": 0.15, "saturante": 0.10}


def test_run_floodcast_prefers_perigoso_any_over_risk_score(monkeypatch):
    """Quando compute_risk_components disponibiliza perigoso_any, raw_proba deve usa-lo em vez de risk_score."""
    async def run():
        fake_writer = _FakeWriter()

        async def fake_get_active_models():
            return [
                {
                    "name": "champion_risk_guarara",
                    "bacia": "guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "artifact_uri": "/tmp/champion-risk.joblib",
                }
            ]

        monkeypatch.setattr(runner_module, "get_active_models", fake_get_active_models)
        monkeypatch.setattr(runner_module, "load_artifact", lambda artifact_uri: _FakeRiskModelWithComponents())
        monkeypatch.setattr(runner_module, "WeatherDataRepository", lambda: _FakeRepo())
        monkeypatch.setattr(runner_module, "InferenceWriter", lambda target_date=None: fake_writer)

        result = await runner_module.run_floodcast(target_date=datetime(2025, 2, 4), debug=False)
        return result, fake_writer

    result, fake_writer = asyncio.run(run())

    assert result is True
    assert fake_writer.passed_predictions is not None
    pred = fake_writer.passed_predictions[0]
    assert pred["raw_proba"] == 0.35, f"raw_proba deve ser perigoso_any (0.35), nao risk_score (0.95). obteve {pred['raw_proba']}"
    assert pred["predict"] == 3
