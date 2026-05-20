"""
Cauda Pesada — maximiza probabilidade em dias de chuva intensa.

Reutiliza a MESMA feature engineering do benchmark_v8 (leak corrigido),
mas com:
  - GradBoost mais expressivo (max_depth 4/6/8, mais árvores, lr menor)
  - Sample weights AGRESSIVOS para forçar aprendizado de eventos
  - Threshold FIXO em 0.1 (não otimiza F1 — deixa a probabilidade respirar)
  - Avaliação focada em proporcionalidade: Spearman rho e prob média por faixa de chuva
"""

import json
import sys
import warnings
from datetime import date, datetime
from functools import reduce
from pathlib import Path

import numpy as np
import polars as pl
from scipy.signal import lfilter
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score, f1_score,
    precision_score, recall_score,
)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)
PLOT_DIR = OUT_DIR / "cauda_pesada_plots"
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

# ─── Feature Engineering (idêntica ao benchmark_v8) ─────────────────────

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

    # API com leak corrigido (shift(1) antes do lfilter)
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

    # Target ordinal
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


# ─── Sample weights AGRESSIVOS ───────────────────────────────────────────

def sample_weights_agressivos(sev):
    """
    severidade 0: peso 0.05 (reduzir drasticamente)
    severidade 1: peso 1.0
    severidade 2: peso 5.0
    severidade 3: peso 20.0
    """
    return np.where(sev == 3, 20.0,
           np.where(sev == 2, 5.0,
           np.where(sev == 1, 1.0, 0.05)))


# ─── Model builders ───────────────────────────────────────────────────────

def mk_gradboost(max_depth):
    def _builder(sw):
        return GradientBoostingClassifier(
            n_estimators=300, learning_rate=0.03,
            max_depth=max_depth, min_samples_leaf=5,
            subsample=0.8, max_features="sqrt",
            random_state=42,
        )
    return _builder


# ─── Avaliação por bacia ─────────────────────────────────────────────────

def avaliar_bacia_cauda_pesada(bacia, sub, max_depth, threshold=0.1):
    t_cut_local = T_CUT
    if bacia == "oratorio":
        ev = sub.filter(pl.col("enchente"))["data"].sort()
        if len(ev) > 0:
            t_cut_local = ev[int(len(ev)*0.75)]

    sub = sub.sort("data")
    train_all = sub.filter(pl.col("data") < t_cut_local)
    test = sub.filter(pl.col("data") >= t_cut_local)

    if train_all.height < 30 or test.height < 5:
        return None

    # treino em TODO o train (sem holdout interno — threshold é fixo)
    X_train = train_all[FEATURES].to_pandas()
    X_test = test[FEATURES].to_pandas()
    sev_train = train_all["severidade"].to_numpy()
    sev_test = test["severidade"].to_numpy()
    max_dia_test = test["max_dia"].to_numpy()

    y_bin_train = (sev_train >= 1).astype(int)
    y_bin_test = (sev_test >= 1).astype(int)

    sw_train = sample_weights_agressivos(sev_train).astype(float)

    mk_clf = mk_gradboost(max_depth)
    clf = mk_clf(sw_train)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        clf.fit(X_train, y_bin_train, sample_weight=sw_train)

    prob_test = clf.predict_proba(X_test)[:, 1]
    pred_test = (prob_test >= threshold).astype(int)

    # Métricas com threshold fixo 0.1
    metrics = {}
    metrics["bacia"] = bacia
    metrics["max_depth"] = max_depth
    metrics["train_n"] = len(sev_train)
    metrics["test_n"] = len(sev_test)
    metrics["threshold"] = threshold

    if y_bin_test.sum() > 0:
        metrics["prauc"] = float(average_precision_score(y_bin_test, prob_test))
        metrics["recall"] = float(recall_score(y_bin_test, pred_test, zero_division=0))
        metrics["prec"] = float(precision_score(y_bin_test, pred_test, zero_division=0))
        metrics["f1"] = float(f1_score(y_bin_test, pred_test, zero_division=0))
    else:
        metrics["prauc"] = 0.0
        metrics["recall"] = 0.0
        metrics["prec"] = 0.0
        metrics["f1"] = 0.0

    # Spearman rho entre max_dia e prob_evento
    corr, pval = spearmanr(max_dia_test, prob_test)
    metrics["spearman_rho"] = float(corr)
    metrics["spearman_p"] = float(pval)

    # Probabilidade média por faixa de chuva
    faixas = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 80), (80, np.inf)]
    for lo, hi in faixas:
        label = f"{lo}-{hi}" if hi < np.inf else f"{lo}+"
        mask = (max_dia_test >= lo) & (max_dia_test < hi)
        if mask.sum() > 0:
            metrics[f"prob_mean_{label}mm"] = float(prob_test[mask].mean())
            metrics[f"count_{label}mm"] = int(mask.sum())
        else:
            metrics[f"prob_mean_{label}mm"] = np.nan
            metrics[f"count_{label}mm"] = 0

    # Guarda arrays para plot agregado
    metrics["_max_dia_test"] = max_dia_test
    metrics["_prob_test"] = prob_test
    metrics["_sev_test"] = sev_test

    return metrics


