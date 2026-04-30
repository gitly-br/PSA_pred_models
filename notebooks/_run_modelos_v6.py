"""
V6 — predição ordinal de severidade na janela 24-48h, granularidade 6h.

Cortes de severidade (por bacia, em janela [t, t+48h]):
  0: sem chamado e chuva normal (≤ p50 dos dias positivos diários)
  1: 1 chamado OU 0 chamado com chuva atípica (> p50 dos positivos)
  2: 2-4 chamados
  3: 5+ chamados OU dia em alagamentos_bacias.csv

Modelagem: ordinal-binário (3 GradBoosts) — m1: y≥1, m2: y≥2, m3: y≥3.
Custo de erro: α=10 (FN grave), β=3 (FN moderado), γ=1 (FN leve), δ=1 (FP).
Modelos: GradBoost + LogisticReg (gama reduzida).
"""

import polars as pl
import json
import numpy as np
import warnings
from datetime import datetime, date
from functools import reduce
from scipy.signal import lfilter

from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    average_precision_score, f1_score, fbeta_score, precision_recall_curve,
    precision_score, recall_score,
)
from sklearn.model_selection import TimeSeriesSplit

MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H = [1, 3, 6, 12, 24, 48, 72]
LIMS = {1: 20, 3: 30, 6: 45, 12: 55, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72
HORIZONTE_H = 48
GRID_H = 6  # uma linha a cada 6h
T_CUT = datetime(2023, 7, 2).date()
K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0
GAP_HORAS_CV = HORIZONTE_H

# pesos de custo: priorizar não perder eventos graves
W_FN = {1: 1.0, 2: 3.0, 3: 10.0}
W_FP = 1.0

# pesos de fit (m3 prioriza graves)
def w_fit_m3(severidade):
    return np.where(severidade == 3, 3.0,
           np.where(severidade == 2, 1.5,
           np.where(severidade == 1, 1.0, 1.0)))

with open("dados/estacoes_bacia.json") as f:
    estacoes_bacia = json.load(f)

# ---- chuva horária por bacia (com agregações espaciais) ----
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

# ---- chamados confirmados por bacia ----
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
    _chamados_idx.join_where(
        df_chuva_h.select(["hora", "chuva_max_mm", "bacia"]),
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
    .with_row_index("_idx")
    .join(_accs, on="_idx", how="left").drop("_idx")
    .with_columns(_cond.alias("confirmado_chuva_bacia"))
    .filter(pl.col("confirmado_chuva_bacia"))
    .select(["dt_abertura", "bacia"])
    .with_columns(pl.col("dt_abertura").dt.truncate("1h").alias("hora"))
)

# ---- fonte externa ----
ext = pl.read_csv("dados/alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
ext_long = ext.select([
    pl.col("dt").alias("data"),
    pl.col("bacia_tamanduatei").alias("tamanduatei"),
    pl.col("bacia_guarara").alias("guarara"),
    pl.col("bacia_oratorio").alias("oratorio"),
    pl.col("bacia_meninos").alias("meninos"),
]).unpivot(index="data", variable_name="bacia", value_name="flag").filter(pl.col("flag") > 0).select(["data", "bacia"])

# ---- max diário por bacia (para p50 / api / cortes de severidade) ----
df_h = df_chuva_h.with_columns(pl.col("hora").dt.date().alias("data"))
df_diario = (
    df_h.group_by(["data", "bacia"])
    .agg([
        pl.col("chuva_max_mm").max().alias("max_dia"),
        pl.col("chuva_max_mm").sum().alias("acum_dia"),
    ]).sort(["bacia", "data"])
)

# p50 do max_dia em dias positivos por bacia (calculado só com dados pré-T_CUT para evitar leak)
chamados_diario = (
    df_chamados_conf.with_columns(pl.col("hora").dt.date().alias("data"))
    .group_by(["data", "bacia"]).len().rename({"len": "n_chamados"})
)
df_diario_pos = df_diario.join(chamados_diario, on=["data", "bacia"], how="left").with_columns(
    pl.col("n_chamados").fill_null(0)
)
P50_BY_BACIA = {}
for b in estacoes_bacia:
    sub = df_diario_pos.filter(
        (pl.col("bacia") == b) & (pl.col("n_chamados") > 0) & (pl.col("data") < T_CUT)
    )
    if sub.height > 0:
        P50_BY_BACIA[b] = float(sub["max_dia"].quantile(0.5))
    else:
        P50_BY_BACIA[b] = float(df_diario.filter(pl.col("bacia") == b)["max_dia"].quantile(0.95))
print(f"p50 max_dia (dias positivos pré-{T_CUT}): {P50_BY_BACIA}")

# ---- severidade diária por bacia (depois replicada em janelas 48h) ----
def severidade_diaria(b: str) -> pl.DataFrame:
    p50 = P50_BY_BACIA[b]
    chamados_b = chamados_diario.filter(pl.col("bacia") == b)
    diario_b = df_diario.filter(pl.col("bacia") == b).join(chamados_b, on=["data", "bacia"], how="left").with_columns(
        pl.col("n_chamados").fill_null(0)
    )
    ext_b = ext_long.filter(pl.col("bacia") == b).with_columns(pl.lit(True).alias("ext"))
    diario_b = diario_b.join(ext_b, on=["data", "bacia"], how="left").with_columns(
        pl.col("ext").fill_null(False)
    )
    sev = (
        pl.when((pl.col("n_chamados") >= 5) | pl.col("ext")).then(3)
        .when(pl.col("n_chamados").is_between(2, 4)).then(2)
        .when((pl.col("n_chamados") == 1) | ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > p50))).then(1)
        .otherwise(0)
    )
    return diario_b.with_columns(sev.alias("sev_dia")).select(["data", "bacia", "sev_dia"])

