"""
Forecast V7 RICH — extende _run_modelos_forecast_v7.py com features de
forecast adicionais (estratégias 1 e 2 da discussão):

  Estratégia 1 (agregações espaciais): além de `mean` dos pontos, computa
  `max`, `std_mean`, `n_chovendo_max` por hora e agrega na janela.

  Estratégia 2 (intensidade): `pico_1h` (max horário na janela) e
  `horas_intensas` (n horas com max≥5mm) — espelham pico_1h_lag1 e
  horas_intensas_lag1 do passado CEMADEN.

Por horizonte (H12, H24, H48), 6 features de forecast em vez de 1:
  forecast_NNh_mean, _max, _std_mean, _n_chovendo_max, _pico_1h, _horas_intensas

Comparação por bacia × horizonte:
  baseline (V4 sem forecast) | forecast_v1 (só mean, igual rodada anterior)
  | forecast_rich (6 features novas)
"""

import polars as pl
import json
import numpy as np
import warnings
import os
from datetime import datetime, date
from functools import reduce
from scipy.signal import lfilter

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import precision_recall_curve
from sklearn.model_selection import TimeSeriesSplit

# ------------------------------------------------------------------
# constantes (idênticas v7)
# ------------------------------------------------------------------
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H      = [1, 3, 6, 24, 48, 72]
LIMS           = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H     = 72
T_CUT          = datetime(2023, 7, 2).date()
K_APIS         = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0
W_FN = {1: 1.0, 2: 3.0, 3: 10.0}
W_FP = 1.0

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
# 1. CEMADEN horário + features V4 (idêntico v7)
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
        ]).select(["hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
        .with_columns(pl.lit(bacia).alias("bacia"))
    )
df_chuva_h = pl.concat(partes).sort(["bacia", "hora"])

df_chamados_raw = pl.read_parquet("dados/chamados_por_bacia.parquet")
_chamados_idx = (
    df_chamados_raw.drop_nulls("dt_abertura").filter(pl.col("bacia").is_not_null())
    .with_row_index("_idx")
    .with_columns([
        (pl.col("dt_abertura") - pl.duration(hours=LOOKBACK_H)).alias("dt_inicio"),
        pl.col("dt_abertura").alias("dt_fim"),
    ]).rename({"bacia": "bacia_cham"})
)
_joined = (
    _chamados_idx.join_where(df_chuva_h,
        pl.col("hora") >= pl.col("dt_inicio"),
        pl.col("hora") <= pl.col("dt_fim"),
    ).filter(pl.col("bacia_cham") == pl.col("bacia"))
    .select(["_idx", "hora", "chuva_max_mm"]).sort(["_idx", "hora"])
)
_accs = _chamados_idx.select("_idx")
for h in JANELAS_H:
    _sub = (_joined.rolling("hora", period=f"{h}h", group_by="_idx")
            .agg(pl.col("chuva_max_mm").sum().alias("acc"))
            .group_by("_idx").agg(pl.col("acc").max().alias(f"acc_{h}h")))
    _accs = _accs.join(_sub, on="_idx", how="left")
_cond = reduce(lambda a, b: a | b,
    [pl.col(f"acc_{h}h").fill_null(0) >= LIMS[h] for h in JANELAS_H])
df_chamados_conf = (
    df_chamados_raw.drop_nulls("dt_abertura").filter(pl.col("bacia").is_not_null())
    .with_row_index("_idx").join(_accs, on="_idx", how="left").drop("_idx")
    .with_columns(_cond.alias("confirmado_chuva_bacia"))
    .filter(pl.col("confirmado_chuva_bacia"))
    .select(["dt_abertura", "bacia"])
)

df_h = df_chuva_h.with_columns([
    pl.col("hora").dt.date().alias("data"),
    (pl.col("hora").dt.hour() // 6).alias("bloco_6h"),
])
df_blocos = (df_h.group_by(["data", "bacia", "bloco_6h"])
             .agg(pl.col("chuva_max_mm").sum().alias("acc_6h"))
             .sort(["bacia", "data", "bloco_6h"]))
df_blocos_wide = (df_blocos
    .with_columns(pl.concat_str([pl.lit("bloco_"), pl.col("bloco_6h").cast(pl.Utf8)]).alias("col"))
    .pivot(on="col", index=["data", "bacia"], values="acc_6h", aggregate_function="first")
    .sort(["bacia", "data"])
    .with_columns([pl.col(c).fill_null(0) for c in ["bloco_0", "bloco_1", "bloco_2", "bloco_3"]]))
df_diario = (df_h.group_by(["data", "bacia"]).agg([
    pl.col("chuva_max_mm").max().alias("max_dia"),
    pl.col("chuva_max_mm").sum().alias("acum_dia"),
    pl.col("chuva_mean_mm").mean().alias("mean_dia"),
    pl.col("chuva_std_mm").mean().alias("std_dia"),
    pl.col("n_chovendo").max().alias("n_chovendo_max"),
    pl.col("chuva_max_mm").max().alias("pico_1h"),
    (pl.col("chuva_max_mm") >= LIM_INTENSO_MM).sum().alias("horas_intensas"),
]).sort(["bacia", "data"]))
df_feat = (df_blocos_wide.join(df_diario, on=["data", "bacia"]).with_columns([
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
]).select(["data", "bacia"]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]))
_api_parts = []
for _bacia in df_diario["bacia"].unique().to_list():
    _sub = df_diario.filter(pl.col("bacia") == _bacia).sort("data")
    _vals = _sub["max_dia"].fill_null(0).to_numpy()
    cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
    for _k in K_APIS:
        cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
    _api_parts.append(pl.DataFrame(cols))
df_api = pl.concat(_api_parts)
df_feat = df_feat.join(df_api, on=["data", "bacia"])

# ------------------------------------------------------------------
# 2. forecast features RICH (estratégias 1+2)
# ------------------------------------------------------------------
def _fname_pt(lat: float, lon: float) -> str:
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
    df_b = series[0]
    for s in series[1:]:
        df_b = df_b.join(s, on="dt", how="full", coalesce=True)
    pcols = [c for c in df_b.columns if c.startswith("prec_")]
    # agregações por hora ENTRE pontos
    df_b = df_b.with_columns([
        pl.mean_horizontal(pcols).alias("h_mean"),
        pl.max_horizontal(pcols).alias("h_max"),
        pl.concat_list(pcols).list.std().alias("h_std"),
        pl.sum_horizontal([(pl.col(c) > 1.0).cast(pl.Int8) for c in pcols]).alias("h_n_chovendo"),
    ]).select(["dt", "h_mean", "h_max", "h_std", "h_n_chovendo"]).sort("dt")
    df_b = df_b.with_columns([
        pl.col("dt").dt.date().alias("data"),
        pl.lit(bacia).alias("bacia"),
    ])
    # agregação dia inteiro [0–24h]
    daily = df_b.group_by(["data", "bacia"]).agg([
        pl.col("h_mean").sum().alias("d24_mean"),
        pl.col("h_max").sum().alias("d24_max"),
        pl.col("h_std").mean().alias("d24_std_mean"),
        pl.col("h_n_chovendo").max().alias("d24_n_chovendo_max"),
        pl.col("h_max").max().alias("d24_pico_1h"),
        (pl.col("h_max") >= LIM_INTENSO_MM).sum().alias("d24_horas_intensas"),
    ]).sort(["bacia", "data"])
    # agregação meio-dia [0–12h]
    half = df_b.filter(pl.col("dt").dt.hour() < 12).group_by(["data", "bacia"]).agg([
        pl.col("h_mean").sum().alias("d12_mean"),
        pl.col("h_max").sum().alias("d12_max"),
        pl.col("h_std").mean().alias("d12_std_mean"),
        pl.col("h_n_chovendo").max().alias("d12_n_chovendo_max"),
        pl.col("h_max").max().alias("d12_pico_1h"),
        (pl.col("h_max") >= LIM_INTENSO_MM).sum().alias("d12_horas_intensas"),
    ])
    fc = daily.join(half, on=["data", "bacia"], how="left").sort(["bacia", "data"])
    # mapear para nomes finais por horizonte
    fc = fc.with_columns([
        # H12
        pl.col("d12_mean").alias("forecast_12h_mean"),
        pl.col("d12_max").alias("forecast_12h_max"),
        pl.col("d12_std_mean").alias("forecast_12h_std_mean"),
        pl.col("d12_n_chovendo_max").alias("forecast_12h_n_chovendo_max"),
        pl.col("d12_pico_1h").alias("forecast_12h_pico_1h"),
        pl.col("d12_horas_intensas").alias("forecast_12h_horas_intensas"),
        # H24
        pl.col("d24_mean").alias("forecast_24h_mean"),
        pl.col("d24_max").alias("forecast_24h_max"),
        pl.col("d24_std_mean").alias("forecast_24h_std_mean"),
        pl.col("d24_n_chovendo_max").alias("forecast_24h_n_chovendo_max"),
        pl.col("d24_pico_1h").alias("forecast_24h_pico_1h"),
        pl.col("d24_horas_intensas").alias("forecast_24h_horas_intensas"),
        # H48: combina dia t com dia t+1
        (pl.col("d24_mean") + pl.col("d24_mean").shift(-1).over("bacia"))
            .alias("forecast_48h_mean"),
        (pl.col("d24_max") + pl.col("d24_max").shift(-1).over("bacia"))
            .alias("forecast_48h_max"),
        ((pl.col("d24_std_mean") + pl.col("d24_std_mean").shift(-1).over("bacia")) / 2)
            .alias("forecast_48h_std_mean"),
        pl.max_horizontal([
            pl.col("d24_n_chovendo_max"),
            pl.col("d24_n_chovendo_max").shift(-1).over("bacia")
        ]).alias("forecast_48h_n_chovendo_max"),
        pl.max_horizontal([
            pl.col("d24_pico_1h"),
            pl.col("d24_pico_1h").shift(-1).over("bacia")
        ]).alias("forecast_48h_pico_1h"),
        (pl.col("d24_horas_intensas") + pl.col("d24_horas_intensas").shift(-1).over("bacia"))
            .alias("forecast_48h_horas_intensas"),
    ])
    fc = fc.select(["data", "bacia"] + [c for c in fc.columns if c.startswith("forecast_")])
    forecast_parts.append(fc)
df_forecast = pl.concat(forecast_parts)

print(f"Forecast features (rich): {df_forecast.shape}")
print(f"  colunas: {[c for c in df_forecast.columns if c.startswith('forecast_')]}")

# ------------------------------------------------------------------
# 3. severidade ordinal (idêntico v7)
# ------------------------------------------------------------------
_chamados_diario = (df_chamados_conf.with_columns(pl.col("dt_abertura").dt.date().alias("data"))
                    .group_by(["data", "bacia"]).len().rename({"len": "n_chamados"}))
_ext = pl.read_csv("dados/alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
_df_ext = _ext.select([
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
_max_dia = df_diario.select(["data", "bacia", "max_dia"])
_chamados_max = _chamados_diario.join(_max_dia, on=["data", "bacia"], how="left").filter(pl.col("data") < T_CUT)
P50_BY_BACIA = {}
for _b in _bacias:
    _s = _chamados_max.filter(pl.col("bacia") == _b)
    if _s.height > 0:
        P50_BY_BACIA[_b] = float(_s["max_dia"].quantile(0.5))
    else:
        P50_BY_BACIA[_b] = float(_max_dia.filter(pl.col("bacia") == _b)["max_dia"].quantile(0.95))

df_ml = (_cal.join(_chamados_diario, on=["data", "bacia"], how="left")
         .join(_df_ext, on=["data", "bacia"], how="left")
         .join(_max_dia, on=["data", "bacia"], how="left")
         .with_columns([
             pl.col("n_chamados").fill_null(0),
             pl.col("pos_externo").fill_null(False),
         ]))
_p50_expr = pl.col("bacia").replace_strict(P50_BY_BACIA, return_dtype=pl.Float64)
df_ml = df_ml.with_columns(
    pl.when((pl.col("n_chamados") >= 5) | pl.col("pos_externo")).then(3)
    .when(pl.col("n_chamados").is_between(2, 4)).then(2)
    .when((pl.col("n_chamados") == 1) | ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > _p50_expr))).then(1)
    .otherwise(0).alias("severidade")
).with_columns((pl.col("severidade") >= 1).alias("enchente"))

df_ml = df_ml.sort(["bacia", "data"]).with_columns([
    pl.max_horizontal([
        pl.col("severidade"),
        pl.col("severidade").shift(-1).over("bacia").fill_null(0),
    ]).alias("severidade_h48"),
])
df_ml = (df_ml.join(df_feat, on=["data", "bacia"], how="left")
         .join(df_forecast, on=["data", "bacia"], how="left")
         .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
         .sort(["bacia", "data"]))

_ev_oratorio = df_ml.filter((pl.col("bacia") == "oratorio") & pl.col("enchente"))["data"].sort()
T_CUT_ORATORIO = _ev_oratorio[int(len(_ev_oratorio) * 0.75)]

# ------------------------------------------------------------------
# 4. modelo + utils (idêntico v7)
# ------------------------------------------------------------------
def mk_gradboost():
    return GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=2, min_samples_leaf=10,
        subsample=0.8, max_features="sqrt", random_state=42,
    )

def w_fit_m3(severidade):
    return np.where(severidade == 3, 3.0,
           np.where(severidade == 2, 1.5,
           np.where(severidade == 1, 1.0, 1.0)))

CV_SPLITS = 5

def _thr_por_f1(y_true, y_prob):
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5

def thr_cv(X_tr, y_tr_bin, sw_arr, n_splits=CV_SPLITS):
    tscv = TimeSeriesSplit(n_splits=n_splits)
    oof = np.full(len(y_tr_bin), np.nan)
    for tr_idx, va_idx in tscv.split(X_tr):
        if y_tr_bin[tr_idx].sum() == 0 or y_tr_bin[va_idx].sum() == 0:
            continue
        clf = mk_gradboost()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr.iloc[tr_idx], y_tr_bin[tr_idx], sample_weight=sw_arr[tr_idx])
        oof[va_idx] = clf.predict_proba(X_tr.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_tr_bin[mask].sum() == 0:
        return 0.5
    return _thr_por_f1(y_tr_bin[mask], oof[mask])

def avaliar_ordinal(X_tr, X_te, sev_tr, sev_te, datas_te):
    probs_te, thrs = {}, {}
    for k in [1, 2, 3]:
        y_tr_bin = (sev_tr >= k).astype(int)
        y_te_bin = (sev_te >= k).astype(int)
        if y_tr_bin.sum() < 2 or y_te_bin.sum() == 0:
            probs_te[k] = np.zeros(len(y_te_bin))
            thrs[k] = 1.5
            continue
        sw_arr = w_fit_m3(sev_tr).astype(float) if k == 3 else np.ones(len(sev_tr), dtype=float)
        thr = thr_cv(X_tr, y_tr_bin, sw_arr)
        clf = mk_gradboost()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr, y_tr_bin, sample_weight=sw_arr)
        probs_te[k] = clf.predict_proba(X_te)[:, 1]
        thrs[k] = thr

    alarme_nivel = np.zeros(len(sev_te), dtype=int)
    for k in [1, 2, 3]:
        alarme_nivel = np.where(probs_te[k] >= thrs[k], k, alarme_nivel)

    tp_1 = int(((sev_te >= 1) & (alarme_nivel >= 1)).sum())
    fp_1 = int(((sev_te == 0) & (alarme_nivel >= 1)).sum())
    n_pos_1 = int((sev_te >= 1).sum())
    n_neg_1 = int((sev_te == 0).sum())
    tn_1 = n_neg_1 - fp_1
    fn_1 = n_pos_1 - tp_1
    acc_1 = (tp_1 + tn_1) / max(tp_1 + tn_1 + fp_1 + fn_1, 1)
    prec_1 = tp_1 / max(tp_1 + fp_1, 1)
    rec_1  = tp_1 / max(n_pos_1, 1)
    f2_1 = (5 * prec_1 * rec_1) / max(4 * prec_1 + rec_1, 1e-9)

    meses = datas_te.dt.year().to_numpy() * 12 + datas_te.dt.month().to_numpy()
    n_meses = max(len(np.unique(meses)), 1)
    return {
        "thrs": {k: round(v, 3) for k, v in thrs.items()},
        "tp_1": tp_1, "fp_1": fp_1, "n_pos_1": n_pos_1, "n_neg_1": n_neg_1,
        "acc_1": round(acc_1, 3),
        "precisao_1": round(prec_1, 3),
        "recall_1": round(rec_1, 3),
        "f2_1": round(f2_1, 3),
        "alarmes_mes_1": round(int((alarme_nivel >= 1).sum()) / n_meses, 2),
    }

