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
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier

MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H      = [1, 3, 6, 24, 48, 72]
LIMS           = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H     = 72
T_CUT          = datetime(2023, 7, 2).date()
K_API          = 0.85

FEATURES_V3 = (
    ["api_085"]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
)

with open("dados/estacoes_bacia.json") as f:
    estacoes_bacia = json.load(f)

partes = []
for bacia in estacoes_bacia:
    df = pl.read_parquet(f"dados/chuva_bacias/chuva_{bacia}.parquet")
    est_cols = [c for c in df.columns if c != "hora"]
    partes.append(
        df.with_columns(pl.max_horizontal(est_cols).alias("chuva_max_mm"))
        .select(["hora", "chuva_max_mm"])
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
df_max_dia = (
    df_h.group_by(["data", "bacia"])
    .agg(pl.col("chuva_max_mm").max().alias("max_dia"))
    .sort(["bacia", "data"])
)
df_feat = (
    df_blocos_wide.join(df_max_dia, on=["data", "bacia"])
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
    ])
    .select(["data", "bacia"] + [f"acc_6h_lag_{i}" for i in range(1, 13)]
            + ["max_day_lag1", "max_day_lag2", "max_day_lag3"])
)
_api_parts = []
for _bacia in df_max_dia["bacia"].unique().to_list():
    _sub  = df_max_dia.filter(pl.col("bacia") == _bacia).sort("data")
    _vals = _sub["max_dia"].fill_null(0).to_numpy()
    _api  = lfilter([1.0], [1.0, -K_API], _vals)
    _api_parts.append(
        _sub.select(["data", "bacia"])
        .with_columns(pl.Series("api_085", _api))
    )
df_api = pl.concat(_api_parts)
df_feat = df_feat.join(df_api, on=["data", "bacia"])

_df_target = (
    df_chamados_conf
    .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
    .group_by(["data", "bacia"]).len()
    .with_columns(pl.lit(True).alias("enchente"))
    .select(["data", "bacia", "enchente"])
)
_bacias = list(estacoes_bacia.keys())
_datas  = pl.date_range(date(2016, 1, 1), date(2025, 12, 31), interval="1d", eager=True).to_list()
_cal    = pl.DataFrame({
    "data":  pl.Series([d for d in _datas for _ in _bacias], dtype=pl.Date),
    "bacia": [b for _ in _datas for b in _bacias],
})
df_ml = (
    _cal
    .join(_df_target, on=["data", "bacia"], how="left")
    .with_columns(pl.col("enchente").fill_null(False))
    .join(df_feat, on=["data", "bacia"], how="left")
    .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
    .sort(["bacia", "data"])
)

_ev_oratorio = df_ml.filter((pl.col("bacia") == "oratorio") & pl.col("enchente"))["data"].sort()
T_CUT_ORATORIO = _ev_oratorio[int(len(_ev_oratorio) * 0.75)]

MODELOS = {
    "LightGBM":    lambda sw: LGBMClassifier(n_estimators=500, learning_rate=0.05, num_leaves=31,
                                              class_weight="balanced", random_state=42, n_jobs=-1, verbose=-1),
    "XGBoost":     lambda sw: XGBClassifier(n_estimators=500, learning_rate=0.05, max_depth=4,
                                             scale_pos_weight=sw, random_state=42, n_jobs=-1,
                                             eval_metric="logloss", verbosity=0),
    "RandomForest": lambda sw: RandomForestClassifier(n_estimators=200, class_weight="balanced",
                                                       random_state=42, n_jobs=-1),
    "ExtraTrees":  lambda sw: ExtraTreesClassifier(n_estimators=200, class_weight="balanced",
                                                    random_state=42, n_jobs=-1),
    "GradBoost":   lambda sw: GradientBoostingClassifier(n_estimators=200, learning_rate=0.05,
                                                          max_depth=2, min_samples_leaf=10,
                                                          subsample=0.8, max_features="sqrt",
                                                          random_state=42),
    "AdaBoost":    lambda sw: AdaBoostClassifier(
                                  estimator=DecisionTreeClassifier(max_depth=1),
                                  n_estimators=200, learning_rate=0.5, random_state=42),
    "LogisticReg": lambda sw: Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    LogisticRegression(class_weight="balanced", max_iter=1000, random_state=42)),
    ]),
}

def _metricas(y_true, y_prob, thr):
    y_pred = (y_prob >= thr).astype(int)
    return {
        "pr_auc":   round(float(average_precision_score(y_true, y_prob)), 3),
        "f1":       round(float(f1_score(y_true, y_pred)), 3),
        "f2":       round(float(fbeta_score(y_true, y_pred, beta=2)), 3),
        "recall":   round(float(recall_score(y_true, y_pred)), 3),
        "precisao": round(float(precision_score(y_true, y_pred)), 3),
    }

def fit_avaliar(clf, X_tr, y_tr, X_te, y_te):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf.fit(X_tr, y_tr)
    y_prob_te = clf.predict_proba(X_te)[:, 1]
    prec, rec, thrs = precision_recall_curve(y_te, y_prob_te)
    f2s = (5 * prec[:-1] * rec[:-1]) / (4 * prec[:-1] + rec[:-1] + 1e-9)
    best = float(thrs[np.argmax(f2s)])
    y_prob_tr = clf.predict_proba(X_tr)[:, 1]
    te = _metricas(y_te, y_prob_te, best)
    tr = _metricas(y_tr, y_prob_tr, best)
    return {
        **{f"te_{k}": v for k, v in te.items()},
        **{f"tr_{k}": v for k, v in tr.items()},
        "test_pos":  int(y_te.sum()),
        "train_pos": int(y_tr.sum()),
    }

rows = []
for bacia in sorted(df_ml["bacia"].unique().to_list()):
    t_cut = T_CUT_ORATORIO if bacia == "oratorio" else T_CUT
    sub   = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES_V3)
    train = sub.filter(pl.col("data") < t_cut)
    test  = sub.filter(pl.col("data") >= t_cut)
    X_tr  = train[FEATURES_V3].to_pandas()
    X_te  = test[FEATURES_V3].to_pandas()
    y_tr  = train["enchente"].cast(pl.Int8).to_numpy()
    y_te  = test["enchente"].cast(pl.Int8).to_numpy()
    if y_te.sum() == 0:
        continue
    sw = float((y_tr == 0).sum()) / max((y_tr == 1).sum(), 1)
    for nome, mk in MODELOS.items():
        res = fit_avaliar(mk(sw), X_tr, y_tr, X_te, y_te)
        rows.append({"bacia": bacia, "modelo": nome, **res})

df_res = pl.DataFrame(rows)

FOCO = ["AdaBoost", "GradBoost"]

for bacia in sorted(df_res["bacia"].unique().to_list()):
    sub = (
        df_res.filter((pl.col("bacia") == bacia) & pl.col("modelo").is_in(FOCO))
        .sort("te_f2", descending=True)
    )
    test_pos  = sub["test_pos"][0]
    train_pos = sub["train_pos"][0]
    print(f"\n{'─'*72}")
    print(f"  {bacia.upper()}  (train_pos={train_pos}  test_pos={test_pos})")
    print(f"{'─'*72}")
    cols = ["modelo",
            "te_pr_auc", "te_f1", "te_f2", "te_recall", "te_precisao",
            "tr_pr_auc", "tr_f1", "tr_f2", "tr_recall", "tr_precisao"]
    print(sub.select(cols).to_pandas().to_string(index=False))
