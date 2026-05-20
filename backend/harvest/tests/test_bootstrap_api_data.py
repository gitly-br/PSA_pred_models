from __future__ import annotations

from datetime import datetime, timezone

import polars as pl

from harvest.bootstrap_api_data import (
    _build_forecast_documents,
    _build_historic_documents,
)


def test_build_historic_documents_maps_bacias():
    frame = pl.DataFrame(
        {
            "municipio": ["MAUÁ"],
            "codEstacao": ["352940103A"],
            "nomeEstacao": ["Feital"],
            "latitude": [-23.657],
            "longitude": [-46.425],
            "dt": [datetime(2016, 1, 1, 0, 0)],
            "valor_mm": [0.0],
        }
    )

    docs = _build_historic_documents(
        frame,
        "weather/cemaden/sample.parquet",
        station_bacias={"352940103A": ["guarara", "meninos"]},
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc["provider"] == "cemaden"
    assert doc["station_id"] == "352940103A"
    assert doc["bacia"] == "guarara"
    assert doc["bacias"] == ["guarara", "meninos"]
    assert doc["dt"].tzinfo == timezone.utc
    assert doc["source_file"] == "weather/cemaden/sample.parquet"


def test_build_forecast_documents_groups_hourly_rows():
    frame = pl.DataFrame(
        {
            "slice_dt": [datetime(2024, 5, 1, 3, 0), datetime(2024, 5, 1, 3, 0)],
            "forecast_dt": [datetime(2024, 5, 1, 4, 0), datetime(2024, 5, 1, 5, 0)],
            "lat": [-23.7, -23.7],
            "lon": [-46.5, -46.5],
            "temperature": [20.0, 21.0],
            "dew_point": [18.0, 18.5],
            "pressure": [1012.0, 1011.0],
            "humidity": [80.0, 82.0],
            "wind_speed": [5.0, 6.0],
            "rain": [0.2, 0.4],
        }
    )

    docs = _build_forecast_documents(frame, "weather/openmeteo/forecast/guarara.parquet")

    assert len(docs) == 1
    doc = docs[0]
    assert doc["provider"] == "openmeteo"
    assert doc["point_id"] == "-23.7_-46.5"
    assert doc["bacia"] == "guarara"
    assert doc["dt_request"].tzinfo == timezone.utc
    assert [hourly["rain"] for hourly in doc["hourly"]] == [0.2, 0.4]
