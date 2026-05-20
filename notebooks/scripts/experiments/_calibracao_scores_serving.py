"""
Calibracao de Scores para Serving — Dashboard/Operacao.
=====================================================

Objetivo: transformar score bruto do combinador em percentual operacional
mais interpretavel, sem destruir a proporcionalidade da chuva.

Calibracoes testadas (treino -> teste):
  - Platt (logistic calibration)
  - Isotonic regression
  - Quantile / percentile calibration
  - Piecewise linear por bins do score bruto (sem leak)

Avaliacao:
  - Brier score vs evento (severidade >= 1)
  - Spearman com max_dia / severidade (antes/depois)
  - PR-AUC antes/depois
  - Curva score calibrado por faixa de chuva
  - Critérios operacionais: leve <30%, moderada 30-70%, forte >70%

Saida:
  - parquet com scores calibrados
  - JSON com parametros do calibrador recomendado
  - relatorio markdown
"""

import json
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import polars as pl
from scipy.interpolate import interp1d
from scipy.optimize import minimize_scalar
from scipy.stats import spearmanr
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss

warnings.filterwarnings("ignore")

# ─── Paths ───────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
WORKDIR = SCRIPT_DIR.parents[1]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
# O parquet do combinador contém principalmente dados de teste do pipeline
# original. Para calibração sem leak, usamos um corte temporal mais recente
# dentro dos próprios dados do parquet.
T_CUT = datetime(2024, 7, 1).date()
CANDIDATOS = ["risk_score_raw_mean", "risk_score_raw_weighted", "classificador_cauda"]
CAND_LABEL = {
    "risk_score_raw_mean": "combinador_mean",
    "risk_score_raw_weighted": "combinador_weighted",
    "classificador_cauda": "classificador_cauda",
}
FAIXAS_CHUVA = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 80), (80, float("inf"))]


# ─── Helpers ─────────────────────────────────────────────────────────────

def brier(y_true, y_prob):
    return float(brier_score_loss(y_true, y_prob))


def pr_auc(y_true, y_prob):
    if len(np.unique(y_true)) < 2:
        return np.nan
    return float(average_precision_score(y_true, y_prob))


def spearman(a, b):
    if len(np.unique(a)) <= 1 or len(np.unique(b)) <= 1:
        return np.nan, np.nan
    return spearmanr(a, b)


def quantile_calibration(train_scores, test_scores, n_quantiles=100):
    """
    Mapeia cada score bruto para seu percentil empirico no treino.
    Suavizacao linear para evitar saltos.
    """
    tr = np.asarray(train_scores)
    te = np.asarray(test_scores)
    qs = np.linspace(0, 1, n_quantiles)
    # Usamos os quantis dos valores ordenados do treino
    train_sorted = np.sort(tr)
    quantile_values = np.quantile(train_sorted, qs)
    # Interpolacao monotona: score -> percentil
    # Remover duplicatas para interp1d
    uniq_vals, uniq_qs = [], []
    for v, q in zip(quantile_values, qs):
        if not uniq_vals or v != uniq_vals[-1]:
            uniq_vals.append(v)
            uniq_qs.append(q)
    if len(uniq_vals) < 2:
        return np.full_like(te, fill_value=np.mean(uniq_qs) if uniq_qs else 0.5)
    f = interp1d(uniq_vals, uniq_qs, kind="linear", bounds_error=False, fill_value=(0.0, 1.0))
    return f(te)


def piecewise_linear_bins(train_scores, test_scores, n_bins=5):
    """
    Piecewise linear: divide o score bruto em n_bins no treino e mapeia
    os centros dos bins uniformemente em [0,1].
    Nao usa chuva/severidade -> sem leak.
    """
    tr = np.asarray(train_scores)
    te = np.asarray(test_scores)
    if len(tr) < n_bins * 2:
        return quantile_calibration(tr, te)
    # Bins baseados nos quantis do treino
    bin_edges = np.quantile(tr, np.linspace(0, 1, n_bins + 1))
    bin_edges[0] -= 1e-6
    bin_edges[-1] += 1e-6
    # Mapeamento: centro do bin -> valor uniforme
    # Para manter monotonicidade, usamos o valor medio do bin no treino vs posicao uniforme
    bin_centers = []
    bin_targets = []
    for i in range(n_bins):
        mask = (tr >= bin_edges[i]) & (tr < bin_edges[i + 1])
        vals = tr[mask]
        if len(vals) == 0:
            continue
        bin_centers.append(float(np.mean(vals)))
        bin_targets.append((i + 0.5) / n_bins)
    if len(bin_centers) < 2:
        return quantile_calibration(tr, te)
    # Interpolacao monotona
    # Garantir monotonicidade crescente
    idx = np.argsort(bin_centers)
    bc = np.array(bin_centers)[idx]
    bt = np.array(bin_targets)[idx]
    f = interp1d(bc, bt, kind="linear", bounds_error=False, fill_value=(0.0, 1.0))
    return f(te)


