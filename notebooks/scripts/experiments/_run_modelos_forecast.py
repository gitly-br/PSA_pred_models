"""
Forecast — adiciona features de precipitação futura (ERA5-Land multipoint como
proxy de previsão perfeita) ao baseline v5b. Três horizontes:

  H12: target = enchente no dia t            | feature extra: forecast_12h
  H24: target = enchente no dia t            | feature extra: forecast_24h
  H48: target = enchente em dia t ou t+1     | feature extra: forecast_48h

Para cada (bacia, horizonte) treina dois modelos:
  - baseline V4 puro (sem forecast)
  - V4 + forecast_H

Comparação direta dentro do mesmo horizonte responde se forecast melhora F2,
recall e precisão. Em produção, ERA5 é substituído por forecast real
(Open-Meteo); aqui mede o teto superior de performance.
"""

import polars as pl
import json
import numpy as np
import warnings
import os
from datetime import datetime, date
from functools import reduce
from scipy.signal import lfilter
from scipy.spatial.distance import cdist

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score, f1_score, fbeta_score, precision_recall_curve,
    precision_score, recall_score,
)
from sklearn.model_selection import TimeSeriesSplit

# ------------------------------------------------------------------
# constantes (idênticas ao v5b)
# ------------------------------------------------------------------
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H      = [1, 3, 6, 24, 48, 72]
LIMS           = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H     = 72
T_CUT          = datetime(2023, 7, 2).date()
K_APIS         = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0
PESO_EXTERNO   = 0.5  # v5b

