"""
Análise de proporcionalidade chuva-probabilidade (benchmark_v8, GradBoost, k=1).

Reusa a mesma feature engineering e corte temporal do _run_benchmark_v8.py
para treinar um modelo GradBoost binário (severidade >= 1) e avaliar se a
probabilidade predita cresce de forma razoável com a chuva observada (max_dia).
"""

import importlib.util
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import polars as pl
from scipy.stats import spearmanr

# ─── Importar módulo do benchmark_v8 dinamicamente ───────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_BM_PATH = _SCRIPT_DIR / "_run_benchmark_v8.py"

_spec = importlib.util.spec_from_file_location("_run_benchmark_v8", _BM_PATH)
_bm = importlib.util.module_from_spec(_spec)
sys.modules["_run_benchmark_v8"] = _bm
_spec.loader.exec_module(_bm)

build_dataset = _bm.build_dataset
FEATURES = _bm.FEATURES
T_CUT = _bm.T_CUT
mk_gradboost = _bm.mk_gradboost
w_fit_m3 = _bm.w_fit_m3

# ─── Configuração de saída ───────────────────────────────────────────────
WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# Faixas de chuva (max_dia em mm)
BINS = [0, 5, 10, 20, 30, 50, 80, 120, float("inf")]
LABELS = ["0-5", "5-10", "10-20", "20-30", "30-50", "50-80", "80-120", "120+"]

# Cores para severidade real no scatter
SEV_COLORS = {0: "#2ca02c", 1: "#ffcc00", 2: "#ff7f0e", 3: "#d62728"}
SEV_LABELS = {0: "0", 1: "1", 2: "2", 3: "3"}


def treinar_e_predizer(bacia: str, sub: pl.DataFrame):
    """Treina GradBoost k=1 em todo o train e retorna (test_df, probs_test)."""
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

    y_bin_train = (sev_train >= 1).astype(int)
    sw_train = w_fit_m3(sev_train).astype(float)

    clf = mk_gradboost(0.0)
    clf.fit(X_train, y_bin_train, sample_weight=sw_train)

    probs_test = clf.predict_proba(X_test)[:, 1]

    # Montar DataFrame de resultado para esta bacia
    df = test.select(["data", "bacia", "max_dia", "severidade"]).to_pandas()
    df["prob_predita"] = probs_test
    df["positivo"] = (df["severidade"] >= 1).astype(int)

    return df


def calcular_faixas(df: pd.DataFrame):
    """Calcula estatísticas por faixa de max_dia."""
    df = df.copy()
    df["faixa"] = pd.cut(df["max_dia"], bins=BINS, labels=LABELS, right=False)

    res = (
        df.groupby("faixa", observed=True)
        .agg(
            n_amostras=("prob_predita", "count"),
            prob_media=("prob_predita", "mean"),
            n_positivos=("positivo", "sum"),
            taxa_positivos=("positivo", "mean"),
        )
        .reset_index()
    )
    return res


def plot_barras_por_bacia(resultados: dict[str, pd.DataFrame]):
    """Gráfico de barras: prob predita vs taxa real de positivos, por bacia."""
    bacias = list(resultados.keys())
    n = len(bacias)
    fig, axes = plt.subplots(n, 1, figsize=(10, 3 * n), sharex=True, squeeze=False)
    axes = axes.flatten()

    for ax, bacia in zip(axes, bacias):
        r = resultados[bacia]
        x = np.arange(len(r))
        width = 0.35

        bars1 = ax.bar(x - width / 2, r["prob_media"], width, label="Prob. predita (modelo)", color="#1f77b4")
        bars2 = ax.bar(x + width / 2, r["taxa_positivos"], width, label="Taxa real de positivos", color="#ff7f0e")

        ax.set_ylabel("Probabilidade / Taxa")
        ax.set_title(f"{bacia.upper()}")
        ax.set_xticks(x)
        ax.set_xticklabels(r["faixa"], rotation=45, ha="right")
        ax.legend(loc="upper left", fontsize=8)
        ax.set_ylim(0, 1.05)

        # Anotar diferença (predita - real)
        for i, (p, t) in enumerate(zip(r["prob_media"], r["taxa_positivos"])):
            diff = p - t
            color = "green" if abs(diff) < 0.1 else "red" if abs(diff) > 0.3 else "orange"
            ax.annotate(f"Δ={diff:+.2f}", xy=(i, max(p, t) + 0.03), ha="center", fontsize=7, color=color)

    fig.suptitle("Proporcionalidade Chuva → Probabilidade (k=1)\nAzul = prob. predita | Laranja = taxa real de positivos", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out_path = OUT_DIR / "analise_prob_chuva_barras.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Figura barras salva em: {out_path}")
    return out_path