df_sev_dia = pl.concat([severidade_diaria(b) for b in estacoes_bacia])
print("Severidade diária — distribuição por bacia:")
print(df_sev_dia.group_by(["bacia", "sev_dia"]).len().sort(["bacia", "sev_dia"]).to_pandas().to_string(index=False))

# ---- features 6h ----
# para cada (t, bacia) com t alinhado em GRID_H, calcular features baseadas em chuva passada
df_chuva_h_idx = df_chuva_h.with_columns([
    pl.col("hora").cast(pl.Int64).alias("hora_int"),
])

# grid: horas múltiplas de GRID_H em meses chuvosos
inicio = datetime(2016, 1, 1, 0, 0)
fim = datetime(2025, 12, 31, 23, 0)
grid_horas = pl.datetime_range(inicio, fim, interval=f"{GRID_H}h", eager=True)
grid = pl.DataFrame({"hora": grid_horas}).with_columns(
    pl.col("hora").dt.month().alias("mes")
).filter(pl.col("mes").is_in(MESES_CHUVOSOS)).drop("mes")
print(f"\nGrid 6h em meses chuvosos: {grid.height} timestamps por bacia")

# para cada (t, bacia) construir features das janelas terminando em t
# usar rolling sums por bacia na série horária
chuva_features = []
for b in estacoes_bacia:
    s = df_chuva_h.filter(pl.col("bacia") == b).sort("hora")
    cols_to_roll = []
    for h in JANELAS_H:
        s = s.with_columns([
            pl.col("chuva_max_mm").rolling_sum(window_size=h, min_samples=1).alias(f"acc_{h}h"),
            pl.col("chuva_mean_mm").rolling_sum(window_size=h, min_samples=1).alias(f"mean_acc_{h}h"),
            pl.col("n_chovendo").rolling_max(window_size=h, min_samples=1).alias(f"n_chov_max_{h}h"),
        ])
    # api horário (decai por hora)
    vals = s["chuva_max_mm"].fill_null(0).to_numpy()
    for k in K_APIS:
        api = lfilter([1.0], [1.0, -k**(1/24)], vals)  # decay K**24 por dia → K^(1/24) por hora
        s = s.with_columns(pl.Series(f"api_{int(k*100):03d}", api))
    chuva_features.append(s)
