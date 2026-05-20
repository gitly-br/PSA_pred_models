from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import polars as pl

from harvest.bootstrap_api_data import (
    _build_forecast_documents,
    _build_historic_documents,
    ensure_api_data_indexes,
)


class FakeCollection:
    def __init__(self):
        self.create_index_calls = []

    async def create_index(self, keys, **kwargs):
        self.create_index_calls.append((keys, kwargs))


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


def test_build_forecast_documents_groups_daily_rows_without_slice_dt():
    frame = pl.DataFrame(
        {
            "dt": [
                datetime(2025, 1, 1, 0, 0),
                datetime(2025, 1, 1, 1, 0),
                datetime(2025, 1, 2, 0, 0),
                datetime(2025, 1, 2, 1, 0),
            ],
            "precipitation_mm": [0.0, 0.1, 0.2, 0.3],
            "latitude": [-23.6, -23.6, -23.6, -23.6],
            "longitude": [-46.5, -46.5, -46.5, -46.5],
        }
    )

    docs = _build_forecast_documents(frame, "weather/openweater/open_meteo_history.parquet")

    assert len(docs) == 2
    assert [len(doc["hourly"]) for doc in docs] == [2, 2]
    assert all(doc["dt_request"].tzinfo == timezone.utc for doc in docs)


def test_ensure_api_data_indexes_creates_historic_query_indexes():
    historic_collection = FakeCollection()
    forecast_collection = FakeCollection()

    asyncio.run(ensure_api_data_indexes(historic_collection, forecast_collection))

    historic_calls = historic_collection.create_index_calls
    historic_query_indexes = {
        tuple(keys): kwargs for keys, kwargs in historic_calls if kwargs.get("name")
    }
    expected_names = {
        (("bacia", 1), ("dt", 1)): "historic_bacia_dt_idx",
        (("bacias", 1), ("dt", 1)): "historic_bacias_dt_idx",
        (("station_id", 1), ("dt", 1)): "historic_station_id_dt_idx",
    }
    assert {
        keys: kwargs["name"] for keys, kwargs in historic_query_indexes.items()
    } == expected_names
    assert all(
        kwargs["background"] is True for kwargs in historic_query_indexes.values()
    )
    assert any(kwargs.get("unique") is True for _, kwargs in historic_calls)
    assert forecast_collection.create_index_calls == [
        ([("provider", 1), ("point_id", 1), ("dt_request", 1)], {"unique": True}),
    ]
