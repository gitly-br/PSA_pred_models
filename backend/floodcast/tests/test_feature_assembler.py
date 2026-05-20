from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from floodcast.feature_assembler import FEATURES_V4, build_feature_frame


def _make_docs(bacia: str, start_day: date, n_days: int) -> list[dict[str, object]]:
    docs: list[dict[str, object]] = []
    for day_offset in range(n_days):
        current_day = start_day + timedelta(days=day_offset)
        for hour in range(24):
            value = float(day_offset + 1)
            dt = datetime(current_day.year, current_day.month, current_day.day, hour, 0, tzinfo=timezone.utc)
            docs.append(
                {
                    "provider": "cemaden",
                    "station_id": "st-1",
                    "bacia": bacia,
                    "bacias": [bacia],
                    "dt": dt,
                    "precipitation_mm": value,
                }
            )
    return docs


def test_build_feature_frame_contract_and_lags():
    bacia = "guarara"
    start_day = date(2025, 1, 1)
    target_day = date(2025, 2, 4)
    docs = _make_docs(bacia, start_day, 34)

    frame = build_feature_frame(docs, bacia, target_day)

    assert list(frame.columns) == ["bacia", "data", *FEATURES_V4]
    assert frame.iloc[0]["bacia"] == bacia
    assert frame.iloc[0]["data"] == target_day

    day_index = (target_day - start_day).days + 1
    prev_day = day_index - 1

    assert frame.iloc[0]["max_day_lag1"] == float(prev_day)
    assert frame.iloc[0]["acc_6h_lag_1"] == float(6 * (day_index - 3))
    assert frame.iloc[0]["acc_6h_lag_9"] == float(6 * prev_day)

    assert np.isfinite(frame.iloc[0]["api_070"])
    assert frame.iloc[0]["api_070"] > frame.iloc[0]["max_day_lag1"]


def test_build_feature_frame_empty_documents():
    bacia = "guarara"
    target_day = date(2025, 2, 4)
    frame = build_feature_frame([], bacia, target_day)

    assert list(frame.columns) == ["bacia", "data", *FEATURES_V4]
    assert frame.iloc[0]["bacia"] == bacia
    assert frame.iloc[0]["data"] == target_day
    assert frame.iloc[0]["max_day_lag1"] == 0.0
    assert frame.iloc[0]["acc_6h_lag_1"] == 0.0


def test_build_feature_frame_station_ids_filter():
    bacia = "guarara"
    start_day = date(2025, 1, 1)
    target_day = date(2025, 1, 5)
    docs = _make_docs(bacia, start_day, 5)
    # Add docs for a different station
    docs_other = []
    for day_offset in range(5):
        current_day = start_day + timedelta(days=day_offset)
        for hour in range(24):
            dt = datetime(current_day.year, current_day.month, current_day.day, hour, 0, tzinfo=timezone.utc)
            docs_other.append(
                {
                    "station_id": "st-other",
                    "bacia": bacia,
                    "bacias": [bacia],
                    "dt": dt,
                    "precipitation_mm": 999.0,
                }
            )
    all_docs = docs + docs_other

    frame = build_feature_frame(all_docs, bacia, target_day, station_ids=["st-1"])
    # max_day_lag1 should reflect st-1 values, not 999.0 from st-other
    assert frame.iloc[0]["max_day_lag1"] < 100.0


def test_build_feature_frame_performance_and_contract():
    import time

    bacia = "guarara"
    start_day = date(2025, 1, 1)
    target_day = date(2025, 4, 1)
    n_days = (target_day - start_day).days  # 90 days
    n_stations = 5
    docs: list[dict[str, object]] = []
    for day_offset in range(n_days):
        current_day = start_day + timedelta(days=day_offset)
        for station_idx in range(n_stations):
            for hour in range(24):
                value = float(day_offset + 1) + (station_idx * 0.1)
                dt = datetime(current_day.year, current_day.month, current_day.day, hour, 0, tzinfo=timezone.utc)
                docs.append(
                    {
                        "station_id": f"st-{station_idx}",
                        "bacia": bacia,
                        "bacias": [bacia],
                        "dt": dt,
                        "precipitation_mm": value,
                    }
                )

    t0 = time.perf_counter()
    frame = build_feature_frame(docs, bacia, target_day)
    elapsed = time.perf_counter() - t0

    assert list(frame.columns) == ["bacia", "data", *FEATURES_V4]
    assert frame.iloc[0]["bacia"] == bacia
    assert frame.iloc[0]["data"] == target_day
    assert elapsed < 2.0, f"Feature assembly took {elapsed:.2f}s, expected < 2.0s"

    # Sanity checks on computed values
    prev_day = n_days
    assert frame.iloc[0]["max_day_lag1"] == pytest.approx(float(prev_day) + (n_stations - 1) * 0.1, rel=1e-6)
    assert np.isfinite(frame.iloc[0]["api_070"])
