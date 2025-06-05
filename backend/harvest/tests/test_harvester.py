import pytest
import asyncio
from unittest.mock import AsyncMock

from harvest.harvester import Harvester
from harvest.config_loader import SourceConfig
from harvest.mongo_client import MongoClientWrapper
from harvest.sources.source_base import SourceBase, HarvestError


# --- Dummy SourceBase subclass to control harvest() behavior ---------------

class DummySource(SourceBase):
    def __init__(self, src_config: SourceConfig, result=None, exception=None):
        super().__init__(src_config, timeout=1)
        self._result = result
        self._exception = exception
        self.src_config = src_config

    @property
    def region(self) -> str:
        # Override the read-only property to return src_config.region
        return self.src_config.region

    @property
    def subregion(self) -> str:
        # Override the read-only property to return src_config.subregion
        return self.src_config.subregion

    async def harvest(self):
        if self._exception:
            raise self._exception
        return self._result


# -----------------------------------------------------------------------------


@pytest.fixture
def dummy_mongo():
    """
    Returns a MongoClientWrapper with AsyncMock methods:
      - get_data_collection(name) → returns a dummy object
      - ensure_indexes(collection, dedup_key, ttl_days)
      - insert_one_safe(collection, payload) → returns 0 or 1
    """
    mongo = MongoClientWrapper(uri="mongodb://localhost:27017")
    fake_collection = object()
    mongo.get_data_collection = lambda name: fake_collection
    mongo.ensure_indexes = AsyncMock()
    mongo.insert_one_safe = AsyncMock()
    return mongo


@pytest.mark.asyncio
async def test_no_configs_returns_empty_summary(dummy_mongo, monkeypatch):
    """
    If there are no SourceConfig objects, harvest() should return an empty dict.
    """
    harv = Harvester(mongo=dummy_mongo)
    # Mock _build_configs() to return an empty list
    monkeypatch.setattr(harv, "_build_configs", AsyncMock(return_value=[]))
    summary = await harv.harvest()
    assert summary == {}


@pytest.mark.asyncio
async def test_unknown_type_raises_not_implemented(dummy_mongo, monkeypatch):
    """
    If ConfigLoader returns a config with an unsupported type,
    harvest() should raise NotImplementedError.
    """
    cfg = SourceConfig(
        type="unknown",
        region="X",
        subregion="Y",
        ttl_days=1,
        url="http://example.com",
        args={}
    )
    harv = Harvester(mongo=dummy_mongo)
    monkeypatch.setattr(harv, "_build_configs", AsyncMock(return_value=[cfg]))

    with pytest.raises(NotImplementedError):
        await harv.harvest()


@pytest.mark.asyncio
async def test_valid_source_inserted(dummy_mongo, monkeypatch):
    """
    Valid source: insert_one_safe returns 0 (inserted),
    so summary shows inserted=1, skipped=0, failed=0.
    Also ensure_indexes is called with correct TTL.
    """
    cfg = SourceConfig(
        type="dummy",
        region="My Region",
        subregion="My Subregion",
        ttl_days=5,
        url="http://example.com",
        args={}
    )
    harv = Harvester(mongo=dummy_mongo)
    monkeypatch.setattr(harv, "_build_configs", AsyncMock(return_value=[cfg]))

    dummy_src = DummySource(cfg, result={"key": "value"})
    monkeypatch.setattr(harv, "_build_source", lambda c: dummy_src)

    dummy_mongo.insert_one_safe.return_value = 0

    summary = await harv.harvest()
    print(summary)
    assert "dummy" in summary
    assert summary["dummy"]["inserted"] == 1
    assert summary["dummy"]["skipped"] == 0
    assert summary["dummy"]["failed"] == 0

    # Verify ensure_indexes was called on “dummy_my_region_my_subregion”
    expected_slug = "dummy_my_region_my_subregion"
    dummy_collection = dummy_mongo.get_data_collection(expected_slug)
    dummy_mongo.ensure_indexes.assert_awaited_once_with(
        dummy_collection,
        dedup_key="dt_request",
        ttl_days=5
    )


@pytest.mark.asyncio
async def test_duplicate_source_skipped(dummy_mongo, monkeypatch):
    """
    Duplicate result: insert_one_safe returns 1 (skipped),
    so summary should show skipped=1.
    """
    cfg = SourceConfig(
        type="dup",
        region="RegionX",
        subregion="SubregionY",
        ttl_days=2,
        url="http://example.com",
        args={}
    )

    harv = Harvester(mongo=dummy_mongo)
    monkeypatch.setattr(harv, "_build_configs", AsyncMock(return_value=[cfg]))
    dummy_src = DummySource(cfg, result={"foo": "bar"})
    monkeypatch.setattr(harv, "_build_source", lambda c: dummy_src)

    # insert_one_safe → 1 (meaning duplicate / skipped)
    dummy_mongo.insert_one_safe.return_value = asyncio.Future()
    dummy_mongo.insert_one_safe.return_value.set_result(1)

    summary = await harv.harvest()
    assert "dup" in summary
    assert summary["dup"]["inserted"] == 0
    assert summary["dup"]["skipped"] == 1
    assert summary["dup"]["failed"] == 0


