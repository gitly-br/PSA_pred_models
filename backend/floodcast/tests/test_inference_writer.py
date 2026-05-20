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
                    "forecast_summary": {"total_mm": 10.0, "point_count": 3, "max_point_total_mm": 4.0, "min_point_total_mm": 2.0},
                }
            ]
        )

    obj = asyncio.run(run())

    assert obj["obj_version"] == "0.3"
    assert obj["region"] == "all"
    assert obj["results"]["2025-02-04"]["guarara"]["predict"] == 1
    assert obj["results"]["2025-02-04"]["guarara"]["raw_proba"] == 0.7


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
                    "proba": 10.0,
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
                    "proba": 80.0,
                    "raw_proba": 0.8,
                    "forecast_summary": {"total_mm": 11.0, "point_count": 1, "max_point_total_mm": 11.0, "min_point_total_mm": 11.0},
                },
            ]
        )

    obj = asyncio.run(run())
    all_result = obj["results"]["2025-02-04"]["all"]

    assert all_result["predict"] == 3
    assert all_result["proba"] == 80.0
    assert all_result["winner_region"] == "meninos"