# ─── Plots ───────────────────────────────────────────────────────────────

def plot_prob_por_faixa(all_results, out_path):
    faixas = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 80), (80, np.inf)]
    labels = [f"{lo}-{hi}" if hi < np.inf else f"{lo}+" for lo, hi in faixas]
    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 5))
    colors = {"4": "tab:blue", "6": "tab:orange", "8": "tab:green"}

    for idx, md in enumerate([4, 6, 8]):
        vals = []
        for lo, hi in faixas:
            label = f"{lo}-{hi}" if hi < np.inf else f"{lo}+"
            # média agregada por faixa
            probs = []
            for r in all_results:
                if r["max_depth"] == md and f"prob_mean_{label}mm" in r:
                    v = r[f"prob_mean_{label}mm"]
                    if not np.isnan(v):
                        probs.append(v)
            vals.append(np.mean(probs) if probs else 0.0)
        ax.bar(x + (idx - 1) * width, vals, width, label=f"max_depth={md}", color=colors[str(md)])

    ax.set_ylabel("Probabilidade média predita")
    ax.set_xlabel("Faixa de chuva (mm)")
    ax.set_title("Probabilidade média por faixa de chuva — Cauda Pesada (threshold=0.1)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.legend()
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Plot salvo: {out_path}")


def plot_scatter_maxdia_prob(all_results, out_path):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
    colors_sev = {0: "#2ca02c", 1: "#ff7f0e", 2: "#d62728", 3: "#9467bd"}

    for ax, md in zip(axes, [4, 6, 8]):
        max_dias = []
        probs = []
        sevs = []
        for r in all_results:
            if r["max_depth"] == md:
                max_dias.extend(r["_max_dia_test"].tolist())
                probs.extend(r["_prob_test"].tolist())
                sevs.extend(r["_sev_test"].tolist())
        max_dias = np.array(max_dias)
        probs = np.array(probs)
        sevs = np.array(sevs)

        for s in [0, 1, 2, 3]:
            mask = sevs == s
            if mask.sum() > 0:
                ax.scatter(max_dias[mask], probs[mask], c=colors_sev[s], label=f"sev={s}", alpha=0.5, s=15)

        ax.set_xlabel("max_dia (mm)")
        ax.set_title(f"max_depth={md}")
        ax.set_ylim(-0.05, 1.05)
        ax.axhline(0.1, color="gray", linestyle="--", linewidth=0.8)

    axes[0].set_ylabel("Probabilidade predita (k=1)")
    axes[2].legend(loc="upper left", fontsize=8)
    fig.suptitle("Scatter: max_dia vs prob predita (colorido por severidade)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Plot salvo: {out_path}")


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    print("Building dataset (mesma feature engineering do benchmark_v8, leak corrigido)...")
    df_ml, estacoes_bacia, p50 = build_dataset()

    if "enchente" not in df_ml.columns:
        df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    all_results = []
    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES)
        if sub.height < 50:
            print(f"  {bacia}: pulado (dados insuficientes)")
            continue

        for md in [4, 6, 8]:
            r = avaliar_bacia_cauda_pesada(bacia, sub, max_depth=md, threshold=0.1)
            if r is None:
                print(f"  {bacia} md={md}: pulado")
                continue
            all_results.append(r)

        print(f"\n{'='*80}")
        print(f"  {bacia.upper()}")
        for md in [4, 6, 8]:
            rs = [rr for rr in all_results if rr["bacia"] == bacia and rr["max_depth"] == md]
            if not rs:
                continue
            r = rs[0]
            print(f"  max_depth={md} | test_n={r['test_n']} | PRAUC={r['prauc']:.3f} | "
                  f"Recall={r['recall']:.3f} | Prec={r['prec']:.3f} | F1={r['f1']:.3f} | "
                  f"Spearman ρ={r['spearman_rho']:.3f}")
            print(f"    Prob média por faixa:")
            for lo, hi in [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 80), (80, np.inf)]:
                label = f"{lo}-{hi}" if hi < np.inf else f"{lo}+"
                print(f"      {label:>6}mm: {r.get(f'prob_mean_{label}mm', np.nan):.3f}  (n={r.get(f'count_{label}mm', 0)})")

    # Plots agregados
    print(f"\n{'='*80}")
    print("Gerando plots...")
    plot_prob_por_faixa(all_results, PLOT_DIR / "prob_por_faixa_cauda_pesada.png")
    plot_scatter_maxdia_prob(all_results, PLOT_DIR / "scatter_maxdia_prob_cauda_pesada.png")

    # Resumo agregado por max_depth
    print(f"\n{'='*80}")
    print("RESUMO AGREGADO POR MAX_DEPTH (média entre bacias)")
    print(f"{'max_depth':>10} {'PRAUC':>7} {'Recall':>7} {'Prec':>7} {'F1':>7} {'Spearman':>10}")
    for md in [4, 6, 8]:
        rs = [r for r in all_results if r["max_depth"] == md]
        if not rs:
            continue
        print(f"{md:>10} {np.mean([r['prauc'] for r in rs]):>7.3f} "
              f"{np.mean([r['recall'] for r in rs]):>7.3f} "
              f"{np.mean([r['prec'] for r in rs]):>7.3f} "
              f"{np.mean([r['f1'] for r in rs]):>7.3f} "
              f"{np.mean([r['spearman_rho'] for r in rs]):>10.3f}")

    print(f"\n{'='*80}")
    print("PROBABILIDADE MÉDIA POR FAIXA DE CHUVA (agregado entre bacias)")
    faixas = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 80), (80, np.inf)]
    for md in [4, 6, 8]:
        print(f"\n  max_depth={md}")
        for lo, hi in faixas:
            label = f"{lo}-{hi}" if hi < np.inf else f"{lo}+"
            probs = [r[f"prob_mean_{label}mm"] for r in all_results if r["max_depth"] == md and not np.isnan(r.get(f"prob_mean_{label}mm", np.nan))]
            print(f"    {label:>6}mm: {np.mean(probs) if probs else np.nan:.3f}")

    # Perguntas do usuário
    print(f"\n{'='*80}")
    print("RESPOSTAS ÀS PERGUNTAS:")
    spearmans = {}
    for md in [4, 6, 8]:
        rs = [r for r in all_results if r["max_depth"] == md]
        if rs:
            spearmans[md] = np.mean([r["spearman_rho"] for r in rs])
    if spearmans:
        best_md_spearman = max(spearmans, key=spearmans.get)
        print(f"  - Melhor Spearman rho: max_depth={best_md_spearman} (ρ={spearmans[best_md_spearman]:.3f})")

    prop_scores = {}
    for md in [4, 6, 8]:
        rs = [r for r in all_results if r["max_depth"] == md]
        probs_20_30 = [r["prob_mean_20-30mm"] for r in rs if not np.isnan(r.get("prob_mean_20-30mm", np.nan))]
        if probs_20_30:
            # quão próximo de 1.0
            prop_scores[md] = np.mean(probs_20_30)
    if prop_scores:
        best_md_prop = max(prop_scores, key=prop_scores.get)
        print(f"  - Melhor proporcionalidade (20-30mm mais próxima de 1.0): max_depth={best_md_prop} (prob={prop_scores[best_md_prop]:.3f})")

    for md in [4, 6, 8]:
        rs = [r for r in all_results if r["max_depth"] == md]
        probs_50_80 = [r["prob_mean_50-80mm"] for r in rs if not np.isnan(r.get("prob_mean_50-80mm", np.nan))]
        probs_80 = [r["prob_mean_80+mm"] for r in rs if not np.isnan(r.get("prob_mean_80+mm", np.nan))]
        if probs_50_80 or probs_80:
            max_prob = max((probs_50_80 + probs_80) if (probs_50_80 and probs_80) else (probs_50_80 or probs_80))
            print(f"  - max_depth={md}: prob máx em faixa intensa (50-80mm ou 80+mm) = {max_prob:.3f}")

    print(f"\n{'='*80}")
    print("Done.")


if __name__ == "__main__":
    main()
