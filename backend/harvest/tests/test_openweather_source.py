import os
import pytest
import datetime as dt

import httpx
from httpx import Response

from harvest.config_loader import SourceConfig
from harvest.sources.openweather_source import OpenWeatherSource, HarvestError

# ----------------------------------------------------------------------
# Helpers: Mock transports to simulate httpx.AsyncClient behavior
# ----------------------------------------------------------------------

class DummyTransport(httpx.AsyncBaseTransport):
    """
    Async transport for httpx.AsyncClient used in tests.
    
    It accepts a handler(request) coroutine function that receives the request
    and returns a mocked httpx.Response.
    """

    def __init__(self, handler):
        super().__init__()
        self._handler = handler

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """
        Handle the request by delegating to the user-defined handler.

        Args:
            request (httpx.Request): The incoming HTTP request.

        Returns:
            httpx.Response: The mocked response.
        """
        return await self._handler(request)


class AlwaysTimeoutTransport(httpx.AsyncBaseTransport):
    """
    Async transport for simulating network errors (timeouts) during tests.
    """

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """
        Always raises a ConnectTimeout error to simulate network failure.

        Args:
            request (httpx.Request): The incoming HTTP request.

        Raises:
            httpx.ConnectTimeout: Simulated timeout error.
        """
        raise httpx.ConnectTimeout("Connection timed out")


# ----------------------------------------------------------------------
# Fixture: a basic SourceConfig and ensure API key is set
# ----------------------------------------------------------------------

@pytest.fixture
def dummy_config(monkeypatch):
    """
    Returns a sample SourceConfig with a valid URL and args.
    Also sets OPENWEATHER_API_KEY in the environment.
    """
    monkeypatch.setenv("OPENWEATHER_API_KEY", "DUMMY_KEY")
    return SourceConfig(
        type="openweather",
        region_name="TestRegion",
        ttl_days=1,
        url="https://api.openweathermap.org/data/2.5/onecall",
        args={"lat": "-23.6", "lon": "-46.5", "exclude": "minutely,daily"}
    )


# ----------------------------------------------------------------------
# 1. Instantiating SourceBase directly should raise TypeError
# ----------------------------------------------------------------------

def test_instantiating_sourcebase_raises():
    from harvest.sources.source_base import SourceBase

    cfg = SourceConfig(
        type="dummy",
        region_name="X",
        ttl_days=1,
        url="http://example.com",
        args={}
    )
    with pytest.raises(TypeError):
        SourceBase(cfg)


# ----------------------------------------------------------------------
# 2. Dummy subclass to check .type and .region
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dummy_subclass_type_and_region():
    from harvest.sources.source_base import SourceBase

    class DummySource(SourceBase):
        async def harvest(self):
            return {}

    cfg = SourceConfig(
        type="dummytype",
        region_name="DummyRegion",
        ttl_days=1,
        url="http://example.com",
        args={}
    )
    src = DummySource(cfg, timeout=1)
    assert src.type == "dummytype"
    assert src.region == "DummyRegion"


# ----------------------------------------------------------------------
# 3. Missing OPENWEATHER_API_KEY should raise HarvestError
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_key_missing_raises(monkeypatch, dummy_config):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    src = OpenWeatherSource(dummy_config, timeout=1)
    with pytest.raises(HarvestError) as excinfo:
        await src.harvest()
    assert "OPENWEATHER_API_KEY not set" in str(excinfo.value)


# ----------------------------------------------------------------------
# 4. Query-string construction (ensuring args + appid, skipping None)
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_query_string_construction(monkeypatch, dummy_config):
    """
    Replace AsyncClient to capture the request URL and method.
    Ensure base URL + params (appid, lat, lon, exclude) are present.
    """

    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        return Response(200, json={
            "lat": -23.6,
            "lon": -46.5,
            "timezone": "America/Sao_Paulo",
            "hourly": []
        })

    transport = DummyTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: orig_client(transport=transport, timeout=timeout)
    )

    src = OpenWeatherSource(dummy_config, timeout=1)
    await src.harvest()

    assert captured["method"] == "GET"
    url = captured["url"]
    assert "https://api.openweathermap.org/data/2.5/onecall" in url
    assert "appid=DUMMY_KEY" in url
    assert "lat=-23.6" in url
    assert "lon=-46.5" in url
    assert "exclude=minutely%2Cdaily" in url
    assert "None" not in url


