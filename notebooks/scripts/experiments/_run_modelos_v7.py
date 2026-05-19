import polars as pl
import json
import numpy as np
import warnings
from datetime import datetime, date
from functools import reduce
from scipy.signal import lfilter

from sklearn.ensemble import (
    RandomForestClassifier, ExtraTreesClassifier,
    GradientBoostingClassifier, AdaBoostClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    average_precision_score, f1_score, fbeta_score, precision_recall_curve,
    precision_score, recall_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.base import clone
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier

MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H      = [1, 3, 6, 24, 48, 72]
LIMS           = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H     = 72
T_CUT          = datetime(2023, 7, 2).date()
K_API          = 0.85

K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0

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

df_h = (
    df_chuva_h
    .with_columns([
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

# target ordinal por (data, bacia):
# 0: sem chamado e chuva normal (≤ p50 dos dias positivos pré-T_CUT)
# 1: 1 chamado OU 0 chamado com chuva atípica (> p50)
# 2: 2-4 chamados
# 3: 5+ chamados OU dia em alagamentos_bacias.csv

_chamados_diario = (
    df_chamados_conf
    .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
    .group_by(["data", "bacia"]).len().rename({"len": "n_chamados"})
)

# fonte externa: alagamentos_bacias.csv → flag por bacia
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

# max_dia para uso no critério de severidade nível 1 (chuva atípica)
_max_dia = df_diario.select(["data", "bacia", "max_dia"])

# p50 do max_dia em dias com chamado, pré-T_CUT (evitar leak)
_chamados_max = _chamados_diario.join(_max_dia, on=["data", "bacia"], how="left").filter(pl.col("data") < T_CUT)
P50_BY_BACIA = {}
for _b in _bacias:
    _s = _chamados_max.filter(pl.col("bacia") == _b)
    if _s.height > 0:
        P50_BY_BACIA[_b] = float(_s["max_dia"].quantile(0.5))
    else:
        P50_BY_BACIA[_b] = float(_max_dia.filter(pl.col("bacia") == _b)["max_dia"].quantile(0.95))
print(f"p50 max_dia (dias positivos pré-{T_CUT}): {P50_BY_BACIA}")

df_ml = (
    _cal
    .join(_chamados_diario, on=["data", "bacia"], how="left")
    .join(_df_ext, on=["data", "bacia"], how="left")
    .join(_max_dia, on=["data", "bacia"], how="left")
    .with_columns([
        pl.col("n_chamados").fill_null(0),
        pl.col("pos_externo").fill_null(False),
    ])
)
# severidade ordinal
_p50_expr = pl.col("bacia").replace_strict(P50_BY_BACIA, return_dtype=pl.Float64)
df_ml = df_ml.with_columns(
    pl.when((pl.col("n_chamados") >= 5) | pl.col("pos_externo")).then(3)
    .when(pl.col("n_chamados").is_between(2, 4)).then(2)
    .when((pl.col("n_chamados") == 1) | ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > _p50_expr))).then(1)
    .otherwise(0)
    .alias("severidade")
).with_columns(
    (pl.col("severidade") >= 1).alias("enchente")  # mantém para compatibilidade do split oratorio
)
df_ml = df_ml.join(df_feat, on=["data", "bacia"], how="left").filter(
    pl.col("data").dt.month().is_in(MESES_CHUVOSOS)
).sort(["bacia", "data"])

print("\nDistribuição de severidade por bacia:")
print(df_ml.group_by(["bacia", "severidade"]).len().sort(["bacia", "severidade"]).to_pandas().to_string(index=False))

_ev_oratorio = df_ml.filter((pl.col("bacia") == "oratorio") & pl.col("enchente"))["data"].sort()
T_CUT_ORATORIO = _ev_oratorio[int(len(_ev_oratorio) * 0.75)]

MODELOS = {
    "GradBoost":   lambda sw: GradientBoostingClassifier(n_estimators=200, learning_rate=0.05,
                                                          max_depth=2, min_samples_leaf=10,
                                                          subsample=0.8, max_features="sqrt",
                                                          random_state=42),
    "LogisticReg": lambda sw: Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
    ]),
}

# pesos de custo (FN por nível, FP)
W_FN = {1: 1.0, 2: 3.0, 3: 10.0}
W_FP = 1.0

