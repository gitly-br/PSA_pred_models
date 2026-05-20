from __future__ import annotations

import asyncio
from pathlib import Path

from harvest import bootstrap_local_weather as blw


class DummyMinio:
    def __init__(self, *args, **kwargs):
        self.uploaded = []
        self.deleted = []
        self.bucket_ensured = False

    def ensure_bucket(self):
        self.bucket_ensured = True

    def upload_file(self, file_path, object_name, content_type=None):
        self.uploaded.append((Path(file_path).name, object_name, content_type))

    def delete_prefix(self, prefix):
        self.deleted.append(prefix)


class DummyMongo:
    def __init__(self, *args, **kwargs):
        self.closed = False
        self.collections = {"forecast": DummyCollection()}

    def get_data_collection(self, name):
        return self.collections[name]

    async def close(self):
        self.closed = True


class DummyCollection:
    def __init__(self):
        self.deleted = []

    async def delete_many(self, query):
        self.deleted.append(query)

        class Result:
            deleted_count = 1

        return Result()


def test_bootstrap_local_weather_seeds_and_bootstraps(monkeypatch, tmp_path):
    cemaden = tmp_path / "cemaden.parquet"
    forecast = tmp_path / "forecast.parquet"
    cemaden.write_bytes(b"cemaden")
    forecast.write_bytes(b"forecast")

    dummy_minio = DummyMinio()
    dummy_mongo = DummyMongo()
    captured = {}

    monkeypatch.setattr(blw, "MinioClientWrapper", lambda *args, **kwargs: dummy_minio)
    monkeypatch.setattr(blw, "MongoClientWrapper", lambda *args, **kwargs: dummy_mongo)
    monkeypatch.setattr(blw, "_filter_parquet_to_window", lambda source_file, start_date, end_date, output_dir: source_file)

    async def fake_bootstrap_api_data(**kwargs):
        captured.update(kwargs)
        return {"historic": 7, "forecast": 3}

    monkeypatch.setattr(blw, "bootstrap_api_data", fake_bootstrap_api_data)

    result = asyncio.run(blw.bootstrap_local_weather(cemaden, forecast))

    assert result == {"historic": 7, "forecast": 3}
    assert dummy_minio.bucket_ensured is True
    assert dummy_minio.deleted == ["weather/cemaden/", "weather/openweather/forecast/"]
    assert sorted(dummy_minio.uploaded) == sorted([
        ("cemaden.parquet", "weather/cemaden/cemaden.parquet", None),
        ("forecast.parquet", "weather/openweather/forecast/forecast.parquet", None),
    ])
    assert captured["historic_prefix"] == "weather/cemaden/"
    assert captured["forecast_prefix"] == "weather/openweather/forecast/"