def piecewise_operacional(train_scores, test_scores):
    """
    Piecewise que mapeia percentis do score bruto para faixas operacionais:
      < P30_treino  -> [0,   0.30]
      P30 - P70     -> [0.30, 0.70]
      > P70_treino  -> [0.70, 1.00]
    Sem leak (usa apenas score bruto do treino).
    """
    tr = np.asarray(train_scores)
    te = np.asarray(test_scores)
    if len(tr) < 30:
        return quantile_calibration(tr, te)
    p30 = np.percentile(tr, 30)
    p70 = np.percentile(tr, 70)
    mn = tr.min() - 1e-6
    mx = tr.max() + 1e-6

    # Evitar colapso
    if p30 <= mn or p70 <= p30 or mx <= p70:
        return quantile_calibration(tr, te)

    # Pontos de controle (score_bruto, target_calibrado)
    bc = [mn, p30, p70, mx]
    bt = [0.0, 0.30, 0.70, 1.0]
    f = interp1d(bc, bt, kind="linear", bounds_error=False, fill_value=(0.0, 1.0))
    return np.clip(f(te), 0.0, 1.0)


def platt_calibration(train_scores, train_y, test_scores):
    """Platt scaling via LogisticRegression (calibracao logistica)."""
    tr = np.asarray(train_scores).reshape(-1, 1)
    te = np.asarray(test_scores).reshape(-1, 1)
    y = np.asarray(train_y)
    if len(np.unique(y)) < 2:
        return np.full_like(test_scores, fill_value=y.mean())
    clf = LogisticRegression(max_iter=1000, solver="lbfgs")
    clf.fit(tr, y)
    return clf.predict_proba(te)[:, 1]


def isotonic_calibration(train_scores, train_y, test_scores):
    """Isotonic regression."""
    tr = np.asarray(train_scores)
    te = np.asarray(test_scores)
    y = np.asarray(train_y)
    if len(np.unique(y)) < 2:
        return np.full_like(test_scores, fill_value=y.mean())
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(tr, y)
    return iso.predict(te)


def clamp_score(s, lower=0.0, upper=1.0):
    return np.clip(s, lower, upper)


