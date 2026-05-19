"""
Comparativo de fontes de precipitação: CEMADEN vs ERA5 vs TomorrowIO D+1

Estratégia: treino sempre com CEMADEN; inferência com features normalizadas.
  1. Calcular features V4 para cada fonte.
  2. Ajustar QuantileTransformer no treino CEMADEN (por bacia).
  3. Transformar features de CEMADEN, ERA5 e TIO com o mesmo mapeamento.
  4. Modelo e threshold calibrados no treino CEMADEN; avaliar cada fonte.

Isso remove o viés de escala entre fontes sem vazar informação do test.
  * CEMADEN   → T_CUT → 2025-12-31
  * ERA5      → T_CUT → 2025-12-31
  * TIO D+1   → 2023-11-22 → 2024-03-09  (janela de overlap com forecasts)
"""

import polars as pl
import pandas as pd
import numpy as np
import json
import warnings
from datetime import datetime, date
from scipy.signal import lfilter

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score, fbeta_score, precision_recall_curve,
    precision_score, recall_score, f1_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import QuantileTransformer

# ── Constantes (idênticas ao V4) ─────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
T_CUT          = date(2023, 7, 2)
K_APIS         = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0
CV_SPLITS      = 5
N_BOOT         = 1000
RNG_BOOT       = np.random.default_rng(42)

FEATURES_V4 = (
    [f"api_{int(k*100):03d}" for k in K_APIS]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

# Features compatíveis com fontes de ponto único (ERA5, TIO):
# exclui std_day_lag1 e n_chovendo_max_lag1 — derivadas de múltiplas estações
FEATURES_COMPAT = (
    [f"api_{int(k*100):03d}" for k in K_APIS]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

GRADBOOST = lambda sw: GradientBoostingClassifier(
    n_estimators=200, learning_rate=0.05, max_depth=2,
    min_samples_leaf=10, subsample=0.8, max_features="sqrt",
    random_state=42,
)

with open("dados/estacoes_bacia.json") as f:
    estacoes_bacia = json.load(f)

BACIAS = sorted(estacoes_bacia.keys())

# ── Helpers de avaliação ─────────────────────────────────────────────────────

def thr_cv(X_tr, y_tr):
    tscv = TimeSeriesSplit(n_splits=CV_SPLITS)
    oof  = np.full(len(y_tr), np.nan)
    for tr_idx, va_idx in tscv.split(X_tr):
        if y_tr[tr_idx].sum() == 0 or y_tr[va_idx].sum() == 0:
            continue
        clf = GRADBOOST(None)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            clf.fit(X_tr.iloc[tr_idx], y_tr[tr_idx])
        oof[va_idx] = clf.predict_proba(X_tr.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_tr[mask].sum() == 0:
        return 0.5
    prec, rec, thrs = precision_recall_curve(y_tr[mask], oof[mask])
    f2s = (5 * prec[:-1] * rec[:-1]) / (4 * prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f2s)]) if np.any(np.isfinite(f2s)) else 0.5

def metricas(y_true, y_prob, thr):
    y_pred = (y_prob >= thr).astype(int)
    pos_total = int(y_true.sum())
    pos_capt  = int(((y_true == 1) & (y_pred == 1)).sum())
    return {
        "f2":          round(float(fbeta_score(y_true, y_pred, beta=2, zero_division=0)), 3),
        "recall":      round(float(recall_score(y_true, y_pred, zero_division=0)), 3),
        "precisao":    round(float(precision_score(y_true, y_pred, zero_division=0)), 3),
        "pr_auc":      round(float(average_precision_score(y_true, y_prob)), 3),
        "eventos_capt": f"{pos_capt}/{pos_total}",
        "thr":         round(thr, 3),
    }

def bootstrap_ic(y_true, y_prob, thr, n=N_BOOT):
    pos_idx = np.where(y_true == 1)[0]
    neg_idx = np.where(y_true == 0)[0]
    if len(pos_idx) == 0 or len(neg_idx) == 0:
        return {"f2": "—", "recall": "—"}
    f2s = []
    recs = []
    for _ in range(n):
        bp  = RNG_BOOT.choice(pos_idx, size=len(pos_idx), replace=True)
        bn  = RNG_BOOT.choice(neg_idx, size=len(neg_idx), replace=True)
        idx = np.concatenate([bp, bn])
        y_p = (y_prob[idx] >= thr).astype(int)
        f2s.append(fbeta_score(y_true[idx], y_p, beta=2, zero_division=0))
        recs.append(recall_score(y_true[idx], y_p, zero_division=0))
    return {
        "f2":     f"[{np.percentile(f2s,2.5):.2f},{np.percentile(f2s,97.5):.2f}]",
        "recall": f"[{np.percentile(recs,2.5):.2f},{np.percentile(recs,97.5):.2f}]",
    }

# ── Pipeline de features genérico ────────────────────────────────────────────
# Recebe df_h: DataFrame Polars com colunas [hora, bacia,
#              chuva_max_mm, chuva_mean_mm, chuva_std_mm, n_chovendo]
# Devolve df_feat: colunas [data, bacia, FEATURES_V4]

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
        cols  = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS:
            cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
        _api_parts.append(pl.DataFrame(cols))

    return df_feat.join(pl.concat(_api_parts), on=["data", "bacia"])


def build_df_ml(df_feat: pl.DataFrame, df_chamados_conf: pl.DataFrame) -> pl.DataFrame:
    _df_target = (
        df_chamados_conf
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by(["data", "bacia"]).len()
        .with_columns(pl.lit(True).alias("enchente"))
        .select(["data", "bacia", "enchente"])
    )
    _datas = pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True).to_list()
    _cal   = pl.DataFrame({
        "data":  pl.Series([d for d in _datas for _ in BACIAS], dtype=pl.Date),
        "bacia": [b for _ in _datas for b in BACIAS],
    })
    return (
        _cal
        .join(_df_target, on=["data", "bacia"], how="left")
        .with_columns(pl.col("enchente").fill_null(False))
        .join(df_feat, on=["data", "bacia"], how="left")
        .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
        .sort(["bacia", "data"])
    )

