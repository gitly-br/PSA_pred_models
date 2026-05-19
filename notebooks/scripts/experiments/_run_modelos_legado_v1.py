"""
Reprodução fiel dos modelos legados de `notebooks_antigos/Modelos_V1.ipynb`
(seção 15 — "Modelos bacias"). Substitui PyCaret por sweep manual.

Pipeline legado:
  1. Por bacia, marca dia como positivo se houve chamado naquele dia.
  2. OW histórico → fill_missing + shift_dt(-24) + agregação diária com janelas 12h/24h
     e funções mean/delta/max/min/sum.
  3. Filtra meses chuvosos (NOV–ABR, remove maio–outubro).
  4. iterative_lower_fence_cuts: remove outliers preservando positivos.
  5. Train/test split aleatório 0.15 + ClusterCentroids undersample (sampling_strategy=0.75).
  6. Sweep: XGBoost, GradBoost, AdaBoost, RandomForest, ExtraTrees, LogisticReg.
  7. Champion = melhor accuracy (sort default do legado).

Reporta DUAS avaliações para revelar a evolução real ao V7:
  - LEGADO:  split aleatório 0.15, métricas de teste do legado.
  - V7-EQUIV: mesmo modelo treinado com split TEMPORAL T_CUT=2023-07-02,
              avaliado com a métrica V7 (precisão/recall/F2 nível ≥1).

Bacias usam coluna pré-mapeada em dados/chamados_enchente_todos.parquet.
"""

import polars as pl
import pandas as pd
import numpy as np
import warnings
from datetime import datetime, date

from sklearn.ensemble import (
    GradientBoostingClassifier, AdaBoostClassifier,
    RandomForestClassifier, ExtraTreesClassifier,
)
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, fbeta_score,
    roc_auc_score,
)
from xgboost import XGBClassifier
from imblearn.under_sampling import ClusterCentroids

warnings.filterwarnings("ignore")
pd.options.mode.chained_assignment = None
RANDOM_STATE = 42
T_CUT = datetime(2023, 7, 2).date()

# ============================================================
# helpers portados do legado
# ============================================================
def fill_missing(df: pd.DataFrame, columns) -> pd.DataFrame:
    out = df.copy()
    for c in columns:
        if out[c].dtype == object:
            continue
        if out[c].isnull().any():
            out[c] = out[c].ffill()
            if out[c].isnull().any():
                out[c] = out[c].bfill()
    return out


def shift_column_up(df: pd.DataFrame, columns, amount: int) -> pd.DataFrame:
    out = df.copy()
    for c in columns:
        out[c] = out[c].shift(-amount)
    out = out.iloc[:-amount].reset_index(drop=True)
    return out


def generate_slices(time_interval, start, end):
    return {f"{i}_{i+time_interval}": (i, i+time_interval)
            for i in range(start, end, time_interval)}


def aggregate_daily(df: pd.DataFrame, agg_config: dict, dt_col="dt") -> pd.DataFrame:
    """
    Reproduz create_agg_dict + groupby(pd.Grouper, freq='D').agg(**dict) do legado.
    Para cada coluna de agg_config(interval, fns), agrega em janelas hora_início:hora_fim.
    """
    df = df.copy()
    df["_date"] = df[dt_col].dt.floor("D")
    df["_hour"] = df[dt_col].dt.hour

    base = pd.DataFrame({"_date": sorted(df["_date"].unique())})
    base = base.set_index("_date")

    for col, (interval, agg_fns) in agg_config.items():
        agg_fns = (agg_fns,) if isinstance(agg_fns, str) else tuple(agg_fns)
        for sk, (h0, h1) in generate_slices(interval, 0, 24).items():
            mask = (df["_hour"] >= h0) & (df["_hour"] < h1)
            sub = df[mask].groupby("_date")[col]
            for fn in agg_fns:
                if fn == "delta":
                    s = sub.max() - sub.min()
                elif fn == "mean":
                    s = sub.mean()
                elif fn == "max":
                    s = sub.max()
                elif fn == "min":
                    s = sub.min()
                elif fn == "sum":
                    s = sub.sum()
                elif fn == "median":
                    s = sub.median()
                else:
                    raise ValueError(f"agg_fn não suportada: {fn}")
                base[f"{col}_{sk}_{fn}"] = s
    return base.reset_index().rename(columns={"_date": "dt"})