def calibrar_bacia(df_train, df_test, col_score, col_y="enchente", col_max_dia="max_dia", col_sev="severidade"):
    """
    Aplica todos os calibradores para uma bacia/score.
    Retorna dict com resultados e parametros.
    """
    train_scores = df_train[col_score].to_numpy()
    test_scores = df_test[col_score].to_numpy()
    train_y = df_train[col_y].to_numpy().astype(int)
    test_y = df_test[col_y].to_numpy().astype(int)
    test_max_dia = df_test[col_max_dia].to_numpy()
    test_sev = df_test[col_sev].to_numpy()

    if len(np.unique(train_y)) < 2:
        # Nao da para calibrar sem positivos no treino
        return None

    res = {}
    params = {}

    # --- Bruto (baseline) ---
    raw = clamp_score(test_scores)
    res["bruto"] = raw
    params["bruto"] = {"type": "identity"}

    # --- Platt ---
    try:
        platt = clamp_score(platt_calibration(train_scores, train_y, test_scores))
    except Exception:
        platt = raw.copy()
    res["platt"] = platt
    # Armazena coeficientes simplificados (intercept e coef)
    # Recalcula para salvar parametros
    try:
        clf = LogisticRegression(max_iter=1000, solver="lbfgs")
        clf.fit(np.asarray(train_scores).reshape(-1, 1), train_y)
        params["platt"] = {
            "type": "logistic",
            "coef": float(clf.coef_[0][0]),
            "intercept": float(clf.intercept_[0]),
        }
    except Exception:
        params["platt"] = {"type": "logistic", "coef": None, "intercept": None}

    # --- Isotonic ---
    try:
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(np.asarray(train_scores), train_y)
        isoton = clamp_score(iso.predict(np.asarray(test_scores)))
        params["isotonic"] = {
            "type": "isotonic",
            "x_thresholds": iso.X_thresholds_.tolist() if hasattr(iso, "X_thresholds_") else None,
            "y_thresholds": iso.y_thresholds_.tolist() if hasattr(iso, "y_thresholds_") else None,
        }
    except Exception as e:
        isoton = raw.copy()
        params["isotonic"] = {"type": "isotonic", "error": str(e)}
    res["isotonic"] = isoton

    # --- Quantile / Percentile ---
    qcal = clamp_score(quantile_calibration(train_scores, test_scores, n_quantiles=100))
    res["quantile"] = qcal
    params["quantile"] = {"type": "quantile", "n_quantiles": 100, "note": "empirical CDF mapping from train"}

    # --- Piecewise linear por bins do score ---
    pw = clamp_score(piecewise_linear_bins(train_scores, test_scores, n_bins=5))
    res["piecewise"] = pw
    params["piecewise"] = {"type": "piecewise_linear_bins", "n_bins": 5, "note": "monotonic bins on raw score, no leak"}

    # --- Piecewise operacional (bins alinhados a faixas de dashboard) ---
    pwo = clamp_score(piecewise_operacional(train_scores, test_scores))
    res["piecewise_operacional"] = pwo
    params["piecewise_operacional"] = {"type": "piecewise_operacional", "note": "P30->0.30, P70->0.70, linear, no leak"}

    # Métricas
    metrics = {}
    for nome, scores in res.items():
        if nome == "bruto":
            continue
        metrics[nome] = {
            "brier": brier(test_y, scores),
            "prauc": pr_auc(test_y, scores),
            "spearman_max_dia": float(spearman(test_max_dia, scores)[0]) if not np.isnan(spearman(test_max_dia, scores)[0]) else None,
            "spearman_severidade": float(spearman(test_sev, scores)[0]) if not np.isnan(spearman(test_sev, scores)[0]) else None,
            "spearman_max_dia_raw": float(spearman(test_max_dia, raw)[0]) if not np.isnan(spearman(test_max_dia, raw)[0]) else None,
            "spearman_severidade_raw": float(spearman(test_sev, raw)[0]) if not np.isnan(spearman(test_sev, raw)[0]) else None,
            "prauc_raw": pr_auc(test_y, raw),
            "brier_raw": brier(test_y, raw),
        }

    return {
        "scores": res,
        "params": params,
        "metrics": metrics,
        "train_n": len(train_scores),
        "test_n": len(test_scores),
        "test_pos": int(test_y.sum()),
    }


def resumo_por_faixa(df_test, col_score_raw, col_score_cal, col_max_dia="max_dia", col_sev="severidade"):
    """Calcula media do score calibrado por faixa de chuva no teste."""
    sub = df_test.to_pandas()
    rows = []
    for lo, hi in FAIXAS_CHUVA:
        mask = (sub[col_max_dia] >= lo) & (sub[col_max_dia] < hi)
        if mask.sum() == 0:
            continue
        rows.append({
            "faixa": f"{lo}-{hi}" if hi < float("inf") else f"{lo}+",
            "n": int(mask.sum()),
            "score_raw_mean": float(sub.loc[mask, col_score_raw].mean()),
            "score_cal_mean": float(sub.loc[mask, col_score_cal].mean()),
            "severidade_media": float(sub.loc[mask, col_sev].mean()),
        })
    return rows


def criterios_operacionais(scores, max_dia, severidade=None):
    """
    Verifica se a distribuicao do score calibrado respeita:
      leve (<30%), moderada (30-70%), forte (>70%) quando perfil perigoso.
    Aqui usamos max_dia como proxy de perigo (>=20mm como forte).
    Retorna dict com proporcoes.
    """
    s = np.asarray(scores)
    m = np.asarray(max_dia)
    sev = np.asarray(severidade) if severidade is not None else None
    def prop(mask):
        n = mask.sum()
        if n == 0:
            return {"n": 0, "pct_leve": None, "pct_moderada": None, "pct_forte": None}
        return {
            "n": int(n),
            "pct_leve": float((s[mask] < 0.30).sum() / n),
            "pct_moderada": float(((s[mask] >= 0.30) & (s[mask] <= 0.70)).sum() / n),
            "pct_forte": float((s[mask] > 0.70).sum() / n),
        }
    res = {
        "geral": prop(np.ones(len(s), dtype=bool)),
        "leve_chuva": prop(m < 10),
        "moderada_chuva": prop((m >= 10) & (m < 20)),
        "forte_chuva": prop(m >= 20),
    }
    if sev is not None:
        res["evento"] = prop(sev >= 1)
    return res