# ----------------------------------------------------------------------
# 5. Successful 200 response with all mandatory fields
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_successful_response_contains_all_fields(monkeypatch, dummy_config):
    """
    Simulate JSON containing lat, lon, timezone, hourly plus extras.
    Verify returned dict includes those fields + dt_request, region_name, type.
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        fake_json = {
            "lat": -23.6,
            "lon": -46.5,
            "timezone": "America/Sao_Paulo",
            "hourly": [{"dt": 1650000000, "temp": 20}],
            "current": {"temp": 22.5}
        }
        return Response(200, json=fake_json)

    transport = DummyTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: orig_client(transport=transport, timeout=timeout)
    )

    src = OpenWeatherSource(dummy_config, timeout=1)
    result = await src.harvest()

    assert result["lat"] == -23.6
    assert result["lon"] == -46.5
    assert result["timezone"] == "America/Sao_Paulo"
    assert isinstance(result["hourly"], list)

    dr = result["dt_request"]
    assert isinstance(dr, dt.datetime)
    assert dr.tzinfo is not None
    assert dr.minute == 0 and dr.second == 0 and dr.microsecond == 0

    assert result["region_name"] == "TestRegion"
    assert result["type"] == "openweather"


# ----------------------------------------------------------------------
# 6. 200 OK missing a mandatory field should raise HarvestError
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_missing_mandatory_field_raises(monkeypatch, dummy_config):
    """
    Simulate JSON missing 'hourly' -> HarvestError.
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        fake_json = {
            "lat": -23.6,
            "lon": -46.5,
            "timezone": "America/Sao_Paulo"
        }
        return Response(200, json=fake_json)

    transport = DummyTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: orig_client(transport=transport, timeout=timeout)
    )

    src = OpenWeatherSource(dummy_config, timeout=1)
    with pytest.raises(HarvestError) as excinfo:
        await src.harvest()
    assert "Missing mandatory field(s)" in str(excinfo.value)


# ----------------------------------------------------------------------
# 7. HTTP error (e.g., 401) -> HarvestError
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_http_error_raises(monkeypatch, dummy_config):
    """
    Simulate HTTP 401 -> HarvestError.
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        return Response(401, json={"message": "Invalid API key"})

    transport = DummyTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: orig_client(transport=transport, timeout=timeout)
    )

    src = OpenWeatherSource(dummy_config, timeout=1)
    with pytest.raises(HarvestError) as excinfo:
        await src.harvest()
    assert "HTTP 401" in str(excinfo.value)


# ----------------------------------------------------------------------
# 8. Network error / timeout -> HarvestError
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_network_error_raises(monkeypatch, dummy_config):
    """
    Simulate httpx.RequestError (e.g., timeout) -> HarvestError.
    """

    transport = AlwaysTimeoutTransport()
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: orig_client(transport=transport, timeout=timeout)
    )

    src = OpenWeatherSource(dummy_config, timeout=1)
    with pytest.raises(HarvestError) as excinfo:
        await src.harvest()
    assert "Network error for 'openweather'" in str(excinfo.value)


# ----------------------------------------------------------------------
# 9. Custom timeout is respected
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_custom_timeout_is_respected(monkeypatch, dummy_config):
    """
    Instantiate OpenWeatherSource with timeout=5 and verify AsyncClient got that value.
    """

    recorded = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        return Response(200, json={
            "lat": -23.6,
            "lon": -46.5,
            "timezone": "America/Sao_Paulo",
            "hourly": []
        })

    transport = DummyTransport(handler)
    orig_client = httpx.AsyncClient

    def client_factory(timeout):
        recorded["timeout"] = timeout
        return orig_client(transport=transport, timeout=timeout)

    monkeypatch.setattr(httpx, "AsyncClient", client_factory)

    src = OpenWeatherSource(dummy_config, timeout=5)
    await src.harvest()

    assert recorded.get("timeout") == 5


# ----------------------------------------------------------------------
# 10. dt_request is timezone-aware and truncated
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dt_request_timezone_and_truncation(monkeypatch, dummy_config):
    """
    Generate a simple response and verify only dt_request field.
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        fake_json = {
            "lat": -23.6,
            "lon": -46.5,
            "timezone": "America/Sao_Paulo",
            "hourly": []
        }
        return Response(200, json=fake_json)

    transport = DummyTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: orig_client(transport=transport, timeout=timeout)
    )

    src = OpenWeatherSource(dummy_config, timeout=1)
    result = await src.harvest()

    dr = result["dt_request"]
    assert isinstance(dr, dt.datetime)
    assert dr.tzinfo is not None
    assert dr.minute == 0 and dr.second == 0 and dr.microsecond == 0


# ----------------------------------------------------------------------
# 11. args with None value are skipped
# ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_args_with_none_are_skipped(monkeypatch):
    """
    Configure src_config.args = {"lat": "-23.6", "lon": None}
    → only lat and appid should appear.
    """

    cfg = SourceConfig(
        type="openweather",
        region_name="XRegion",
        ttl_days=1,
        url="https://api.openweathermap.org/data/2.5/onecall",
        args={"lat": "-23.6", "lon": None}
    )
    monkeypatch.setenv("OPENWEATHER_API_KEY", "DUMMY_KEY")

    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return Response(200, json={
            "lat": -23.6,
            "lon": -46.5,
            "timezone": "America/Sao_Paulo",
            "hourly": []
        })

    transport = DummyTransport(handler)
    orig_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda timeout: orig_client(transport=transport, timeout=timeout)
    )

    src = OpenWeatherSource(cfg, timeout=1)
    await src.harvest()

    url = captured["url"]
    assert "lat=-23.6" in url
    assert "appid=DUMMY_KEY" in url
    assert "lon=None" not in url
