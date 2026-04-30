"""
Comparativo CEMADEN vs ERA5-multipoint usando pipeline V7 completo.

Experimentos:
  CEM→CEM      : treino CEMADEN, test CEMADEN  (baseline V7)
  ERA5mp→ERA5mp: treino ERA5-multipoint, test ERA5-multipoint
  CEM→ERA5mp   : treino CEMADEN, test ERA5-multipoint (cross-source)

Features: FEATURES_V4 completas (incluindo std_day_lag1, n_chovendo_max_lag1).
Para ERA5-multipoint, os features espaciais são calculados a partir dos
múltiplos pontos de grade ERA5-Land (~11 km) por bacia.

Modelo: GradBoost ordinal V7 (m1: sev≥1, m2: sev≥2, m3: sev≥3).
"""

import json
import warnings
from datetime import date, datetime
from functools import reduce
from pathlib import Path

import numpy as np
import polars as pl
import pandas as pd
from scipy.signal import lfilter
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import precision_recall_curve, f1_score, fbeta_score, average_precision_score
from sklearn.model_selection import TimeSeriesSplit

# ── Constantes (idênticas ao V7) ─────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H      = [1, 3, 6, 24, 48, 72]
LIMS           = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H     = 72
T_CUT          = date(2023, 7, 2)
K_APIS         = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0
CV_SPLITS      = 5
N_BOOT         = 1000
W_FN           = {1: 1.0, 2: 3.0, 3: 10.0}
W_FP           = 1.0

FEATURES_V4 = (
    [f"api_{int(k*100):03d}" for k in K_APIS]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

with open("dados/estacoes_bacia.json") as f:
    estacoes_bacia = json.load(f)
BACIAS = sorted(estacoes_bacia.keys())

# ── Helpers do V7 ─────────────────────────────────────────────────────────────

def w_fit_m3(severidade):
    return np.where(severidade == 3, 3.0,
           np.where(severidade == 2, 1.5,
           np.where(severidade == 1, 1.0, 1.0)))

def _thr_por_f1(y_true, y_prob):
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5

def thr_por_f1_cv(mk, X_tr, y_tr_bin, sw_arr, n_splits=CV_SPLITS):
    tscv = TimeSeriesSplit(n_splits=n_splits)
    oof  = np.full(len(y_tr_bin), np.nan)
    for tr_idx, va_idx in tscv.split(X_tr):
        if y_tr_bin[tr_idx].sum() == 0 or y_tr_bin[va_idx].sum() == 0:
            continue
        clf = mk()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr.iloc[tr_idx], y_tr_bin[tr_idx], sample_weight=sw_arr[tr_idx])
        oof[va_idx] = clf.predict_proba(X_tr.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_tr_bin[mask].sum() == 0:
        return 0.5
    return _thr_por_f1(y_tr_bin[mask], oof[mask])

def avaliar_ordinal(mk, X_tr, X_te, sev_tr, sev_te, datas_te):
    probs_te = {}
    thrs = {}
    for k in [1, 2, 3]:
        y_tr_bin = (sev_tr >= k).astype(int)
        y_te_bin = (sev_te >= k).astype(int)
        if y_tr_bin.sum() < 2 or y_te_bin.sum() == 0:
            probs_te[k] = np.zeros(len(y_te_bin))
            thrs[k] = 1.5
            continue
        sw_arr = w_fit_m3(sev_tr).astype(float) if k == 3 else np.ones(len(sev_tr), dtype=float)
        thr = thr_por_f1_cv(mk, X_tr, y_tr_bin, sw_arr)
        clf = mk()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr, y_tr_bin, sample_weight=sw_arr)
        probs_te[k] = clf.predict_proba(X_te)[:, 1]
        thrs[k] = thr

    alarme_nivel = np.zeros(len(sev_te), dtype=int)
    for k in [1, 2, 3]:
        alarme_nivel = np.where(probs_te[k] >= thrs[k], k, alarme_nivel)

    tabela = {}
    for sev in [0, 1, 2, 3]:
        mask = sev_te == sev
        n = int(mask.sum())
        tabela[sev] = {
            "n":   n,
            ">=1": int((mask & (alarme_nivel >= 1)).sum()),
            ">=2": int((mask & (alarme_nivel >= 2)).sum()),
            ">=3": int((mask & (alarme_nivel >= 3)).sum()),
        }

    custo = sum(W_FN[s] * int(((sev_te == s) & (alarme_nivel < s)).sum()) for s in [1, 2, 3])
    custo += W_FP * int(((sev_te == 0) & (alarme_nivel >= 1)).sum())

    meses = datas_te.dt.year().to_numpy() * 12 + datas_te.dt.month().to_numpy()
    n_meses = max(len(np.unique(meses)), 1)
    alarmes_mes = {f">={k}": round(int((alarme_nivel >= k).sum()) / n_meses, 2) for k in [1, 2, 3]}

    # PR-AUC para m1 (sev≥1 vs sev=0) — probabilidade bruta vs label binário
    y_bin_te = (sev_te >= 1).astype(int)
    pr_auc_m1 = float(average_precision_score(y_bin_te, probs_te[1])) if y_bin_te.sum() > 0 else 0.0

    return {"thrs": thrs, "tabela": tabela, "custo": custo, "alarmes_mes": alarmes_mes,
            "pr_auc_m1": pr_auc_m1, "probs_m1": probs_te[1], "sev_te": sev_te}