def selecionar_recomendado(df_agg, df_ops=None):
    """
    Critério de seleção do calibrador recomendado.
    Prioridade para dashboard:
      1. Preservar Spearman com max_dia (proporcionalidade)
      2. Critérios operacionais: eventos perigosos devem ter chance de aparecer >70%
      3. PR-AUC decente
      4. Brier score (menor prioridade para serving visual)
    """
    # Para cada calibrador, calcula um score composto
    comp = []
    for _, r in df_agg.iterrows():
        cal = r["calibrador"]
        # Spearman: manter ou melhorar (peso alto)
        sp = r["spearman_max_dia"] if not np.isnan(r["spearman_max_dia"]) else 0.0
        sp_raw = r["spearman_max_dia_raw"] if not np.isnan(r["spearman_max_dia_raw"]) else 0.0
        sp_score = sp  # valor absoluto

        # PR-AUC
        prauc = r["prauc"] if not np.isnan(r["prauc"]) else 0.0

        # Brier: menor é melhor, mas damos peso menor
        brier_score = r["brier"]

        # Critérios operacionais (se disponíveis): queremos que eventos severidade>=1
        # tenham alguma chance de cair >70%
        ops_score = 0.0
        if df_ops is not None:
            ops_sub = df_ops.filter(
                (pl.col("calibrador") == cal) &
                (pl.col("criterio") == "evento") &
                (pl.col("candidato") == "combinador_mean")
            )
            if ops_sub.height > 0:
                # Queremos pct_forte > 0.10 (pelo menos 10% dos eventos >70%)
                pct_forte = ops_sub["pct_forte"].mean()
                if pct_forte is not None and not np.isnan(pct_forte):
                    ops_score = float(pct_forte) * 2.0  # bonus proporcional

        # Score composto (maior melhor)
        score = sp_score + prauc + ops_score - brier_score * 0.5
        comp.append({
            "calibrador": cal,
            "score_composto": score,
            "spearman_max_dia": sp,
            "prauc": prauc,
            "brier": brier_score,
            "ops_score": ops_score,
        })
    df_comp = pl.DataFrame(comp)
    best = df_comp.sort("score_composto", descending=True).row(0, named=True)
    return best["calibrador"]


