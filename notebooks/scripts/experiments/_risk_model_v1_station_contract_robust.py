"""
Risk Model V1 — Station Contract ROBUST Validation
====================================================

Validação robusta do contrato de estações com:
- modelo conservador (max_depth=2 / regularização forte);
- sensibilidade operacional (simulação de perda de estações);
- comparação com rodada anterior quando viável;
- holdout 2026 out-of-time (thresholds/calibradores fixos no treino);
- métricas: PR-AUC, Spearman, estabilidade, inversões, curva por faixa de chuva.

Otimizações de tempo:
- CV temporal 3 splits (vs 5 na rodada anterior);
- gradboost_std com 150 árvores (vs 300) — ainda comparável;
- cache de thresholds do test histórico para holdout 2026 (sem re-CV no holdout).

Não altera backend nem Mongo.
"""

import json
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import polars as pl
from scipy.signal import lfilter
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ─── Paths ────────────────────────────────────────────────────────────────
WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
T_CUT = datetime(2023, 7, 2).date()
K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0
HORIZONTES_FC = [24, 48]

PCT_PANCADA = 0.95
PCT_PROLONGADA = 0.90
PCT_SATURANTE = 0.90

# ─── 1. Load contract ────────────────────────────────────────────────────


def load_station_contract():
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        return json.load(f)


# ─── 2. Build hourly dataset (contract stations only) ────────────────────


def build_hourly_data(estacoes_bacia):
    """Concatena chuva_bacias (2016-2025) com dados mensais CEMADEN 2026."""
    parts = []
    for bacia, stations in estacoes_bacia.items():
        df_hist = pl.read_parquet(
            WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet"
        )
        cols_keep = ["hora"] + [s for s in stations if s in df_hist.columns]
        df_hist = df_hist.select(cols_keep)
        parts.append(df_hist.with_columns(pl.lit(bacia).alias("bacia")))

    all_cols = set()
    for p in parts:
        all_cols.update(p.columns)
    for i in range(len(parts)):
        for c in all_cols:
            if c not in parts[i].columns:
                parts[i] = parts[i].with_columns(
                    pl.lit(None).cast(pl.Float64).alias(c)
                )
        parts[i] = parts[i].select(sorted(all_cols))
    df_h = pl.concat(parts).sort(["bacia", "hora"])

    meses_2026 = ["2026_01", "2026_02", "2026_03", "2026_04", "2026_05"]
    dfs_2026 = []
    for m in meses_2026:
        path = (
            WORKDIR
            / "dados"
            / "weather"
            / "monthly"
            / "historic"
            / f"cemaden_{m}.parquet"
        )
        if path.exists():
            dfs_2026.append(pl.read_parquet(path))
    if dfs_2026:
        df_2026_raw = pl.concat(dfs_2026)
    else:
        df_2026_raw = pl.DataFrame(
            schema={
                "municipio": pl.String,
                "codEstacao": pl.String,
                "nomeEstacao": pl.String,
                "latitude": pl.Float64,
                "longitude": pl.Float64,
                "dt": pl.Datetime("us"),
                "valor_mm": pl.Float64,
            }
        )

    df_2026_wide = (
        df_2026_raw.select(["dt", "codEstacao", "valor_mm"])
        .pivot(
            index="dt",
            on="codEstacao",
            values="valor_mm",
            aggregate_function="first",
        )
    )

    parts_2026 = []
    for bacia, stations in estacoes_bacia.items():
        cols = [s for s in stations if s in df_2026_wide.columns]
        if not cols:
            continue
        sub = df_2026_wide.select(["dt"] + cols)
        sub = sub.rename({"dt": "hora"})
        parts_2026.append(sub.with_columns(pl.lit(bacia).alias("bacia")))

    if parts_2026:
        all_cols_2026 = set()
        for p in parts_2026:
            all_cols_2026.update(p.columns)
        for i in range(len(parts_2026)):
            for c in all_cols_2026:
                if c not in parts_2026[i].columns:
                    parts_2026[i] = parts_2026[i].with_columns(
                        pl.lit(None).cast(pl.Float64).alias(c)
                    )
            parts_2026[i] = parts_2026[i].select(sorted(all_cols_2026))
        df_2026 = pl.concat(parts_2026).sort(["bacia", "hora"])
    else:
        df_2026 = pl.DataFrame(
            schema={"hora": pl.Datetime("us"), "bacia": pl.String}
        )

    all_station_cols = set()
    for c in df_h.columns:
        if c not in ("hora", "bacia"):
            all_station_cols.add(c)
    for c in df_2026.columns:
        if c not in ("hora", "bacia"):
            all_station_cols.add(c)

    for col in all_station_cols:
        if col not in df_h.columns:
            df_h = df_h.with_columns(pl.lit(None).cast(pl.Float64).alias(col))
        if col not in df_2026.columns:
            df_2026 = df_2026.with_columns(
                pl.lit(None).cast(pl.Float64).alias(col)
            )

    df_full = pl.concat(
        [df_h, df_2026.select(df_h.columns)], how="vertical"
    ).sort(["bacia", "hora"])
    return df_full


# ─── 3. Coverage report 2026 ─────────────────────────────────────────────


def compute_coverage_2026(df_hourly, estacoes_bacia):
    df_2026 = df_hourly.filter(pl.col("hora").dt.year() == 2026)
    rows = []
    for bacia, stations in estacoes_bacia.items():
        sub = df_2026.filter(pl.col("bacia") == bacia)
        for month in range(1, 6):
            sub_m = sub.filter(pl.col("hora").dt.month() == month)
            for st in stations:
                if st not in sub_m.columns:
                    rows.append(
                        {
                            "bacia": bacia,
                            "mes": month,
                            "station_id": st,
                            "n_registros": 0,
                            "max_mm": None,
                            "mean_mm": None,
                        }
                    )
                    continue
                s = sub_m[st]
                n = s.drop_nulls().len()
                rows.append(
                    {
                        "bacia": bacia,
                        "mes": month,
                        "station_id": st,
                        "n_registros": int(n),
                        "max_mm": float(s.max()) if n > 0 else None,
                        "mean_mm": float(s.mean()) if n > 0 else None,
                    }
                )
    return pl.DataFrame(rows)


# ─── 4. Daily aggregation ───────────────────────────────────────────────