@pytest.mark.asyncio
async def test_source_harvest_failure_counts_failed(dummy_mongo, monkeypatch):
    """
    If source.harvest() raises HarvestError, summary should show failed=1.
    """
    cfg = SourceConfig(
        type="fail",
        region="RegionY",
        subregion="SubregionZ",
        ttl_days=3,
        url="http://example.com",
        args={}
    )

    harv = Harvester(mongo=dummy_mongo)
    monkeypatch.setattr(harv, "_build_configs", AsyncMock(return_value=[cfg]))
    dummy_src = DummySource(cfg, exception=HarvestError("fail"))
    monkeypatch.setattr(harv, "_build_source", lambda c: dummy_src)

    summary = await harv.harvest()
    assert "fail" in summary
    assert summary["fail"]["inserted"] == 0
    assert summary["fail"]["skipped"] == 0
    assert summary["fail"]["failed"] == 1


@pytest.mark.asyncio
async def test_mixed_sources_summary(dummy_mongo, monkeypatch):
    """
    A mix of inserted, skipped, and failed sources should produce correct summary.
    """
    cfg1 = SourceConfig(type="type1", region="R1", subregion="SR1", ttl_days=1, url="", args={})
    cfg2 = SourceConfig(type="type1", region="R1", subregion="SR2", ttl_days=1, url="", args={})
    cfg3 = SourceConfig(type="type2", region="R2", subregion="SR3", ttl_days=1, url="", args={})

    harv = Harvester(mongo=dummy_mongo)
    monkeypatch.setattr(
        harv, "_build_configs",
        AsyncMock(return_value=[cfg1, cfg2, cfg3])
    )

    src1 = DummySource(cfg1, result={"a": 1})              # will be inserted
    src2 = DummySource(cfg2, result={"a": 2})              # will be skipped
    src3 = DummySource(cfg3, exception=HarvestError("oops"))  # will fail

    calls = iter([src1, src2, src3])
    monkeypatch.setattr(harv, "_build_source", lambda c: next(calls))

    # Make insert_one_safe return 0 for payload {"a": 1} (inserted), 1 otherwise (skipped)
    async def insert_side_effect(coll, payload):
        if payload == {"a": 1}:
            return 0
        return 1

    dummy_mongo.insert_one_safe.side_effect = insert_side_effect

    summary = await harv.harvest()
    # For type1: one inserted, one skipped
    assert summary["type1"]["inserted"] == 1
    assert summary["type1"]["skipped"] == 1
    assert summary["type1"]["failed"] == 0
    # For type2: one failed
    assert summary["type2"]["inserted"] == 0
    assert summary["type2"]["skipped"] == 0
    assert summary["type2"]["failed"] == 1


@pytest.mark.asyncio
async def test_collection_name_slug(monkeypatch, dummy_mongo):
    """
    Ensure collection name is '<type>_<slug(region>_<slug(subregion)>)'.
    """
    cfg = SourceConfig(
        type="t",
        region="My Region",
        subregion="My Subregion",
        ttl_days=1,
        url="",
        args={}
    )
    harv = Harvester(mongo=dummy_mongo)
    monkeypatch.setattr(harv, "_build_configs", AsyncMock(return_value=[cfg]))
    dummy_src = DummySource(cfg, result={"x": 1})
    monkeypatch.setattr(harv, "_build_source", lambda c: dummy_src)

    # Force insert_one_safe → 0 (insert)
    dummy_mongo.insert_one_safe.return_value = asyncio.Future()
    dummy_mongo.insert_one_safe.return_value.set_result(0)

    # Capture the name passed to get_data_collection
    names = []
    def capture_coll_name(name):
        names.append(name)
        return object()

    dummy_mongo.get_data_collection = capture_coll_name

    await harv.harvest()
    # slugify("My Region My Subregion") → "my_region_my_subregion"
    assert names == ["t_my_region_my_subregion"]


@pytest.mark.asyncio
async def test_ttl_correctly_passed_to_ensure_indexes(monkeypatch, dummy_mongo):
    """
    TTL days from config must be passed unchanged to ensure_indexes().
    """
    cfg = SourceConfig(
        type="t2",
        region="R",
        subregion="",        # no subregion in this case
        ttl_days=10,
        url="",
        args={}
    )
    harv = Harvester(mongo=dummy_mongo)
    monkeypatch.setattr(harv, "_build_configs", AsyncMock(return_value=[cfg]))
    dummy_src = DummySource(cfg, result={"y": 2})
    monkeypatch.setattr(harv, "_build_source", lambda c: dummy_src)

    # insert_one_safe → 0
    dummy_mongo.insert_one_safe.return_value = asyncio.Future()
    dummy_mongo.insert_one_safe.return_value.set_result(0)

    await harv.harvest()
    # slugify("R ") → "r"   (because subregion is empty)
    dummy_collection = dummy_mongo.get_data_collection("t2_r_")
    dummy_mongo.ensure_indexes.assert_awaited_with(
        dummy_collection,
        dedup_key="dt_request",
        ttl_days=10
    )


@pytest.mark.asyncio
async def test_config_loader_called_once(monkeypatch, dummy_mongo):
    """
    ConfigLoader.load() should only be called once, even if harvest() is invoked twice.
    """
    harv = Harvester(mongo=dummy_mongo)
    fake_configs = [
        SourceConfig(type="a", region="R", subregion="", ttl_days=1, url="", args={})
    ]
    loader_coro = AsyncMock(return_value=fake_configs)
    monkeypatch.setattr(harv, "_build_configs", loader_coro)

    dummy_src = DummySource(fake_configs[0], result={"z": 3})
    monkeypatch.setattr(harv, "_build_source", lambda c: dummy_src)

    # insert_one_safe → 0
    dummy_mongo.insert_one_safe.return_value = asyncio.Future()
    dummy_mongo.insert_one_safe.return_value.set_result(0)

    # First harvest() → triggers _build_configs()
    await harv.harvest()
    # Second harvest() → should not call _build_configs() again
    await harv.harvest()

    loader_coro.assert_awaited_once()