def compare_lower_fence_cuts(df, target_column="chamado", min_=False):
    results = []
    for col in df.columns:
        if col == target_column or col == "dt":
            continue
        if df[col].dtype == object:
            continue
        if min_:
            lf = df[col].min()
        else:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lf = q1 - 1.5 * iqr
        below = df[df[col] <= lf]
        results.append({
            "feature": col,
            "threshold": lf,
            "false_cut_count": int((below[target_column] == False).sum()),
            "true_cut_count":  int((below[target_column] == True).sum()),
        })
    return pd.DataFrame(results).sort_values("false_cut_count", ascending=False)


def iterative_lower_fence_cuts(df, target_column="chamado", true_cut_max=0):
    df_c = df.copy()
    prev = df_c.shape[0]
    while True:
        cuts = compare_lower_fence_cuts(df_c, target_column)
        best = None
        for _, row in cuts.iterrows():
            if row["true_cut_count"] <= true_cut_max:
                best = row
                break
        if best is None:
            break
        df_c = df_c[df_c[best["feature"]] > best["threshold"]]
        if df_c.shape[0] == prev:
            break
        prev = df_c.shape[0]
    return df_c.reset_index(drop=True)


# ============================================================
# 1. carrega dados
# ============================================================
print("→ Carregando chamados (dados/chamados_enchente_todos.parquet)…")
df_cham = pl.read_parquet("dados/chamados_enchente_todos.parquet").to_pandas()
df_cham["data"] = pd.to_datetime(df_cham["dt_abertura"]).dt.floor("D")
print(f"  {df_cham.shape[0]} chamados, {df_cham['bacia'].nunique()} bacias")

print("→ Carregando OpenWeather histórico (dados/weather/openweather_history.parquet)…")
df_ow = pl.read_parquet("dados/weather/openweather_history.parquet").to_pandas()
df_ow["dt"] = pd.to_datetime(df_ow["dt"]).dt.tz_localize(None)
print(f"  OW: {df_ow.shape}, range {df_ow['dt'].min()} → {df_ow['dt'].max()}")

# ============================================================
# 2. preparação de features OW histórico (cells 283-285 do legado)
# ============================================================
# fill_missing em todas as colunas numéricas
num_cols_ow = [c for c in df_ow.columns
               if c != "dt" and df_ow[c].dtype != object]
df_ow = fill_missing(df_ow, num_cols_ow)
# remove colunas de texto (weather_main/description/icon) — não são numéricas para agg
df_ow = df_ow.drop(columns=[c for c in df_ow.columns if df_ow[c].dtype == object])
# shift dt 24 posições (1 dia) — alinha features de D-1 ao alvo de D
df_ow = shift_column_up(df_ow, ["dt"], 24)

agg_config_hist = {
    "temp":         (24, ("mean",)),
    "visibility":   (24, ("mean",)),
    "dew_point":    (12, ("delta",)),
    "feels_like":   (24, ("max", "min")),
    "temp_min":     (12, ("delta",)),
    "temp_max":     (12, ("delta",)),
    "pressure":     (24, ("mean",)),
    "humidity":     (24, ("mean",)),
    "wind_speed":   (24, ("mean",)),
    "wind_deg":     (24, ("mean",)),
    "wind_gust":    (24, ("mean",)),
    "rain_1h":      (24, ("sum",)),
    "clouds_all":   (24, ("mean",)),
}
print("→ Agregando OW histórico em janelas diárias…")
df_ow_agg = aggregate_daily(df_ow, agg_config_hist, dt_col="dt")
print(f"  → {df_ow_agg.shape}, range {df_ow_agg['dt'].min().date()} → {df_ow_agg['dt'].max().date()}")
print(f"  features: {df_ow_agg.shape[1]-1}")