def build_daily_cemaden(df_hourly, estacoes_bacia):
    parts = []
    for bacia, stations in estacoes_bacia.items():
        sub = df_hourly.filter(pl.col("bacia") == bacia).drop("bacia")
        est_cols = [s for s in stations if s in sub.columns]
        if not est_cols:
            continue
        sub = sub.with_columns(
            [
                pl.max_horizontal(est_cols).alias("chuva_max_mm"),
                pl.mean_horizontal(est_cols).alias("chuva_mean_mm"),
                pl.concat_list([pl.col(c) for c in est_cols])
                .list.std()
                .alias("chuva_std_mm"),
                pl.sum_horizontal(
                    [(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]
                ).alias("n_chovendo"),
            ]
        )
        parts.append(
            sub.select(
                [
                    "hora",
                    "chuva_max_mm",
                    "chuva_mean_mm",
                    "chuva_std_mm",
                    "n_chovendo",
                ]
            ).with_columns(pl.lit(bacia).alias("bacia"))
        )

    df_h = pl.concat(parts).sort(["bacia", "hora"])
    df_h = df_h.with_columns(pl.col("hora").dt.date().alias("data"))

    df_diario = (
        df_h.group_by(["data", "bacia"])
        .agg(
            [
                pl.col("chuva_max_mm").max().alias("max_dia"),
                pl.col("chuva_max_mm").sum().alias("acum_dia"),
                pl.col("chuva_mean_mm").mean().alias("mean_dia"),
                pl.col("chuva_std_mm").mean().alias("std_dia"),
                pl.col("n_chovendo").max().alias("n_chovendo_max"),
                pl.col("chuva_max_mm").max().alias("pico_1h"),
                (pl.col("chuva_max_mm") >= LIM_INTENSO_MM)
                .sum()
                .alias("horas_intensas"),
            ]
        )
        .sort(["bacia", "data"])
    )
    return df_diario


# ─── 5. OpenMeteo forecast features ─────────────────────────────────────


def build_openmeteo_forecast_features():
    meses = [f"2026_{m:02d}" for m in range(1, 6)]
    dfs = []
    for m in meses:
        path = (
            WORKDIR
            / "dados"
            / "weather"
            / "monthly"
            / "forecast"
            / f"openmeteo_{m}.parquet"
        )
        if path.exists():
            dfs.append(pl.read_parquet(path))
    if not dfs:
        return pl.DataFrame(schema={"data": pl.Date})

    df_raw = pl.concat(dfs)
    df_h = (
        df_raw.group_by("dt")
        .agg(
            [
                pl.col("precipitation_mm").mean().alias("precipitation_mm"),
                pl.col("rain_mm").mean().alias("rain_mm"),
                pl.col("temperature_c").mean().alias("temperature_c"),
                pl.col("humidity_pct").mean().alias("humidity_pct"),
                pl.col("wind_speed_kmh").max().alias("wind_max_kmh"),
                pl.col("pressure_hpa").mean().alias("pressure_hpa"),
            ]
        )
        .sort("dt")
    )

    df_h = df_h.with_columns(pl.col("dt").dt.date().alias("data"))

    rows = []
    for data in df_h["data"].unique().sort().to_list():
        row = {"data": data}
        dt_start = datetime.combine(data, datetime.min.time())
        for H in HORIZONTES_FC:
            dt_end = dt_start + timedelta(hours=H)
            janela = df_h.filter(
                (pl.col("dt") >= dt_start) & (pl.col("dt") < dt_end)
            )
            if janela.height == 0:
                row[f"om_precip_sum_h{H}"] = 0.0
                row[f"om_rain_max_h{H}"] = 0.0
                row[f"om_temp_mean_h{H}"] = None
                row[f"om_humidity_mean_h{H}"] = None
                row[f"om_wind_max_h{H}"] = None
                row[f"om_pressure_mean_h{H}"] = None
                continue
            row[f"om_precip_sum_h{H}"] = float(janela["precipitation_mm"].sum())
            row[f"om_rain_max_h{H}"] = float(janela["rain_mm"].max())
            row[f"om_temp_mean_h{H}"] = float(janela["temperature_c"].mean())
            row[f"om_humidity_mean_h{H}"] = float(
                janela["humidity_pct"].mean()
            )
            row[f"om_wind_max_h{H}"] = float(janela["wind_max_kmh"].max())
            row[f"om_pressure_mean_h{H}"] = float(
                janela["pressure_hpa"].mean()
            )
        rows.append(row)

    return pl.DataFrame(rows)


# ─── 6. Targets ─────────────────────────────────────────────────────────


def build_targets(df_diario: pl.DataFrame, estacoes_bacia: dict, t_cut: date):
    df_diario = df_diario.with_columns(
        [
            pl.col("acum_dia")
            .rolling_sum(window_size=2, min_samples=1)
            .over("bacia")
            .alias("acum_48h_proxy"),
        ]
    )

    train = df_diario.filter(pl.col("data") < t_cut)
    thresholds = {}
    for bacia in estacoes_bacia:
        sub = train.filter(pl.col("bacia") == bacia)
        thresholds[bacia] = {
            "pancada": float(sub["max_dia"].quantile(PCT_PANCADA))
            if sub.height > 0
            else 50.0,
            "prolongada": float(sub["acum_dia"].quantile(PCT_PROLONGADA))
            if sub.height > 0
            else 80.0,
        }

    sat_thr = {}
    for bacia in estacoes_bacia:
        sub = train.filter(pl.col("bacia") == bacia)
        sat_thr[bacia] = (
            float(sub["acum_48h_proxy"].quantile(PCT_SATURANTE))
            if sub.height > 0
            else 150.0
        )

    df_thr = pl.DataFrame(
        [
            {
                "bacia": b,
                "thr_pancada": v["pancada"],
                "thr_prolongada": v["prolongada"],
                "thr_saturante": sat_thr[b],
            }
            for b, v in thresholds.items()
        ]
    )
    df_diario = df_diario.join(df_thr, on="bacia", how="left")

    df_diario = df_diario.with_columns(
        [
            (pl.col("max_dia") > pl.col("thr_pancada")).alias("pancada"),
            (pl.col("acum_dia") > pl.col("thr_prolongada")).alias(
                "prolongada"
            ),
            (pl.col("acum_48h_proxy") > pl.col("thr_saturante")).alias(
                "saturante"
            ),
        ]
    ).with_columns(
        (
            pl.col("pancada")
            | pl.col("prolongada")
            | pl.col("saturante")
        ).alias("perigoso_any")
    )

    return df_diario, thresholds, sat_thr


# ─── 7. Feature engineering ─────────────────────────────────────────────


def build_features(df_diario: pl.DataFrame):
    df = df_diario.with_columns(
        [
            pl.col("max_dia").shift(1).over("bacia").alias("max_day_lag1"),
            pl.col("max_dia").shift(2).over("bacia").alias("max_day_lag2"),
            pl.col("max_dia").shift(3).over("bacia").alias("max_day_lag3"),
            pl.col("acum_dia").shift(1).over("bacia").alias("acum_dia_lag1"),
            pl.col("mean_dia").shift(1).over("bacia").alias("mean_day_lag1"),
            pl.col("std_dia").shift(1).over("bacia").alias("std_day_lag1"),
            pl.col("n_chovendo_max")
            .shift(1)
            .over("bacia")
            .alias("n_chovendo_max_lag1"),
            pl.col("pico_1h").shift(1).over("bacia").alias("pico_1h_lag1"),
            pl.col("horas_intensas")
            .shift(1)
            .over("bacia")
            .alias("horas_intensas_lag1"),
            pl.col("acum_dia")
            .rolling_sum(window_size=7, min_samples=1)
            .shift(1)
            .over("bacia")
            .alias("acum_7d"),
            pl.col("acum_dia")
            .rolling_sum(window_size=30, min_samples=1)
            .shift(1)
            .over("bacia")
            .alias("acum_30d"),
            (2 * np.pi * pl.col("data").dt.month() / 12)
            .sin()
            .alias("mes_sin"),
            (2 * np.pi * pl.col("data").dt.month() / 12)
            .cos()
            .alias("mes_cos"),
        ]
    )

    _api_parts = []
    for bacia in df["bacia"].unique().to_list():
        _sub = df.filter(pl.col("bacia") == bacia).sort("data")
        _vals = _sub["max_dia"].shift(1).fill_null(0).to_numpy()
        cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS:
            cols[f"api_{int(_k*100):03d}"] = lfilter(
                [1.0], [1.0, -_k], _vals
            )
        _api_parts.append(pl.DataFrame(cols))
    df_api = pl.concat(_api_parts)
    df = df.join(df_api, on=["data", "bacia"], how="left")

    return df


def add_openmeteo_features(df: pl.DataFrame, df_om: pl.DataFrame):
    return df.join(df_om, on="data", how="left")


def add_risk_components(df: pl.DataFrame):
    df = df.with_columns(
        [
            (pl.col("max_day_lag1") + pl.col("pico_1h_lag1")).alias(
                "comp_pancada_raw"
            ),
            (
                pl.col("api_070") + pl.col("api_085") + pl.col("api_095")
            ).alias("api_sum"),
        ]
    )
    df = df.with_columns(
        (
            pl.col("comp_pancada_raw") * (1 + pl.col("api_sum") / 100)
        ).alias("comp_pancada")
    )
    df = df.with_columns(
        (
            pl.col("acum_7d")
            + pl.col("acum_dia_lag1")
            + pl.col("mean_day_lag1") * pl.col("n_chovendo_max_lag1")
        ).alias("comp_prolongada")
    )
    df = df.with_columns(
        pl.when(pl.col("om_humidity_mean_h24").is_not_null())
        .then(
            pl.col("acum_30d") * (1 + pl.col("om_humidity_mean_h24") / 100)
        )
        .otherwise(pl.col("acum_30d"))
        .alias("comp_saturacao")
    )
    return df


def add_severidade_secundaria(df: pl.DataFrame, estacoes_bacia: dict):
    try:
        df_chamados_raw = pl.read_parquet(
            WORKDIR / "dados" / "chamados_por_bacia.parquet"
        )
        _chamados_diario = (
            df_chamados_raw.drop_nulls("dt_abertura")
            .filter(pl.col("bacia").is_not_null())
            .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
            .group_by(["data", "bacia"])
            .len()
            .rename({"len": "n_chamados"})
        )
        _ext = (
            pl.read_csv(WORKDIR / "dados" / "alagamentos_bacias.csv")
            .with_columns(pl.col("dt").str.to_date())
        )
        _df_ext = (
            _ext.select(
                [
                    pl.col("dt").alias("data"),
                    pl.col("bacia_tamanduatei").alias("tamanduatei"),
                    pl.col("bacia_guarara").alias("guarara"),
                    pl.col("bacia_oratorio").alias("oratorio"),
                    pl.col("bacia_meninos").alias("meninos"),
                ]
            )
            .unpivot(
                index="data", variable_name="bacia", value_name="flag"
            )
            .filter(pl.col("flag") > 0)
            .select(
                [
                    "data",
                    "bacia",
                    pl.lit(True).alias("pos_externo"),
                ]
            )
        )

        _max_dia = df.select(["data", "bacia", "max_dia"])
        _chamados_max = _chamados_diario.join(
            _max_dia, on=["data", "bacia"], how="left"
        )
        p50_by_bacia = {}
        for b in estacoes_bacia:
            _s = _chamados_max.filter(pl.col("bacia") == b)
            p50_by_bacia[b] = (
                float(_s["max_dia"].quantile(0.5))
                if _s.height > 0
                else 95.0
            )

        df = (
            df.join(_chamados_diario, on=["data", "bacia"], how="left")
            .join(_df_ext, on=["data", "bacia"], how="left")
            .with_columns(
                [
                    pl.col("n_chamados").fill_null(0),
                    pl.col("pos_externo").fill_null(False),
                ]
            )
        )
        _p50_expr = pl.col("bacia").replace_strict(
            p50_by_bacia, return_dtype=pl.Float64
        )
        df = df.with_columns(
            pl.when(
                (pl.col("n_chamados") >= 5) | pl.col("pos_externo")
            )
            .then(3)
            .when(pl.col("n_chamados").is_between(2, 4))
            .then(2)
            .when(
                (pl.col("n_chamados") == 1)
                | (
                    (pl.col("n_chamados") == 0)
                    & (pl.col("max_dia") > _p50_expr)
                )
            )
            .then(1)
            .otherwise(0)
            .alias("severidade")
        )
    except Exception as e:
        print(f"  [WARN] Não foi possível carregar severidade secundária: {e}")
        df = df.with_columns(pl.lit(0).cast(pl.Int8).alias("severidade"))
    return df


# ─── 8. Modelos e avaliação ──────────────────────────────────────────────


def _thr_f1(y_true, y_prob):
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return (
        float(thrs[np.nanargmax(f1s)])
        if np.any(np.isfinite(f1s))
        else 0.5
    )


def get_model(modelo: str):
    if modelo == "logreg_std":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=1000, C=1.0, random_state=42)),
            ]
        )
    elif modelo == "logreg_cons":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=1000, C=0.1, random_state=42)),
            ]
        )
    elif modelo == "gradboost_std":
        # Reduzido de 300 para 150 para acelerar sem perder comparabilidade
        return GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=5,
            subsample=0.8,
            max_features="sqrt",
            random_state=42,
        )
    elif modelo == "gradboost_cons":
        return GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.08,
            max_depth=2,
            min_samples_leaf=20,
            subsample=0.9,
            max_features="sqrt",
            random_state=42,
        )
    else:
        raise ValueError(f"Modelo desconhecido: {modelo}")