# ── 1. Fonte CEMADEN ─────────────────────────────────────────────────────────
print("Construindo features CEMADEN...")
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

# Confirmação de chamados via CEMADEN (igual ao V4)
from functools import reduce
JANELAS_H = [1, 3, 6, 24, 48, 72]
LIMS      = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72

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

df_feat_cemaden = build_features(df_h_cemaden)
df_ml_cemaden   = build_df_ml(df_feat_cemaden, df_chamados_conf)

# T_CUT dinâmico para oratório (75% dos eventos)
_ev_oratorio   = df_ml_cemaden.filter((pl.col("bacia") == "oratorio") & pl.col("enchente"))["data"].sort()
T_CUT_ORATORIO = _ev_oratorio[int(len(_ev_oratorio) * 0.75)]

# ── 2. Fonte ERA5 (Open-Meteo) ───────────────────────────────────────────────
print("Construindo features ERA5...")
era5 = pl.read_parquet("dados/openweater/open_meteo_history.parquet")
# Replicar para todas as bacias (ERA5 é um único ponto geográfico)
era5_h_partes = []
for bacia in BACIAS:
    era5_h_partes.append(
        era5.select([
            pl.col("dt").alias("hora"),
            pl.col("precipitation_mm").alias("chuva_max_mm"),
            pl.col("precipitation_mm").alias("chuva_mean_mm"),
            pl.lit(0.0).alias("chuva_std_mm"),
            (pl.col("precipitation_mm") > 1.0).cast(pl.Int8).alias("n_chovendo"),
            pl.lit(bacia).alias("bacia"),
        ])
    )
df_h_era5     = pl.concat(era5_h_partes).sort(["bacia", "hora"])
df_feat_era5  = build_features(df_h_era5)
df_ml_era5    = build_df_ml(df_feat_era5, df_chamados_conf)

# ── 3. Fonte TomorrowIO D+1 (lead 24–48h) ────────────────────────────────────
print("Construindo features TomorrowIO D+1...")
FCST_START = date(2023, 11, 22)
FCST_END   = date(2024, 3, 9)

tio = pd.read_csv("dados/openweater/TomorrowIO.csv", low_memory=False)
tio["target_dt"] = pd.to_datetime(tio["time"], utc=True).dt.tz_localize(None)
tio["now_dt"]    = pd.to_datetime(tio["Now"], utc=False, errors="coerce")
tio = tio[tio["now_dt"].notna()].copy()
tio["lead_h"] = (tio["target_dt"] - tio["now_dt"]).dt.total_seconds() / 3600

# D+1: média de runs com lead entre 24h e 48h por hora-alvo
d1 = tio[(tio["lead_h"] >= 24) & (tio["lead_h"] < 48)].copy()
hourly_d1 = (
    d1.groupby("target_dt")["rainIntensity"]
    .mean()
    .reset_index()
    .rename(columns={"rainIntensity": "precip_mmh"})
)
hourly_d1["hora"] = pd.to_datetime(hourly_d1["target_dt"])
hourly_d1 = hourly_d1[["hora", "precip_mmh"]].sort_values("hora")

tio_pl = pl.from_pandas(hourly_d1)
tio_h_partes = []
for bacia in BACIAS:
    tio_h_partes.append(
        tio_pl.select([
            pl.col("hora"),
            pl.col("precip_mmh").alias("chuva_max_mm"),
            pl.col("precip_mmh").alias("chuva_mean_mm"),
            pl.lit(0.0).alias("chuva_std_mm"),
            (pl.col("precip_mmh") > 1.0).cast(pl.Int8).alias("n_chovendo"),
            pl.lit(bacia).alias("bacia"),
        ])
    )
df_h_tio    = pl.concat(tio_h_partes).sort(["bacia", "hora"])
df_feat_tio = build_features(df_h_tio)
df_ml_tio   = build_df_ml(df_feat_tio, df_chamados_conf)