def w_fit_m3(severidade):
    """Pesar amostras no fit do m3 (graves) — graves valem mais."""
    return np.where(severidade == 3, 3.0,
           np.where(severidade == 2, 1.5,
           np.where(severidade == 1, 1.0, 1.0)))

N_BOOT     = 1000
CV_SPLITS  = 5
RNG_BOOT   = np.random.default_rng(42)

def _metricas(y_true, y_prob, thr):
    y_pred = (y_prob >= thr).astype(int)
    return {
        "pr_auc":   float(average_precision_score(y_true, y_prob)),
        "f1":       float(f1_score(y_true, y_pred, zero_division=0)),
        "f2":       float(fbeta_score(y_true, y_pred, beta=2, zero_division=0)),
        "recall":   float(recall_score(y_true, y_pred, zero_division=0)),
        "precisao": float(precision_score(y_true, y_pred, zero_division=0)),
    }

def _thr_por_f2(y_true, y_prob):
    """Otimiza F1 (não F2) — usado para escolha de threshold; nome mantido por compatibilidade."""
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5

def _fit_with_sw(clf, X, y, sw_arr):
    """Fit suportando pipelines (LogisticReg) e classificadores diretos."""
    if isinstance(clf, Pipeline):
        clf.fit(X, y, clf__sample_weight=sw_arr)
    else:
        clf.fit(X, y, sample_weight=sw_arr)
    return clf

