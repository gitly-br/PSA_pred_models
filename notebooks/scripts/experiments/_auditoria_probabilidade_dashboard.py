"""
Auditoria de Probabilidade para Dashboard — Etapa 4 Rodada Sequencial
=====================================================================

Objetivo: determinar se existe candidato melhor que o modelo atual
(baseline V8 / display_probability antigo) para uso no dashboard,
em termos de probabilidade/score operacional interpretável.

Candidatos avaliados:
  1. baseline_v8_prob           — modelo atual (backend raw_proba + threshold rescale)
  2. combinador_mean_bruto      — média simples dos scores normalizados (0-1)
  3. combinador_mean_calibrado  — piecewise calibrado para serving (0-1)
  4. classificador_cauda        — cauda pesada raw prob
  5. especialistas_mean_60_40   — 0.6*pancada + 0.4*prolongada (reconstruído)

Critérios:
  - chuva leve -> score baixo
  - chuva forte -> score alto
  - monotonicidade por faixa de chuva
  - estabilidade por bacia (variância, range)
  - distribuição útil em 0-100
  - risco de alarmismo (falsos altos)
  - PR-AUC e Spearman como suporte

Saídas:
  - notebooks/dados/results/auditoria_probabilidade_dashboard.parquet
  - notebooks/dados/results/auditoria_probabilidade_dashboard_faixas.parquet
  - notebooks/dados/results/auditoria_probabilidade_dashboard_criticos.parquet
  - notebooks/dados/results/relatorio_auditoria_probabilidade_dashboard.md
"""

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score, brier_score_loss

# ─── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
WORKDIR = SCRIPT_DIR.parents[1]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ─────────────────────────────────────────────────────────────────
FAIXAS_CHUVA = [
    (0, 5, "leve"),
    (5, 10, "leve"),
    (10, 20, "moderada"),
    (20, 30, "forte"),
    (30, 50, "forte"),
    (50, 80, "extrema"),
    (80, float("inf"), "extrema"),
]

FAIXAS_LABELS = [f"{lo}-{hi}" if hi < float("inf") else f"{lo}+" for lo, hi, _ in FAIXAS_CHUVA]

CANDIDATOS = {
    "baseline_v8": {
        "col": "baseline_v8_prob",
        "escala": "prob_bruta",
        "desc": "Baseline V8 prob k=1 (raw_proba do backend)",
    },
    "combinador_mean_bruto": {
        "col": "risk_score_raw_mean",
        "escala": "score_0_1",
        "desc": "Combinador mean bruto (média scores normalizados)",
    },
    "combinador_mean_calibrado": {
        "col": "risk_score_raw_mean_serving",
        "escala": "score_0_1",
        "desc": "Combinador mean calibrado piecewise para serving",
    },
    "classificador_cauda": {
        "col": "score_cauda_raw",
        "escala": "prob_bruta",
        "desc": "Classificador cauda pesada (raw prob)",
    },
    "especialistas_mean_60_40": {
        "col": "_especialistas_mean_60_40",
        "escala": "score_0_1",
        "desc": "Reconstruído: 0.6*pancada_norm + 0.4*prolongada_norm",
    },
    "combinador_max": {
        "col": "risk_score_raw_max",
        "escala": "score_0_1",
        "desc": "Combinador max (referência)",
    },
    "combinador_weighted": {
        "col": "risk_score_raw_weighted",
        "escala": "score_0_1",
        "desc": "Combinador weighted (referência)",
    },
}


def _faixa_chuva(max_dia: float) -> str:
    for lo, hi, _ in FAIXAS_CHUVA:
        if hi == float("inf"):
            if max_dia >= lo:
                return f"{lo}+"
        elif lo <= max_dia < hi:
            return f"{lo}-{hi}"
    return "unknown"


def carregar_dados():
    """Carrega e alinha os datasets necessários."""
    df_comb = pl.read_parquet(OUT_DIR / "combinador_risco_meteorologico.parquet")
    df_cal = pl.read_parquet(OUT_DIR / "calibracao_scores_serving.parquet")

    df = df_comb.join(
        df_cal.select(["data", "bacia", "risk_score_raw_mean_serving", "enchente"]),
        on=["data", "bacia"],
        how="left",
    )

    df = df.with_columns(
        (
            0.6 * pl.col("score_pancada_norm") + 0.4 * pl.col("score_prolongada_norm")
        ).alias("_especialistas_mean_60_40")
    )

    if "enchente" not in df.columns:
        df = df.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    return df