# ── Feature engineering (igual ao V7) ────────────────────────────────────────
# Recebe df_h com [hora, bacia, chuva_max_mm, chuva_mean_mm, chuva_std_mm, n_chovendo]

def build_diario(df_h: pl.DataFrame) -> pl.DataFrame:
    """Agrega precipitação horária em diária por bacia. Usado para o target."""
    return (
        df_h.with_columns(pl.col("hora").dt.date().alias("data"))
        .group_by(["data", "bacia"])
        .agg(pl.col("chuva_max_mm").max().alias("max_dia"))
        .sort(["bacia", "data"])
    )

def build_features(df_h: pl.DataFrame) -> pl.DataFrame:
    df_h = df_h.with_columns([
        pl.col("hora").dt.date().alias("data"),
        (pl.col("hora").dt.hour() // 6).alias("bloco_6h"),
    ])
    df_blocos_wide = (
        df_h.group_by(["data", "bacia", "bloco_6h"])
        .agg(pl.col("chuva_max_mm").sum().alias("acc_6h"))
        .sort(["bacia", "data", "bloco_6h"])
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
            pl.col("acum_dia").rolling_sum(window_size=7,  min_samples=1).shift(1).over("bacia").alias("acum_7d"),
            pl.col("acum_dia").rolling_sum(window_size=30, min_samples=1).shift(1).over("bacia").alias("acum_30d"),
            (2 * np.pi * pl.col("data").dt.month() / 12).sin().alias("mes_sin"),
            (2 * np.pi * pl.col("data").dt.month() / 12).cos().alias("mes_cos"),
        ])
        .select(["data", "bacia"]
                + [f"acc_6h_lag_{i}" for i in range(1, 13)]
                + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
                + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
                + ["pico_1h_lag1", "horas_intensas_lag1"]
                + ["acum_7d", "acum_30d"]
                + ["mes_sin", "mes_cos"])
    )
    _api_parts = []
    for _bacia in df_diario["bacia"].unique().to_list():
        _sub  = df_diario.filter(pl.col("bacia") == _bacia).sort("data")
        _vals = _sub["max_dia"].fill_null(0).to_numpy()
        cols  = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS:
            cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
        _api_parts.append(pl.DataFrame(cols))
    return df_feat.join(pl.concat(_api_parts), on=["data", "bacia"])


def build_df_ml(df_feat: pl.DataFrame, df_diario_src: pl.DataFrame,
                df_chamados_conf: pl.DataFrame, P50_BY_BACIA: dict) -> pl.DataFrame:
    _chamados_diario = (
        df_chamados_conf
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by(["data", "bacia"]).len().rename({"len": "n_chamados"})
    )
    _ext = pl.read_csv("dados/alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
    _df_ext = (
        _ext.select([
            pl.col("dt").alias("data"),
            pl.col("bacia_tamanduatei").alias("tamanduatei"),
            pl.col("bacia_guarara").alias("guarara"),
            pl.col("bacia_oratorio").alias("oratorio"),
            pl.col("bacia_meninos").alias("meninos"),
        ])
        .unpivot(index="data", variable_name="bacia", value_name="flag")
        .filter(pl.col("flag") > 0)
        .select(["data", "bacia", pl.lit(True).alias("pos_externo")])
    )
    _datas = pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True).to_list()
    _cal   = pl.DataFrame({
        "data":  pl.Series([d for d in _datas for _ in BACIAS], dtype=pl.Date),
        "bacia": [b for _ in _datas for b in BACIAS],
    })
    _max_dia = df_diario_src.select(["data", "bacia", "max_dia"])

    _p50_expr = pl.col("bacia").replace_strict(P50_BY_BACIA, return_dtype=pl.Float64)
    return (
        _cal
        .join(_chamados_diario, on=["data", "bacia"], how="left")
        .join(_df_ext,          on=["data", "bacia"], how="left")
        .join(_max_dia,         on=["data", "bacia"], how="left")
        .with_columns([
            pl.col("n_chamados").fill_null(0),
            pl.col("pos_externo").fill_null(False),
        ])
        .with_columns(
            pl.when((pl.col("n_chamados") >= 5) | pl.col("pos_externo")).then(3)
            .when(pl.col("n_chamados").is_between(2, 4)).then(2)
            .when((pl.col("n_chamados") == 1) |
                  ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > _p50_expr))).then(1)
            .otherwise(0)
            .alias("severidade")
        )
        .with_columns((pl.col("severidade") >= 1).alias("enchente"))
        .join(df_feat, on=["data", "bacia"], how="left")
        .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
        .sort(["bacia", "data"])
    )