# ── Treino e avaliação ────────────────────────────────────────────────────────
print("\nTreinando e avaliando...\n")

FONTES = {
    # (df_ml, periodo, features)
    "CEMADEN_v4":   (df_ml_cemaden, None,                FEATURES_V4),
    "CEMADEN_base": (df_ml_cemaden, None,                FEATURES_COMPAT),
    "ERA5":         (df_ml_era5,   None,                FEATURES_COMPAT),
    "TIO_D+1":      (df_ml_tio,   (FCST_START, FCST_END), FEATURES_COMPAT),
}

results = []

for bacia in BACIAS:
    t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT

    # Treino CEMADEN com features completas (V4) e com features compatíveis
    train_cem = (
        df_ml_cemaden
        .filter(pl.col("bacia") == bacia)
        .filter(pl.col("data") < t_cut)
        .drop_nulls(FEATURES_V4)
    )
    y_tr = train_cem["enchente"].cast(pl.Int8).to_numpy()
    if y_tr.sum() == 0:
        continue

    # Dois QTs: um por conjunto de features
    qt_v4     = QuantileTransformer(output_distribution="normal", random_state=42)
    qt_compat = QuantileTransformer(output_distribution="normal", random_state=42)

    X_tr_v4     = pd.DataFrame(qt_v4.fit_transform(train_cem[FEATURES_V4].to_pandas()),     columns=FEATURES_V4)
    X_tr_compat = pd.DataFrame(qt_compat.fit_transform(train_cem[FEATURES_COMPAT].to_pandas()), columns=FEATURES_COMPAT)

    # Dois modelos e dois thresholds
    clf_v4     = GRADBOOST(None)
    clf_compat = GRADBOOST(None)
    thr_v4     = thr_cv(X_tr_v4,     y_tr)
    thr_compat = thr_cv(X_tr_compat, y_tr)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf_v4.fit(X_tr_v4, y_tr)
        clf_compat.fit(X_tr_compat, y_tr)

    for fonte, (df_ml_f, periodo, feats) in FONTES.items():
        sub = df_ml_f.filter(pl.col("bacia") == bacia).drop_nulls(feats)
        if periodo:
            sub = sub.filter(
                (pl.col("data") >= periodo[0]) & (pl.col("data") <= periodo[1])
            )
        else:
            sub = sub.filter(pl.col("data") >= t_cut)

        if len(sub) == 0 or sub["enchente"].cast(pl.Int8).sum() == 0:
            print(f"  {bacia}/{fonte}: sem eventos positivos no período — pulando")
            continue

        if feats is FEATURES_V4:
            qt, clf, thr = qt_v4, clf_v4, thr_v4
        else:
            qt, clf, thr = qt_compat, clf_compat, thr_compat

        X_te  = pd.DataFrame(qt.transform(sub[feats].to_pandas()), columns=feats)
        y_te  = sub["enchente"].cast(pl.Int8).to_numpy()
        datas = sub["data"]

        y_prob = clf.predict_proba(X_te)[:, 1]
        m  = metricas(y_te, y_prob, thr)
        ic = bootstrap_ic(y_te, y_prob, thr)

        meses = (datas.dt.year().to_numpy() * 12 + datas.dt.month().to_numpy())
        alarmes_mes = round(int((y_prob >= thr).sum()) / max(len(np.unique(meses)), 1), 2)

        row = {
            "bacia":       bacia,
            "fonte":       fonte,
            "features":    "v4" if feats is FEATURES_V4 else "compat",
            "periodo":     f"{sub['data'].min()} → {sub['data'].max()}",
            "n_dias":      len(sub),
            "alarmes_mes": alarmes_mes,
            **m,
            "f2_ic95":     ic["f2"],
            "recall_ic95": ic["recall"],
        }
        results.append(row)
        print(f"  {bacia:12s} | {fonte:12s} | F2={m['f2']:.3f} {ic['f2']:>18s} | "
              f"recall={m['recall']:.2f} | precisao={m['precisao']:.2f} | "
              f"eventos={m['eventos_capt']} | alarmes/mês={alarmes_mes}")

print()
df_out = pl.DataFrame(results)
df_out.write_parquet("dados/results/comparativo_fontes_precipitacao.parquet")
print("Salvo em dados/results/comparativo_fontes_precipitacao.parquet")

# ── Tabela consolidada para o relatório ──────────────────────────────────────
print("\n" + "═"*110)
print("RESUMO FINAL")
print("═"*110)
print(f"\n{'Bacia':12s} {'Fonte':8s} {'F2':>6} {'IC95 F2':>18} {'Recall':>7} {'Precisão':>9} {'Eventos':>10} {'Alarmes/mês':>12}")
print("-"*90)
for row in results:
    print(f"{row['bacia']:12s} {row['fonte']:14s} {row['f2']:>6.3f} {row['f2_ic95']:>18s} "
          f"{row['recall']:>7.2f} {row['precisao']:>9.2f} {row['eventos_capt']:>10s} {row['alarmes_mes']:>12.2f}")