def _thr_cv_treino(mk, sw_full, X_tr, y_tr, w_tr, n_splits=CV_SPLITS):
    """Walk-forward CV no treino: out-of-fold predictions → threshold por F1."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    oof_prob = np.full(len(y_tr), np.nan)
    for tr_idx, va_idx in tscv.split(X_tr):
        if y_tr[tr_idx].sum() == 0 or y_tr[va_idx].sum() == 0:
            continue
        sw = float((y_tr[tr_idx] == 0).sum()) / max((y_tr[tr_idx] == 1).sum(), 1)
        clf = mk(sw)
        sw_arr = np.where(y_tr[tr_idx] == 1, w_tr[tr_idx], 1.0).astype(float)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _fit_with_sw(clf, X_tr.iloc[tr_idx], y_tr[tr_idx], sw_arr)
        oof_prob[va_idx] = clf.predict_proba(X_tr.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof_prob)
    if mask.sum() == 0 or y_tr[mask].sum() == 0:
        return 0.5
    return _thr_por_f2(y_tr[mask], oof_prob[mask])

def _bootstrap_ic(y_true, y_prob, thr, n=N_BOOT):
    """Bootstrap estratificado: IC95 para pr_auc/f2/recall/precisao."""
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

def thr_por_f1_cv_simples(mk, X_tr, y_tr_bin, sw_arr, n_splits=CV_SPLITS):
    """Walk-forward CV no treino: out-of-fold predictions → threshold por F1."""
    tscv = TimeSeriesSplit(n_splits=n_splits)
    oof = np.full(len(y_tr_bin), np.nan)
    for tr_idx, va_idx in tscv.split(X_tr):
        if y_tr_bin[tr_idx].sum() == 0 or y_tr_bin[va_idx].sum() == 0:
            continue
        clf = mk(0.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _fit_with_sw(clf, X_tr.iloc[tr_idx], y_tr_bin[tr_idx], sw_arr[tr_idx])
        oof[va_idx] = clf.predict_proba(X_tr.iloc[va_idx])[:, 1]
    mask = ~np.isnan(oof)
    if mask.sum() == 0 or y_tr_bin[mask].sum() == 0:
        return 0.5
    return _thr_por_f2(y_tr_bin[mask], oof[mask])

def avaliar_ordinal(mk, X_tr, X_te, sev_tr, sev_te, datas_te):
    """3 modelos binários: m1 (≥1), m2 (≥2), m3 (≥3). Retorna alarme_nivel + métricas."""
    probs_te = {}
    thrs = {}
    for k in [1, 2, 3]:
        y_tr_bin = (sev_tr >= k).astype(int)
        y_te_bin = (sev_te >= k).astype(int)
        if y_tr_bin.sum() < 2 or y_te_bin.sum() == 0:
            probs_te[k] = np.zeros(len(y_te_bin))
            thrs[k] = 1.5  # nunca dispara
            continue
        # peso de fit: m3 prioriza graves; m1/m2 com peso uniforme
        if k == 3:
            sw_arr = w_fit_m3(sev_tr).astype(float)
        else:
            sw_arr = np.ones(len(sev_tr), dtype=float)
        thr = thr_por_f1_cv_simples(mk, X_tr, y_tr_bin, sw_arr)
        clf = mk(0.0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _fit_with_sw(clf, X_tr, y_tr_bin, sw_arr)
        probs_te[k] = clf.predict_proba(X_te)[:, 1]
        thrs[k] = thr

    # nivel de alarme = maior k com prob ≥ thr; default 0
    alarme_nivel = np.zeros(len(sev_te), dtype=int)
    for k in [1, 2, 3]:
        alarme_nivel = np.where(probs_te[k] >= thrs[k], k, alarme_nivel)

    # tabela de detecção: linha = severidade real; cols = detectados por nivel ≥k
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
    # custo: FN ponderado por gravidade + FP
    custo = 0.0
    for s in [1, 2, 3]:
        fn = int(((sev_te == s) & (alarme_nivel < s)).sum())
        custo += W_FN[s] * fn
    fp = int(((sev_te == 0) & (alarme_nivel >= 1)).sum())
    custo += W_FP * fp

    # alarmes/mês por nível
    if datas_te is not None and len(datas_te) > 0:
        meses = datas_te.dt.year().to_numpy() * 12 + datas_te.dt.month().to_numpy()
        n_meses = max(len(np.unique(meses)), 1)
    else:
        n_meses = 1
    alarmes_mes = {
        ">=1": round(int((alarme_nivel >= 1).sum()) / n_meses, 2),
        ">=2": round(int((alarme_nivel >= 2).sum()) / n_meses, 2),
        ">=3": round(int((alarme_nivel >= 3).sum()) / n_meses, 2),
    }
    return {"thrs": thrs, "tabela": tabela, "custo": custo, "alarmes_mes": alarmes_mes}

todos = {}
for bacia in sorted(df_ml["bacia"].unique().to_list()):
    t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT
    sub   = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES_V4)
    train = sub.filter(pl.col("data") < t_cut)
    test  = sub.filter(pl.col("data") >= t_cut)
    X_tr  = train[FEATURES_V4].to_pandas()
    X_te  = test[FEATURES_V4].to_pandas()
    sev_tr = train["severidade"].to_numpy()
    sev_te = test["severidade"].to_numpy()
    datas_te = test["data"]
    if sev_te.max() == 0:
        print(f"\n{bacia}: test sem positivos, pulando.")
        continue

    res_bacia = {}
    for nome, mk in MODELOS.items():
        r = avaliar_ordinal(mk, X_tr, X_te, sev_tr, sev_te, datas_te)
        res_bacia[nome] = r
    todos[bacia] = res_bacia

    print(f"\n{'═'*100}")
    print(f"  {bacia.upper()}  (train_n={train.height}  test_n={test.height})")
    print(f"  Severidade no treino: ", end="")
    for s in [0, 1, 2, 3]:
        print(f"{s}={int((sev_tr == s).sum())}", end="  ")
    print()
    print(f"  Severidade no test:   ", end="")
    for s in [0, 1, 2, 3]:
        print(f"{s}={int((sev_te == s).sum())}", end="  ")
    print()
    print(f"{'═'*100}")
    for nome, r in res_bacia.items():
        print(f"\n  Modelo: {nome}")
        print(f"    Thresholds: m1={r['thrs'][1]:.3f}  m2={r['thrs'][2]:.3f}  m3={r['thrs'][3]:.3f}")
        print(f"    Custo total (α=10, β=3, γ=1, δ=1): {r['custo']}")
        print(f"    Alarmes/mês: ≥1={r['alarmes_mes']['>=1']}  ≥2={r['alarmes_mes']['>=2']}  ≥3={r['alarmes_mes']['>=3']}")
        print(f"    Tabela de detecção:")
        print(f"      {'sev':>3}  {'n':>4}    {'≥1':>8}    {'≥2':>8}    {'≥3':>8}")
        for sev, d in r["tabela"].items():
            n = d["n"]
            if n == 0:
                print(f"      {sev:>3}  {n:>4}        ---        ---        ---")
            else:
                print(f"      {sev:>3}  {n:>4}     {d['>=1']:>3}/{n:<3}    {d['>=2']:>3}/{n:<3}    {d['>=3']:>3}/{n:<3}")