# ── 1. Fonte CEMADEN ──────────────────────────────────────────────────────────
print("Construindo fonte CEMADEN...")
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
df_h_cemaden = pl.concat(partes).sort(["bacia", "hora"])

# Confirmar chamados por chuva CEMADEN (igual V7)
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
    _chamados_idx.join_where(df_h_cemaden,
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

df_diario_cem = build_diario(df_h_cemaden)
df_feat_cem   = build_features(df_h_cemaden)

# P50 por bacia (pré-T_CUT, baseado em CEMADEN — igual V7)
_chamados_diario_cem = (
    df_chamados_conf
    .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
    .group_by(["data", "bacia"]).len().rename({"len": "n_chamados"})
)
_chamados_max = _chamados_diario_cem.join(df_diario_cem, on=["data", "bacia"], how="left").filter(pl.col("data") < T_CUT)
P50_BY_BACIA = {}
for _b in BACIAS:
    _s = _chamados_max.filter(pl.col("bacia") == _b)
    P50_BY_BACIA[_b] = float(_s["max_dia"].quantile(0.5)) if _s.height > 0 else 0.0
print(f"P50 max_dia (CEMADEN, pré-{T_CUT}): {P50_BY_BACIA}")

df_ml_cem = build_df_ml(df_feat_cem, df_diario_cem, df_chamados_conf, P50_BY_BACIA)

_ev_oratorio   = df_ml_cem.filter((pl.col("bacia") == "oratorio") & pl.col("enchente"))["data"].sort()
T_CUT_ORATORIO = _ev_oratorio[int(len(_ev_oratorio) * 0.75)]

# ── 2. Fonte ERA5-multipoint ──────────────────────────────────────────────────
print("\nConstruindo fonte ERA5-multipoint...")
mp_dir = Path("dados/openmeteo_multipoint")
with open(mp_dir / "index.json") as f:
    mp_index = json.load(f)

partes_era5 = []
for bacia in BACIAS:
    pts = mp_index[bacia]
    pt_frames = []
    for p in pts:
        fname = mp_dir / f"pt_{p['lat']:.6f}_{p['lon']:.6f}.parquet".replace("-", "m")
        df_pt = pl.read_parquet(fname).select([
            pl.col("dt").alias("hora"),
            pl.col("precipitation_mm"),
        ])
        pt_frames.append(df_pt)

    # Combinar pontos: mesmo que CEMADEN combina estações
    merged = pt_frames[0].rename({"precipitation_mm": "p_0"})
    for i, df_pt in enumerate(pt_frames[1:], 1):
        merged = merged.join(df_pt.rename({"precipitation_mm": f"p_{i}"}), on="hora", how="left")

    p_cols = [f"p_{i}" for i in range(len(pt_frames))]
    partes_era5.append(
        merged.with_columns([
            pl.max_horizontal(p_cols).alias("chuva_max_mm"),
            pl.mean_horizontal(p_cols).alias("chuva_mean_mm"),
            pl.concat_list(p_cols).list.std().fill_null(0.0).alias("chuva_std_mm"),
            pl.sum_horizontal([(pl.col(c) > 1.0).cast(pl.Int8) for c in p_cols]).alias("n_chovendo"),
            pl.lit(bacia).alias("bacia"),
        ])
        .select(["hora", "bacia", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
    )

df_h_era5mp    = pl.concat(partes_era5).sort(["bacia", "hora"])
df_diario_era5mp = build_diario(df_h_era5mp)
df_feat_era5mp   = build_features(df_h_era5mp)
df_ml_era5mp     = build_df_ml(df_feat_era5mp, df_diario_era5mp, df_chamados_conf, P50_BY_BACIA)

# Verificar cobertura de features espaciais
print("\nComparação de features espaciais (média do test):")
for bacia in BACIAS:
    t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT
    cem_std = df_ml_cem.filter((pl.col("bacia") == bacia) & (pl.col("data") >= t_cut))["std_day_lag1"].mean()
    mp_std  = df_ml_era5mp.filter((pl.col("bacia") == bacia) & (pl.col("data") >= t_cut))["std_day_lag1"].mean()
    cem_nc  = df_ml_cem.filter((pl.col("bacia") == bacia) & (pl.col("data") >= t_cut))["n_chovendo_max_lag1"].mean()
    mp_nc   = df_ml_era5mp.filter((pl.col("bacia") == bacia) & (pl.col("data") >= t_cut))["n_chovendo_max_lag1"].mean()
    print(f"  {bacia}: std_day_lag1 CEM={cem_std:.3f} ERA5mp={mp_std:.3f} | n_chovendo_max_lag1 CEM={cem_nc:.3f} ERA5mp={mp_nc:.3f}")

# ── Treino e avaliação ────────────────────────────────────────────────────────
mk = lambda: GradientBoostingClassifier(
    n_estimators=200, learning_rate=0.05, max_depth=2,
    min_samples_leaf=10, subsample=0.8, max_features="sqrt", random_state=42,
)

EXPERIMENTOS = {
    "CEM→CEM":       (df_ml_cem,    df_ml_cem),
    "ERA5mp→ERA5mp": (df_ml_era5mp, df_ml_era5mp),
    "CEM→ERA5mp":    (df_ml_cem,    df_ml_era5mp),
}

print("\n" + "═"*110)
print("RESULTADOS — GradBoost V7 ordinal (sev≥1 como alarme operacional)")
print("═"*110)

all_results = []

for exp_nome, (df_train_src, df_test_src) in EXPERIMENTOS.items():
    print(f"\n{'─'*110}")
    print(f"  Experimento: {exp_nome}")
    print(f"{'─'*110}")

    for bacia in BACIAS:
        t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT

        train = df_train_src.filter(pl.col("bacia") == bacia).filter(pl.col("data") < t_cut).drop_nulls(FEATURES_V4)
        test  = df_test_src.filter(pl.col("bacia") == bacia).filter(pl.col("data") >= t_cut).drop_nulls(FEATURES_V4)

        if train.height == 0 or test.height == 0:
            print(f"  {bacia}: dados insuficientes — pulando")
            continue

        sev_tr = train["severidade"].to_numpy()
        sev_te = test["severidade"].to_numpy()

        if sev_te.max() == 0:
            print(f"  {bacia}: test sem positivos — pulando")
            continue

        X_tr = train[FEATURES_V4].to_pandas()
        X_te = test[FEATURES_V4].to_pandas()

        r = avaliar_ordinal(mk, X_tr, X_te, sev_tr, sev_te, test["data"])

        tab = r["tabela"]
        sev0 = tab[0]
        sev_pos = {s: tab[s] for s in [1, 2, 3] if tab[s]["n"] > 0}

        # TPs e FPs para sev≥1
        tp = sum(tab[s][">=1"] for s in [1, 2, 3])
        fp = tab[0][">=1"]
        fn = sum(tab[s]["n"] - tab[s][">=1"] for s in [1, 2, 3])
        n_pos = sum(tab[s]["n"] for s in [1, 2, 3])
        total_alarmes = tp + fp
        precisao = tp / total_alarmes if total_alarmes > 0 else 0.0
        recall   = tp / n_pos if n_pos > 0 else 0.0

        print(f"  {bacia:12s} | TPs={tp:>3}/{n_pos:<3} FPs={fp:>3} | "
              f"Precisão={precisao:.0%} Recall={recall:.0%} PR-AUC={r['pr_auc_m1']:.3f} | "
              f"Alarmes/mês={r['alarmes_mes']['>=1']:>5} | Custo={r['custo']}")

        all_results.append({
            "experimento": exp_nome,
            "bacia":       bacia,
            "n_pos_test":  n_pos,
            "tp":          tp,
            "fp":          fp,
            "fn":          fn,
            "precisao":    round(precisao, 3),
            "recall":      round(recall, 3),
            "pr_auc":      round(r["pr_auc_m1"], 3),
            "alarmes_mes": r["alarmes_mes"][">=1"],
            "custo":       r["custo"],
        })

# ── Tabela resumo ─────────────────────────────────────────────────────────────
print("\n\n" + "═"*110)
print("RESUMO COMPARATIVO")
print("═"*110)
print(f"\n{'Experimento':>16} {'Bacia':>12} {'TPs':>6} {'FPs':>6} {'Pos':>5} {'Precisão':>9} {'Recall':>8} {'PR-AUC':>8} {'Alarmes/mês':>12}")
print("-"*90)
for row in all_results:
    print(f"{row['experimento']:>16} {row['bacia']:>12} {row['tp']:>6} {row['fp']:>6} "
          f"{row['n_pos_test']:>5} {row['precisao']:>9.0%} {row['recall']:>8.0%} "
          f"{row['pr_auc']:>8.3f} {row['alarmes_mes']:>12}")

pl.DataFrame(all_results).write_parquet("dados/comparativo_multipoint.parquet")
print("\nSalvo em dados/comparativo_multipoint.parquet")