# ------------------------------------------------------------------
# 5. loop principal: 9 runs por bacia (3 horizontes × {baseline, fc_v1, fc_rich})
# ------------------------------------------------------------------
def fc_feats(h, mode):
    """h='12h'|'24h'|'48h', mode='v1'|'rich'."""
    aggs = ["mean"] if mode == "v1" else ["mean", "max", "std_mean", "n_chovendo_max", "pico_1h", "horas_intensas"]
    return [f"forecast_{h}_{a}" for a in aggs]

RUNS = [
    ("H12_baseline",     "severidade",     FEATURES_V4),
    ("H12_forecast_v1",  "severidade",     FEATURES_V4 + ["forecast_12h_mean"]),
    ("H12_forecast_max", "severidade",     FEATURES_V4 + ["forecast_12h_max"]),
    ("H12_forecast_rich","severidade",     FEATURES_V4 + fc_feats("12h", "rich")),
    ("H24_baseline",     "severidade",     FEATURES_V4),
    ("H24_forecast_v1",  "severidade",     FEATURES_V4 + ["forecast_24h_mean"]),
    ("H24_forecast_max", "severidade",     FEATURES_V4 + ["forecast_24h_max"]),
    ("H24_forecast_rich","severidade",     FEATURES_V4 + fc_feats("24h", "rich")),
    ("H48_baseline",     "severidade_h48", FEATURES_V4),
    ("H48_forecast_v1",  "severidade_h48", FEATURES_V4 + ["forecast_48h_mean"]),
    ("H48_forecast_max", "severidade_h48", FEATURES_V4 + ["forecast_48h_max"]),
    ("H48_forecast_rich","severidade_h48", FEATURES_V4 + fc_feats("48h", "rich")),
]