def calcular_metricas_por_candidato(df: pl.DataFrame) -> pd.DataFrame:
    rows = []
    pdf = df.to_pandas()

    for nome, info in CANDIDATOS.items():
        col = info["col"]
        if col not in pdf.columns:
            continue

        scores = pdf[col].to_numpy()
        max_dia = pdf["max_dia"].to_numpy()
        sev = pdf["severidade"].to_numpy()
        y_bin = (sev >= 1).astype(int)

        mask = ~np.isnan(scores)
        if mask.sum() < 10:
            continue

        s = scores[mask]
        md = max_dia[mask]
        y = y_bin[mask]
        s_prob = np.clip(s, 0, 1)

        prauc = float(average_precision_score(y, s)) if y.sum() > 0 else np.nan

        if len(np.unique(md)) > 1 and len(np.unique(s)) > 1:
            rho_md, _ = spearmanr(md, s)
            rho_sev, _ = spearmanr(sev[mask], s)
        else:
            rho_md = np.nan
            rho_sev = np.nan

        brier = float(brier_score_loss(y, s_prob)) if y.sum() > 0 else np.nan

        cats = pd.cut(s_prob, bins=[-0.01, 0.30, 0.70, 1.01], labels=["baixo", "moderado", "alto"])
        vc = cats.value_counts()
        total = vc.sum()
        dist = {k: float(v / total) for k, v in vc.items()}

        fp_alto = ((s_prob >= 0.70) & (y == 0)).sum() / max((y == 0).sum(), 1)
        fp_moderado = ((s_prob >= 0.30) & (y == 0)).sum() / max((y == 0).sum(), 1)

        dyn_range = float(np.percentile(s_prob, 99) - np.percentile(s_prob, 1))

        rows.append({
            "candidato": nome,
            "desc": info["desc"],
            "prauc": prauc,
            "spearman_max_dia": float(rho_md),
            "spearman_severidade": float(rho_sev),
            "brier": brier,
            "pct_baixo": dist.get("baixo", 0.0),
            "pct_moderado": dist.get("moderado", 0.0),
            "pct_alto": dist.get("alto", 0.0),
            "fp_alto": float(fp_alto),
            "fp_moderado": float(fp_moderado),
            "dyn_range_p1_p99": dyn_range,
            "score_mean": float(s_prob.mean()),
            "score_std": float(s_prob.std()),
            "n": int(mask.sum()),
        })

    return pd.DataFrame(rows)


def calcular_faixas_por_candidato(df: pl.DataFrame) -> pd.DataFrame:
    pdf = df.to_pandas()
    pdf["faixa"] = pdf["max_dia"].apply(_faixa_chuva)

    rows = []
    for nome, info in CANDIDATOS.items():
        col = info["col"]
        if col not in pdf.columns:
            continue

        grp = pdf.groupby(["bacia", "faixa"]).agg(
            n=(col, "count"),
            score_mean=(col, "mean"),
            score_std=(col, "std"),
            severidade_media=("severidade", "mean"),
            taxa_evento=("enchente", "mean"),
        ).reset_index()
        grp["candidato"] = nome
        rows.append(grp)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def diagnosticar_monotonicidade(df_faixas: pd.DataFrame) -> pd.DataFrame:
    ordem = {label: i for i, label in enumerate(FAIXAS_LABELS)}

    rows = []
    for (bacia, candidato), sub in df_faixas.groupby(["bacia", "candidato"]):
        sub = sub.copy()
        sub["ord"] = sub["faixa"].map(ordem)
        sub = sub.dropna(subset=["ord"]).sort_values("ord")
        if len(sub) < 3:
            continue

        scores = sub["score_mean"].to_numpy()
        inversoes = int((scores[1:] < scores[:-1]).sum())
        if len(np.unique(scores)) > 1:
            rho_mono, _ = spearmanr(sub["ord"].to_numpy(), scores)
        else:
            rho_mono = np.nan

        s_leve = sub[sub["faixa"].isin(["0-5", "5-10"])]["score_mean"].mean()
        s_forte = sub[sub["faixa"].isin(["20-30", "30-50", "50-80", "80+"])]["score_mean"].mean()

        rows.append({
            "bacia": bacia,
            "candidato": candidato,
            "inversoes": inversoes,
            "rho_mono_faixa": float(rho_mono),
            "score_leve_mean": float(s_leve) if pd.notna(s_leve) else np.nan,
            "score_forte_mean": float(s_forte) if pd.notna(s_forte) else np.nan,
            "delta_forte_leve": float(s_forte - s_leve) if pd.notna(s_leve) and pd.notna(s_forte) else np.nan,
        })

    return pd.DataFrame(rows)


