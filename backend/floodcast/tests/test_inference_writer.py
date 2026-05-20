from __future__ import annotations

from datetime import datetime
import asyncio

from floodcast.inference_writer import InferenceWriter


def test_build_inference_object_with_minimal_prediction():
    async def run():
        writer = InferenceWriter(target_date=datetime(2025, 2, 4))
        return await writer._build_inference_object(
            [
                {
                    "model_name": "champion_guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "bacia": "guarara",
                    "day": "2025-02-04",
                    "predict": 1,
                    "proba": 0.7,
                    "raw_proba": 0.7,
                    "severity": 2,
                    "forecast_summary": {
                        "total_mm": 10.0,
                        "point_count": 3,
                        "max_point_total_mm": 4.0,
                        "min_point_total_mm": 2.0,
                        "rain_by_period_mm": {"night": 1.0, "morning": 2.0, "afternoon": 3.0, "evening": 4.0},
                    },
                }
            ]
        )

    obj = asyncio.run(run())

    assert obj["obj_version"] == "0.3"
    assert obj["region"] == "all"
    assert obj["results"]["2025-02-04"]["guarara"]["predict"] == 1
    assert obj["results"]["2025-02-04"]["guarara"]["raw_proba"] == 0.7
    rain_today = obj["results"]["2025-02-04"]["guarara"]["rain_today"]
    assert max(rain_today.values()) <= 9.9
    assert rain_today["evening"] > rain_today["afternoon"] > rain_today["morning"] > rain_today["night"]


def test_build_inference_object_zeros_low_rain():
    async def run():
        writer = InferenceWriter(target_date=datetime(2025, 2, 4))
        return await writer._build_inference_object(
            [
                {
                    "model_name": "champion_guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "bacia": "guarara",
                    "day": "2025-02-04",
                    "predict": 3,
                    "proba": 0.7,
                    "raw_proba": 0.7,
                    "forecast_summary": {"total_mm": 2.0, "point_count": 1, "max_point_total_mm": 2.0, "min_point_total_mm": 2.0},
                }
            ]
        )

    obj = asyncio.run(run())
    result = obj["results"]["2025-02-04"]["guarara"]

    assert result["predict"] == 0
    assert result["proba"] == 0.0
    assert "Não há precipitação significativa" in result["explanation"]
    assert max(result["rain_today"].values()) <= 4.9


def test_build_inference_object_municipal_uses_worst_regional():
    async def run():
        writer = InferenceWriter(target_date=datetime(2025, 2, 4))
        return await writer._build_inference_object(
            [
                {
                    "model_name": "champion_guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "bacia": "guarara",
                    "day": "2025-02-04",
                    "predict": 0,
                    "severity": 1,
                    "proba": 0.1,
                    "raw_proba": 0.2,
                    "forecast_summary": {"total_mm": 9.0, "point_count": 1, "max_point_total_mm": 9.0, "min_point_total_mm": 9.0},
                },
                {
                    "model_name": "champion_meninos",
                    "region": "meninos",
                    "subregion": "meninos",
                    "bacia": "meninos",
                    "day": "2025-02-04",
                    "predict": 3,
                    "severity": 3,
                    "proba": 0.8,
                    "raw_proba": 0.8,
                    "forecast_summary": {"total_mm": 11.0, "point_count": 1, "max_point_total_mm": 11.0, "min_point_total_mm": 11.0},
                },
            ]
        )

    obj = asyncio.run(run())
    all_result = obj["results"]["2025-02-04"]["all"]

    assert all_result["predict"] == 3
    assert all_result["severity"] == 3
    assert all_result["proba"] == 0.8
    assert all_result["winner_region"] == "meninos"


