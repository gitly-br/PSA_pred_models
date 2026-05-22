from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl
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

REQUIRED_FIELDS = ("dt", "station_id", "bacia", "bacias", "precipitation_mm")

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


def _build_api_series(max_dia: np.ndarray) -> dict[str, np.ndarray]:
    prev = np.concatenate(([0.0], max_dia[:-1]))
    series: dict[str, np.ndarray] = {}
    for k in K_APIS:
        out = np.zeros(len(prev), dtype=float)
        for idx, value in enumerate(prev):
            out[idx] = value + (k * out[idx - 1] if idx else 0.0)
        series[f"api_{int(k * 100):03d}"] = out
    return series


def _filter_documents_by_bacia_or_station(
    documents: list[dict[str, Any]],
    bacia: str,
    station_ids: list[str] | None,
) -> list[dict[str, Any]]:
    station_id_set = {str(s) for s in (station_ids or [])}
    if station_id_set:
        return [d for d in documents if str(d.get("station_id", "")) in station_id_set]

    def _matches_bacia(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, list):
            return bacia in value
        if isinstance(value, tuple):
            return bacia in list(value)
        return value == bacia

    return [
        d
        for d in documents
        if _matches_bacia(d.get("bacia")) or _matches_bacia(d.get("bacias"))
    ]


