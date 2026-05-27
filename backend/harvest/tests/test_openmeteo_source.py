from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harvest.config_loader import SourceConfig
from harvest.sources.openmeteo_source import OpenMeteoSource
from harvest.sources.source_base import HarvestError


def _make_config(**overrides) -> SourceConfig:
    defaults = {
        "type": "openmeteo",
        "region": "santo_andre",
        "subregion": "all",
        "ttl_days": 30,
        "url": "https://api.open-meteo.com/v1/forecast",
        "args": {
            "hourly": "precipitation,rain,temperature_2m",
            "timezone": "America/Sao_Paulo",
            "forecast_days": 2,
        },
        "target": "api_data.forecast",
    }
    defaults.update(overrides)
    return SourceConfig(**defaults)


def test_harvest_normalizes_forecast_data():
    config = _make_config()
    source = OpenMeteoSource(config)

    source._point_bacias = {
        "-23.7_-46.5": ["guarara"],
    }

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "hourly": {
            "time": ["2024-10-14T00:00", "2024-10-14T01:00"],
            "precipitation": [0.0, 0.5],
            "rain": [0.0, 0.5],
            "temperature_2m": [20.0, 19.5],
            "relative_humidity_2m": [80.0, 82.0],
            "wind_speed_10m": [5.0, 6.0],
            "pressure_msl": [1012.0, 1011.0],
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        docs = asyncio.run(source.harvest())

    docs = list(docs)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["provider"] == "openmeteo"
    assert doc["point_id"] == "-23.7_-46.5"
    assert "bacia" not in doc
    assert doc["bacias"] == ["guarara"]
    assert len(doc["hourly"]) == 2
    assert doc["hourly"][0]["precipitation_mm"] == 0.0
    assert doc["hourly"][1]["precipitation_mm"] == 0.5
    assert doc["dt_request"].tzinfo == dt.timezone.utc


def test_harvest_raises_when_no_points_configured():
    config = _make_config()
    source = OpenMeteoSource(config)
    source._point_bacias = {}

    with pytest.raises(HarvestError, match="No grid points"):
        asyncio.run(source.harvest())


def test_harvest_raises_when_all_requests_fail():
    config = _make_config()
    source = OpenMeteoSource(config)
    source._point_bacias = {
        "-23.7_-46.5": ["guarara"],
    }

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Network error"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HarvestError, match="Failed to fetch"):
            asyncio.run(source.harvest())


def test_get_unique_points_deduplicates():
    config = _make_config()
    source = OpenMeteoSource(config)
    source._point_bacias = {
        "-23.7_-46.5": ["guarara", "meninos"],
        "-23.6_-46.5": ["oratorio"],
    }

    points = source._get_unique_points()
    assert len(points) == 2
    point_ids = {p[2] for p in points}
    assert point_ids == {"-23.7_-46.5", "-23.6_-46.5"}