def test_build_inference_object_prefers_severity_over_probability():
    async def run():
        writer = InferenceWriter(target_date=datetime(2025, 2, 4))
        return await writer._build_inference_object(
            [
                {
                    "model_name": "champion_guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "bacia": "guarara",
                    "day": "2025-02-04",
                    "predict": 1,
                    "severity": 1,
                    "proba": 0.9,
                    "raw_proba": 0.9,
                    "forecast_summary": {"total_mm": 12.0, "point_count": 1, "max_point_total_mm": 12.0, "min_point_total_mm": 12.0},
                },
                {
                    "model_name": "champion_meninos",
                    "region": "meninos",
                    "subregion": "meninos",
                    "bacia": "meninos",
                    "day": "2025-02-04",
                    "predict": 2,
                    "severity": 3,
                    "proba": 0.6,
                    "raw_proba": 0.6,
                    "forecast_summary": {"total_mm": 14.0, "point_count": 1, "max_point_total_mm": 14.0, "min_point_total_mm": 14.0},
                },
            ]
        )

    obj = asyncio.run(run())
    all_result = obj["results"]["2025-02-04"]["all"]

    assert all_result["winner_region"] == "meninos"
    assert all_result["severity"] == 3
    assert set(all_result["models"]) == {"guarara", "meninos"}


def test_build_inference_object_aggregates_raw_proba_per_subregion():
    """raw_proba e calibrated_proba devem ser agregados por subregiao, nao do ultimo loop."""
    async def run():
        writer = InferenceWriter(target_date=datetime(2025, 2, 4))
        return await writer._build_inference_object(
            [
                {
                    "model_name": "champion_oratorio_a",
                    "region": "oratorio",
                    "subregion": "oratorio",
                    "bacia": "oratorio",
                    "day": "2025-02-04",
                    "predict": 3,
                    "severity": 3,
                    "proba": 0.5,
                    "raw_proba": 0.5,
                    "calibrated_proba": 0.45,
                    "forecast_summary": {"total_mm": 10.0, "point_count": 1, "max_point_total_mm": 10.0, "min_point_total_mm": 10.0},
                },
                {
                    "model_name": "champion_oratorio_b",
                    "region": "oratorio",
                    "subregion": "oratorio",
                    "bacia": "oratorio",
                    "day": "2025-02-04",
                    "predict": 3,
                    "severity": 3,
                    "proba": 0.9,
                    "raw_proba": 0.9,
                    "calibrated_proba": 0.85,
                    "forecast_summary": {"total_mm": 10.0, "point_count": 1, "max_point_total_mm": 10.0, "min_point_total_mm": 10.0},
                },
            ]
        )

    obj = asyncio.run(run())
    result = obj["results"]["2025-02-04"]["oratorio"]

    # Deve ser media dos dois modelos, nao o valor do ultimo (0.9 / 0.85)
    assert result["raw_proba"] == 0.7, f"raw_proba deve ser media dos modelos, obteve {result['raw_proba']}"
    assert result["calibrated_proba"] == 0.65, f"calibrated_proba deve ser media dos modelos, obteve {result['calibrated_proba']}"


def test_build_inference_object_uses_model_forecast_for_rain_threshold():
    """total_mm deve vir do proprio modelo, nao do ultimo loop."""
    async def run():
        writer = InferenceWriter(target_date=datetime(2025, 2, 4))
        return await writer._build_inference_object(
            [
                {
                    "model_name": "champion_guarara",
                    "region": "guarara",
                    "subregion": "guarara",
                    "bacia": "guarara",
                    "day": "2025-02-04",
                    "predict": 3,
                    "severity": 3,
                    "proba": 0.8,
                    "raw_proba": 0.8,
                    "forecast_summary": {"total_mm": 2.0, "point_count": 1, "max_point_total_mm": 2.0, "min_point_total_mm": 2.0},
                },
            ]
        )

    obj = asyncio.run(run())
    result = obj["results"]["2025-02-04"]["guarara"]

    assert result["predict"] == 0, "predict deve ser 0 quando total_mm < 3.5"
    assert result["proba"] == 0.0, "proba deve ser 0.0 quando total_mm < 3.5"
    assert "Não há precipitação significativa" in result["explanation"]
