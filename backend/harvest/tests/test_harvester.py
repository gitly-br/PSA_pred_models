import pytest
import asyncio
from pathlib import Path

from harvest.config_loader import ConfigLoader
from harvest.harvester import Harvester

@pytest.fixture
def sample_configs():
    path = Path(__file__).parent.parent / "sample_configs.yml"
    return ConfigLoader(path).load()

@pytest.mark.asyncio
async def test_harvester_run_all(sample_configs):
    harv = Harvester(sample_configs, city="Santo André")
    counts = await harv.run_all()

    assert isinstance(counts, dict)
    assert all(isinstance(k, str) for k in counts.keys())
    assert all(isinstance(v, int) for v in counts.values())
    assert sum(counts.values()) > 0   # at least one doc harvested