df_chuva_feat = pl.concat(chuva_features)

# acum_7d e acum_30d (rolling sums longas no diário, replicadas pra hora)
acums_dia = []
for b in estacoes_bacia:
    s = df_diario.filter(pl.col("bacia") == b).sort("data")
    s = s.with_columns([
        pl.col("acum_dia").rolling_sum(window_size=7, min_samples=1).shift(1).alias("acum_7d"),
        pl.col("acum_dia").rolling_sum(window_size=30, min_samples=1).shift(1).alias("acum_30d"),
    ]).select(["data", "bacia", "acum_7d", "acum_30d"])
    acums_dia.append(s)
df_acum_long = pl.concat(acums_dia)

# montar df_ml: para cada (t, bacia) na grid, fazer join com features e target
ml_parts = []
for b in estacoes_bacia:
    g = grid.with_columns(pl.lit(b).alias("bacia"))
    feat_b = df_chuva_feat.filter(pl.col("bacia") == b).select(
        ["hora", "bacia"]
        + [f"acc_{h}h" for h in JANELAS_H]
        + [f"mean_acc_{h}h" for h in JANELAS_H]
        + [f"n_chov_max_{h}h" for h in JANELAS_H]
        + [f"api_{int(k*100):03d}" for k in K_APIS]
    )
    g = g.join(feat_b, on=["hora", "bacia"], how="left")
    g = g.with_columns([
        pl.col("hora").dt.date().alias("data"),
        pl.col("hora").dt.hour().alias("hora_dia"),
        pl.col("hora").dt.month().alias("mes"),
    ])
    g = g.join(df_acum_long, on=["data", "bacia"], how="left")
    g = g.with_columns([
        (2 * np.pi * pl.col("hora_dia") / 24).sin().alias("hora_sin"),
        (2 * np.pi * pl.col("hora_dia") / 24).cos().alias("hora_cos"),
        (2 * np.pi * pl.col("mes") / 12).sin().alias("mes_sin"),
        (2 * np.pi * pl.col("mes") / 12).cos().alias("mes_cos"),
    ])
    ml_parts.append(g)
df_ml_h = pl.concat(ml_parts)

# ---- target: severidade na janela [t, t+48h] = max(sev_dia em dia(t), dia(t+1), dia(t+2)) ----
# truque: para cada t, o target é max sev_dia em datas em [data(t), data(t+48h)]
df_sev_dia = df_sev_dia.with_columns(pl.col("data").alias("data_dia"))
sev_horario = []
for b in estacoes_bacia:
    sd = df_sev_dia.filter(pl.col("bacia") == b).sort("data_dia").rename({"sev_dia": "sev"})
    # cada linha do grid pega max das próximas 3 datas (data, data+1, data+2 cobrem 48h+)
    g = df_ml_h.filter(pl.col("bacia") == b).select(["hora", "bacia", "data"])
    g0 = g.join(sd.select(["data_dia", "sev"]).rename({"data_dia": "data", "sev": "sev_d0"}),
                on="data", how="left")
    g0 = g0.with_columns([
        (pl.col("data") + pl.duration(days=1)).alias("data_d1"),
        (pl.col("data") + pl.duration(days=2)).alias("data_d2"),
    ])
    g0 = g0.join(sd.select(["data_dia", "sev"]).rename({"data_dia": "data_d1", "sev": "sev_d1"}),
                 on="data_d1", how="left")
    g0 = g0.join(sd.select(["data_dia", "sev"]).rename({"data_dia": "data_d2", "sev": "sev_d2"}),
                 on="data_d2", how="left")
    g0 = g0.with_columns(
        pl.max_horizontal(["sev_d0", "sev_d1", "sev_d2"]).fill_null(0).alias("severidade")
    ).select(["hora", "bacia", "severidade"])
    sev_horario.append(g0)
df_sev_h = pl.concat(sev_horario)