def train_eval(
    X_train, X_test, y_train, y_test, max_dia_test, modelo="gradboost_cons"
):
    if y_train.sum() < 2 or y_test.sum() == 0:
        return None, None

    clf = get_model(modelo)
    sw = np.where(y_train == 1, 3.0, 0.7).astype(float)

    fit_kwargs = {}
    if "logreg" in modelo:
        fit_kwargs["clf__sample_weight"] = sw
    else:
        fit_kwargs["sample_weight"] = sw

    clf.fit(X_train, y_train, **fit_kwargs)
    prob_test = clf.predict_proba(X_test)[:, 1]

    # CV temporal 3 splits (otimizado)
    tscv = TimeSeriesSplit(n_splits=3)
    oof = np.full(len(y_train), np.nan)
    for tr_i, va_i in tscv.split(X_train):
        if y_train[tr_i].sum() == 0 or y_train[va_i].sum() == 0:
            continue
        clf_cv = get_model(modelo)
        sw_tr = sw[tr_i]
        if "logreg" in modelo:
            clf_cv.fit(X_train[tr_i], y_train[tr_i], clf__sample_weight=sw_tr)
        else:
            clf_cv.fit(X_train[tr_i], y_train[tr_i], sample_weight=sw_tr)
        oof[va_i] = clf_cv.predict_proba(X_train[va_i])[:, 1]
    mask = ~np.isnan(oof)
    thr = (
        _thr_f1(y_train[mask], oof[mask])
        if mask.sum() > 0 and y_train[mask].sum() > 0
        else 0.5
    )

    pred_test = (prob_test >= thr).astype(int)

    prauc = average_precision_score(y_test, prob_test)
    rec = recall_score(y_test, pred_test, zero_division=0)
    prec = precision_score(y_test, pred_test, zero_division=0)
    f1 = f1_score(y_test, pred_test, zero_division=0)
    rho, pval = spearmanr(max_dia_test, prob_test)

    metrics = {
        "prauc": float(prauc),
        "recall": float(rec),
        "precision": float(prec),
        "f1": float(f1),
        "threshold": float(thr),
        "spearman_rho": float(rho),
        "spearman_p": float(pval),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "n_pos_train": int(y_train.sum()),
        "n_pos_test": int(y_test.sum()),
    }
    return metrics, prob_test