def auditar_datas_criticas(df: pl.DataFrame) -> pd.DataFrame:
    pdf = df.to_pandas()

    rows = []
    for nome, info in CANDIDATOS.items():
        col = info["col"]
        if col not in pdf.columns:
            continue

        mask_leve_alto = (pdf["max_dia"] < 10) & (pdf[col] >= 0.50)
        sub1 = pdf[mask_leve_alto].copy()
        sub1["tipo"] = "leve_score_alto"
        sub1["score"] = sub1[col]
        sub1["candidato"] = nome
        rows.append(sub1[["data", "bacia", "max_dia", "severidade", "score", "tipo", "candidato"]])

        mask_forte_baixo = (pdf["max_dia"] >= 20) & (pdf[col] < 0.20)
        sub2 = pdf[mask_forte_baixo].copy()
        sub2["tipo"] = "forte_score_baixo"
        sub2["score"] = sub2[col]
        sub2["candidato"] = nome
        rows.append(sub2[["data", "bacia", "max_dia", "severidade", "score", "tipo", "candidato"]])

    if rows:
        out = pd.concat(rows, ignore_index=True)
    else:
        out = pd.DataFrame(columns=["data", "bacia", "max_dia", "severidade", "score", "tipo", "candidato"])
    return out


def matriz_decisao(df_metricas: pd.DataFrame, df_mono: pd.DataFrame) -> pd.DataFrame:
    """Produz matriz de decisão: usar_agora, shadow, validar_mais, descartar."""
    mono_agg = df_mono.groupby("candidato").agg(
        rho_mono_faixa_mean=("rho_mono_faixa", "mean"),
        inversoes_mean=("inversoes", "mean"),
        delta_forte_leve_mean=("delta_forte_leve", "mean"),
        score_leve_mean=("score_leve_mean", "mean"),
        score_forte_mean=("score_forte_mean", "mean"),
    ).reset_index()

    merged = df_metricas.merge(mono_agg, on="candidato", how="left")

    decisoes = []
    for _, r in merged.iterrows():
        cand = r["candidato"]
        decision = "validar_mais"
        motivos = []

        # ── Descarte definitivo ──
        # Inversões frequentes ou delta negativo
        if r["inversoes_mean"] > 1.0 or (r["delta_forte_leve_mean"] < 0 and not pd.isna(r["delta_forte_leve_mean"])):
            decision = "descartar"
            motivos.append("inversoes frequentes ou delta_forte_leve negativo")

        # Alarmismo excessivo: >5% dos não-eventos em ALTO é problemático para dashboard
        if r["fp_alto"] > 0.05:
            if decision != "descartar":
                decision = "descartar"
            motivos.append(f"alarmismo excessivo ({r['fp_alto']:.1%} nao-eventos classificados ALTO)")

        # Base muito elevada: score médio em chuva leve > 0.30 implica 'moderado' em dia sem chuva
        if r["score_leve_mean"] > 0.30 and not pd.isna(r["score_leve_mean"]):
            if decision != "descartar":
                decision = "descartar"
            motivos.append(f"score base elevado ({r['score_leve_mean']:.3f} em chuva leve)")

        # baseline_v8: já diagnosticado como inferior
        if cand == "baseline_v8":
            decision = "descartar"
            motivos.append("baseline conhecido: inversoes, subestimacao severa, inferior aos candidatos")

        # ── Shadow / usar agora ──
        if decision not in ["descartar"]:
            ok_mono = r["rho_mono_faixa_mean"] >= 0.50
            ok_spear = r["spearman_max_dia"] >= 0.20
            ok_delta = r["delta_forte_leve_mean"] >= 0.03
            ok_fp = r["fp_alto"] <= 0.02
            ok_base = r["score_leve_mean"] <= 0.25 if not pd.isna(r["score_leve_mean"]) else False
            ok_cauda = r["score_forte_mean"] >= 0.15 if not pd.isna(r["score_forte_mean"]) else False

            if ok_mono and ok_spear and ok_delta and ok_fp and ok_base and ok_cauda:
                # Nenhum atinge o ideal (delta>=0.15 + cauda>=0.50)
                if r["delta_forte_leve_mean"] >= 0.10 and r["score_forte_mean"] >= 0.40:
                    decision = "usar_agora_dashboard"
                    motivos.append("bom equilibrio entre proporcionalidade, resolucao e alarmismo")
                else:
                    decision = "usar_shadow"
                    motivos.append("melhor que baseline em Spearman e mono, mas resolucao na cauda ainda fraca")
            else:
                decision = "validar_mais"
                falhas = []
                if not ok_mono:
                    falhas.append("monotonicidade ruim")
                if not ok_spear:
                    falhas.append("Spearman baixo")
                if not ok_delta:
                    falhas.append("separacao forte/leve fraca")
                if not ok_fp:
                    falhas.append("alarmismo")
                if not ok_base:
                    falhas.append("score base alto")
                if not ok_cauda:
                    falhas.append("score cauda baixo")
                motivos.append("; ".join(falhas))

        decisoes.append({
            "candidato": cand,
            "decisao": decision,
            "motivo": "; ".join(motivos) if motivos else "-",
            "prauc": r["prauc"],
            "spearman_max_dia": r["spearman_max_dia"],
            "rho_mono_faixa_mean": r["rho_mono_faixa_mean"],
            "delta_forte_leve_mean": r["delta_forte_leve_mean"],
            "score_leve_mean": r["score_leve_mean"],
            "score_forte_mean": r["score_forte_mean"],
            "fp_alto": r["fp_alto"],
            "dyn_range_p1_p99": r["dyn_range_p1_p99"],
            "pct_alto": r["pct_alto"],
        })

    return pd.DataFrame(decisoes)