def plot_scatter_por_bacia(dfs: dict[str, pd.DataFrame]):
    """Scatter: max_dia vs prob predita, colorido por severidade real."""
    bacias = list(dfs.keys())
    n = len(bacias)
    fig, axes = plt.subplots(n, 1, figsize=(10, 3 * n), sharex=True, squeeze=False)
    axes = axes.flatten()

    for ax, bacia in zip(axes, bacias):
        df = dfs[bacia]
        for sev in [0, 1, 2, 3]:
            sub = df[df["severidade"] == sev]
            ax.scatter(sub["max_dia"], sub["prob_predita"], c=SEV_COLORS[sev], label=f"Sev {sev}", alpha=0.6, edgecolors="none", s=30)

        ax.set_ylabel("Prob. predita (k=1)")
        ax.set_title(f"{bacia.upper()}")
        ax.set_ylim(-0.05, 1.05)
        ax.legend(title="Severidade real", loc="upper right", fontsize=7)
        ax.axhline(0, color="gray", linestyle="--", linewidth=0.5)

    axes[-1].set_xlabel("max_dia (mm)")
    fig.suptitle("Scatter: max_dia vs prob. predita (colorido por severidade real)", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    out_path = OUT_DIR / "analise_prob_chuva_scatter.png"
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Figura scatter salva em: {out_path}")
    return out_path


def main():
    print("Carregando dataset (mesma feature engineering do benchmark_v8)...")
    df_ml, estacoes_bacia, p50 = build_dataset()

    if "enchente" not in df_ml.columns:
        df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    resultados_faixa: dict[str, pd.DataFrame] = {}
    resultados_df: dict[str, pd.DataFrame] = {}
    spearman_results: dict[str, tuple[float, float]] = {}
    superestimacao: dict[str, list[tuple[str, float]]] = {}
    subestimacao: dict[str, list[tuple[str, float]]] = {}

    print("\n" + "=" * 80)
    print("Análise de proporcionalidade chuva → probabilidade (k=1)")
    print("=" * 80)

    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES)
        df_test = treinar_e_predizer(bacia, sub)
        if df_test is None:
            print(f"\n  {bacia.upper()}: pulado (dados insuficientes)")
            continue

        resultados_df[bacia] = df_test

        # Spearman entre max_dia e prob predita (test set)
        rho, pval = spearmanr(df_test["max_dia"], df_test["prob_predita"])
        spearman_results[bacia] = (float(rho), float(pval))

        # Faixas
        res = calcular_faixas(df_test)
        resultados_faixa[bacia] = res

        # Identificar superestimação / subestimação
        res["delta"] = res["prob_media"] - res["taxa_positivos"]
        sup = res.loc[res["delta"] > 0].sort_values("delta", ascending=False)
        sub = res.loc[res["delta"] < 0].sort_values("delta", ascending=True)
        superestimacao[bacia] = list(zip(sup["faixa"].astype(str), sup["delta"])) if not sup.empty else []
        subestimacao[bacia] = list(zip(sub["faixa"].astype(str), sub["delta"])) if not sub.empty else []

        print(f"\n  {bacia.upper()} — test_n={len(df_test)}")
        print(f"  Spearman rho = {rho:.3f} (p={pval:.3e})")
        print(f"  Faixa com maior superestimação: {superestimacao[bacia][0] if superestimacao[bacia] else 'N/A'}")
        print(f"  Faixa com maior subestimação:   {subestimacao[bacia][0] if subestimacao[bacia] else 'N/A'}")

    # ─── Tabelas agregadas ────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("TABELA: Probabilidade média predita por faixa de chuva")
    print("=" * 80)
    tabela_prob = pd.DataFrame({b: r.set_index("faixa")["prob_media"] for b, r in resultados_faixa.items()})
    print(tabela_prob.to_string())

    print("\n" + "=" * 80)
    print("TABELA: Taxa real de positivos (severidade >= 1) por faixa de chuva")
    print("=" * 80)
    tabela_taxa = pd.DataFrame({b: r.set_index("faixa")["taxa_positivos"] for b, r in resultados_faixa.items()})
    print(tabela_taxa.to_string())

    print("\n" + "=" * 80)
    print("TABELA: Número de amostras por faixa de chuva")
    print("=" * 80)
    tabela_n = pd.DataFrame({b: r.set_index("faixa")["n_amostras"] for b, r in resultados_faixa.items()})
    print(tabela_n.to_string())

    print("\n" + "=" * 80)
    print("TABELA: Número de positivos por faixa de chuva")
    print("=" * 80)
    tabela_pos = pd.DataFrame({b: r.set_index("faixa")["n_positivos"] for b, r in resultados_faixa.items()})
    print(tabela_pos.to_string())

    # ─── Gráficos ─────────────────────────────────────────────────────────
    print("\nGerando gráficos...")
    plot_barras_por_bacia(resultados_faixa)
    plot_scatter_por_bacia(resultados_df)

    # ─── Conclusão agregada ───────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("CONCLUSÃO AGREGADA")
    print("=" * 80)
    for bacia in sorted(resultados_faixa.keys()):
        rho, pval = spearman_results[bacia]
        sup_faixa, sup_delta = superestimacao[bacia][0] if superestimacao[bacia] else ("N/A", 0.0)
        sub_faixa, sub_delta = subestimacao[bacia][0] if subestimacao[bacia] else ("N/A", 0.0)
        print(f"  {bacia.upper()}:")
        print(f"    Spearman rho = {rho:.3f}")
        print(f"    Maior superestimação: {sup_faixa} (Δ={sup_delta:+.3f})")
        print(f"    Maior subestimação:   {sub_faixa} (Δ={sub_delta:+.3f})")

    # Salvar resultados em Parquet para análise posterior
    df_faixa_all = pd.concat(
        [r.assign(bacia=b) for b, r in resultados_faixa.items()],
        ignore_index=True,
    )
    out_parquet = OUT_DIR / "analise_prob_chuva_faixas.parquet"
    df_faixa_all.to_parquet(out_parquet)
    print(f"\nResultados por faixa salvos em: {out_parquet}")

    # Conclusão textual
    print("\n" + "=" * 80)
    print("INTERPRETAÇÃO")
    print("=" * 80)
    rhos = [spearman_results[b][0] for b in resultados_faixa.keys()]
    rho_medio = np.mean(rhos)
    print(f"  Spearman rho médio entre bacias: {rho_medio:.3f}")
    if rho_medio > 0.5:
        print("  → Correlação positiva moderada/forte: o modelo tende a atribuir maior")
        print("    probabilidade em dias de maior chuva. Comportamento proporcional razoável.")
    elif rho_medio > 0.3:
        print("  → Correlação positiva fraca a moderada: há alguma proporcionalidade,")
        print("    mas com espaço para melhoria (modelo pode ser muito conservador).")
    else:
        print("  → Correlação muito fraca: o modelo NÃO está respondendo de forma")
        print("    proporcional à chuva. Precisa de ajustes significativos.")

    # Checar se há faixas onde o modelo é claramente não-proporcional
    problemas = []
    for bacia, res in resultados_faixa.items():
        for _, row in res.iterrows():
            if row["faixa"] in ["0-5", "5-10"] and row["prob_media"] > 0.30:
                problemas.append(f"{bacia} na faixa {row['faixa']}: prob={row['prob_media']:.2f}")
            if row["faixa"] in ["80-120", "120+"] and row["prob_media"] < 0.30:
                problemas.append(f"{bacia} na faixa {row['faixa']}: prob={row['prob_media']:.2f}")

    if problemas:
        print("\n  ALERTAS DE NÃO-PROPORCIONALIDADE:")
        for p in problemas:
            print(f"    - {p}")
    else:
        print("\n  Nenhum alerta grave de não-proporcionalidade detectado.")

    print("\nDone.")


if __name__ == "__main__":
    main()