todos = []
for bacia in sorted(df_ml["bacia"].unique().to_list()):
    t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT
    print(f"\n>>> {bacia.upper()}  (t_cut={t_cut})")
    for nome_run, col_sev, feats in RUNS:
        sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(feats + [col_sev])
        train = sub.filter(pl.col("data") < t_cut)
        test  = sub.filter(pl.col("data") >= t_cut)
        X_tr = train[feats].to_pandas()
        X_te = test[feats].to_pandas()
        sev_tr = train[col_sev].to_numpy()
        sev_te = test[col_sev].to_numpy()
        datas_te = test["data"]
        if sev_te.max() == 0:
            print(f"  {nome_run}: pulado")
            continue
        r = avaliar_ordinal(X_tr, X_te, sev_tr, sev_te, datas_te)
        todos.append({"bacia": bacia, "run": nome_run, **r})
        print(f"  {nome_run:<22}  acc={r['acc_1']:.3f}  prec={r['precisao_1']:.3f}  "
              f"rec={r['recall_1']:.3f}  F2={r['f2_1']:.3f}  "
              f"TP={r['tp_1']}/{r['n_pos_1']}  FP={r['fp_1']}  "
              f"alarmes/mês={r['alarmes_mes_1']}")

# ------------------------------------------------------------------
# 6. tabelas comparativas
# ------------------------------------------------------------------
df_res = pl.DataFrame([{
    "bacia": t["bacia"], "run": t["run"],
    "acc_1": t["acc_1"], "precisao_1": t["precisao_1"],
    "recall_1": t["recall_1"], "f2_1": t["f2_1"],
    "tp_1": t["tp_1"], "fp_1": t["fp_1"], "n_pos_1": t["n_pos_1"],
    "alarmes_mes_1": t["alarmes_mes_1"],
} for t in todos])