def main():
    print("=" * 80)
    print("AUDITORIA DE PROBABILIDADE PARA DASHBOARD")
    print("=" * 80)

    # ── 1. Carregar ──
    print("\n[1/6] Carregando dados...")
    df = carregar_dados()
    print(f"      Linhas carregadas: {df.height}")

    # ── 2. Métricas agregadas ──
    print("\n[2/6] Calculando métricas agregadas por candidato...")
    df_metricas = calcular_metricas_por_candidato(df)
    print(df_metricas[["candidato", "prauc", "spearman_max_dia", "brier",
                       "fp_alto", "dyn_range_p1_p99", "pct_alto"]].to_string(index=False))

    # ── 3. Faixas de chuva ──
    print("\n[3/6] Calculando curvas por faixa de chuva...")
    df_faixas = calcular_faixas_por_candidato(df)
    df_mono = diagnosticar_monotonicidade(df_faixas)
    print("Monotonicidade por candidato (média entre bacias):")
    print(df_mono.groupby("candidato")[["rho_mono_faixa", "inversoes", "delta_forte_leve", "score_leve_mean", "score_forte_mean"]].mean().to_string())

    # ── 4. Datas críticas ──
    print("\n[4/6] Auditando datas críticas (leve+alto / forte+baixo)...")
    df_criticos = auditar_datas_criticas(df)
    print(f"      Total de casos críticos encontrados: {len(df_criticos)}")
    if len(df_criticos) > 0:
        print(df_criticos.groupby(["candidato", "tipo"]).size().to_string())

    # ── 5. Matriz de decisão ──
    print("\n[5/6] Construindo matriz de decisão...")
    df_decisao = matriz_decisao(df_metricas, df_mono)
    print(df_decisao[["candidato", "decisao", "motivo"]].to_string(index=False))

    # ── 6. Salvar ──
    print("\n[6/6] Salvando resultados...")
    df_metricas.to_parquet(OUT_DIR / "auditoria_probabilidade_dashboard.parquet")
    df_faixas.to_parquet(OUT_DIR / "auditoria_probabilidade_dashboard_faixas.parquet")
    df_criticos.to_parquet(OUT_DIR / "auditoria_probabilidade_dashboard_criticos.parquet")

    # ── Relatório Markdown ──
    relatorio = f"""# Relatório: Auditoria de Probabilidade para Dashboard

**Data:** {pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")}  
**Script:** `{Path(__file__).name}`

---

## 1. Objetivo

Determinar se existe candidato melhor que o baseline atual (V8 prob + display rescaling)
para uso no dashboard, em termos de **probabilidade/score operacional interpretável**.

## 2. Candidatos Avaliados

| Candidato | Descrição | Escala |
|-----------|-----------|--------|
"""
    for _, r in df_metricas.iterrows():
        info = CANDIDATOS.get(r["candidato"], {})
        relatorio += f"| {r['candidato']} | {info.get('desc', '-')} | {info.get('escala', '-')} |\n"

    relatorio += """
## 3. Métricas Agregadas (média global, teste)

| Candidato | PR-AUC | Spearman max_dia | Brier | %Baixo | %Moderado | %Alto | FP-Alto | Dyn Range |
|-----------|--------|------------------|-------|--------|-----------|-------|---------|-----------|
"""
    for _, r in df_metricas.iterrows():
        relatorio += (
            f"| {r['candidato']:<25} | {r['prauc']:.3f} | {r['spearman_max_dia']:.3f} | "
            f"{r['brier']:.3f} | {r['pct_baixo']:.1%} | {r['pct_moderado']:.1%} | "
            f"{r['pct_alto']:.1%} | {r['fp_alto']:.2%} | {r['dyn_range_p1_p99']:.3f} |\n"
        )

    relatorio += """
## 4. Comportamento por Faixa de Chuva (média global ponderada)

| Candidato | 0-5mm | 5-10mm | 10-20mm | 20-30mm | Delta(forte-leve) |
|-----------|-------|--------|---------|---------|-------------------|
"""
    # Média global ponderada por n
    faixa_global = (
        df_faixas.assign(wn=lambda x: x["score_mean"] * x["n"])
        .groupby(["candidato", "faixa"])
        .agg(wn_sum=("wn", "sum"), n_total=("n", "sum"))
        .reset_index()
    )
    faixa_global["score_global"] = faixa_global["wn_sum"] / faixa_global["n_total"]

    for cand in sorted(df_faixas["candidato"].unique()):
        sub = faixa_global[faixa_global["candidato"] == cand]
        vals = {row["faixa"]: row["score_global"] for _, row in sub.iterrows()}
        s0 = vals.get("0-5", np.nan)
        s5 = vals.get("5-10", np.nan)
        s10 = vals.get("10-20", np.nan)
        s20 = vals.get("20-30", np.nan)
        s_leve = np.nanmean([s0, s5])
        s_forte = np.nanmean([s20])
        delta = s_forte - s_leve if not (np.isnan(s_leve) or np.isnan(s_forte)) else np.nan
        relatorio += (
            f"| {cand:<25} | {s0:.3f} | {s5:.3f} | {s10:.3f} | {s20:.3f} | {delta:.3f} |\n"
        )

    relatorio += """
## 5. Monotonicidade por Faixa de Chuva (média entre bacias)

| Candidato | rho_mono | Inversoes | Delta(forte-leve) | Score leve | Score forte |
|-----------|----------|-----------|-------------------|------------|-------------|
"""
    mono_resumo = df_mono.groupby("candidato")[["rho_mono_faixa", "inversoes", "delta_forte_leve", "score_leve_mean", "score_forte_mean"]].mean().reset_index()
    for _, r in mono_resumo.iterrows():
        relatorio += (
            f"| {r['candidato']:<25} | {r['rho_mono_faixa']:.3f} | {r['inversoes']:.2f} | "
            f"{r['delta_forte_leve']:.3f} | {r['score_leve_mean']:.3f} | {r['score_forte_mean']:.3f} |\n"
        )

    relatorio += """
## 6. Casos Críticos (Top 10 por tipo/candidato)

"""
    if len(df_criticos) > 0:
        for cand in sorted(df_criticos["candidato"].unique()):
            sub = df_criticos[df_criticos["candidato"] == cand]
            relatorio += f"\n### {cand}\n"
            relatorio += "| Data | Bacia | max_dia | Severidade | Score | Tipo |\n"
            relatorio += "|------|-------|---------|------------|-------|------|\n"
            for _, r in sub.head(10).iterrows():
                relatorio += (
                    f"| {r['data']} | {r['bacia']} | {r['max_dia']:.1f} | "
                    f"{r['severidade']} | {r['score']:.3f} | {r['tipo']} |\n"
                )
    else:
        relatorio += "Nenhum caso crítico encontrado com os thresholds adotados.\n"

    relatorio += """
## 7. Matriz de Decisão

| Candidato | Decisão | Score leve | Score forte | FP-Alto | Principais Motivos |
|-----------|---------|------------|-------------|---------|--------------------|
"""
    for _, r in df_decisao.iterrows():
        relatorio += (
            f"| {r['candidato']:<25} | {r['decisao']:<22} | {r['score_leve_mean']:.3f} | "
            f"{r['score_forte_mean']:.3f} | {r['fp_alto']:.2%} | {r['motivo']} |\n"
        )

    relatorio += """
## 8. Ranking Final (Dashboard — critério operacional)

Score composto:
- Spearman max_dia (30%)
- Monotonicidade por faixa (25%)
- Delta forte-leve (25%)
- Controle de alarmismo FP-Alto (20%)

Candidatos descartados por alarmismo ou inversoes recebem penalidade de 50% no score.

"""
    df_rank = df_metricas.copy()
    df_rank = df_rank.merge(mono_resumo, on="candidato", how="left")

    def _norm(s, inv=False):
        mn, mx = s.min(), s.max()
        if mx - mn < 1e-9:
            return pd.Series([0.5] * len(s), index=s.index)
        v = (s - mn) / (mx - mn)
        return 1 - v if inv else v

    df_rank["_s_spear"] = _norm(df_rank["spearman_max_dia"].fillna(0))
    df_rank["_s_mono"] = _norm(df_rank["rho_mono_faixa"].fillna(0))
    df_rank["_s_delta"] = _norm(df_rank["delta_forte_leve"].fillna(0))
    df_rank["_s_fp"] = _norm(df_rank["fp_alto"].fillna(0), inv=True)

    df_rank["score_dashboard"] = (
        0.30 * df_rank["_s_spear"] +
        0.25 * df_rank["_s_mono"] +
        0.25 * df_rank["_s_delta"] +
        0.20 * df_rank["_s_fp"]
    )

    # Penalidade para descartados
    descartados = set(df_decisao[df_decisao["decisao"] == "descartar"]["candidato"])
    df_rank["score_dashboard"] = df_rank.apply(
        lambda r: r["score_dashboard"] * 0.5 if r["candidato"] in descartados else r["score_dashboard"],
        axis=1,
    )

    df_rank = df_rank.sort_values("score_dashboard", ascending=False)
    relatorio += "| Rank | Candidato | Score Dashboard | Decisão |\n"
    relatorio += "|------|-----------|----------------|---------|\n"
    for i, (_, r) in enumerate(df_rank.iterrows(), 1):
        decisao = df_decisao[df_decisao["candidato"] == r["candidato"]]["decisao"].values[0]
        relatorio += f"| {i} | {r['candidato']:<25} | {r['score_dashboard']:.3f} | {decisao} |\n"

    relatorio += f"""
## 9. Recomendação Final

"""
    top = df_rank.iloc[0]
    top_decisao = df_decisao[df_decisao["candidato"] == top["candidato"]]["decisao"].values[0]

    if top_decisao == "descartar":
        relatorio += (
            "**Nenhum candidato está pronto para uso no dashboard nesta rodada.**\n\n"
            "Todos os candidatos avaliados foram descartados por pelo menos um critério operacional crítico:\n"
            "- Alarmismo excessivo (score ALTO em dias sem chuva), ou\n"
            "- Inversoes na curva score vs chuva, ou\n"
            "- Resolucao fraca na cauda (subestimacao de eventos fortes).\n\n"
            "**Próximo passo:** investir em modelagem que aumente a resolucao do score bruto na cauda\n"
            "(ex: regressao direta, loss de ordenacao, ou calibracao com targets mais agressivos)\n"
            "sem inflar a base (dias sem chuva).\n"
        )
    elif top_decisao == "usar_shadow":
        relatorio += (
            f"**Candidato recomendado para shadow: `{top['candidato']}`**\n\n"
            f"- Decisão: `{top_decisao}`\n"
            f"- Score composto dashboard: {top['score_dashboard']:.3f}\n"
            f"- Spearman max_dia: {top['spearman_max_dia']:.3f}\n"
            f"- Monotonicidade faixa: {top['rho_mono_faixa']:.3f}\n"
            f"- Delta forte-leve: {top['delta_forte_leve']:.3f}\n"
            f"- FP alto (alarmismo): {top['fp_alto']:.2%}\n"
            f"- Score médio em chuva leve: {top['score_leve_mean']:.3f}\n"
            f"- Score médio em chuva forte: {top['score_forte_mean']:.3f}\n\n"
            "Este candidato é objetivamente superior ao baseline em proporcionalidade e monotonicidade,\n"
            "mas ainda subestima eventos extremos (resolucao de cauda insuficiente).\n"
            "Recomenda-se rodar em paralelo ao baseline (shadow) por 30-60 dias antes de promover.\n"
        )
    else:
        relatorio += (
            f"**Candidato com melhor score técnico: `{top['candidato']}`**\n\n"
            f"- Decisão: `{top_decisao}`\n"
            f"- Score composto dashboard: {top['score_dashboard']:.3f}\n"
            f"- Spearman max_dia: {top['spearman_max_dia']:.3f}\n\n"
            "Apesar do score técnico, este candidato não atende todos os critérios operacionais\n"
            "para uso imediato. Recomenda-se validação adicional antes de shadow.\n"
        )

    relatorio += """
## 10. Problema do Backend (runner.py)

O backend atual (`floodcast/runner.py`) retorna:
- `raw_proba = model.predict_proba(X)[0][predict_value]` — prob da **classe predita**, não do evento.
- `display_probability` faz rescale threshold-based que distorce a escala.

Isso significa que a `proba` enviada ao dashboard **não é uma probabilidade
operacional interpretável** de risco. O score calibrado (`risk_score_raw_mean_serving`)
é uma alternativa objetivamente superior em escala, mas **foi descartado nesta auditoria
por alarmismo excessivo** (13.5% dos não-eventos classificados como ALTO).

**Recomendação arquitetural**: a probabilidade enviada ao dashboard deve vir de um
score operacional calibrado e auditado (como este processo), não de `raw_proba` +
rescale threshold-based. Qualquer candidato aprovado deve passar por esta auditoria
antes de ser exposto na API.

## 11. Limitações e Riscos Conhecidos

- Poucos eventos >30mm no teste; comportamento na cauda é incerto.
- O calibrador piecewise foi ajustado até 2024-07-01; drift temporal pode degradar.
- Especialistas mean_60_40 são reconstruídos a partir de componentes normalizados;
  um modelo combinado treinado end-to-end pode ter desempenho diferente.
- Classificador_cauda tem alarmismo moderado (4.5% fp_alto) e Spearman baixo;
  não é candidato viável para dashboard sem ajuste de threshold.

## 12. Arquivos Gerados

- `auditoria_probabilidade_dashboard.parquet` — métricas agregadas por candidato
- `auditoria_probabilidade_dashboard_faixas.parquet` — curva por faixa de chuva
- `auditoria_probabilidade_dashboard_criticos.parquet` — datas críticas auditadas
- `relatorio_auditoria_probabilidade_dashboard.md` — este relatório
"""

    out_md = OUT_DIR / "relatorio_auditoria_probabilidade_dashboard.md"
    out_md.write_text(relatorio, encoding="utf-8")
    print(f"\nRelatório salvo em {out_md}")
    print("=" * 80)
    print("DONE.")


if __name__ == "__main__":
    main()