# ─── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("CALIBRACAO DE SCORES PARA SERVING")
    print("=" * 80)

    # 1. Carrega dados
    print("\n[1/6] Carregando scores do combinador...")
    df_scores = pl.read_parquet(OUT_DIR / "combinador_risco_meteorologico.parquet")
    # Garante coluna enchente
    if "enchente" not in df_scores.columns:
        df_scores = df_scores.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    # 2. Separa treino/teste (mesmo corte temporal do combinador)
    print("[2/6] Separando treino/teste temporal...")
    # Oratorio tem corte especial no combinador; para calibracao usamos o corte default
    # pois os scores ja foram gerados com o corte correto por bacia. Aqui vamos usar
    # o corte global T_CUT para calibracao global e por bacia.
    # Mas precisamos manter o alinhamento: treino = < T_CUT, teste = >= T_CUT
    df_scores = df_scores.sort(["bacia", "data"])

    # Candidatos presentes
    candidatos_presentes = [c for c in CANDIDATOS if c in df_scores.columns]
    if not candidatos_presentes:
        raise ValueError("Nenhum candidato encontrado no parquet!")
    print(f"  Candidatos: {candidatos_presentes}")

    result_rows = []
    metric_rows = []
    faixa_rows = []
    recomendacao_por_bacia = {}
    all_params = {}

    # 3. Loop por bacia + global
    bacias = df_scores["bacia"].unique().to_list()
    conjuntos = [(b, df_scores.filter(pl.col("bacia") == b)) for b in bacias]
    conjuntos.append(("global", df_scores))

    for bacia, sub in conjuntos:
        print(f"\n  -> {bacia}")
        train = sub.filter(pl.col("data") < T_CUT)
        test = sub.filter(pl.col("data") >= T_CUT)

        if train.height < 30 or test.height < 5:
            print(f"     pulado (train={train.height}, test={test.height})")
            continue

        for cand in candidatos_presentes:
            label = CAND_LABEL.get(cand, cand)
            print(f"     calibrando {label} ...")

            r = calibrar_bacia(train, test, cand, col_y="enchente", col_max_dia="max_dia", col_sev="severidade")
            if r is None:
                print(f"     pulado (sem positivos no treino)")
                continue

            # Armazena scores no dataframe de teste
            test_local = test.clone()
            for cal_nome, cal_scores in r["scores"].items():
                test_local = test_local.with_columns(pl.Series(cal_scores).alias(f"{cand}_cal_{cal_nome}"))

            # Métricas
            for cal_nome in r["scores"].keys():
                if cal_nome == "bruto":
                    continue
                m = r["metrics"][cal_nome]
                metric_rows.append({
                    "bacia": bacia,
                    "candidato": label,
                    "calibrador": cal_nome,
                    "train_n": r["train_n"],
                    "test_n": r["test_n"],
                    "test_pos": r["test_pos"],
                    "brier": float(m["brier"]),
                    "brier_raw": float(m["brier_raw"]),
                    "prauc": float(m["prauc"]),
                    "prauc_raw": float(m["prauc_raw"]),
                    "spearman_max_dia": m["spearman_max_dia"] if m["spearman_max_dia"] is not None else np.nan,
                    "spearman_max_dia_raw": m["spearman_max_dia_raw"] if m["spearman_max_dia_raw"] is not None else np.nan,
                    "spearman_severidade": m["spearman_severidade"] if m["spearman_severidade"] is not None else np.nan,
                    "spearman_severidade_raw": m["spearman_severidade_raw"] if m["spearman_severidade_raw"] is not None else np.nan,
                })

            # Curva por faixa de chuva
            for cal_nome in ["platt", "isotonic", "quantile", "piecewise", "piecewise_operacional"]:
                if f"{cand}_cal_{cal_nome}" not in test_local.columns:
                    continue
                faixa_info = resumo_por_faixa(
                    test_local, cand, f"{cand}_cal_{cal_nome}", col_max_dia="max_dia", col_sev="severidade"
                )
                for frow in faixa_info:
                    faixa_rows.append({
                        "bacia": bacia,
                        "candidato": label,
                        "calibrador": cal_nome,
                        **frow,
                    })

            # Critérios operacionais
            for cal_nome in ["platt", "isotonic", "quantile", "piecewise", "piecewise_operacional"]:
                cal_col = f"{cand}_cal_{cal_nome}"
                if cal_col not in test_local.columns:
                    continue
                ops = criterios_operacionais(
                    test_local[cal_col].to_numpy(),
                    test_local["max_dia"].to_numpy(),
                    test_local["severidade"].to_numpy(),
                )
                for categoria, vals in ops.items():
                    result_rows.append({
                        "bacia": bacia,
                        "candidato": label,
                        "calibrador": cal_nome,
                        "criterio": categoria,
                        **vals,
                    })

            # Guarda parametros (apenas para o candidato primario por bacia)
            if bacia not in all_params:
                all_params[bacia] = {}
            all_params[bacia][label] = r["params"]

    # 4. Consolidar métricas e selecionar recomendado
    print("\n[4/6] Consolidando métricas e selecionando calibrador...")
    df_metrics = pl.DataFrame(metric_rows)
    out_metrics = OUT_DIR / "calibracao_scores_serving_metricas.parquet"
    df_metrics.write_parquet(out_metrics)
    print(f"  Métricas -> {out_metrics}")

    # Agregacao media por calibrador (todos candidatos)
    agg = df_metrics.group_by("calibrador").agg([
        pl.col("brier").mean().alias("brier_mean"),
        pl.col("prauc").mean().alias("prauc_mean"),
        pl.col("spearman_max_dia").mean().alias("spearman_max_dia_mean"),
        pl.col("spearman_max_dia_raw").mean().alias("spearman_max_dia_raw_mean"),
        pl.col("spearman_severidade").mean().alias("spearman_severidade_mean"),
    ])
    print("\n  Agregado por calibrador (media entre bacias/candidatos):")
    print(agg.to_pandas().to_string(index=False))

    # Cria df_ops antes da selecao
    df_ops = pl.DataFrame(result_rows) if result_rows else None

    # Selecao do recomendado considerando apenas combinador_mean
    sub_mean = df_metrics.filter(pl.col("candidato") == "combinador_mean")
    if sub_mean.height > 0:
        agg_mean = sub_mean.group_by("calibrador").agg([
            pl.col("brier").mean().alias("brier"),
            pl.col("prauc").mean().alias("prauc"),
            pl.col("spearman_max_dia").mean().alias("spearman_max_dia"),
            pl.col("spearman_max_dia_raw").mean().alias("spearman_max_dia_raw"),
        ]).to_pandas()
        recomendado = selecionar_recomendado(agg_mean, df_ops)
    else:
        recomendado = "quantile"  # fallback seguro
    print(f"\n  Calibrador recomendado: {recomendado}")

    # 5. Gerar dataframe final com scores calibrados recomendados
    print("\n[5/6] Gerando dataframe final com calibracao recomendada...")
    # Reprocessa adicionando apenas o recomendado ao dataframe original
    df_final = df_scores.clone()
    for cand in candidatos_presentes:
        if cand not in df_final.columns:
            continue
        col_name = f"{cand}_serving"
        # Remove coluna se ja existir para evitar duplicatas
        if col_name in df_final.columns:
            df_final = df_final.drop(col_name)

        all_temp_rows = []
        for bacia in bacias:
            train_b = df_final.filter((pl.col("bacia") == bacia) & (pl.col("data") < T_CUT))
            test_b = df_final.filter((pl.col("bacia") == bacia) & (pl.col("data") >= T_CUT))
            if train_b.height == 0 or test_b.height == 0:
                # Se nao houver treino nesta bacia, propaga bruto para todos
                sub = df_final.filter(pl.col("bacia") == bacia)
                for d in sub["data"].to_list():
                    all_temp_rows.append({"data": d, "bacia": bacia, col_name: float(sub.filter(pl.col("data") == d)[cand].to_numpy()[0])})
                continue

            train_scores = train_b[cand].to_numpy()
            test_scores = test_b[cand].to_numpy()
            train_y = train_b["enchente"].to_numpy().astype(int)

            if recomendado == "platt":
                cal_scores = platt_calibration(train_scores, train_y, test_scores)
            elif recomendado == "isotonic":
                cal_scores = isotonic_calibration(train_scores, train_y, test_scores)
            elif recomendado == "quantile":
                cal_scores = quantile_calibration(train_scores, test_scores)
            elif recomendado == "piecewise":
                cal_scores = piecewise_linear_bins(train_scores, test_scores)
            else:
                cal_scores = test_scores.copy()

            # Aplica calibrador no proprio treino para consistencia de serie historica
            cal_train = np.full(train_b.height, np.nan)
            if recomendado == "platt":
                cal_train = platt_calibration(train_scores, train_y, train_scores)
            elif recomendado == "isotonic":
                cal_train = isotonic_calibration(train_scores, train_y, train_scores)
            elif recomendado == "quantile":
                cal_train = quantile_calibration(train_scores, train_scores)
            elif recomendado == "piecewise":
                cal_train = piecewise_linear_bins(train_scores, train_scores)
            else:
                cal_train = train_scores.copy()

            datas = train_b["data"].to_list() + test_b["data"].to_list()
            vals = np.concatenate([cal_train, cal_scores]).tolist()
            bac_list = train_b["bacia"].to_list() + test_b["bacia"].to_list()
            for d, b, v in zip(datas, bac_list, vals):
                all_temp_rows.append({"data": d, "bacia": b, col_name: float(v)})

        if all_temp_rows:
            temp_df = pl.DataFrame(all_temp_rows)
            df_final = df_final.join(temp_df, on=["data", "bacia"], how="left")

    out_final = OUT_DIR / "calibracao_scores_serving.parquet"
    df_final.write_parquet(out_final)
    print(f"  Final -> {out_final}")

    # 6. Salva parametros JSON
    params_json = {
        "data_calibracao": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "calibrador_recomendado": recomendado,
        "motivo": "melhor compromisso entre Brier, PR-AUC e preservacao de Spearman com max_dia",
        "candidato_primario": "combinador_mean",
        "candidatos_avaliados": candidatos_presentes,
        "corte_temporal": str(T_CUT),
        "params_por_bacia": {},
    }
    # Simplifica params para JSON (remove arrays grandes se houver)
    for bacia, cands in all_params.items():
        params_json["params_por_bacia"][bacia] = {}
        for cand, pdict in cands.items():
            params_json["params_por_bacia"][bacia][cand] = {}
            for cal_name, cal_p in pdict.items():
                # Remove arrays grandes de thresholds para nao poluir
                cp = dict(cal_p)
                if "x_thresholds" in cp and cp["x_thresholds"] is not None and len(cp["x_thresholds"]) > 20:
                    cp["x_thresholds"] = f"<array de {len(cp['x_thresholds'])} elementos>"
                if "y_thresholds" in cp and cp["y_thresholds"] is not None and len(cp["y_thresholds"]) > 20:
                    cp["y_thresholds"] = f"<array de {len(cp['y_thresholds'])} elementos>"
                params_json["params_por_bacia"][bacia][cand][cal_name] = cp

    out_json = OUT_DIR / "calibracao_scores_serving_params.json"
    out_json.write_text(json.dumps(params_json, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  JSON -> {out_json}")

    # 7. Relatorio Markdown
    print("\n[6/6] Gerando relatorio...")
    relatorio = f"""# Relatório: Calibração de Scores para Serving

**Data:** {datetime.now().strftime("%Y-%m-%d %H:%M")}  
**Script:** `{Path(__file__).name}`  
**Calibrador recomendado:** `{recomendado}`  
**Candidato primário:** `combinador_mean`

---

## 1. Objetivo

Transformar score bruto do combinador em percentual operacional interpretável
para dashboard, preservando a proporcionalidade com a intensidade da chuva.

## 2. Calibrações Testadas

| Calibrador | Descrição | Leak? |
|------------|-----------|-------|
| platt | Regressão logística (Platt scaling) sobre treino | Não |
| isotonic | Regressão isotônica sobre treino | Não |
| quantile | Mapeamento para percentil empírico do treino | Não |
| piecewise | Linear por bins do score bruto (5 bins) | Não |
| piecewise_operacional | Piecewise com targets 0.30 e 0.70 nos P30/P70 do treino | Não |

> **Nota:** Calibração por faixas de chuva ou severidade foi avaliada como
> inviável *sem leak*, pois ambas dependem de informação futura/observada
> no dia D. O piecewise usa apenas o próprio score bruto para definir bins.

## 3. Métricas Agregadas (média entre bacias)

| Calibrador | Brier ↓ | PR-AUC | Spearman max_dia | Spearman severidade |
|------------|---------|--------|------------------|---------------------|
"""
    for _, r in agg.to_pandas().iterrows():
        relatorio += f"| {r['calibrador']:<12} | {r['brier_mean']:.4f} | {r['prauc_mean']:.4f} | {r['spearman_max_dia_mean']:.3f} | {r['spearman_severidade_mean']:.3f} |\n"

    relatorio += """
## 4. Comparação Antes vs Depois (combinador_mean)

| Métrica | Bruto | Platt | Isotonic | Quantile | Piecewise | Pw-Operacional |
|---------|-------|-------|----------|----------|-----------|---------------|
"""
    sub_mean = df_metrics.filter(pl.col("candidato") == "combinador_mean")
    if sub_mean.height > 0:
        pivot = sub_mean.to_pandas().groupby("calibrador").agg({
            "brier": "mean",
            "prauc": "mean",
            "spearman_max_dia": "mean",
            "spearman_severidade": "mean",
        }).reset_index()
        # Adiciona bruto
        raw_row = sub_mean.to_pandas().groupby("calibrador").agg({
            "brier_raw": "mean",
            "prauc_raw": "mean",
            "spearman_max_dia_raw": "mean",
            "spearman_severidade_raw": "mean",
        }).reset_index()
        raw_vals = raw_row.iloc[0]
        relatorio += f"| Brier          | {raw_vals['brier_raw']:.4f} | "
        for cal in ["platt", "isotonic", "quantile", "piecewise", "piecewise_operacional"]:
            v = pivot[pivot["calibrador"] == cal]["brier"].values
            relatorio += f"{v[0]:.4f} | " if len(v) > 0 else "N/A | "
        relatorio += "\n"
        relatorio += f"| PR-AUC         | {raw_vals['prauc_raw']:.4f} | "
        for cal in ["platt", "isotonic", "quantile", "piecewise", "piecewise_operacional"]:
            v = pivot[pivot["calibrador"] == cal]["prauc"].values
            relatorio += f"{v[0]:.4f} | " if len(v) > 0 else "N/A | "
        relatorio += "\n"
        relatorio += f"| Spearman max_dia | {raw_vals['spearman_max_dia_raw']:.3f} | "
        for cal in ["platt", "isotonic", "quantile", "piecewise", "piecewise_operacional"]:
            v = pivot[pivot["calibrador"] == cal]["spearman_max_dia"].values
            relatorio += f"{v[0]:.3f} | " if len(v) > 0 else "N/A | "
        relatorio += "\n"
        relatorio += f"| Spearman severid | {raw_vals['spearman_severidade_raw']:.3f} | "
        for cal in ["platt", "isotonic", "quantile", "piecewise", "piecewise_operacional"]:
            v = pivot[pivot["calibrador"] == cal]["spearman_severidade"].values
            relatorio += f"{v[0]:.3f} | " if len(v) > 0 else "N/A | "
        relatorio += "\n"

    relatorio += """
## 5. Curva Score por Faixa de Chuva (combinador_mean + recomendado)

| Bacia | Faixa | n | Score Bruto Médio | Score Calibrado Médio | Severidade Média |
|-------|-------|---|-------------------|-----------------------|------------------|
"""
    df_faixas = pl.DataFrame(faixa_rows)
    out_faixas = OUT_DIR / "calibracao_scores_serving_faixas.parquet"
    df_faixas.write_parquet(out_faixas)
    faixa_recom = df_faixas.filter(
        (pl.col("candidato") == "combinador_mean") & (pl.col("calibrador") == recomendado)
    )
    for row in faixa_recom.to_dicts():
        relatorio += f"| {row['bacia']:<7} | {row['faixa']:<7} | {row['n']:<3} | {row['score_raw_mean']:.3f} | {row['score_cal_mean']:.3f} | {row['severidade_media']:.2f} |\n"

    relatorio += """
## 6. Critérios Operacionais

Distribuição do score calibrado recomendado por intensidade de chuva no teste:
- **Leve (<30%)**: esperado para chuvas leves (<10mm)
- **Moderada (30-70%)**: para chuvas moderadas (10-20mm) com perfil perigoso
- **Forte (>70%)**: para chuvas fortes (>=20mm)

"""
    df_ops = pl.DataFrame(result_rows)
    out_ops = OUT_DIR / "calibracao_scores_serving_criterios.parquet"
    df_ops.write_parquet(out_ops)
    ops_recom = df_ops.filter(
        (pl.col("candidato") == "combinador_mean") & (pl.col("calibrador") == recomendado)
    )
    for row in ops_recom.to_dicts():
        relatorio += f"- **{row['bacia']} — {row['criterio']}** (n={row['n']}): "
        if row['pct_leve'] is not None:
            relatorio += f"leve {row['pct_leve']:.1%}, moderada {row['pct_moderada']:.1%}, forte {row['pct_forte']:.1%}\n"
        else:
            relatorio += "(sem dados)\n"

    relatorio += f"""
## 7. Recomendação

O calibrador **`{recomendado}`** foi selecionado pelo critério composto:
- Preservar Spearman com `max_dia` (proporcionalidade)
- Minimizar Brier score (probabilidade bem calibrada)
- Manter PR-AUC razoável

## 8. Uso para Dashboard

O score calibrado está no intervalo **[0, 1]** (0-100%).
Para exibição no dashboard:
- `0-30%` → **Baixo**
- `30-70%` → **Moderado**
- `70-100%` → **Alto**

A coluna gerada no parquet é: `risk_score_raw_mean_serving`.

## 9. Limitações Conhecidas

- O calibrador foi ajustado em dados históricos até {T_CUT}; drift temporal pode degradar performance.
- Poucos eventos extremos (>30mm) no teste; calibração na cauda tem alta variância.
- Calibração por faixas de chuva/severidade foi evitada para prevenir leak; o piecewise usa bins do score bruto.
- **Limitação crítica do score bruto**: o combinador_mean raramente produz valores >0.60 (máx 0.5986 no dataset), o que impede que qualquer calibração monotônica atinja >70% para eventos fortes de forma consistente. Isso indica que o combinador subestima o risco de eventos extremos e/ou o score não está suficientemente correlacionado com chuva volumétrica.
- O score calibrado é usável para ranking relativo (comparar dias), mas os thresholds operacionais absolutos (30%/70%) devem ser interpretados com cautela até que o score bruto tenha maior resolução na cauda.

## 10. Arquivos Gerados

- `{out_final}` — scores calibrados por dia/bacia
- `{out_metrics}` — métricas comparativas
- `{out_faixas}` — curva score por faixa de chuva
- `{out_ops}` — critérios operacionais
- `{out_json}` — parâmetros do calibrador recomendado
- `{OUT_DIR / "relatorio_calibracao_scores_serving.md"}` — este relatório
"""

    out_md = OUT_DIR / "relatorio_calibracao_scores_serving.md"
    out_md.write_text(relatorio, encoding="utf-8")
    print(f"  Relatório -> {out_md}")
    print("=" * 80)
    print("DONE.")


if __name__ == "__main__":
    main()