df_ml_h = df_ml_h.join(df_sev_h, on=["hora", "bacia"], how="left").with_columns(
    pl.col("severidade").fill_null(0)
)

print(f"\ndf_ml_h shape: {df_ml_h.shape}")
print("Distribuição de severidade no grid 6h:")
print(df_ml_h.group_by(["bacia", "severidade"]).len().sort(["bacia", "severidade"]).to_pandas().to_string(index=False))

# ---- features finais ----
FEATURES_V6 = (
    [f"acc_{h}h" for h in JANELAS_H]
    + [f"mean_acc_{h}h" for h in JANELAS_H]
    + [f"n_chov_max_{h}h" for h in JANELAS_H]
    + [f"api_{int(k*100):03d}" for k in K_APIS]
    + ["acum_7d", "acum_30d"]
    + ["hora_sin", "hora_cos", "mes_sin", "mes_cos"]
)
print(f"\nFeatures V6: {len(FEATURES_V6)}")

# ---- modelagem ordinal-binário ----
def mk_gradboost(sw):
    return GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=2, min_samples_leaf=10,
        subsample=0.8, max_features="sqrt", random_state=42,
    )

def mk_logreg(sw):
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
    ])

MODELOS = {"GradBoost": mk_gradboost, "LogisticReg": mk_logreg}

CV_SPLITS = 5
N_BOOT = 1000
RNG = np.random.default_rng(42)

def fit_with_sw(clf, X, y, sw):
    if isinstance(clf, Pipeline):
        clf.fit(X, y, clf__sample_weight=sw)
    else:
        clf.fit(X, y, sample_weight=sw)
    return clf

