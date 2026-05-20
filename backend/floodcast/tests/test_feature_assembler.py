from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np

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
