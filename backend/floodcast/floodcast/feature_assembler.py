from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd
import pytz


FEATURES_V4 = (
    ["api_070", "api_085", "api_095"]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

K_APIS = (0.70, 0.85, 0.95)
LIM_INTENSO_MM = 5.0
TZ_NAME = "America/Sao_Paulo"


def _as_local_date(value: date | datetime, tz) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = tz.localize(value)
        else:
            value = value.astimezone(tz)
        return value.date()
    return value


def _build_api_series(max_dia: pd.Series) -> dict[str, np.ndarray]:
    prev = max_dia.shift(1).fillna(0.0).to_numpy(dtype=float)
    series: dict[str, np.ndarray] = {}
    for k in K_APIS:
        out = np.zeros(len(prev), dtype=float)
        for idx, value in enumerate(prev):
            out[idx] = value + (k * out[idx - 1] if idx else 0.0)
        series[f"api_{int(k * 100):03d}"] = out
    return series


def build_feature_frame(
    documents: list[dict[str, Any]],
    bacia: str,
    target_date: date | datetime,
    lookback_days: int = 90,
    tz_name: str = TZ_NAME,
) -> pd.DataFrame:
    tz = pytz.timezone(tz_name)
    target_day = _as_local_date(target_date, tz)
    start_day = target_day - timedelta(days=lookback_days)

    frame = pd.DataFrame(documents)
    if frame.empty:
        frame = pd.DataFrame(columns=["dt", "station_id", "bacia", "bacias", "precipitation_mm"])

    def _matches_bacia(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, list):
            return bacia in value
        if isinstance(value, tuple):
            return bacia in list(value)
        return value == bacia

    if not frame.empty:
        frame = frame.copy()
        frame = frame[frame.apply(lambda row: _matches_bacia(row.get("bacia")) or _matches_bacia(row.get("bacias")), axis=1)]
        if not frame.empty:
            frame["dt"] = pd.to_datetime(frame["dt"], utc=True, errors="coerce")
            frame = frame.dropna(subset=["dt"])
            frame["dt_local"] = frame["dt"].dt.tz_convert(tz)
            frame["data"] = frame["dt_local"].dt.date
            frame["hora"] = frame["dt_local"].dt.floor("h")
            frame["precipitation_mm"] = pd.to_numeric(frame.get("precipitation_mm"), errors="coerce").fillna(0.0)
        else:
            frame = pd.DataFrame(columns=["dt_local", "data", "hora", "precipitation_mm"])

    if frame.empty:
        hourly = pd.DataFrame(columns=["data", "hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
    else:
        hourly = (
            frame.groupby(["data", "hora"], as_index=False)
            .agg(
                chuva_max_mm=("precipitation_mm", "max"),
                chuva_mean_mm=("precipitation_mm", "mean"),
                chuva_std_mm=("precipitation_mm", "std"),
                n_chovendo=("precipitation_mm", lambda s: int((s > 1.0).sum())),
            )
            .fillna({"chuva_std_mm": 0.0})
        )

    daily = (
        hourly.groupby("data", as_index=False)
        .agg(
            max_dia=("chuva_max_mm", "max"),
            acum_dia=("chuva_max_mm", "sum"),
            mean_dia=("chuva_mean_mm", "mean"),
            std_dia=("chuva_std_mm", "mean"),
            n_chovendo_max=("n_chovendo", "max"),
            pico_1h=("chuva_max_mm", "max"),
            horas_intensas=("chuva_max_mm", lambda s: int((s >= LIM_INTENSO_MM).sum())),
        )
        if not hourly.empty
        else pd.DataFrame(columns=["data", "max_dia", "acum_dia", "mean_dia", "std_dia", "n_chovendo_max", "pico_1h", "horas_intensas"])
    )

    if not daily.empty:
        daily["data"] = pd.to_datetime(daily["data"]).dt.date

    complete_dates = pd.date_range(start_day, target_day, freq="D").date
    base = pd.DataFrame({"data": complete_dates})
    daily = base.merge(daily, on="data", how="left").fillna(0.0)

    blocks = pd.DataFrame(columns=["data", "bloco_0", "bloco_1", "bloco_2", "bloco_3"])
    if not frame.empty:
        hour_blocks = frame.copy()
        hour_blocks["bloco_6h"] = hour_blocks["hora"].dt.hour // 6
        blocks = (
            hour_blocks.groupby(["data", "bloco_6h"], as_index=False)
            .agg(acc_6h=("precipitation_mm", "sum"))
            .assign(col=lambda df: "bloco_" + df["bloco_6h"].astype(str))
            .pivot(index="data", columns="col", values="acc_6h")
            .reset_index()
        )
        blocks["data"] = pd.to_datetime(blocks["data"]).dt.date
        blocks = base.merge(blocks, on="data", how="left").fillna(0.0)
        for col in ("bloco_0", "bloco_1", "bloco_2", "bloco_3"):
            if col not in blocks.columns:
                blocks[col] = 0.0
    else:
        blocks = base.assign(bloco_0=0.0, bloco_1=0.0, bloco_2=0.0, bloco_3=0.0)

    merged = daily.merge(blocks, on="data", how="left").sort_values("data").reset_index(drop=True)

    for col in ("max_dia", "acum_dia", "mean_dia", "std_dia", "n_chovendo_max", "pico_1h", "horas_intensas", "bloco_0", "bloco_1", "bloco_2", "bloco_3"):
        merged[col] = merged[col].fillna(0.0)

    merged["acc_6h_lag_1"] = merged["bloco_0"].shift(3)
    merged["acc_6h_lag_2"] = merged["bloco_1"].shift(3)
    merged["acc_6h_lag_3"] = merged["bloco_2"].shift(3)
    merged["acc_6h_lag_4"] = merged["bloco_3"].shift(3)
    merged["acc_6h_lag_5"] = merged["bloco_0"].shift(2)
    merged["acc_6h_lag_6"] = merged["bloco_1"].shift(2)
    merged["acc_6h_lag_7"] = merged["bloco_2"].shift(2)
    merged["acc_6h_lag_8"] = merged["bloco_3"].shift(2)
    merged["acc_6h_lag_9"] = merged["bloco_0"].shift(1)
    merged["acc_6h_lag_10"] = merged["bloco_1"].shift(1)
    merged["acc_6h_lag_11"] = merged["bloco_2"].shift(1)
    merged["acc_6h_lag_12"] = merged["bloco_3"].shift(1)

    merged["max_day_lag1"] = merged["max_dia"].shift(1)
    merged["max_day_lag2"] = merged["max_dia"].shift(2)
    merged["max_day_lag3"] = merged["max_dia"].shift(3)
    merged["mean_day_lag1"] = merged["mean_dia"].shift(1)
    merged["std_day_lag1"] = merged["std_dia"].shift(1)
    merged["n_chovendo_max_lag1"] = merged["n_chovendo_max"].shift(1)
    merged["pico_1h_lag1"] = merged["pico_1h"].shift(1)
    merged["horas_intensas_lag1"] = merged["horas_intensas"].shift(1)
    merged["acum_7d"] = merged["acum_dia"].rolling(window=7, min_periods=1).sum().shift(1)
    merged["acum_30d"] = merged["acum_dia"].rolling(window=30, min_periods=1).sum().shift(1)

    month_angle = 2 * np.pi * pd.to_datetime(merged["data"]).dt.month / 12.0
    merged["mes_sin"] = np.sin(month_angle)
    merged["mes_cos"] = np.cos(month_angle)

    api_series = _build_api_series(merged["max_dia"])
    for name, values in api_series.items():
        merged[name] = values

    row = merged[merged["data"] == target_day].tail(1).copy()
    row.insert(0, "bacia", bacia)
    row[FEATURES_V4] = row[FEATURES_V4].fillna(0.0)
    return row[["bacia", "data", *FEATURES_V4]]


class FeatureAssembler:
    def __init__(self, repository, lookback_days: int = 90):
        self.repository = repository
        self.lookback_days = lookback_days

    async def assemble(self, bacia: str, target_date: date | datetime) -> pd.DataFrame:
        target_day = _as_local_date(target_date, pytz.timezone(TZ_NAME))
        start_day = target_day - timedelta(days=self.lookback_days)
        documents = await self.repository.fetch_historic_documents(bacia, start_day, target_day)
        return build_feature_frame(documents, bacia, target_day, lookback_days=self.lookback_days)