# ─── 9. Sensibilidade operacional ───────────────────────────────────────


def build_daily_cemaden_with_drop(df_hourly, estacoes_bacia, bacia_target, drop_frac=0.0, seed=42):
    rng = np.random.default_rng(seed)
    parts = []
    for bacia, stations in estacoes_bacia.items():
        sub = df_hourly.filter(pl.col("bacia") == bacia).drop("bacia")
        est_cols = [s for s in stations if s in sub.columns]
        if bacia == bacia_target and drop_frac > 0:
            n_drop = max(1, int(len(est_cols) * drop_frac))
            drop_cols = rng.choice(est_cols, size=n_drop, replace=False).tolist()
            est_cols = [c for c in est_cols if c not in drop_cols]
        if not est_cols:
            continue
        sub = sub.with_columns(
            [
                pl.max_horizontal(est_cols).alias("chuva_max_mm"),
                pl.mean_horizontal(est_cols).alias("chuva_mean_mm"),
                pl.concat_list([pl.col(c) for c in est_cols])
                .list.std()
                .alias("chuva_std_mm"),
                pl.sum_horizontal(
                    [(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]
                ).alias("n_chovendo"),
            ]
        )
        parts.append(
            sub.select(
                [
                    "hora",
                    "chuva_max_mm",
                    "chuva_mean_mm",
                    "chuva_std_mm",
                    "n_chovendo",
                ]
            ).with_columns(pl.lit(bacia).alias("bacia"))
        )

    df_h = pl.concat(parts).sort(["bacia", "hora"])
    df_h = df_h.with_columns(pl.col("hora").dt.date().alias("data"))

    df_diario = (
        df_h.group_by(["data", "bacia"])
        .agg(
            [
                pl.col("chuva_max_mm").max().alias("max_dia"),
                pl.col("chuva_max_mm").sum().alias("acum_dia"),
                pl.col("chuva_mean_mm").mean().alias("mean_dia"),
                pl.col("chuva_std_mm").mean().alias("std_dia"),
                pl.col("n_chovendo").max().alias("n_chovendo_max"),
                pl.col("chuva_max_mm").max().alias("pico_1h"),
                (pl.col("chuva_max_mm") >= LIM_INTENSO_MM)
                .sum()
                .alias("horas_intensas"),
            ]
        )
        .sort(["bacia", "data"])
    )
    return df_diario


def run_station_drop_sensitivity(df_hourly, df_feat_base, estacoes_bacia, t_cut):
    print("\n[9/9] Sensibilidade operacional (perda de estações)...")
    LABELS_SENS = ["perigoso_any"]
    MODELOS_SENS = ["gradboost_cons"]
    drop_fracs = [0.0, 0.25, 0.50]
    results_sens = []

    CEMADEN_VARS = (
        [f"api_{int(k*100):03d}" for k in K_APIS]
        + [
            "max_day_lag1",
            "max_day_lag2",
            "max_day_lag3",
            "acum_dia_lag1",
            "mean_day_lag1",
            "std_day_lag1",
            "n_chovendo_max_lag1",
            "pico_1h_lag1",
            "horas_intensas_lag1",
            "acum_7d",
            "acum_30d",
            "mes_sin",
            "mes_cos",
        ]
    )

    for bacia in sorted(estacoes_bacia.keys()):
        for drop_frac in drop_fracs:
            df_diario_drop = build_daily_cemaden_with_drop(
                df_hourly, estacoes_bacia, bacia, drop_frac=drop_frac, seed=42
            )
            df_diario_drop = df_diario_drop.with_columns(
                [
                    pl.col("acum_dia")
                    .rolling_sum(window_size=2, min_samples=1)
                    .over("bacia")
                    .alias("acum_48h_proxy"),
                ]
            )
            thr_df = df_feat_base.select(
                ["data", "bacia", "thr_pancada", "thr_prolongada", "thr_saturante"]
            ).unique(["data", "bacia"])
            df_diario_drop = df_diario_drop.join(thr_df, on=["data", "bacia"], how="left")
            df_diario_drop = df_diario_drop.with_columns(
                [
                    (pl.col("max_dia") > pl.col("thr_pancada")).alias("pancada"),
                    (pl.col("acum_dia") > pl.col("thr_prolongada")).alias("prolongada"),
                    (pl.col("acum_48h_proxy") > pl.col("thr_saturante")).alias("saturante"),
                ]
            ).with_columns(
                (pl.col("pancada") | pl.col("prolongada") | pl.col("saturante")).alias("perigoso_any")
            )

            df_feat_drop = build_features(df_diario_drop)
            for c in df_feat_base.columns:
                if c.startswith("om_") and c not in df_feat_drop.columns:
                    med = df_feat_base[c].median()
                    df_feat_drop = df_feat_drop.with_columns(
                        pl.lit(med if med is not None else 0).cast(pl.Float64).alias(c)
                    )
            for c in ["comp_pancada", "comp_prolongada", "comp_saturacao"]:
                if c not in df_feat_drop.columns:
                    df_feat_drop = df_feat_drop.with_columns(pl.lit(0).cast(pl.Float64).alias(c))

            sub = df_feat_drop.filter(pl.col("bacia") == bacia).sort("data")
            train = sub.filter(pl.col("data") < t_cut)
            test_hist = sub.filter(
                (pl.col("data") >= t_cut) & (pl.col("data").dt.year() <= 2025)
            )
            if train.height < 30 or test_hist.height < 5:
                continue

            for label in LABELS_SENS:
                y_train = train[label].to_numpy().astype(int)
                if y_train.sum() < 2:
                    continue
                cols_ok = [c for c in CEMADEN_VARS if c in sub.columns]
                sub_v = sub.drop_nulls(cols_ok + [label, "max_dia"])
                train_v = sub_v.filter(pl.col("data") < t_cut)
                test_v = sub_v.filter(
                    (pl.col("data") >= t_cut) & (pl.col("data").dt.year() <= 2025)
                )
                if train_v.height < 30 or test_v.height < 5:
                    continue
                X_train = train_v[cols_ok].to_pandas().to_numpy()
                y_train_v = train_v[label].to_numpy().astype(int)
                X_test = test_v[cols_ok].to_pandas().to_numpy()
                y_test = test_v[label].to_numpy().astype(int)
                max_dia_test = test_v["max_dia"].to_numpy()
                for modelo in MODELOS_SENS:
                    r, _ = train_eval(
                        X_train, X_test, y_train_v, y_test, max_dia_test, modelo=modelo
                    )
                    if r:
                        results_sens.append(
                            {
                                "bacia": bacia,
                                "drop_frac": drop_frac,
                                "label": label,
                                "modelo": modelo,
                                **r,
                            }
                        )
    return results_sens


# ─── 10. Main ────────────────────────────────────────────────────────────


def main():
    print("=" * 80)
    print("RISK MODEL V1 — STATION CONTRACT ROBUST VALIDATION")
    print("=" * 80)

    estacoes_bacia = load_station_contract()

    print("\n[1/9] Carregando dados horários...")
    df_hourly = build_hourly_data(estacoes_bacia)
    print(
        f"  Hourly shape: {df_hourly.shape}, range: {df_hourly['hora'].min()} to {df_hourly['hora'].max()}"
    )

    print("\n[2/9] Computando cobertura 2026...")
    df_cov = compute_coverage_2026(df_hourly, estacoes_bacia)
    cov_path = OUT_DIR / "risk_model_v1_station_contract_robust_coverage_2026.parquet"
    df_cov.write_parquet(cov_path)
    print(f"  Cobertura salva em: {cov_path}")
    cov_summary = (
        df_cov.group_by(["bacia", "mes"])
        .agg(
            [
                pl.col("station_id").count().alias("n_stations_contract"),
                (pl.col("n_registros") > 0).sum().alias("n_stations_present"),
                pl.col("n_registros").sum().alias("total_registros"),
            ]
        )
        .sort(["bacia", "mes"])
    )
    print(cov_summary)

    print("\n[3/9] Agregando diário CEMADEN por bacia...")
    df_diario = build_daily_cemaden(df_hourly, estacoes_bacia)
    print(f"  Daily shape: {df_diario.shape}")

    print("\n[4/9] Construindo targets meteorológicos...")
    df_diario, thresholds, sat_thr = build_targets(
        df_diario, estacoes_bacia, T_CUT
    )
    print(
        f"  Thresholds pancada: { {k: f'{v:.1f}' for k,v in {b: thresholds[b]['pancada'] for b in thresholds}.items() } }"
    )
    print(
        f"  Thresholds prolongada: { {k: f'{v:.1f}' for k,v in {b: thresholds[b]['prolongada'] for b in thresholds}.items() } }"
    )
    print(
        f"  Thresholds saturante: { {k: f'{v:.1f}' for k,v in sat_thr.items() } }"
    )

    print("\n[5/9] Feature engineering...")
    df_feat = build_features(df_diario)
    df_om = build_openmeteo_forecast_features()
    df_feat = add_openmeteo_features(df_feat, df_om)

    om_cols = [c for c in df_feat.columns if c.startswith("om_")]
    for c in om_cols:
        if "precip" in c or "rain" in c:
            df_feat = df_feat.with_columns(pl.col(c).fill_null(0))
        else:
            med = df_feat[c].median()
            df_feat = df_feat.with_columns(
                pl.col(c).fill_null(pl.lit(med) if med is not None else 0)
            )

    df_feat = add_risk_components(df_feat)
    df_feat = add_severidade_secundaria(df_feat, estacoes_bacia)
    print(f"  Final feature shape: {df_feat.shape}")

    CEMADEN_VARS = (
        [f"api_{int(k*100):03d}" for k in K_APIS]
        + [
            "max_day_lag1",
            "max_day_lag2",
            "max_day_lag3",
            "acum_dia_lag1",
            "mean_day_lag1",
            "std_day_lag1",
            "n_chovendo_max_lag1",
            "pico_1h_lag1",
            "horas_intensas_lag1",
            "acum_7d",
            "acum_30d",
            "mes_sin",
            "mes_cos",
        ]
    )
    OM_VARS = []
    for H in HORIZONTES_FC:
        OM_VARS += [
            f"om_precip_sum_h{H}",
            f"om_rain_max_h{H}",
            f"om_temp_mean_h{H}",
            f"om_humidity_mean_h{H}",
            f"om_wind_max_h{H}",
            f"om_pressure_mean_h{H}",
        ]
    COMP_VARS = ["comp_pancada", "comp_prolongada", "comp_saturacao"]

    ALL_VARS = [c for c in (CEMADEN_VARS + OM_VARS + COMP_VARS) if c in df_feat.columns]

    VARIANTES = {
        "CEMADEN_ONLY": [c for c in CEMADEN_VARS if c in df_feat.columns],
        "CEMADEN_OM": [c for c in (CEMADEN_VARS + OM_VARS) if c in df_feat.columns],
        "ALL": ALL_VARS,
    }

    LABELS = ["pancada", "prolongada", "saturante", "perigoso_any"]
    MODELOS = ["gradboost_cons", "gradboost_std", "logreg_cons", "logreg_std"]

    print(f"\n[6/9] Modelagem e avaliação...")
    resultados = []
    resultados_detalhe = []
    # Cache de thresholds do test histórico para reutilizar no holdout
    threshold_cache = {}

    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_feat.filter(pl.col("bacia") == bacia).sort("data")
        train = sub.filter(pl.col("data") < T_CUT)
        test_hist = sub.filter(
            (pl.col("data") >= T_CUT) & (pl.col("data").dt.year() <= 2025)
        )
        holdout_2026 = sub.filter(pl.col("data").dt.year() == 2026)

        if train.height < 30:
            print(f"  {bacia}: pulado (train insuficiente)")
            continue

        for label in LABELS:
            y_train = train[label].to_numpy().astype(int)
            if y_train.sum() < 2:
                continue

            for var_nome, var_cols in VARIANTES.items():
                cols_ok = [c for c in var_cols if c in sub.columns]
                sub_v = sub.drop_nulls(cols_ok + [label, "max_dia"])
                if sub_v.height < 30:
                    continue
                train_v = sub_v.filter(pl.col("data") < T_CUT)
                test_hist_v = sub_v.filter(
                    (pl.col("data") >= T_CUT) & (pl.col("data").dt.year() <= 2025)
                )
                holdout_v = sub_v.filter(pl.col("data").dt.year() == 2026)

                if train_v.height < 30:
                    continue

                X_train = train_v[cols_ok].to_pandas().to_numpy()
                y_train_v = train_v[label].to_numpy().astype(int)

                for modelo in MODELOS:
                    cache_key = (bacia, label, var_nome, modelo)

                    # Test histórico
                    if test_hist_v.height >= 5 and y_train_v.sum() >= 2:
                        X_test = test_hist_v[cols_ok].to_pandas().to_numpy()
                        y_test = test_hist_v[label].to_numpy().astype(int)
                        max_dia_test = test_hist_v["max_dia"].to_numpy()
                        r, _ = train_eval(
                            X_train,
                            X_test,
                            y_train_v,
                            y_test,
                            max_dia_test,
                            modelo=modelo,
                        )
                        if r:
                            threshold_cache[cache_key] = r["threshold"]
                            resultados.append(
                                {
                                    "bacia": bacia,
                                    "label": label,
                                    "variante": var_nome,
                                    "modelo": modelo,
                                    "periodo": "test_hist",
                                    **r,
                                }
                            )

                    # Holdout 2026 — usa threshold do test histórico (cache)
                    if holdout_v.height >= 3:
                        X_ho = holdout_v[cols_ok].to_pandas().to_numpy()
                        y_ho = holdout_v[label].to_numpy().astype(int)
                        max_dia_ho = holdout_v["max_dia"].to_numpy()
                        # Treinar modelo final em train+test_hist
                        X_all = (
                            np.vstack([X_train, X_test])
                            if test_hist_v.height >= 5
                            else X_train
                        )
                        y_all = (
                            np.concatenate([y_train_v, y_test])
                            if test_hist_v.height >= 5
                            else y_train_v
                        )
                        clf_final = get_model(modelo)
                        sw_all = np.where(y_all == 1, 3.0, 0.7).astype(float)
                        try:
                            if "logreg" in modelo:
                                clf_final.fit(
                                    X_all, y_all, clf__sample_weight=sw_all
                                )
                            else:
                                clf_final.fit(
                                    X_all, y_all, sample_weight=sw_all
                                )
                            prob_ho = clf_final.predict_proba(X_ho)[:, 1]
                        except Exception:
                            continue

                        # Reutiliza threshold do test histórico; se não existir, pula holdout
                        if cache_key not in threshold_cache:
                            continue
                        thr = threshold_cache[cache_key]
                        pred_ho = (prob_ho >= thr).astype(int)

                        prauc = (
                            average_precision_score(y_ho, prob_ho)
                            if y_ho.sum() > 0
                            else 0.0
                        )
                        rec = (
                            recall_score(y_ho, pred_ho, zero_division=0)
                            if y_ho.sum() > 0
                            else 0.0
                        )
                        prec = (
                            precision_score(y_ho, pred_ho, zero_division=0)
                            if y_ho.sum() > 0
                            else 0.0
                        )
                        f1 = (
                            f1_score(y_ho, pred_ho, zero_division=0)
                            if y_ho.sum() > 0
                            else 0.0
                        )
                        rho, pval = (
                            spearmanr(max_dia_ho, prob_ho)
                            if len(set(prob_ho)) > 1
                            else (0.0, 1.0)
                        )

                        resultados.append(
                            {
                                "bacia": bacia,
                                "label": label,
                                "variante": var_nome,
                                "modelo": modelo,
                                "periodo": "holdout_2026",
                                "prauc": float(prauc),
                                "recall": float(rec),
                                "precision": float(prec),
                                "f1": float(f1),
                                "threshold": float(thr),
                                "spearman_rho": float(rho),
                                "spearman_p": float(pval),
                                "n_train": int(len(y_all)),
                                "n_test": int(len(y_ho)),
                                "n_pos_train": int(y_all.sum()),
                                "n_pos_test": int(y_ho.sum()),
                            }
                        )

                        for i in range(len(y_ho)):
                            resultados_detalhe.append(
                                {
                                    "bacia": bacia,
                                    "data": holdout_v["data"][i],
                                    "label": label,
                                    "variante": var_nome,
                                    "modelo": modelo,
                                    "max_dia": float(max_dia_ho[i]),
                                    "y_true": int(y_ho[i]),
                                    "prob": float(prob_ho[i]),
                                    "pred": int(pred_ho[i]),
                                }
                            )

    # ─── 11. Análise de estabilidade e curvas ─────────────────────────────
    print("\n[7/9] Análise de estabilidade, curvas e inversões...")
    import pandas as pd

    df_res = pd.DataFrame(resultados)
    df_det = pd.DataFrame(resultados_detalhe)

    stab = pd.DataFrame()
    curva = pd.DataFrame()
    inv = pd.DataFrame()

    if not df_det.empty:
        stab = (
            df_det.groupby(["bacia", "label", "variante", "modelo"])
            .agg(prob_std=("prob", "std"), prob_mean=("prob", "mean"), n=("prob", "count"))
            .reset_index()
        )
        df_det["faixa_chuva"] = pd.cut(
            df_det["max_dia"],
            bins=[0, 5, 10, 20, 30, 50, 999],
            labels=["0-5", "5-10", "10-20", "20-30", "30-50", "50+"],
        )
        curva = (
            df_det.groupby(["bacia", "label", "variante", "modelo", "faixa_chuva"])
            .agg(prob_mean=("prob", "mean"), prob_max=("prob", "max"), n=("prob", "count"))
            .reset_index()
        )
        inv = (
            df_det.groupby(["bacia", "label", "variante", "modelo"])
            .apply(
                lambda g: spearmanr(g["max_dia"], g["prob"])[0]
                if g["prob"].nunique() > 1
                else np.nan
            )
            .reset_index(name="spearman_rho")
        )
        inv["inversao"] = inv["spearman_rho"] < 0

    # ─── 12. Sensibilidade operacional ────────────────────────────────────
    print("\n[8/9] Sensibilidade operacional...")
    results_sens = run_station_drop_sensitivity(
        df_hourly, df_feat, estacoes_bacia, T_CUT
    )
    df_sens = pd.DataFrame(results_sens)

    # ─── 13. Comparar com rodada anterior ─────────────────────────────────
    print("\n[9/9] Comparando com rodada anterior...")
    prev_parquet = OUT_DIR / "risk_model_v1_station_contract.parquet"
    df_prev = None
    if prev_parquet.exists():
        try:
            df_prev = pd.read_parquet(prev_parquet)
            df_prev["modelo_mapped"] = df_prev["modelo"].map(
                {"gradboost": "gradboost_std", "logreg": "logreg_std"}
            )
            print(f"  Rodada anterior carregada: {len(df_prev)} registros")
        except Exception as e:
            print(f"  [WARN] Não foi possível carregar rodada anterior: {e}")

    # ─── 14. Export ───────────────────────────────────────────────────────
    print("\n[Export] Salvando resultados...")
    out_parquet = OUT_DIR / "risk_model_v1_station_contract_robust.parquet"
    df_res.to_parquet(out_parquet)
    print(f"  Métricas: {out_parquet}")

    if not df_det.empty:
        out_det = OUT_DIR / "risk_model_v1_station_contract_robust_detalhe.parquet"
        df_det.to_parquet(out_det)
        out_stab = (
            OUT_DIR / "risk_model_v1_station_contract_robust_estabilidade.parquet"
        )
        stab.to_parquet(out_stab)
        out_curva = (
            OUT_DIR / "risk_model_v1_station_contract_robust_curva_faixas.parquet"
        )
        curva.to_parquet(out_curva)
        out_inv = OUT_DIR / "risk_model_v1_station_contract_robust_inversoes.parquet"
        inv.to_parquet(out_inv)

    if not df_sens.empty:
        out_sens = (
            OUT_DIR / "risk_model_v1_station_contract_robust_sensibilidade.parquet"
        )
        df_sens.to_parquet(out_sens)
        print(f"  Sensibilidade: {out_sens}")

    # Relatório
    relatorio_path = OUT_DIR / "relatorio_risk_model_v1_station_contract_robust.md"
    with open(relatorio_path, "w") as f:
        f.write("# Relatório Risk Model V1 — Station Contract ROBUST\n\n")
        f.write(f"**Data:** 2026-05-20\n\n")
        f.write("## 1. Configuração\n\n")
        f.write(f"- Treino: até {T_CUT}\n")
        f.write("- Test histórico: após corte até 2025-12-31\n")
        f.write("- Holdout 2026: 2026-01-01 a 2026-05-19 (dados parciais)\n")
        f.write(f"- Modelos: {MODELOS}\n")
        f.write(f"- Variantes: {list(VARIANTES.keys())}\n")
        f.write(f"- Labels: {LABELS}\n")
        f.write(
            "- Regularização: gradboost_cons (max_depth=2, min_samples_leaf=20); logreg_cons (C=0.1)\n\n"
        )

        f.write("## 2. Cobertura 2026 (contrato atualizado)\n\n")
        f.write("```\n")
        f.write(cov_summary.to_pandas().to_string(index=False))
        f.write("\n```\n\n")

        f.write("### Análise de proxies\n\n")
        cov_detail = cov_summary.to_pandas()
        for _, row in cov_detail.iterrows():
            ausentes = row["n_stations_contract"] - row["n_stations_present"]
            f.write(
                f"- **{row['bacia']}** mês {row['mes']}: {row['n_stations_present']}/{row['n_stations_contract']} estações presentes"
            )
            if ausentes > 0:
                f.write(f" ({ausentes} ausente(s))")
            f.write(f" — {row['total_registros']} registros\n")
        f.write("\n")

        if not df_res.empty:
            f.write("## 3. Métricas Test Histórico (até 2025)\n\n")
            summary_hist = (
                df_res[df_res["periodo"] == "test_hist"]
                .groupby(["bacia", "label", "variante", "modelo"])
                .agg(
                    {
                        "prauc": "mean",
                        "spearman_rho": "mean",
                        "recall": "mean",
                        "precision": "mean",
                        "f1": "mean",
                    }
                )
                .reset_index()
                .sort_values(
                    ["bacia", "label", "prauc"], ascending=[True, True, False]
                )
            )
            f.write("```\n")
            f.write(summary_hist.to_string(index=False))
            f.write("\n```\n\n")

            f.write("## 4. Métricas Holdout 2026\n\n")
            summary_ho = (
                df_res[df_res["periodo"] == "holdout_2026"]
                .groupby(["bacia", "label", "variante", "modelo"])
                .agg(
                    {
                        "prauc": "mean",
                        "spearman_rho": "mean",
                        "recall": "mean",
                        "precision": "mean",
                        "f1": "mean",
                        "n_test": "sum",
                    }
                )
                .reset_index()
                .sort_values(
                    ["bacia", "label", "prauc"], ascending=[True, True, False]
                )
            )
            f.write("```\n")
            f.write(summary_ho.to_string(index=False))
            f.write("\n```\n\n")

            if not df_det.empty:
                f.write("## 5. Estabilidade (std prob em 2026)\n\n")
                f.write("```\n")
                f.write(stab.to_string(index=False))
                f.write("\n```\n\n")

                f.write("## 6. Inversões (Spearman negativo)\n\n")
                f.write("```\n")
                f.write(inv.to_string(index=False))
                f.write("\n```\n\n")

            if not df_sens.empty:
                f.write("## 7. Sensibilidade operacional (perda de estações)\n\n")
                sens_summary = (
                    df_sens.groupby(["bacia", "drop_frac", "modelo"])
                    .agg({"prauc": "mean", "spearman_rho": "mean", "f1": "mean"})
                    .reset_index()
                    .sort_values(["bacia", "drop_frac", "prauc"], ascending=[True, True, False])
                )
                f.write("```\n")
                f.write(sens_summary.to_string(index=False))
                f.write("\n```\n\n")

            if df_prev is not None and not df_prev.empty:
                f.write("## 8. Comparação com rodada anterior\n\n")
                f.write(
                    "Comparando modelos standard (gradboost_std/logreg_std) com resultados anteriores (gradboost/logreg).\n\n"
                )
                for periodo in ["test_hist", "holdout_2026"]:
                    f.write(f"### {periodo}\n\n")
                    cur = df_res[df_res["periodo"] == periodo]
                    prev = df_prev[df_prev["periodo"] == periodo]
                    if cur.empty or prev.empty:
                        f.write("  Dados insuficientes para comparação.\n\n")
                        continue
                    merged = cur.merge(
                        prev,
                        on=["bacia", "label", "variante"],
                        suffixes=("_robust", "_prev"),
                        how="inner",
                    )
                    if merged.empty:
                        f.write("  Nenhuma combinação comparável encontrada.\n\n")
                        continue
                    for label in LABELS:
                        sub = merged[merged["label"] == label]
                        if sub.empty:
                            continue
                        delta_prauc = sub["prauc_robust"] - sub["prauc_prev"]
                        f.write(f"**{label}**: média PR-AUC robust={sub['prauc_robust'].mean():.3f} vs prev={sub['prauc_prev'].mean():.3f} (delta={delta_prauc.mean():+.3f})\n")
                    f.write("\n")
        else:
            f.write("## 3. Resultados\n\nNenhum resultado gerado.\n")

    print(f"  Relatório: {relatorio_path}")

    # ─── 15. Contrato JSON experimental ───────────────────────────────────
    if not df_res.empty:
        best_prauc = df_res["prauc"].max()
        best_cons = df_res[df_res["modelo"].isin(["gradboost_cons", "logreg_cons"])]["prauc"].max()
        if best_prauc > 0.25 and best_cons > 0.25:
            print(
                f"\n  PR-AUC máximo = {best_prauc:.3f}, conservador = {best_cons:.3f} -> contrato viável. Gerando JSON..."
            )
            contrato = {
                "modeling_family": "psa_risk_v1_station_contract_robust",
                "obj_version": "0.2-exp",
                "data_cutoff": str(T_CUT),
                "bacias": {},
                "features": {
                    "cemaden_passado": CEMADEN_VARS,
                    "openmeteo_forecast": OM_VARS,
                    "componentes_risco": COMP_VARS,
                },
                "forecast_horizons": HORIZONTES_FC,
                "risk_components": ["pancada", "prolongada", "saturante", "perigoso_any"],
                "thresholds_calibration": {
                    "pct_pancada": PCT_PANCADA,
                    "pct_prolongada": PCT_PROLONGADA,
                    "pct_saturante": PCT_SATURANTE,
                    "by_bacia": {
                        b: {
                            "pancada": thresholds[b]["pancada"],
                            "prolongada": thresholds[b]["prolongada"],
                            "saturante": sat_thr[b],
                        }
                        for b in thresholds
                    },
                },
                "robustness": {
                    "models": {
                        "gradboost_cons": {"max_depth": 2, "min_samples_leaf": 20},
                        "logreg_cons": {"C": 0.1},
                    },
                    "station_drop_tested": [0.0, 0.25, 0.50],
                },
            }
            for bacia, stations in estacoes_bacia.items():
                contrato["bacias"][bacia] = {
                    "station_ids": stations,
                    "thresholds": {
                        "pancada_mm": thresholds.get(bacia, {}).get("pancada", None),
                        "prolongada_mm": thresholds.get(bacia, {}).get("prolongada", None),
                        "saturante_mm": sat_thr.get(bacia, None),
                    },
                }
            json_path = OUT_DIR / "risk_model_v1_station_contract_robust.json"
            with open(json_path, "w") as f:
                json.dump(contrato, f, indent=2, default=str)
            print(f"  Contrato JSON: {json_path}")
        else:
            print(
                f"\n  PR-AUC máximo = {best_prauc:.3f}, conservador = {best_cons:.3f} -> contrato NÃO gerado."
            )

    # ─── Print final ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("RESUMO EXECUTIVO")
    print("=" * 80)
    if not df_res.empty:
        for periodo in ["test_hist", "holdout_2026"]:
            sub = df_res[df_res["periodo"] == periodo]
            if sub.empty:
                continue
            print(f"\n{periodo.upper()}:")
            print(f"  PR-AUC médio (todas configs): {sub['prauc'].mean():.3f}")
            print(f"  Spearman ρ médio: {sub['spearman_rho'].mean():.3f}")
            print(f"  F1 médio: {sub['f1'].mean():.3f}")
            for modelo in MODELOS:
                sub_m = sub[sub["modelo"] == modelo]
                if sub_m.empty:
                    continue
                melhor = sub_m.loc[sub_m["prauc"].idxmax()]
                print(
                    f"  [{modelo}] Melhor: bacia={melhor['bacia']}, label={melhor['label']}, variante={melhor['variante']}, PR-AUC={melhor['prauc']:.3f}"
                )
    else:
        print("  Nenhum resultado gerado.")

    # Veredito
    print("\n" + "=" * 80)
    print("VEREDICTO")
    print("=" * 80)
    if not df_res.empty:
        sub_cons = df_res[df_res["modelo"].isin(["gradboost_cons", "logreg_cons"])]
        sub_saturante_perigoso = sub_cons[sub_cons["label"].isin(["saturante", "perigoso_any"])]
        if not sub_saturante_perigoso.empty:
            mean_prauc_sp = sub_saturante_perigoso["prauc"].mean()
            min_prauc_sp = sub_saturante_perigoso["prauc"].min()
            print(f"  saturante/perigoso_any conservador — mean PR-AUC={mean_prauc_sp:.3f}, min={min_prauc_sp:.3f}")
            if mean_prauc_sp > 0.45 and min_prauc_sp > 0.30:
                print("  VEREDICTO: prosseguir_para_shadow")
            elif mean_prauc_sp > 0.35:
                print("  VEREDICTO: validar_mais")
            else:
                print("  VEREDICTO: descartar")
        else:
            print("  VEREDICTO: validar_mais (dados insuficientes)")
    else:
        print("  VEREDICTO: descartar (sem resultados)")

    print("\nDone.")


if __name__ == "__main__":
    main()