# ============================================================
# 3. modelos a sweep (substitui PyCaret compare_models)
# ============================================================
def make_models():
    return {
        "XGBoost": XGBClassifier(
            n_estimators=300, learning_rate=0.05, max_depth=4,
            random_state=RANDOM_STATE, n_jobs=-1, eval_metric="logloss",
            verbosity=0,
        ),
        "GradBoost": GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=3,
            random_state=RANDOM_STATE,
        ),
        "AdaBoost": AdaBoostClassifier(
            n_estimators=200, learning_rate=0.5, random_state=RANDOM_STATE,
        ),
        "RandomForest": RandomForestClassifier(
            n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "ExtraTrees": ExtraTreesClassifier(
            n_estimators=300, random_state=RANDOM_STATE, n_jobs=-1,
        ),
        "LogisticReg": Pipeline([
            ("scaler", StandardScaler()),
            ("clf",    LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
        ]),
    }

def metricas(y_true, y_pred):
    return {
        "acc":       round(accuracy_score(y_true, y_pred), 3),
        "precisao":  round(precision_score(y_true, y_pred, zero_division=0), 3),
        "recall":    round(recall_score(y_true, y_pred, zero_division=0), 3),
        "f1":        round(f1_score(y_true, y_pred, zero_division=0), 3),
        "f2":        round(fbeta_score(y_true, y_pred, beta=2, zero_division=0), 3),
    }

def treinar_avaliar(X_train, y_train, X_test, y_test, sampling_strategy=0.75):
    # undersample com ClusterCentroids
    cc = ClusterCentroids(random_state=RANDOM_STATE, sampling_strategy=sampling_strategy)
    Xr, yr = cc.fit_resample(X_train, y_train)
    rows = []
    for nome, mdl in make_models().items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mdl.fit(Xr, yr)
            yp = mdl.predict(X_test)
            try:
                ypp = mdl.predict_proba(X_test)[:, 1]
                roc = round(roc_auc_score(y_test, ypp), 3)
            except Exception:
                roc = float("nan")
        m = metricas(y_test, yp)
        m["roc_auc"] = roc
        m["modelo"] = nome
        rows.append(m)
    return pd.DataFrame(rows)


# ============================================================
# 4. loop por bacia + municipal: avaliação LEGADO + V7-EQUIV
# ============================================================
# "municipal" = Santo André inteiro, sem filtrar por bacia (modelo da seção 16
# do notebook legado, usado como referência de "modelo decente" do V1).
BACIAS = ["municipal", "meninos", "oratorio", "tamanduatei", "guarara"]
resultados_legado = []
resultados_v7eq   = []

for bacia in BACIAS:
    print(f"\n{'='*80}\n  {'MUNICIPAL (Santo André)' if bacia == 'municipal' else 'BACIA: ' + bacia.upper()}\n{'='*80}")
    # dias com chamado: município inteiro (todos chamados) ou da bacia específica
    if bacia == "municipal":
        dias_pos = set(df_cham["data"].dt.date)
    else:
        dias_pos = set(df_cham[df_cham["bacia"] == bacia]["data"].dt.date)
    print(f"  Dias com chamado: {len(dias_pos)}")

    # constrói df: features OW + flag chamado
    df_b = df_ow_agg.copy()
    df_b["chamado"] = df_b["dt"].dt.date.isin(dias_pos)
    # filtro sazonal: remove maio–outubro (mantém nov–abr)
    df_b = df_b[~df_b["dt"].dt.month.between(5, 10)].copy()
    n_pos = int(df_b["chamado"].sum())
    print(f"  Após filtro sazonal: {df_b.shape[0]} dias, {n_pos} positivos")
    if n_pos < 5:
        print(f"  → poucos positivos, pulando")
        continue

    # iterative_lower_fence_cuts (sem prints de cada cut)
    df_b_cut = iterative_lower_fence_cuts(df_b, target_column="chamado")
    n_pos2 = int(df_b_cut["chamado"].sum())
    print(f"  Após lower fence cuts: {df_b_cut.shape[0]} dias, {n_pos2} positivos")

    feats = [c for c in df_b_cut.columns if c not in ("dt", "chamado")]

    # ===== AVALIAÇÃO LEGADO (split aleatório 0.15) =====
    X = df_b_cut[feats]
    y = df_b_cut["chamado"].astype(int).values
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.15, random_state=RANDOM_STATE,
                                           stratify=y)
    res_leg = treinar_avaliar(Xtr.values, ytr, Xte.values, yte)
    res_leg["bacia"] = bacia
    res_leg["eval"] = "LEGADO_random15"
    resultados_legado.append(res_leg)
    best_leg = res_leg.sort_values("acc", ascending=False).iloc[0]
    print(f"  Champion LEGADO (acc): {best_leg['modelo']:>14}  "
          f"acc={best_leg['acc']:.3f}  prec={best_leg['precisao']:.3f}  "
          f"recall={best_leg['recall']:.3f}  F1={best_leg['f1']:.3f}  F2={best_leg['f2']:.3f}")

    # ===== AVALIAÇÃO V7-EQUIV (split temporal T_CUT) =====
    train = df_b_cut[df_b_cut["dt"] < pd.Timestamp(T_CUT)]
    test  = df_b_cut[df_b_cut["dt"] >= pd.Timestamp(T_CUT)]
    if test["chamado"].sum() == 0:
        print(f"  → test temporal sem positivos, pulando V7-equiv")
        continue
    Xtr_t = train[feats].values
    Xte_t = test[feats].values
    ytr_t = train["chamado"].astype(int).values
    yte_t = test["chamado"].astype(int).values
    res_v7 = treinar_avaliar(Xtr_t, ytr_t, Xte_t, yte_t)
    res_v7["bacia"] = bacia
    res_v7["eval"] = "V7equiv_temporal"
    resultados_v7eq.append(res_v7)
    best_v7 = res_v7.sort_values("f2", ascending=False).iloc[0]
    print(f"  Champion V7eq  (F2):  {best_v7['modelo']:>14}  "
          f"acc={best_v7['acc']:.3f}  prec={best_v7['precisao']:.3f}  "
          f"recall={best_v7['recall']:.3f}  F1={best_v7['f1']:.3f}  F2={best_v7['f2']:.3f}")