print(f"\n{'═'*108}")
print("  COMPARAÇÃO 3-VIAS: baseline vs forecast_v1 (mean) vs forecast_rich (6 features)")
print(f"{'═'*108}")
for bacia in sorted({t["bacia"] for t in todos}):
    sub = df_res.filter(pl.col("bacia") == bacia)
    print(f"\n  {bacia.upper()}")
    print(f"  {'Run':<22}  {'Acc':>6}  {'Prec':>6}  {'Recall':>7}  {'F2':>6}  {'TP/Pos':>8}  {'FP':>4}  {'alarmes/mês':>12}")
    print(f"  {'-'*22}  {'-'*6}  {'-'*6}  {'-'*7}  {'-'*6}  {'-'*8}  {'-'*4}  {'-'*12}")
    for r in sub.iter_rows(named=True):
        print(f"  {r['run']:<22}  {r['acc_1']:>6.3f}  {r['precisao_1']:>6.3f}  "
              f"{r['recall_1']:>7.3f}  {r['f2_1']:>6.3f}  "
              f"{r['tp_1']:>3}/{r['n_pos_1']:<4}  {r['fp_1']:>4}  {r['alarmes_mes_1']:>12.2f}")

# comparação 4-vias por horizonte
print(f"\n{'═'*108}")
print("  COMPARAÇÃO F2: baseline vs v1 (mean) vs max (substitui mean) vs rich (6 feats)")
print(f"{'═'*108}")
print(f"  {'bacia':<14} {'horiz':<6}  {'F2 base':>8} {'F2 v1':>8} {'F2 max':>8} {'F2 rich':>8} "
      f"{'Δ max-v1':>10} {'Δ max-base':>12}")
print("  " + "─" * 100)
by = {(r["bacia"], r["run"]): r for r in df_res.iter_rows(named=True)}
for bacia in sorted({t["bacia"] for t in todos}):
    for h in ["H12", "H24", "H48"]:
        b = by.get((bacia, f"{h}_baseline"))
        v1 = by.get((bacia, f"{h}_forecast_v1"))
        mx = by.get((bacia, f"{h}_forecast_max"))
        rc = by.get((bacia, f"{h}_forecast_rich"))
        if b is None or v1 is None or mx is None:
            continue
        rc_f2 = rc['f2_1'] if rc else float('nan')
        print(f"  {bacia:<14} {h:<6}  {b['f2_1']:>8.3f} {v1['f2_1']:>8.3f} {mx['f2_1']:>8.3f} {rc_f2:>8.3f} "
              f"{mx['f2_1']-v1['f2_1']:>+10.3f} {mx['f2_1']-b['f2_1']:>+12.3f}")

df_res.write_parquet("dados/results/resultados_forecast_v7_rich.parquet")
print(f"\nResultados em dados/results/resultados_forecast_v7_rich.parquet")