def thr_por_f1_cv(mk, X_tr, y_tr_bin, sw_arr=None, gap=GAP_HORAS_CV // GRID_H):
    """Walk-forward CV com gap. y_tr_bin é binário."""
    tscv = TimeSeriesSplit(n_splits=CV_SPLITS, gap=gap)
    oof = np.full(len(y_tr_bin), np.nan)
    for tr_idx, va_idx in tscv.split(X_tr):
        if y_tr_bin[tr_idx].sum() == 0 or y_tr_bin[va_idx].sum() == 0:
            continue
        clf = mk(0.0)
        sw_fold = sw_arr[tr_idx] if sw_arr is not None else np.ones(len(tr_idx))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit_with_sw(clf, X_tr.iloc[tr_idx], y_tr_bin[tr_idx], sw_fold)
        oof[va_idx] = clf.predict_proba(X_tr.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_tr_bin[mask].sum() == 0:
        return 0.5
    prec, rec, thrs = precision_recall_curve(y_tr_bin[mask], oof[mask])
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5

def evento_capt_por_severidade(sev_te, alarme):
    """Tabela: linha=severidade real, coluna=detectado (sim/não) por nivel ≥k."""
    out = {}
    for sev in [0, 1, 2, 3]:
        mask = sev_te == sev
        out[sev] = {
            "n": int(mask.sum()),
            "alarme_sim": int((mask & alarme).sum()),
        }
    return out

def custo_total(sev_te, alarme_nivel):
    """Custo: FN ponderado por gravidade + FP."""
    custo = 0.0
    for s in [1, 2, 3]:
        # FN nesse nível: severidade real == s mas alarme_nivel < s
        fn = int(((sev_te == s) & (alarme_nivel < s)).sum())
        custo += W_FN[s] * fn
    fp = int(((sev_te == 0) & (alarme_nivel >= 1)).sum())
    custo += W_FP * fp
    return custo

def avaliar_bacia(bacia, train, test):
    X_tr = train[FEATURES_V6].to_pandas()
    X_te = test[FEATURES_V6].to_pandas()
    sev_tr = train["severidade"].to_numpy()
    sev_te = test["severidade"].to_numpy()
    horas_te = test["hora"]

    resultados = {}
    for nome_modelo, mk in MODELOS.items():
        # treinar 3 modelos binários
        probs_te = {}
        thrs = {}
        for k in [1, 2, 3]:
            y_tr_bin = (sev_tr >= k).astype(int)
            y_te_bin = (sev_te >= k).astype(int)
            if y_tr_bin.sum() == 0 or y_te_bin.sum() == 0:
                probs_te[k] = np.zeros(len(y_te_bin))
                thrs[k] = 0.5
                continue
            sw_arr = w_fit_m3(sev_tr) if k == 3 else np.ones(len(sev_tr))
            thr = thr_por_f1_cv(mk, X_tr, y_tr_bin, sw_arr=sw_arr)
            clf = mk(0.0)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                fit_with_sw(clf, X_tr, y_tr_bin, sw_arr)
            probs_te[k] = clf.predict_proba(X_te)[:, 1]
            thrs[k] = thr

        # nivel de alarme = maior k tal que prob[k] >= thr[k]; senão 0
        alarme_nivel = np.zeros(len(sev_te), dtype=int)
        for k in [1, 2, 3]:
            alarme_nivel = np.where(probs_te[k] >= thrs[k], k, alarme_nivel)

        # tabela de detecção: para cada (sev_real, k_alarme >= 1/2/3), quantos foram capturados
        tabela = {}
        for sev in [0, 1, 2, 3]:
            mask = sev_te == sev
            n = int(mask.sum())
            tabela[sev] = {
                "n": n,
                ">=1": int((mask & (alarme_nivel >= 1)).sum()),
                ">=2": int((mask & (alarme_nivel >= 2)).sum()),
                ">=3": int((mask & (alarme_nivel >= 3)).sum()),
            }
        custo = custo_total(sev_te, alarme_nivel)
        # alarmes/mês por nível
        meses = horas_te.dt.year().to_numpy() * 12 + horas_te.dt.month().to_numpy()
        n_meses = max(len(np.unique(meses)), 1)
        alarmes_mes = {
            ">=1": round(int((alarme_nivel >= 1).sum()) / n_meses, 2),
            ">=2": round(int((alarme_nivel >= 2).sum()) / n_meses, 2),
            ">=3": round(int((alarme_nivel >= 3).sum()) / n_meses, 2),
        }
        resultados[nome_modelo] = {
            "thrs": {k: round(v, 4) for k, v in thrs.items()},
            "tabela": tabela,
            "custo": custo,
            "alarmes_mes": alarmes_mes,
        }
    return resultados

# ---- loop principal ----
todos = {}
for bacia in sorted(df_ml_h["bacia"].unique().to_list()):
    sub = df_ml_h.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES_V6).sort("hora")
    train = sub.filter(pl.col("data") < T_CUT)
    test = sub.filter(pl.col("data") >= T_CUT)
    if test["severidade"].max() == 0:
        print(f"\n{bacia}: test sem positivos, pulando.")
        continue
    res = avaliar_bacia(bacia, train, test)
    todos[bacia] = res

    print(f"\n{'═'*100}")
    print(f"  {bacia.upper()}  (train_rows={train.height}  test_rows={test.height})")
    print(f"  Distribuição severidade no test:")
    for sev in [0, 1, 2, 3]:
        n = int((test["severidade"] == sev).sum())
        print(f"    sev={sev}: {n}")
    print(f"{'═'*100}")
    for nome, r in res.items():
        print(f"\n  Modelo: {nome}")
        print(f"    Thresholds: {r['thrs']}")
        print(f"    Custo total (α=10, β=3, γ=1, δ=1): {r['custo']}")
        print(f"    Alarmes/mês: {r['alarmes_mes']}")
        print(f"    Tabela de detecção (linha = severidade real, valor = detectados/total):")
        print(f"      {'sev':>4} {'n':>6} {'≥1':>10} {'≥2':>10} {'≥3':>10}")
        for sev, d in r["tabela"].items():
            n = d["n"]
            print(f"      {sev:>4} {n:>6} {d['>=1']:>4}/{n:<5} {d['>=2']:>4}/{n:<5} {d['>=3']:>4}/{n:<5}")