FEATURES_V4 = (
    [f"api_{int(k*100):03d}" for k in K_APIS]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

# ------------------------------------------------------------------
# 1. CEMADEN horário por bacia (V4)
# ------------------------------------------------------------------
with open("dados/estacoes_bacia.json") as f:
    estacoes_bacia = json.load(f)

partes = []
for bacia in estacoes_bacia:
    df = pl.read_parquet(f"dados/chuva_bacias/chuva_{bacia}.parquet")
    est_cols = [c for c in df.columns if c != "hora"]
    partes.append(
        df.with_columns([
            pl.max_horizontal(est_cols).alias("chuva_max_mm"),
            pl.mean_horizontal(est_cols).alias("chuva_mean_mm"),
            pl.concat_list(est_cols).list.std().alias("chuva_std_mm"),
            pl.sum_horizontal([(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]).alias("n_chovendo"),
        ])
        .select(["hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
        .with_columns(pl.lit(bacia).alias("bacia"))
    )
df_chuva_h = pl.concat(partes).sort(["bacia", "hora"])

# ------------------------------------------------------------------
# 2. chamados confirmados por chuva (igual v5b)
# ------------------------------------------------------------------
df_chamados_raw = pl.read_parquet("dados/chamados_por_bacia.parquet")
_chamados_idx = (
    df_chamados_raw.drop_nulls("dt_abertura").filter(pl.col("bacia").is_not_null())
    .with_row_index("_idx")
    .with_columns([
        (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
        pl.col("dt_abertura").alias("dt_fim"),
    ])
    .rename({"bacia": "bacia_cham"})
)
_joined = (
    _chamados_idx.join_where(df_chuva_h,
        pl.col("hora") >= pl.col("dt_inicio"),
        pl.col("hora") <= pl.col("dt_fim"),
    )
    .filter(pl.col("bacia_cham") == pl.col("bacia"))
    .select(["_idx", "hora", "chuva_max_mm"]).sort(["_idx", "hora"])
)
_accs = _chamados_idx.select("_idx")
for h in JANELAS_H:
    _sub = (
        _joined.rolling("hora", period=f"{h}h", group_by="_idx")
        .agg(pl.col("chuva_max_mm").sum().alias("acc"))
        .group_by("_idx").agg(pl.col("acc").max().alias(f"acc_{h}h"))
    )
    _accs = _accs.join(_sub, on="_idx", how="left")
_cond = reduce(lambda a, b: a | b,
    [pl.col(f"acc_{h}h").fill_null(0) >= LIMS[h] for h in JANELAS_H])
df_chamados_conf = (
    df_chamados_raw.drop_nulls("dt_abertura").filter(pl.col("bacia").is_not_null())
    .with_row_index("_idx")
    .join(_accs, on="_idx", how="left").drop("_idx")
    .with_columns(_cond.alias("confirmado_chuva_bacia"))
    .filter(pl.col("confirmado_chuva_bacia"))
    .select(["dt_abertura", "bacia"])
)

# ------------------------------------------------------------------
# 3. features V4 (idênticas v5b)
# ------------------------------------------------------------------
df_h = (
    df_chuva_h.with_columns([
        pl.col("hora").dt.date().alias("data"),
        (pl.col("hora").dt.hour() // 6).alias("bloco_6h"),
    ])
)
df_blocos = (
    df_h.group_by(["data", "bacia", "bloco_6h"])
    .agg(pl.col("chuva_max_mm").sum().alias("acc_6h"))
    .sort(["bacia", "data", "bloco_6h"])
)
df_blocos_wide = (
    df_blocos
    .with_columns(pl.concat_str([pl.lit("bloco_"), pl.col("bloco_6h").cast(pl.Utf8)]).alias("col"))
    .pivot(on="col", index=["data", "bacia"], values="acc_6h", aggregate_function="first")
    .sort(["bacia", "data"])
    .with_columns([pl.col(c).fill_null(0) for c in ["bloco_0", "bloco_1", "bloco_2", "bloco_3"]])
)
df_diario = (
    df_h.group_by(["data", "bacia"])
    .agg([
        pl.col("chuva_max_mm").max().alias("max_dia"),
        pl.col("chuva_max_mm").sum().alias("acum_dia"),
        pl.col("chuva_mean_mm").mean().alias("mean_dia"),
        pl.col("chuva_std_mm").mean().alias("std_dia"),
        pl.col("n_chovendo").max().alias("n_chovendo_max"),
        pl.col("chuva_max_mm").max().alias("pico_1h"),
        (pl.col("chuva_max_mm") >= LIM_INTENSO_MM).sum().alias("horas_intensas"),
    ])
    .sort(["bacia", "data"])
)
df_feat = (
    df_blocos_wide.join(df_diario, on=["data", "bacia"])
    .with_columns([
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
        pl.col("n_chovendo_max").shift(1).over("bacia").alias("n_chovendo_max_lag1"),
        pl.col("pico_1h").shift(1).over("bacia").alias("pico_1h_lag1"),
        pl.col("horas_intensas").shift(1).over("bacia").alias("horas_intensas_lag1"),
        pl.col("acum_dia").rolling_sum(window_size=7, min_samples=1).shift(1).over("bacia").alias("acum_7d"),
        pl.col("acum_dia").rolling_sum(window_size=30, min_samples=1).shift(1).over("bacia").alias("acum_30d"),
        (2 * np.pi * pl.col("data").dt.month() / 12).sin().alias("mes_sin"),
        (2 * np.pi * pl.col("data").dt.month() / 12).cos().alias("mes_cos"),
    ])
    .select(
        ["data", "bacia"]
        + [f"acc_6h_lag_{i}" for i in range(1, 13)]
        + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
        + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
        + ["pico_1h_lag1", "horas_intensas_lag1"]
        + ["acum_7d", "acum_30d"]
        + ["mes_sin", "mes_cos"]
    )
)
_api_parts = []
for _bacia in df_diario["bacia"].unique().to_list():
    _sub  = df_diario.filter(pl.col("bacia") == _bacia).sort("data")
    _vals = _sub["max_dia"].fill_null(0).to_numpy()
    cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
    for _k in K_APIS:
        cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
    _api_parts.append(pl.DataFrame(cols))
df_api = pl.concat(_api_parts)
df_feat = df_feat.join(df_api, on=["data", "bacia"])

# ------------------------------------------------------------------
# 4. features de FORECAST (ERA5-Land multipoint, média dos pontos por bacia)
# ------------------------------------------------------------------
def _fname_pt(lat: float, lon: float) -> str:
    """Reproduz nome de arquivo: pt_m{abs_lat}_m{abs_lon}.parquet (lat/lon negativos)."""
    return f"pt_m{abs(lat):.6f}_m{abs(lon):.6f}.parquet"

with open("dados/weather/openmeteo_multipoint/index.json") as f:
    pontos_por_bacia = json.load(f)

forecast_parts = []
for bacia, pontos in pontos_por_bacia.items():
    series = []
    for p in pontos:
        path = os.path.join("dados/weather/openmeteo_multipoint", _fname_pt(p["lat"], p["lon"]))
        s = pl.read_parquet(path).select(["dt", "precipitation_mm"])
        series.append(s.rename({"precipitation_mm": f"prec_{p['lat']:.4f}_{p['lon']:.4f}"}))
    # join todos os pontos por dt, depois média
    df_b = series[0]
    for s in series[1:]:
        df_b = df_b.join(s, on="dt", how="full", coalesce=True)
    pcols = [c for c in df_b.columns if c.startswith("prec_")]
    df_b = df_b.with_columns(
        pl.mean_horizontal(pcols).alias("prec_mean")
    ).select(["dt", "prec_mean"]).sort("dt")
    df_b = df_b.with_columns([
        pl.col("dt").dt.date().alias("data"),
        pl.lit(bacia).alias("bacia"),
    ])
    # acumulado diário [0h-24h]
    fc_24 = df_b.group_by(["data", "bacia"]).agg(
        pl.col("prec_mean").sum().alias("forecast_24h_dia")
    )
    # acumulado [0h-12h]
    fc_12 = (
        df_b.filter(pl.col("dt").dt.hour() < 12)
        .group_by(["data", "bacia"])
        .agg(pl.col("prec_mean").sum().alias("forecast_12h"))
    )
    fc = fc_24.join(fc_12, on=["data", "bacia"], how="left").sort(["bacia", "data"])
    # forecast_24h = mesmo dia; forecast_48h = soma do dia t + dia t+1
    fc = fc.with_columns([
        pl.col("forecast_24h_dia").alias("forecast_24h"),
        (pl.col("forecast_24h_dia") + pl.col("forecast_24h_dia").shift(-1).over("bacia"))
            .alias("forecast_48h"),
    ]).select(["data", "bacia", "forecast_12h", "forecast_24h", "forecast_48h"])
    forecast_parts.append(fc)
df_forecast = pl.concat(forecast_parts)

print(f"Forecast features construídas: {df_forecast.shape}")
print(f"Range datas: {df_forecast['data'].min()} → {df_forecast['data'].max()}")
print(f"Nulls: forecast_12h={df_forecast['forecast_12h'].null_count()}  "
      f"24h={df_forecast['forecast_24h'].null_count()}  "
      f"48h={df_forecast['forecast_48h'].null_count()}")

# ------------------------------------------------------------------
# 5. targets enriquecidos (chamado | externo) — base por dia
# ------------------------------------------------------------------
_df_target_cham = (
    df_chamados_conf
    .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
    .group_by(["data", "bacia"]).len()
    .with_columns(pl.lit(True).alias("pos_chamado"))
    .select(["data", "bacia", "pos_chamado"])
)
_ext = pl.read_csv("dados/alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
_df_target_ext = _ext.select([
    pl.col("dt").alias("data"),
    pl.col("bacia_tamanduatei").alias("tamanduatei"),
    pl.col("bacia_guarara").alias("guarara"),
    pl.col("bacia_oratorio").alias("oratorio"),
    pl.col("bacia_meninos").alias("meninos"),
]).unpivot(index="data", variable_name="bacia", value_name="flag").filter(pl.col("flag") > 0).select([
    "data", "bacia", pl.lit(True).alias("pos_externo"),
])

_bacias = list(estacoes_bacia.keys())
_datas  = pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True).to_list()
_cal    = pl.DataFrame({
    "data":  pl.Series([d for d in _datas for _ in _bacias], dtype=pl.Date),
    "bacia": [b for _ in _datas for b in _bacias],
})

df_ml = (
    _cal
    .join(_df_target_cham, on=["data", "bacia"], how="left")
    .join(_df_target_ext, on=["data", "bacia"], how="left")
    .with_columns([
        pl.col("pos_chamado").fill_null(False),
        pl.col("pos_externo").fill_null(False),
    ])
    .with_columns((pl.col("pos_chamado") | pl.col("pos_externo")).alias("enchente"))
    .sort(["bacia", "data"])
)

# targets por horizonte
df_ml = df_ml.with_columns([
    pl.col("enchente").alias("target_h12"),
    pl.col("enchente").alias("target_h24"),
    (pl.col("enchente") | pl.col("enchente").shift(-1).over("bacia").fill_null(False))
        .alias("target_h48"),
    # peso amostra: 1.0 chamado, 0.5 só externo (igual v5b)
    pl.when(pl.col("pos_chamado")).then(1.0)
      .when(pl.col("pos_externo")).then(PESO_EXTERNO)
      .otherwise(1.0).alias("weight_h12"),
])
# para H48, peso baseado em chamado-OR-externo no dia t ou t+1
df_ml = df_ml.with_columns([
    # se há chamado em t ou t+1, peso = 1.0
    (pl.col("pos_chamado") | pl.col("pos_chamado").shift(-1).over("bacia").fill_null(False))
        .alias("_cham_h48"),
])
df_ml = df_ml.with_columns([
    pl.when(pl.col("_cham_h48")).then(1.0)
      .when(pl.col("target_h48")).then(PESO_EXTERNO)
      .otherwise(1.0).alias("weight_h48"),
])
df_ml = df_ml.with_columns([
    pl.col("weight_h12").alias("weight_h24"),  # mesmo target
])

df_ml = (
    df_ml
    .join(df_feat, on=["data", "bacia"], how="left")
    .join(df_forecast, on=["data", "bacia"], how="left")
    .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
    .sort(["bacia", "data"])
)

# ------------------------------------------------------------------
# 6. dias suspeitos (negativos similares a positivos), igual v5b
# ------------------------------------------------------------------
_FEATS_SIM = ["max_day_lag1", "acum_7d", "mean_day_lag1", "n_chovendo_max_lag1",
              "horas_intensas_lag1", "api_085"]
_susp_flags = []
for _b in _bacias:
    _sub = df_ml.filter(pl.col("bacia") == _b).drop_nulls(_FEATS_SIM)
    _y = _sub["enchente"].to_numpy()
    _X = _sub.select(_FEATS_SIM).to_numpy()
    _sd = _X.std(axis=0) + 1e-9
    _Xn = _X / _sd
    _pos = np.where(_y)[0]
    _neg = np.where(~_y)[0]
    if len(_pos) < 2 or len(_neg) == 0:
        _flag = np.zeros(_sub.height, dtype=bool)
    else:
        _dists = cdist(_Xn[_neg], _Xn[_pos], metric="euclidean").min(axis=1)
        _dpos = cdist(_Xn[_pos], _Xn[_pos], metric="euclidean")
        np.fill_diagonal(_dpos, np.inf)
        _thr = float(np.percentile(_dpos.min(axis=1), 25))
        _p75_max = float(np.percentile(_X[_pos, 0], 75))
        _datas_neg = _sub.filter(~pl.Series(_y))["data"].to_list()
        _wknd = np.array([d.weekday() >= 5 for d in _datas_neg])
        _cand_neg = (_dists <= _thr) & (_X[_neg, 0] >= _p75_max) & _wknd
        _flag = np.zeros(_sub.height, dtype=bool)
        _flag[_neg[_cand_neg]] = True
    _susp_flags.append(_sub.select(["data", "bacia"]).with_columns(pl.Series("suspeito", _flag)))
df_susp = pl.concat(_susp_flags)
df_ml = df_ml.join(df_susp, on=["data", "bacia"], how="left").with_columns(
    pl.col("suspeito").fill_null(False)
)

print("\nPositivos por bacia:")
for col in ["target_h12", "target_h24", "target_h48"]:
    print(f"  {col}:")
    print(df_ml.filter(pl.col(col)).group_by("bacia").len().sort("bacia").to_pandas().to_string(index=False))

# split temporal especial pra oratorio (75% dos eventos)
_ev_oratorio = df_ml.filter((pl.col("bacia") == "oratorio") & pl.col("enchente"))["data"].sort()
T_CUT_ORATORIO = _ev_oratorio[int(len(_ev_oratorio) * 0.75)]

# ------------------------------------------------------------------
# 7. modelo + utils (idênticos v5b, só GradBoost)
# ------------------------------------------------------------------
def mk_gradboost():
    return GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=2, min_samples_leaf=10,
        subsample=0.8, max_features="sqrt", random_state=42,
    )

N_BOOT, CV_SPLITS = 1000, 5
RNG_BOOT = np.random.default_rng(42)

def _metricas(y_true, y_prob, thr):
    y_pred = (y_prob >= thr).astype(int)
    return {
        "pr_auc":   float(average_precision_score(y_true, y_prob)),
        "f2":       float(fbeta_score(y_true, y_pred, beta=2, zero_division=0)),
        "recall":   float(recall_score(y_true, y_pred, zero_division=0)),
        "precisao": float(precision_score(y_true, y_pred, zero_division=0)),
    }

def _thr_por_f1(y_true, y_prob):
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5

def _thr_cv_treino(X_tr, y_tr, w_tr, n_splits=CV_SPLITS):
    tscv = TimeSeriesSplit(n_splits=n_splits)
    oof = np.full(len(y_tr), np.nan)
    for tr_idx, va_idx in tscv.split(X_tr):
        if y_tr[tr_idx].sum() == 0 or y_tr[va_idx].sum() == 0:
            continue
        clf = mk_gradboost()
        sw = np.where(y_tr[tr_idx] == 1, w_tr[tr_idx], 1.0).astype(float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr.iloc[tr_idx], y_tr[tr_idx], sample_weight=sw)
        oof[va_idx] = clf.predict_proba(X_tr.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_tr[mask].sum() == 0:
        return 0.5
    return _thr_por_f1(y_tr[mask], oof[mask])

def _bootstrap_ic(y_true, y_prob, thr, n=N_BOOT):
    pos_idx = np.where(y_true == 1)[0]
    neg_idx = np.where(y_true == 0)[0]
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        return {}
    keys = ["pr_auc", "f2", "recall", "precisao"]
    samples = {k: np.empty(n) for k in keys}
    for i in range(n):
        bp = RNG_BOOT.choice(pos_idx, size=len(pos_idx), replace=True)
        bn = RNG_BOOT.choice(neg_idx, size=len(neg_idx), replace=True)
        idx = np.concatenate([bp, bn])
        m = _metricas(y_true[idx], y_prob[idx], thr)
        for k in keys:
            samples[k][i] = m[k]
    return {k: (float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5)))
            for k, s in samples.items()}

def fit_avaliar(X_tr, y_tr, X_te, y_te, datas_te, w_tr):
    thr = _thr_cv_treino(X_tr, y_tr, w_tr)
    clf = mk_gradboost()
    sw = np.where(y_tr == 1, w_tr, 1.0).astype(float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf.fit(X_tr, y_tr, sample_weight=sw)
    y_prob_te = clf.predict_proba(X_te)[:, 1]
    te = _metricas(y_te, y_prob_te, thr)
    ic = _bootstrap_ic(y_te, y_prob_te, thr)
    y_pred_te = (y_prob_te >= thr).astype(int)
    n_alarmes = int(y_pred_te.sum())
    meses = (datas_te.dt.year().to_numpy() * 12 + datas_te.dt.month().to_numpy())
    n_meses = max(len(np.unique(meses)), 1)
    return {
        "thr":          round(thr, 3),
        "alarmes_mes":  round(n_alarmes / n_meses, 2),
        "eventos_capt": f"{int(((y_te == 1) & (y_pred_te == 1)).sum())}/{int(y_te.sum())}",
        "f2":           round(te["f2"], 3),
        "f2_ic95":      f"[{ic.get('f2', (0,0))[0]:.2f},{ic.get('f2', (0,0))[1]:.2f}]",
        "recall":       round(te["recall"], 3),
        "recall_ic95":  f"[{ic.get('recall', (0,0))[0]:.2f},{ic.get('recall', (0,0))[1]:.2f}]",
        "precisao":     round(te["precisao"], 3),
        "precisao_ic95": f"[{ic.get('precisao', (0,0))[0]:.2f},{ic.get('precisao', (0,0))[1]:.2f}]",
        "pr_auc":       round(te["pr_auc"], 3),
        "test_pos":     int(y_te.sum()),
        "train_pos":    int(y_tr.sum()),
    }

# ------------------------------------------------------------------
# 8. loop: 4 bacias × 6 runs (3 horizontes × {baseline, +forecast})
# ------------------------------------------------------------------
RUNS = [
    ("H12_baseline", "target_h12", "weight_h12", FEATURES_V4),
    ("H12_forecast", "target_h12", "weight_h12", FEATURES_V4 + ["forecast_12h"]),
    ("H24_baseline", "target_h24", "weight_h24", FEATURES_V4),
    ("H24_forecast", "target_h24", "weight_h24", FEATURES_V4 + ["forecast_24h"]),
    ("H48_baseline", "target_h48", "weight_h48", FEATURES_V4),
    ("H48_forecast", "target_h48", "weight_h48", FEATURES_V4 + ["forecast_48h"]),
]

rows = []
for bacia in sorted(df_ml["bacia"].unique().to_list()):
    t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT
    print(f"\n>>> {bacia.upper()}  (t_cut={t_cut})")
    for nome_run, col_target, col_weight, feats in RUNS:
        feats_drop = feats + [col_target, col_weight]
        sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(feats_drop)
        train = sub.filter((pl.col("data") < t_cut) & ~pl.col("suspeito"))
        test  = sub.filter(pl.col("data") >= t_cut)
        X_tr = train[feats].to_pandas()
        X_te = test[feats].to_pandas()
        y_tr = train[col_target].cast(pl.Int8).to_numpy()
        y_te = test[col_target].cast(pl.Int8).to_numpy()
        w_tr = train[col_weight].to_numpy().astype(float)
        datas_te = test["data"]
        if y_te.sum() == 0 or y_tr.sum() < 5:
            print(f"  {nome_run}: pulado (sem positivos suficientes)")
            continue
        res = fit_avaliar(X_tr, y_tr, X_te, y_te, datas_te, w_tr)
        rows.append({"bacia": bacia, "run": nome_run, **res})
        print(f"  {nome_run}: F2={res['f2']:.3f}  recall={res['recall']:.3f}  "
              f"precisao={res['precisao']:.3f}  alarmes/mês={res['alarmes_mes']}  "
              f"capt={res['eventos_capt']}")

df_res = pl.DataFrame(rows)

# ------------------------------------------------------------------
# 9. tabela detalhada por bacia
# ------------------------------------------------------------------
for bacia in sorted(df_res["bacia"].unique().to_list()):
    sub = df_res.filter(pl.col("bacia") == bacia)
    print(f"\n{'═'*108}")
    print(f"  {bacia.upper()}  (test_pos por horizonte = ver coluna)")
    print(f"{'═'*108}")
    cols = ["run", "thr", "alarmes_mes", "eventos_capt",
            "f2", "f2_ic95", "recall", "recall_ic95", "precisao", "precisao_ic95",
            "pr_auc", "test_pos", "train_pos"]
    print(sub.select(cols).to_pandas().to_string(index=False))

# ------------------------------------------------------------------
# 10. comparação direta: forecast vs baseline (delta por horizonte)
# ------------------------------------------------------------------
print(f"\n{'═'*108}")
print("  COMPARAÇÃO DIRETA: forecast vs baseline (Δ = forecast − baseline)")
print(f"{'═'*108}")
print(f"  {'bacia':<14} {'horizonte':<10} {'F2_base':>8} {'F2_fc':>8} {'ΔF2':>7}  "
      f"{'rec_base':>9} {'rec_fc':>8} {'Δrec':>7}  "
      f"{'prec_base':>10} {'prec_fc':>9} {'Δprec':>7}")
print("  " + "─" * 106)
for bacia in sorted(df_res["bacia"].unique().to_list()):
    for h in ["H12", "H24", "H48"]:
        b = df_res.filter((pl.col("bacia") == bacia) & (pl.col("run") == f"{h}_baseline"))
        f = df_res.filter((pl.col("bacia") == bacia) & (pl.col("run") == f"{h}_forecast"))
        if b.height == 0 or f.height == 0:
            continue
        f2_b, f2_f = b["f2"][0], f["f2"][0]
        rec_b, rec_f = b["recall"][0], f["recall"][0]
        prec_b, prec_f = b["precisao"][0], f["precisao"][0]
        print(f"  {bacia:<14} {h:<10} {f2_b:>8.3f} {f2_f:>8.3f} {f2_f-f2_b:>+7.3f}  "
              f"{rec_b:>9.3f} {rec_f:>8.3f} {rec_f-rec_b:>+7.3f}  "
              f"{prec_b:>10.3f} {prec_f:>9.3f} {prec_f-prec_b:>+7.3f}")

# salvar artefato
df_res.write_parquet("dados/results/resultados_forecast.parquet")
print(f"\nResultados salvos em dados/results/resultados_forecast.parquet")
