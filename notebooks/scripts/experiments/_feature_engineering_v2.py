"""
Feature Engineering V2 — Magnitude e persistência da chuva.

Baseado no Benchmark V8 (leak-corrected).
Adiciona features que capturam magnitude, persistência e interações,
com o objetivo de tornar P(evento) proporcional à intensidade da chuva.
"""

import json
import warnings
from datetime import date, datetime
from functools import reduce
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
from scipy.signal import lfilter
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit

WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H = [1, 3, 6, 24, 48, 72]
LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72
T_CUT = datetime(2023, 7, 2).date()
K_APIS_BASE = [0.70, 0.85, 0.95]
K_APIS_V2 = [0.70, 0.85, 0.95, 0.99]
LIM_INTENSO_MM = 5.0

FEATURES_BASELINE = (
    [f"api_{int(k*100):03d}" for k in K_APIS_BASE]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

FEATURES_V2 = (
    [f"api_{int(k*100):03d}" for k in K_APIS_V2]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
    + [
        "tendencia_chuva",
        "max_dia_rel",
        "pico_vs_media",
        "chuva_persistente",
        "acc_24h_lag1",
        "acc_48h_lag1",
        "razao_7d_30d",
        "n_chovendo_lag2",
        "n_chovendo_lag3",
        "inter_max_acum7d",
        "inter_max_std",
    ]
)


# ─── Feature Engineering ────────────────────────────────────────────────

def build_dataset():
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        estacoes_bacia = json.load(f)

    partes = []
    for bacia in estacoes_bacia:
        df = pl.read_parquet(
            WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet"
        )
        est_cols = [c for c in df.columns if c != "hora"]
        partes.append(
            df.with_columns(
                [
                    pl.max_horizontal(est_cols).alias("chuva_max_mm"),
                    pl.mean_horizontal(est_cols).alias("chuva_mean_mm"),
                    pl.concat_list(est_cols).list.std().alias("chuva_std_mm"),
                    pl.sum_horizontal(
                        [(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]
                    ).alias("n_chovendo"),
                ]
            )
            .select(
                ["hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"]
            )
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
    df_chuva_h = pl.concat(partes).sort(["bacia", "hora"])

    # confirmados por chuva na bacia
    df_chamados_raw = pl.read_parquet(WORKDIR / "dados" / "chamados_por_bacia.parquet")
    _chamados_idx = (
        df_chamados_raw.drop_nulls("dt_abertura")
        .filter(pl.col("bacia").is_not_null())
        .with_row_index("_idx")
        .with_columns(
            [
                (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias(
                    "dt_inicio"
                ),
                pl.col("dt_abertura").alias("dt_fim"),
            ]
        )
        .rename({"bacia": "bacia_cham"})
    )
    _joined = (
        _chamados_idx.join_where(
            df_chuva_h,
            pl.col("hora") >= pl.col("dt_inicio"),
            pl.col("hora") <= pl.col("dt_fim"),
        )
        .filter(pl.col("bacia_cham") == pl.col("bacia"))
        .select(["_idx", "hora", "chuva_max_mm"])
        .sort(["_idx", "hora"])
    )
    _accs = _chamados_idx.select("_idx")
    for h in JANELAS_H:
        _sub = (
            _joined.rolling("hora", period=f"{h}h", group_by="_idx")
            .agg(pl.col("chuva_max_mm").sum().alias("acc"))
            .group_by("_idx")
            .agg(pl.col("acc").max().alias(f"acc_{h}h"))
        )
        _accs = _accs.join(_sub, on="_idx", how="left")
    _cond = reduce(
        lambda a, b: a | b,
        [pl.col(f"acc_{h}h").fill_null(0) >= LIMS[h] for h in JANELAS_H],
    )
    df_chamados_conf = (
        df_chamados_raw.drop_nulls("dt_abertura")
        .filter(pl.col("bacia").is_not_null())
        .with_row_index("_idx")
        .join(_accs, on="_idx", how="left")
        .drop("_idx")
        .with_columns(_cond.alias("confirmado_chuva_bacia"))
        .filter(pl.col("confirmado_chuva_bacia"))
        .select(["dt_abertura", "bacia"])
    )

    # diários
    df_h = df_chuva_h.with_columns(
        [
            pl.col("hora").dt.date().alias("data"),
            (pl.col("hora").dt.hour() // 6).alias("bloco_6h"),
        ]
    )
    df_blocos = (
        df_h.group_by(["data", "bacia", "bloco_6h"])
        .agg(pl.col("chuva_max_mm").sum().alias("acc_6h"))
        .sort(["bacia", "data", "bloco_6h"])
    )
    df_blocos_wide = (
        df_blocos.with_columns(
            pl.concat_str(
                [pl.lit("bloco_"), pl.col("bloco_6h").cast(pl.Utf8)]
            ).alias("col")
        )
        .pivot(
            on="col",
            index=["data", "bacia"],
            values="acc_6h",
            aggregate_function="first",
        )
        .sort(["bacia", "data"])
        .with_columns(
            [pl.col(c).fill_null(0) for c in ["bloco_0", "bloco_1", "bloco_2", "bloco_3"]]
        )
    )
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

    # Média histórica de max_dia por bacia (para max_dia_rel)
    _media_max_dia = df_diario.group_by("bacia").agg(
        pl.col("max_dia").mean().alias("_media_max_dia_hist")
    )

    df_feat = (
        df_blocos_wide.join(df_diario, on=["data", "bacia"])
        .with_columns(
            [
                pl.col("bloco_0").shift(3).over("bacia").alias("acc_6h_lag_1"),
                pl.col("bloco_1").shift(3).over("bacia").alias("acc_6h_lag_2"),
                pl.col("bloco_2").shift(3).over("bacia").alias("acc_6h_lag_3"),
                pl.col("bloco_3").shift(3).over("bacia").alias("acc_6h_lag_4"),
                pl.col("bloco_0").shift(2).over("bacia").alias("acc_6h_lag_5"),
                pl.col("bloco_1").shift(2).over("bacia").alias("acc_6h_lag_6"),
                pl.col("bloco_2").shift(2).over("bacia").alias("acc_6h_lag_7"),
                pl.col("bloco_3").shift(2).over("bacia").alias("acc_6h_lag_8"),
                pl.col("bloco_0").shift(1).over("bacia").alias("acc_6h_lag_9"),
                pl.col("bloco_1").shift(1).over("bacia").alias("acc_6h_lag_10"),
                pl.col("bloco_2").shift(1).over("bacia").alias("acc_6h_lag_11"),
                pl.col("bloco_3").shift(1).over("bacia").alias("acc_6h_lag_12"),
                pl.col("max_dia").shift(1).over("bacia").alias("max_day_lag1"),
                pl.col("max_dia").shift(2).over("bacia").alias("max_day_lag2"),
                pl.col("max_dia").shift(3).over("bacia").alias("max_day_lag3"),
                pl.col("mean_dia").shift(1).over("bacia").alias("mean_day_lag1"),
                pl.col("std_dia").shift(1).over("bacia").alias("std_day_lag1"),
                pl.col("n_chovendo_max")
                .shift(1)
                .over("bacia")
                .alias("n_chovendo_max_lag1"),
                pl.col("n_chovendo_max")
                .shift(2)
                .over("bacia")
                .alias("n_chovendo_lag2"),
                pl.col("n_chovendo_max")
                .shift(3)
                .over("bacia")
                .alias("n_chovendo_lag3"),
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
                (2 * np.pi * pl.col("data").dt.month() / 12).sin().alias("mes_sin"),
                (2 * np.pi * pl.col("data").dt.month() / 12).cos().alias("mes_cos"),
            ]
        )
        .join(_media_max_dia, on="bacia")
        .with_columns(
            [
                (pl.col("max_day_lag1") - pl.col("max_day_lag3")).alias(
                    "tendencia_chuva"
                ),
                (
                    pl.col("max_day_lag1") / pl.col("_media_max_dia_hist")
                ).alias("max_dia_rel"),
                (
                    pl.col("pico_1h_lag1")
                    / pl.max_horizontal([pl.col("mean_day_lag1"), pl.lit(1e-6)])
                ).alias("pico_vs_media"),
                pl.when(pl.col("max_day_lag1") <= 10)
                .then(0)
                .when(pl.col("max_day_lag2") <= 10)
                .then(1)
                .when(pl.col("max_day_lag3") <= 10)
                .then(2)
                .otherwise(3)
                .alias("chuva_persistente"),
                (
                    pl.col("acc_6h_lag_9")
                    + pl.col("acc_6h_lag_10")
                    + pl.col("acc_6h_lag_11")
                    + pl.col("acc_6h_lag_12")
                ).alias("acc_24h_lag1"),
            ]
        )
        .with_columns(
            [
                (
                    pl.col("acc_24h_lag1")
                    + pl.col("acc_6h_lag_5")
                    + pl.col("acc_6h_lag_6")
                    + pl.col("acc_6h_lag_7")
                    + pl.col("acc_6h_lag_8")
                ).alias("acc_48h_lag1"),
                (
                    pl.col("acum_7d")
                    / pl.max_horizontal([pl.col("acum_30d"), pl.lit(1.0)])
                ).alias("razao_7d_30d"),
                (pl.col("max_day_lag1") * pl.col("acum_7d")).alias(
                    "inter_max_acum7d"
                ),
                (pl.col("max_day_lag1") * pl.col("std_day_lag1")).alias(
                    "inter_max_std"
                ),
            ]
        )
    )

    # ── API com leak corrigido (shift(1) antes do lfilter) ──
    _api_parts = []
    for _bacia in df_diario["bacia"].unique().to_list():
        _sub = df_diario.filter(pl.col("bacia") == _bacia).sort("data")
        _vals = _sub["max_dia"].shift(1).fill_null(0).to_numpy()
        cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS_V2:
            cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
        _api_parts.append(pl.DataFrame(cols))
    df_api = pl.concat(_api_parts)

    df_feat = df_feat.join(df_api, on=["data", "bacia"])

    # ── Target ordinal ──
    _chamados_diario = (
        df_chamados_conf.with_columns(
            pl.col("dt_abertura").dt.date().alias("data")
        )
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
        .unpivot(index="data", variable_name="bacia", value_name="flag")
        .filter(pl.col("flag") > 0)
        .select(["data", "bacia", pl.lit(True).alias("pos_externo")])
    )

    _bacias = list(estacoes_bacia.keys())
    _datas = (
        pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True)
        .to_list()
    )
    _cal = pl.DataFrame(
        {
            "data": pl.Series([d for d in _datas for _ in _bacias], dtype=pl.Date),
            "bacia": [b for _ in _datas for b in _bacias],
        }
    )
    _max_dia = df_diario.select(["data", "bacia", "max_dia"])
    _chamados_max = (
        _chamados_diario.join(_max_dia, on=["data", "bacia"], how="left")
        .filter(pl.col("data") < T_CUT)
    )
    P50_BY_BACIA = {}
    for _b in _bacias:
        _s = _chamados_max.filter(pl.col("bacia") == _b)
        P50_BY_BACIA[_b] = (
            float(_s["max_dia"].quantile(0.5)) if _s.height > 0 else 95.0
        )

    df_ml = (
        _cal.join(_chamados_diario, on=["data", "bacia"], how="left")
        .join(_df_ext, on=["data", "bacia"], how="left")
        .join(_max_dia, on=["data", "bacia"], how="left")
        .with_columns(
            [
                pl.col("n_chamados").fill_null(0),
                pl.col("pos_externo").fill_null(False),
            ]
        )
    )
    _p50_expr = pl.col("bacia").replace_strict(P50_BY_BACIA, return_dtype=pl.Float64)
    df_ml = df_ml.with_columns(
        pl.when((pl.col("n_chamados") >= 5) | pl.col("pos_externo"))
        .then(3)
        .when(pl.col("n_chamados").is_between(2, 4))
        .then(2)
        .when(
            (pl.col("n_chamados") == 1)
            | ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > _p50_expr))
        )
        .then(1)
        .otherwise(0)
        .alias("severidade")
    )

    # join com features
    df_ml = df_ml.join(df_feat, on=["data", "bacia"], how="left").filter(
        pl.col("data").dt.month().is_in(MESES_CHUVOSOS)
    ).sort(["bacia", "data"])

    return df_ml, estacoes_bacia, P50_BY_BACIA


# ─── Helpers ─────────────────────────────────────────────────────────────

def _thr_f1(y_true, y_prob):
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return (
        float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5
    )


def _fit_with_sw(clf, X, y, sw):
    if hasattr(clf, "fit"):
        clf.fit(X, y, sample_weight=sw)
    return clf


def mk_gradboost(sw):
    return GradientBoostingClassifier(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=2,
        min_samples_leaf=10,
        subsample=0.8,
        max_features="sqrt",
        random_state=42,
    )


def w_fit_m3(sev):
    return np.where(
        sev == 3, 3.0, np.where(sev == 2, 1.5, np.where(sev == 1, 1.0, 1.0))
    )


# ─── Avaliação com holdout dedicado ───────────────────────────────────────

def avaliar_bacia(bacia, sub, feature_cols):
    t_cut_local = T_CUT
    if bacia == "oratorio":
        ev = sub.filter(pl.col("enchente"))["data"].sort()
        if len(ev) > 0:
            t_cut_local = ev[int(len(ev) * 0.75)]

    sub = sub.sort("data")
    train_all = sub.filter(pl.col("data") < t_cut_local)
    test = sub.filter(pl.col("data") >= t_cut_local)

    if train_all.height < 30 or test.height < 5:
        return None

    n_train = train_all.height
    split_idx = int(n_train * 0.75)
    train = train_all[:split_idx]
    val_holdout = train_all[split_idx:]

    X_train = train[feature_cols].to_pandas()
    X_val = val_holdout[feature_cols].to_pandas()
    X_test = test[feature_cols].to_pandas()
    sev_train = train["severidade"].to_numpy()
    sev_val = val_holdout["severidade"].to_numpy()
    sev_test = test["severidade"].to_numpy()

    row = {"bacia": bacia}
    row["train_n"] = len(sev_train)
    row["val_n"] = len(sev_val)
    row["test_n"] = len(sev_test)
    row["sev_dist_train"] = {
        int(s): int((sev_train == s).sum()) for s in [0, 1, 2, 3]
    }
    row["sev_dist_test"] = {
        int(s): int((sev_test == s).sum()) for s in [0, 1, 2, 3]
    }

    probs_val = {}
    probs_test = {}
    thrs_val = {}

    for k in [1, 2, 3]:
        y_bin_train = (sev_train >= k).astype(int)
        y_bin_val = (sev_val >= k).astype(int)

        if y_bin_train.sum() < 2 or y_bin_val.sum() == 0:
            probs_val[k] = np.zeros(len(sev_val))
            probs_test[k] = np.zeros(len(sev_test))
            thrs_val[k] = 1.5
            continue

        sw_train = (
            w_fit_m3(sev_train).astype(float)
            if k == 3
            else np.ones(len(sev_train), dtype=float)
        )

        # threshold tuning via TSS no train
        tscv = TimeSeriesSplit(n_splits=5)
        oof = np.full(len(y_bin_train), np.nan)
        for tr_i, va_i in tscv.split(X_train):
            if y_bin_train[tr_i].sum() == 0 or y_bin_train[va_i].sum() == 0:
                continue
            sw = np.where(y_bin_train[tr_i] == 1, sw_train[tr_i], 1.0).astype(float)
            clf = mk_gradboost(0.0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                _fit_with_sw(clf, X_train.iloc[tr_i], y_bin_train[tr_i], sw)
            oof[va_i] = clf.predict_proba(X_train.iloc[va_i])[:, 1]
        mask_oof = ~np.isnan(oof)
        if mask_oof.sum() > 0 and y_bin_train[mask_oof].sum() > 0:
            thrs_val[k] = _thr_f1(y_bin_train[mask_oof], oof[mask_oof])
        else:
            thrs_val[k] = 0.5

        # modelo final em todo train
        clf = mk_gradboost(0.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _fit_with_sw(clf, X_train, y_bin_train, sw_train)

        probs_val[k] = clf.predict_proba(X_val)[:, 1]
        probs_test[k] = clf.predict_proba(X_test)[:, 1]

    # alarmes
    alarme_val = np.zeros(len(sev_val), dtype=int)
    for k in [1, 2, 3]:
        alarme_val = np.where(probs_val[k] >= thrs_val[k], k, alarme_val)

    alarme_test = np.zeros(len(sev_test), dtype=int)
    for k in [1, 2, 3]:
        alarme_test = np.where(probs_test[k] >= thrs_val[k], k, alarme_test)

    # métricas val
    for k in [1, 2, 3]:
        y_bin = (sev_val >= k).astype(int)
        pk = probs_val[k]
        tk = thrs_val[k]
        al_k = (alarme_val >= k).astype(int)
        row[f"thr_k{k}"] = float(tk)
        row[f"prauc_k{k}"] = (
            float(average_precision_score(y_bin, pk)) if y_bin.sum() > 0 else 0.0
        )
        row[f"recall_k{k}"] = (
            float(recall_score(y_bin, al_k, zero_division=0))
            if y_bin.sum() > 0
            else 0.0
        )
        row[f"prec_k{k}"] = (
            float(precision_score(y_bin, al_k, zero_division=0))
            if y_bin.sum() > 0
            else 0.0
        )
        row[f"f1_k{k}"] = (
            float(f1_score(y_bin, al_k, zero_division=0))
            if y_bin.sum() > 0
            else 0.0
        )

    # métricas test
    for k in [1, 2, 3]:
        y_bin = (sev_test >= k).astype(int)
        pk = probs_test[k]
        tk = thrs_val[k]
        al_k = (alarme_test >= k).astype(int)
        row[f"prauc_test_k{k}"] = (
            float(average_precision_score(y_bin, pk)) if y_bin.sum() > 0 else 0.0
        )
        row[f"recall_test_k{k}"] = (
            float(recall_score(y_bin, al_k, zero_division=0))
            if y_bin.sum() > 0
            else 0.0
        )
        row[f"prec_test_k{k}"] = (
            float(precision_score(y_bin, al_k, zero_division=0))
            if y_bin.sum() > 0
            else 0.0
        )
        row[f"f1_test_k{k}"] = (
            float(f1_score(y_bin, al_k, zero_division=0))
            if y_bin.sum() > 0
            else 0.0
        )

    # Spearman val (mantido para compatibilidade com v8)
    max_dia_val = val_holdout["max_dia"].to_numpy()
    corr_val, pval_val = spearmanr(max_dia_val, probs_val[1])
    row["spearman_rho_val"] = float(corr_val)
    row["spearman_p_val"] = float(pval_val)

    # Spearman test (novo)
    max_dia_test = test["max_dia"].to_numpy()
    corr_test, pval_test = spearmanr(max_dia_test, probs_test[1])
    row["spearman_rho_test"] = float(corr_test)
    row["spearman_p_test"] = float(pval_test)

    # Guarda probs e max_dia do teste para plot agregado
    row["_max_dia_test"] = max_dia_test
    row["_prob_m1_test"] = probs_test[1]

    return row


# ─── Plot agregado ────────────────────────────────────────────────────────

def plot_prob_por_faixa(df_test_records, out_path):
    """Plota probabilidade média do m1 por faixa de max_dia no test set."""
    faixas = [(0, 5), (5, 15), (15, 30), (30, 50), (50, 80), (80, np.inf)]
    labels = ["0-5", "5-15", "15-30", "30-50", "50-80", "80+"]

    probs_means = {label: [] for label in labels}

    for rec in df_test_records:
        max_dia = rec["_max_dia_test"]
        probs = rec["_prob_m1_test"]
        for (lo, hi), label in zip(faixas, labels):
            mask = (max_dia >= lo) & (max_dia < hi) if hi != np.inf else (max_dia >= lo)
            if mask.sum() > 0:
                probs_means[label].append(probs[mask].mean())

    means = [np.mean(probs_means[label]) if probs_means[label] else 0.0 for label in labels]
    counts = [len(probs_means[label]) for label in labels]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(labels, means, color="steelblue", edgecolor="black")
    ax.set_xlabel("Faixa de chuva (max_dia, mm)")
    ax.set_ylabel("Prob. média P(evento) — m1")
    ax.set_title("Probabilidade média por faixa de chuva (test set, todas as bacias)")
    ax.set_ylim(0, max(means) * 1.2 if max(means) > 0 else 1)

    for bar, m, c in zip(bars, means, counts):
        height = bar.get_height()
        ax.annotate(
            f"{m:.3f}\n(n={c})",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
        )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"\nPlot salvo em {out_path}")


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    print("Building dataset with new features...")
    df_ml, estacoes_bacia, p50 = build_dataset()

    if "enchente" not in df_ml.columns:
        df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    todos_baseline = []
    todos_v2 = []

    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_ml.filter(pl.col("bacia") == bacia)
        sub_base = sub.drop_nulls(FEATURES_BASELINE)
        sub_v2 = sub.drop_nulls(FEATURES_V2)

        r_base = avaliar_bacia(bacia, sub_base, FEATURES_BASELINE)
        r_v2 = avaliar_bacia(bacia, sub_v2, FEATURES_V2)

        if r_base is None or r_v2 is None:
            print(f"  {bacia}: pulado (dados insuficientes)")
            continue

        todos_baseline.append(r_base)
        todos_v2.append(r_v2)

        print(f"\n{'='*80}")
        print(
            f"  {bacia.upper()} (train_n={r_base['train_n']}, val_n={r_base['val_n']}, test_n={r_base['test_n']})"
        )
        print(f"  Severidade train: {r_base['sev_dist_train']}")
        print(f"  Severidade test:  {r_base['sev_dist_test']}")

        print(f"\n  BASELINE — Test set:")
        print(
            f"  {'k':>2}  {'PRAUC':>6}  {'Recall':>7}  {'Prec':>6}  {'F1':>5}  {'Spearman ρ':>10}"
        )
        for k in [1, 2, 3]:
            print(
                f"  {k:>2}  "
                f"{r_base[f'prauc_test_k{k}']:>6.3f}  "
                f"{r_base[f'recall_test_k{k}']:>7.3f}  "
                f"{r_base[f'prec_test_k{k}']:>6.3f}  "
                f"{r_base[f'f1_test_k{k}']:>5.3f}  "
                f"{r_base['spearman_rho_test']:>10.3f}"
            )

        print(f"\n  V2 — Test set:")
        print(
            f"  {'k':>2}  {'PRAUC':>6}  {'Recall':>7}  {'Prec':>6}  {'F1':>5}  {'Spearman ρ':>10}"
        )
        for k in [1, 2, 3]:
            print(
                f"  {k:>2}  "
                f"{r_v2[f'prauc_test_k{k}']:>6.3f}  "
                f"{r_v2[f'recall_test_k{k}']:>7.3f}  "
                f"{r_v2[f'prec_test_k{k}']:>6.3f}  "
                f"{r_v2[f'f1_test_k{k}']:>5.3f}  "
                f"{r_v2['spearman_rho_test']:>10.3f}"
            )

    # ── Resumo agregado ──
    print(f"\n{'='*80}")
    print("RESUMO AGREGADO — Test set")
    print(f"{'='*80}")
    for k in [1, 2, 3]:
        for metric in ["prauc_test", "recall_test", "prec_test", "f1_test"]:
            base_vals = [r[f"{metric}_k{k}"] for r in todos_baseline]
            v2_vals = [r[f"{metric}_k{k}"] for r in todos_v2]
            print(
                f"  {metric:<18} k={k} | baseline={np.mean(base_vals):.3f} | v2={np.mean(v2_vals):.3f} | delta={np.mean(v2_vals)-np.mean(base_vals):+.3f}"
            )
    base_rho = [r["spearman_rho_test"] for r in todos_baseline]
    v2_rho = [r["spearman_rho_test"] for r in todos_v2]
    print(
        f"  {'Spearman ρ (test)':<18}      | baseline={np.mean(base_rho):.3f} | v2={np.mean(v2_rho):.3f} | delta={np.mean(v2_rho)-np.mean(base_rho):+.3f}"
    )

    # ── Plot ──
    plot_prob_por_faixa(todos_v2, OUT_DIR / "feature_engineering_v2_prob_por_faixa.png")

    # ── Salva resultados ──
    df_base = pd.DataFrame(todos_baseline)
    df_v2 = pd.DataFrame(todos_v2)
    for col in ["sev_dist_train", "sev_dist_test"]:
        df_base[col] = df_base[col].apply(lambda d: str({str(k): v for k, v in d.items()}))
        df_v2[col] = df_v2[col].apply(lambda d: str({str(k): v for k, v in d.items()}))
    # remove colunas internas
    for c in ["_max_dia_test", "_prob_m1_test"]:
        if c in df_base.columns:
            df_base.drop(columns=[c], inplace=True)
        if c in df_v2.columns:
            df_v2.drop(columns=[c], inplace=True)

    df_base.to_parquet(OUT_DIR / "feature_engineering_v2_baseline.parquet")
    df_v2.to_parquet(OUT_DIR / "feature_engineering_v2.parquet")
    print(f"\nResultados salvos em {OUT_DIR}")


if __name__ == "__main__":
    main()
