from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harvest.config_loader import SourceConfig
from harvest.sources.defesa_civil_source import DefesaCivilSource
from harvest.sources.source_base import HarvestError


def _make_config(**overrides) -> SourceConfig:
    defaults = {
        "type": "defesa_civil",
        "region": "santo_andre",
        "subregion": "all",
        "ttl_days": 365,
        "url": "https://example.com/api",
        "args": {"periodicidade": 60},
        "target": "api_data.historic",
    }
    defaults.update(overrides)
    return SourceConfig(**defaults)


def test_harvest_raises_when_env_vars_missing():
    config = _make_config()
    source = DefesaCivilSource(config)

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(HarvestError, match="DEFESA_CIVIL_API_ID"):
            asyncio.run(source.harvest())


def test_harvest_normalizes_readings():
    config = _make_config()
    source = DefesaCivilSource(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "dados": {
            "apiResultado": "S",
            "apiDados": [
                {
                    "estacao_id": 15,
                    "localidade": "Area 15 - Guarará",
                    "intervalo": "2024-10-14 14:00:00",
                    "pluviometro": "2.5",
                    "temperatura": "22.3",
                    "umidade": "75.0",
                },
            ],
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"DEFESA_CIVIL_API_ID": "test-id", "DEFESA_CIVIL_SISTEMA_ID": "2"}):
        with patch("httpx.AsyncClient", return_value=mock_client):
            docs = asyncio.run(source.harvest())

    docs = list(docs)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["provider"] == "defesa_civil"
    assert doc["station_id"] == "15"
    assert doc["station_name"] == "Area 15 - Guarará"
    assert doc["precipitation_mm"] == 2.5
    assert doc["temperature"] == 22.3
    assert doc["humidity"] == 75.0
    assert doc["dt"].tzinfo == dt.timezone.utc


def test_harvest_returns_empty_when_no_data():
    config = _make_config()
    source = DefesaCivilSource(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "dados": {
            "apiResultado": "S",
            "apiDados": [],
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"DEFESA_CIVIL_API_ID": "test-id", "DEFESA_CIVIL_SISTEMA_ID": "2"}):
        with patch("httpx.AsyncClient", return_value=mock_client):
            docs = asyncio.run(source.harvest())

    assert list(docs) == []


def test_harvest_raises_on_api_error():
    config = _make_config()
    source = DefesaCivilSource(config)

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "dados": {
            "apiResultado": "N",
        }
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch.dict("os.environ", {"DEFESA_CIVIL_API_ID": "test-id", "DEFESA_CIVIL_SISTEMA_ID": "2"}):
        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HarvestError, match="error"):
                asyncio.run(source.harvest())