# ============================================================
# 5. tabelas finais comparativas
# ============================================================
df_leg = pd.concat(resultados_legado, ignore_index=True) if resultados_legado else pd.DataFrame()
df_v7  = pd.concat(resultados_v7eq, ignore_index=True) if resultados_v7eq else pd.DataFrame()

print(f"\n{'═'*100}")
print("  RESULTADOS LEGADO (random split 0.15) — todos os modelos")
print(f"{'═'*100}")
if df_leg.empty:
    print("  (vazio)")
else:
    cols = ["bacia", "modelo", "acc", "precisao", "recall", "f1", "f2", "roc_auc"]
    print(df_leg[cols].sort_values(["bacia", "acc"], ascending=[True, False]).to_string(index=False))

print(f"\n{'═'*100}")
print("  CHAMPIONS LEGADO (1 por bacia, ranking por acc — método legado)")
print(f"{'═'*100}")
if not df_leg.empty:
    champs_leg = df_leg.sort_values("acc", ascending=False).groupby("bacia").head(1)
    print(champs_leg[["bacia", "modelo", "acc", "precisao", "recall", "f1", "f2", "roc_auc"]].to_string(index=False))

print(f"\n{'═'*100}")
print("  CHAMPIONS V7-EQUIV (mesmo pipeline, split temporal T_CUT, ranking por F2)")
print(f"{'═'*100}")
if not df_v7.empty:
    champs_v7 = df_v7.sort_values("f2", ascending=False).groupby("bacia").head(1)
    print(champs_v7[["bacia", "modelo", "acc", "precisao", "recall", "f1", "f2", "roc_auc"]].to_string(index=False))

# salvar
if not df_leg.empty:
    pl.from_pandas(df_leg).write_parquet("dados/results/resultados_legado_v1_legacy_eval.parquet")
    pl.from_pandas(df_v7).write_parquet("dados/results/resultados_legado_v1_v7eval.parquet")

print(f"\nResultados salvos em dados/results/resultados_legado_v1_*.parquet")
