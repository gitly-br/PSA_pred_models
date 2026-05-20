"""
XGBoost Monotônico — leak-corrected feature engineering,
com e sem monotone_constraints.

Todas as features que representam chuva recebem constraint=1
para forçar relação monotônica positiva com a probabilidade.
"""

import json
import warnings
from datetime import date, datetime
from functools import reduce
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.signal import lfilter
from scipy.stats import spearmanr
from sklearn.metrics import (
    average_precision_score, f1_score,
    precision_score, recall_score,
)
from xgboost import XGBClassifier

WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)
PLOT_DIR = WORKDIR / "dados" / "plots"
PLOT_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
JANELAS_H = [1, 3, 6, 24, 48, 72]
LIMS = {1: 20, 3: 30, 6: 45, 24: 60, 48: 80, 72: 100}
LOOKBACK_H = 72
T_CUT = datetime(2023, 7, 2).date()
K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0

FEATURES = (
    [f"api_{int(k*100):03d}" for k in K_APIS]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

# ─── monotone_constraints ────────────────────────────────────────────────
# 1 = monotônico positivo, 0 = sem restrição
RAIN_FEATURES = {
    "api_070", "api_085", "api_095",
    *(f"acc_6h_lag_{i}" for i in range(1, 13)),
    "max_day_lag1", "max_day_lag2", "max_day_lag3",
    "mean_day_lag1",
    "n_chovendo_max_lag1",
    "pico_1h_lag1",
    "horas_intensas_lag1",
    "acum_7d", "acum_30d",
}
MONOTONE_CONSTRAINTS = {f: 1 if f in RAIN_FEATURES else 0 for f in FEATURES}

# ─── Feature Engineering ────────────────────────────────────────────────

def build_dataset():
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        estacoes_bacia = json.load(f)

    partes = []
    for bacia in estacoes_bacia:
        df = pl.read_parquet(WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet")
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

    # confirmados por chuva na bacia
    df_chamados_raw = pl.read_parquet(WORKDIR / "dados" / "chamados_por_bacia.parquet")
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

    # diários
    df_h = df_chuva_h.with_columns([
        pl.col("hora").dt.date().alias("data"),
        (pl.col("hora").dt.hour() // 6).alias("bloco_6h"),
    ])
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
        .with_columns([pl.col(c).fill_null(0) for c in ["bloco_0","bloco_1","bloco_2","bloco_3"]])
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
    )

    # ── API com leak corrigido (shift(1) antes do lfilter) ──
    _api_parts = []
    for _bacia in df_diario["bacia"].unique().to_list():
        _sub = df_diario.filter(pl.col("bacia") == _bacia).sort("data")
        _vals = _sub["max_dia"].shift(1).fill_null(0).to_numpy()
        cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS:
            cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
        _api_parts.append(pl.DataFrame(cols))
    df_api = pl.concat(_api_parts)

    df_feat = df_feat.join(df_api, on=["data", "bacia"])
    df_feat = df_feat.select(["data", "bacia"] + FEATURES)

    # ── Target ordinal ──
    _chamados_diario = (
        df_chamados_conf
        .with_columns(pl.col("dt_abertura").dt.date().alias("data"))
        .group_by(["data","bacia"]).len().rename({"len":"n_chamados"})
    )
    _ext = pl.read_csv(WORKDIR / "dados" / "alagamentos_bacias.csv").with_columns(pl.col("dt").str.to_date())
    _df_ext = _ext.select([
        pl.col("dt").alias("data"),
        pl.col("bacia_tamanduatei").alias("tamanduatei"),
        pl.col("bacia_guarara").alias("guarara"),
        pl.col("bacia_oratorio").alias("oratorio"),
        pl.col("bacia_meninos").alias("meninos"),
    ]).unpivot(index="data", variable_name="bacia", value_name="flag").filter(pl.col("flag") > 0).select([
        "data","bacia", pl.lit(True).alias("pos_externo"),
    ])

    _bacias = list(estacoes_bacia.keys())
    _datas = pl.date_range(date(2016,1,1), date(2025,12,31), interval="1d", eager=True).to_list()
    _cal = pl.DataFrame({
        "data": pl.Series([d for d in _datas for _ in _bacias], dtype=pl.Date),
        "bacia": [b for _ in _datas for b in _bacias],
    })
    _max_dia = df_diario.select(["data","bacia","max_dia"])
    _chamados_max = _chamados_diario.join(_max_dia, on=["data","bacia"], how="left").filter(pl.col("data") < T_CUT)
    P50_BY_BACIA = {}
    for _b in _bacias:
        _s = _chamados_max.filter(pl.col("bacia") == _b)
        P50_BY_BACIA[_b] = float(_s["max_dia"].quantile(0.5)) if _s.height > 0 else 95.0

    df_ml = (
        _cal
        .join(_chamados_diario, on=["data","bacia"], how="left")
        .join(_df_ext, on=["data","bacia"], how="left")
        .join(_max_dia, on=["data","bacia"], how="left")
        .with_columns([
            pl.col("n_chamados").fill_null(0),
            pl.col("pos_externo").fill_null(False),
        ])
    )
    _p50_expr = pl.col("bacia").replace_strict(P50_BY_BACIA, return_dtype=pl.Float64)
    df_ml = df_ml.with_columns(
        pl.when((pl.col("n_chamados") >= 5) | pl.col("pos_externo")).then(3)
        .when(pl.col("n_chamados").is_between(2,4)).then(2)
        .when((pl.col("n_chamados") == 1) | ((pl.col("n_chamados") == 0) & (pl.col("max_dia") > _p50_expr))).then(1)
        .otherwise(0)
        .alias("severidade")
    )
    df_ml = df_ml.join(df_feat, on=["data","bacia"], how="left").filter(
        pl.col("data").dt.month().is_in(MESES_CHUVOSOS)
    ).sort(["bacia","data"])

    return df_ml, estacoes_bacia, P50_BY_BACIA


# ─── Treinamento XGBoost ─────────────────────────────────────────────

def mk_xgboost(monotone: dict | None, scale_pos_weight: float) -> XGBClassifier:
    kwargs = dict(
        n_estimators=200,
        learning_rate=0.05,
        max_depth=2,
        min_child_weight=10,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=4,
        eval_metric="logloss",
    )
    if scale_pos_weight > 0:
        kwargs["scale_pos_weight"] = scale_pos_weight
    if monotone:
        # XGBClassifier aceita dict com nome de feature → int
        kwargs["monotone_constraints"] = monotone
    return XGBClassifier(**kwargs)


def treinar_bacia(bacia: str, sub: pl.DataFrame) -> dict | None:
    t_cut_local = T_CUT
    if bacia == "oratorio":
        ev = sub.filter(pl.col("enchente"))["data"].sort()
        if len(ev) > 0:
            t_cut_local = ev[int(len(ev) * 0.75)]

    sub = sub.sort("data")
    train = sub.filter(pl.col("data") < t_cut_local)
    test = sub.filter(pl.col("data") >= t_cut_local)

    if train.height < 30 or test.height < 5:
        return None

    X_train = train[FEATURES].to_pandas()
    X_test = test[FEATURES].to_pandas()
    sev_train = train["severidade"].to_numpy()
    sev_test = test["severidade"].to_numpy()
    max_dia_test = test["max_dia"].to_numpy()

    resultados = {"bacia": bacia, "train_n": len(sev_train), "test_n": len(sev_test)}
    resultados["sev_dist_train"] = {int(s): int((sev_train == s).sum()) for s in [0, 1, 2, 3]}
    resultados["sev_dist_test"] = {int(s): int((sev_test == s).sum()) for s in [0, 1, 2, 3]}

    probs_test = {"mono": {}, "free": {}}

    for k in [1, 2, 3]:
        y_bin_train = (sev_train >= k).astype(int)
        y_bin_test = (sev_test >= k).astype(int)

        n_neg = (y_bin_train == 0).sum()
        n_pos = (y_bin_train == 1).sum()
        spw = n_neg / n_pos if n_pos > 0 else 1.0

        for modo, mono in [("mono", MONOTONE_CONSTRAINTS), ("free", None)]:
            clf = mk_xgboost(monotone=mono, scale_pos_weight=spw)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                clf.fit(X_train, y_bin_train)
            prob = clf.predict_proba(X_test)[:, 1]
            probs_test[modo][k] = prob

            resultados[f"prauc_test_k{k}_{modo}"] = (
                float(average_precision_score(y_bin_test, prob)) if y_bin_test.sum() > 0 else 0.0
            )
            resultados[f"recall_test_k{k}_{modo}"] = (
                float(recall_score(y_bin_test, (prob >= 0.5).astype(int), zero_division=0)) if y_bin_test.sum() > 0 else 0.0
            )
            resultados[f"prec_test_k{k}_{modo}"] = (
                float(precision_score(y_bin_test, (prob >= 0.5).astype(int), zero_division=0)) if y_bin_test.sum() > 0 else 0.0
            )
            resultados[f"f1_test_k{k}_{modo}"] = (
                float(f1_score(y_bin_test, (prob >= 0.5).astype(int), zero_division=0)) if y_bin_test.sum() > 0 else 0.0
            )

    # ── Spearman rho no test set ──
    for modo in ["mono", "free"]:
        prob_evento = probs_test[modo][1]  # P(severidade >= 1)
        corr, pval = spearmanr(max_dia_test, prob_evento)
        resultados[f"spearman_rho_{modo}"] = float(corr)
        resultados[f"spearman_p_{modo}"] = float(pval)

    # Guardar arrays para plot agregado
    resultados["max_dia_test"] = max_dia_test
    resultados["prob_mono"] = probs_test["mono"][1]
    resultados["prob_free"] = probs_test["free"][1]

    return resultados


# ─── Plot ──────────────────────────────────────────────────────────────

def plot_prob_por_faixa(todos: list[dict]):
    def _agg_prob(arr_max_dia, arr_prob):
        faixas = [(0, 5), (5, 15), (15, 30), (30, 50), (50, 80), (80, np.inf)]
        rotulos = ["0-5", "5-15", "15-30", "30-50", "50-80", "80+"]
        medias = []
        for lo, hi in faixas:
            mask = (arr_max_dia >= lo) & (arr_max_dia < hi)
            medias.append(float(arr_prob[mask].mean()) if mask.sum() > 0 else np.nan)
        return rotulos, medias

    max_dia_all = np.concatenate([r["max_dia_test"] for r in todos])
    prob_mono_all = np.concatenate([r["prob_mono"] for r in todos])
    prob_free_all = np.concatenate([r["prob_free"] for r in todos])

    labels, means_mono = _agg_prob(max_dia_all, prob_mono_all)
    _, means_free = _agg_prob(max_dia_all, prob_free_all)

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x - width/2, means_mono, width, label="XGBoost monotônico", color="steelblue")
    ax.bar(x + width/2, means_free, width, label="XGBoost livre", color="coral")
    ax.set_xlabel("Faixa de chuva max_dia (mm)")
    ax.set_ylabel("Prob. média P(sev ≥ 1)")
    ax.set_title("Probabilidade por faixa de chuva (test set, todas bacias)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.set_ylim(0, max(max(means_mono), max(means_free)) * 1.2 if any(np.isfinite([*means_mono, *means_free])) else 1.0)
    fig.tight_layout()
    out = PLOT_DIR / "xgboost_prob_por_faixa_chuva.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"\nPlot salvo em: {out}")


# ─── Main ──────────────────────────────────────────────────────────────

def main():
    print("Building dataset with leak-corrected api_* ...")
    df_ml, estacoes_bacia, p50 = build_dataset()

    if "enchente" not in df_ml.columns:
        df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    todos = []
    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES)
        r = treinar_bacia(bacia, sub)
        if r is None:
            print(f"  {bacia}: pulado (dados insuficientes)")
            continue
        todos.append(r)

    # ── Imprimir métricas ──
    print("\n" + "=" * 90)
    print(f"{'Bacia':<14}  {'k':>2}  {'Modo':<6}  {'PRAUC':>6}  {'Recall':>7}  {'Prec':>6}  {'F1':>5}  {'Spearman ρ':>10}")
    print("=" * 90)
    for r in todos:
        bacia = r["bacia"]
        for modo, modo_label in [("mono", "mono"), ("free", "free")]:
            for k in [1, 2, 3]:
                print(
                    f"{bacia:<14}  {k:>2}  {modo_label:<6}  "
                    f"{r[f'prauc_test_k{k}_{modo}']:>6.3f}  "
                    f"{r[f'recall_test_k{k}_{modo}']:>7.3f}  "
                    f"{r[f'prec_test_k{k}_{modo}']:>6.3f}  "
                    f"{r[f'f1_test_k{k}_{modo}']:>5.3f}"
                )
            print(f"{'':>14}     {modo_label:<6}  {'':>6}  {'':>7}  {'':>6}  {'':>5}  {r[f'spearman_rho_{modo}']:>10.3f}  (p={r[f'spearman_p_{modo}']:.3e})")
            print("-" * 90)

    # ── Resumo agregado ──
    print("\n--- RESUMO AGREGADO (média por bacia) ---")
    for modo in ["mono", "free"]:
        print(f"\nXGBoost {'monotônico' if modo == 'mono' else 'livre'}:")
        for k in [1, 2, 3]:
            praucs = [r[f"prauc_test_k{k}_{modo}"] for r in todos]
            recalls = [r[f"recall_test_k{k}_{modo}"] for r in todos]
            precs = [r[f"prec_test_k{k}_{modo}"] for r in todos]
            f1s = [r[f"f1_test_k{k}_{modo}"] for r in todos]
            print(f"  k={k}:  PRAUC={np.mean(praucs):.3f}  Recall={np.mean(recalls):.3f}  Prec={np.mean(precs):.3f}  F1={np.mean(f1s):.3f}")
        rhos = [r[f"spearman_rho_{modo}"] for r in todos]
        print(f"  Spearman ρ médio = {np.mean(rhos):.3f}")

    # ── Melhor versão ──
    prauc_mono = np.mean([r["prauc_test_k1_mono"] for r in todos])
    prauc_free = np.mean([r["prauc_test_k1_free"] for r in todos])
    rho_mono = np.mean([r["spearman_rho_mono"] for r in todos])
    rho_free = np.mean([r["spearman_rho_free"] for r in todos])
    print(f"\nMelhor PRAUC (k=1): {'MONOTÔNICO' if prauc_mono > prauc_free else 'LIVRE'} ({prauc_mono:.3f} vs {prauc_free:.3f})")
    print(f"Melhor Spearman ρ:  {'MONOTÔNICO' if rho_mono > rho_free else 'LIVRE'} ({rho_mono:.3f} vs {rho_free:.3f})")

    plot_prob_por_faixa(todos)


if __name__ == "__main__":
    main()
