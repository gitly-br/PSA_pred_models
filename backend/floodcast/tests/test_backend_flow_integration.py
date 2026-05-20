from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest

try:
    import pymongo
except ModuleNotFoundError as exc:  # pragma: no cover - integration-only dependency
    raise unittest.SkipTest("pymongo is not installed") from exc


MONGO_URI = "mongodb://psa:psa@localhost:16521/?authSource=admin"
API_URL = "http://127.0.0.1:8080/region/all?date={}"


def _day_bounds(date_str: str) -> tuple[datetime, datetime]:
    start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _fetch(date_str: str) -> tuple[int, dict[str, object]]:
    req = Request(API_URL.format(date_str), headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, payload
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except Exception:
            payload = {"error": body}
        return exc.code, payload


def _clean_date(db, collection_name: str, field: str, date_str: str) -> None:
    start, end = _day_bounds(date_str)
    db[collection_name].delete_many({field: {"$gte": start, "$lt": end}})


def _find_cached_date(db) -> str:
    doc = db["inference"].find_one({"region": "all"}, sort=[("dt_key", -1)])
    if not doc:
        raise RuntimeError("No cached municipal inference found in floodcast.inference")
    return doc["dt_key"].astimezone(timezone.utc).date().isoformat()


def _find_ondemand_date(db) -> str:
    historic_dates = {
        row["_id"]
        for row in db["historic"].aggregate(
            [
                {"$match": {"station_id": {"$ne": None}}},
                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$dt"}}}},
            ]
        )
    }
    forecast_dates = {
        row["_id"]
        for row in db["forecast"].aggregate(
            [
                {"$match": {"dt_request": {"$ne": None}}},
                {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$dt_request"}}}},
            ]
        )
    }
    cached_dates = {
        row["_id"].astimezone(timezone.utc).date().isoformat()
        for row in db["inference"].find({"region": "all"}, {"_id": 0, "dt_key": 1})
    }
    candidates = sorted((historic_dates & forecast_dates) - cached_dates)
    if not candidates:
        raise RuntimeError("No uncached on-demand date with historic+forecast found")
    return candidates[0]


def _find_no_data_date(db) -> str:
    latest_historic = db["historic"].find_one({}, sort=[("dt", -1)])
    latest_forecast = db["forecast"].find_one({}, sort=[("dt_request", -1)])
    latest = max(
        [
            latest_historic["dt"],
            latest_forecast["dt_request"],
        ]
    )
    return (latest.astimezone(timezone.utc).date() + timedelta(days=3650)).isoformat()


def test_backend_flow_integration():
    client = pymongo.MongoClient(MONGO_URI)
    floodcast_db = client["floodcast"]
    api_db = client["api_data"]

    cached_date = _find_cached_date(floodcast_db)
    status, payload = _fetch(cached_date)
    assert status == 200
    assert payload.get("predict") is not None
    assert payload.get("explanation") is not None

    ondemand_date = _find_ondemand_date(api_db)
    _clean_date(floodcast_db, "inference", "dt_key", ondemand_date)
    status, payload = _fetch(ondemand_date)
    assert status == 200
    assert payload.get("forecast_summary") is not None
    assert floodcast_db["inference"].count_documents({"region": "all", "dt_key": {"$gte": _day_bounds(ondemand_date)[0], "$lt": _day_bounds(ondemand_date)[1]}}) == 1

    parquet_date = "2025-04-22"
    _clean_date(floodcast_db, "inference", "dt_key", parquet_date)
    _clean_date(api_db, "historic", "dt", parquet_date)
    _clean_date(api_db, "forecast", "dt_request", parquet_date)
    status, payload = _fetch(parquet_date)
    assert status == 200
    assert payload.get("forecast_summary") is not None
    assert floodcast_db["inference"].count_documents({"region": "all", "dt_key": {"$gte": _day_bounds(parquet_date)[0], "$lt": _day_bounds(parquet_date)[1]}}) == 1

    no_data_date = _find_no_data_date(api_db)
    status, payload = _fetch(no_data_date)
    assert status == 404
    assert "Sem dados para inferencia" in payload.get("error", "")

    client.close()