def build_feature_frame(
    documents: list[dict[str, Any]],
    bacia: str,
    target_date: date | datetime,
    lookback_days: int = 90,
    tz_name: str = TZ_NAME,
    station_ids: list[str] | None = None,
) -> pl.DataFrame:
    tz = pytz.timezone(tz_name)
    target_day = _as_local_date(target_date, tz)
    start_day = target_day - timedelta(days=lookback_days)

    # ------------------------------------------------------------------
    # 1. Filter documents in plain Python (handles heterogeneous bacias)
    # ------------------------------------------------------------------
    if not documents:
        filtered_docs: list[dict[str, Any]] = []
    else:
        filtered_docs = _filter_documents_by_bacia_or_station(documents, bacia, station_ids)

    # ------------------------------------------------------------------
    # 2. Build Polars DataFrame (normalize to only required fields to
    #    avoid costly schema inference on extra document fields)
    # ------------------------------------------------------------------
    PL_SCHEMA = {
        "dt": pl.Datetime("us", "UTC"),
        "station_id": pl.Utf8,
        "bacia": pl.Utf8,
        "bacias": pl.List(pl.Utf8),
        "precipitation_mm": pl.Float64,
    }

    if not filtered_docs:
        frame = pl.DataFrame(schema=PL_SCHEMA)
    else:
        normalized = []
        for d in filtered_docs:
            nd = {k: d.get(k) for k in REQUIRED_FIELDS if k in d}
            # Normalize: bacias must be list (some sources emit tuple)
            if "bacias" in nd and isinstance(nd["bacias"], tuple):
                nd["bacias"] = list(nd["bacias"])
            normalized.append(nd)
        frame = pl.from_dicts(normalized, schema=PL_SCHEMA)

        # Ensure required columns exist (belt-and-suspenders for
        # edge cases where a field is missing from every document)
        for col, dtype in PL_SCHEMA.items():
            if col not in frame.columns:
                frame = frame.with_columns(pl.lit(None).cast(dtype).alias(col))

    # ------------------------------------------------------------------
    # 3. Parse dt / localise / extract date and hour
    # ------------------------------------------------------------------
    if not frame.is_empty():
        # Try to cast dt to datetime; if it fails (e.g. string), parse it.
        dt_dtype = frame.schema.get("dt")
        if dt_dtype == pl.Utf8:
            frame = frame.with_columns(
                pl.col("dt")
                .str.to_datetime(time_zone="UTC", strict=False)
                .alias("dt")
            )
        elif dt_dtype != pl.Datetime("us", "UTC"):
            frame = frame.with_columns(
                pl.col("dt").cast(pl.Datetime("us", "UTC"), strict=False).alias("dt")
            )

        frame = frame.with_columns(
            pl.col("precipitation_mm").cast(pl.Float64, strict=False).fill_null(0.0)
        ).drop_nulls("dt")

        if frame.is_empty():
            frame = pl.DataFrame(
                schema={
                    "data": pl.Date,
                    "hora": pl.Datetime("us", tz_name),
                    "precipitation_mm": pl.Float64,
                }
            )
        else:
            frame = frame.with_columns(
                pl.col("dt")
                .dt.convert_time_zone(tz_name)
                .alias("dt_local")
            ).with_columns(
                pl.col("dt_local").dt.date().alias("data"),
                pl.col("dt_local").dt.truncate("1h").alias("hora"),
            )
    else:
        frame = pl.DataFrame(
            schema={
                "data": pl.Date,
                "hora": pl.Datetime("us", tz_name),
                "precipitation_mm": pl.Float64,
            }
        )

    # ------------------------------------------------------------------
    # 4. Hourly aggregation
    # ------------------------------------------------------------------
    if not frame.is_empty():
        hourly = (
            frame.group_by(["data", "hora"])
            .agg(
                chuva_max_mm=pl.col("precipitation_mm").max(),
                chuva_mean_mm=pl.col("precipitation_mm").mean(),
                chuva_std_mm=pl.col("precipitation_mm").std(),
                n_chovendo=(pl.col("precipitation_mm") > 1.0).sum().cast(pl.Int64),
            )
            .with_columns(pl.col("chuva_std_mm").fill_nan(0.0).fill_null(0.0))
        )
    else:
        hourly = pl.DataFrame(
            schema={
                "data": pl.Date,
                "hora": pl.Datetime("us", tz_name),
                "chuva_max_mm": pl.Float64,
                "chuva_mean_mm": pl.Float64,
                "chuva_std_mm": pl.Float64,
                "n_chovendo": pl.Int64,
            }
        )

    # ------------------------------------------------------------------
    # 5. Daily aggregation
    # ------------------------------------------------------------------
    if not hourly.is_empty():
        daily = hourly.group_by("data").agg(
            max_dia=pl.col("chuva_max_mm").max(),
            acum_dia=pl.col("chuva_max_mm").sum(),
            mean_dia=pl.col("chuva_mean_mm").mean(),
            std_dia=pl.col("chuva_std_mm").mean(),
            n_chovendo_max=pl.col("n_chovendo").max(),
            pico_1h=pl.col("chuva_max_mm").max(),
            horas_intensas=(pl.col("chuva_max_mm") >= LIM_INTENSO_MM)
            .sum()
            .cast(pl.Int64),
        )
    else:
        daily = pl.DataFrame(
            schema={
                "data": pl.Date,
                "max_dia": pl.Float64,
                "acum_dia": pl.Float64,
                "mean_dia": pl.Float64,
                "std_dia": pl.Float64,
                "n_chovendo_max": pl.Int64,
                "pico_1h": pl.Float64,
                "horas_intensas": pl.Int64,
            }
        )

    # ------------------------------------------------------------------
    # 6. Complete date range base
    # ------------------------------------------------------------------
    n_days = (target_day - start_day).days + 1
    complete_dates = [start_day + timedelta(days=i) for i in range(n_days)]
    base = pl.DataFrame({"data": complete_dates})

    daily = base.join(daily, on="data", how="left").fill_null(0.0)

    # ------------------------------------------------------------------
    # 7. 6-hour blocks per day
    # ------------------------------------------------------------------
    if not frame.is_empty():
        blocks = (
            frame.with_columns(
                (pl.col("hora").dt.hour() // 6).cast(pl.Int64).alias("bloco_6h")
            )
            .group_by(["data", "bloco_6h"])
            .agg(acc_6h=pl.col("precipitation_mm").sum())
            .pivot(index="data", on="bloco_6h", values="acc_6h")
        )
        rename_map = {}
        for i in range(4):
            if str(i) in blocks.columns:
                rename_map[str(i)] = f"bloco_{i}"
        if rename_map:
            blocks = blocks.rename(rename_map)
    else:
        blocks = pl.DataFrame({"data": complete_dates})

    for col in ("bloco_0", "bloco_1", "bloco_2", "bloco_3"):
        if col not in blocks.columns:
            blocks = blocks.with_columns(pl.lit(0.0).alias(col))

    blocks = base.join(blocks, on="data", how="left").fill_null(0.0)

    # ------------------------------------------------------------------
    # 8. Merge daily + blocks
    # ------------------------------------------------------------------
    merged = daily.join(blocks, on="data", how="left").sort("data")

    # Ensure numeric columns are not null before lags/rolling
    numeric_cols = [
        "max_dia",
        "acum_dia",
        "mean_dia",
        "std_dia",
        "n_chovendo_max",
        "pico_1h",
        "horas_intensas",
        "bloco_0",
        "bloco_1",
        "bloco_2",
        "bloco_3",
    ]
    merged = merged.with_columns(
        [pl.col(c).fill_null(0.0) for c in numeric_cols]
    )

    # ------------------------------------------------------------------
    # 9. Lags and rolling windows
    # ------------------------------------------------------------------
    merged = merged.with_columns(
        acc_6h_lag_1=pl.col("bloco_0").shift(3),
        acc_6h_lag_2=pl.col("bloco_1").shift(3),
        acc_6h_lag_3=pl.col("bloco_2").shift(3),
        acc_6h_lag_4=pl.col("bloco_3").shift(3),
        acc_6h_lag_5=pl.col("bloco_0").shift(2),
        acc_6h_lag_6=pl.col("bloco_1").shift(2),
        acc_6h_lag_7=pl.col("bloco_2").shift(2),
        acc_6h_lag_8=pl.col("bloco_3").shift(2),
        acc_6h_lag_9=pl.col("bloco_0").shift(1),
        acc_6h_lag_10=pl.col("bloco_1").shift(1),
        acc_6h_lag_11=pl.col("bloco_2").shift(1),
        acc_6h_lag_12=pl.col("bloco_3").shift(1),
        max_day_lag1=pl.col("max_dia").shift(1),
        max_day_lag2=pl.col("max_dia").shift(2),
        max_day_lag3=pl.col("max_dia").shift(3),
        mean_day_lag1=pl.col("mean_dia").shift(1),
        std_day_lag1=pl.col("std_dia").shift(1),
        n_chovendo_max_lag1=pl.col("n_chovendo_max").shift(1),
        pico_1h_lag1=pl.col("pico_1h").shift(1),
        horas_intensas_lag1=pl.col("horas_intensas").shift(1),
        acum_7d=pl.col("acum_dia")
        .rolling_sum(window_size=7, min_periods=1)
        .shift(1),
        acum_30d=pl.col("acum_dia")
        .rolling_sum(window_size=30, min_periods=1)
        .shift(1),
    )

    # ------------------------------------------------------------------
    # 10. Month cyclical features
    # ------------------------------------------------------------------
    month_angle = 2 * np.pi * merged["data"].dt.month() / 12.0
    merged = merged.with_columns(
        mes_sin=month_angle.sin(),
        mes_cos=month_angle.cos(),
    )

    # ------------------------------------------------------------------
    # 11. API series
    # ------------------------------------------------------------------
    api_series = _build_api_series(merged["max_dia"].to_numpy(allow_copy=True))
    for name, values in api_series.items():
        merged = merged.with_columns(pl.Series(name, values))

    # ------------------------------------------------------------------
    # 12. Select target row and return a Polars row
    # ------------------------------------------------------------------
    row = merged.filter(pl.col("data") == target_day)
    if row.is_empty():
        # target_day is guaranteed to be in the complete date range,
        # but defensively build an empty row if data is missing.
        row = pl.DataFrame(
            {c: [0.0] for c in FEATURES_V4},
            schema={c: pl.Float64 for c in FEATURES_V4},
        ).with_columns(pl.lit(target_day).alias("data"))
    else:
        row = row.tail(1)

    row = row.with_columns(pl.lit(bacia).alias("bacia"))
    row = row.with_columns([pl.col(f).fill_null(0.0) for f in FEATURES_V4])

    selected = row.select(["bacia", "data", *FEATURES_V4])
    return selected


class FeatureAssembler:
    def __init__(self, repository, lookback_days: int = 90):
        self.repository = repository
        self.lookback_days = lookback_days

    async def assemble(
        self,
        bacia: str,
        target_date: date | datetime,
        station_ids: list[str] | None = None,
        documents: list[dict[str, Any]] | None = None,
    ) -> pl.DataFrame:
        target_day = _as_local_date(target_date, pytz.timezone(TZ_NAME))
        start_day = target_day - timedelta(days=self.lookback_days)
        if documents is None:
            documents = await self.repository.fetch_historic_documents(
                bacia,
                start_day,
                target_day,
                station_ids=station_ids,
                fields=list(REQUIRED_FIELDS),
            )
        return build_feature_frame(
            documents,
            bacia,
            target_day,
            lookback_days=self.lookback_days,
            station_ids=station_ids,
        )
