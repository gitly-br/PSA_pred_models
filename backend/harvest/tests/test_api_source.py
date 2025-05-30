import pytest
import asyncio
from harvest.sources.api_source import ApiSource
from harvest.config_loader import SourceConfig

@pytest.fixture
def dummy_source_config():
    return SourceConfig(
        source_id="openweather",
        type="api",
        city="Santo André",
        dedup_key="dt",
        params={"lat": -23.67, "lon": -46.52},
        ttl_days=7
    )

@pytest.mark.asyncio
async def test_api_source_harvest(dummy_source_config):
    src = ApiSource(dummy_source_config, city=dummy_source_config.city)
    docs = await src.harvest()

    assert isinstance(docs, list)
    assert all(isinstance(d, dict) for d in docs)
    assert any(d.get("city") == "Santo André" for d in docs)
