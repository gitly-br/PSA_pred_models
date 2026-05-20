"""
_bias_correction_openmeteo_cemaden.py

Testa bias correction / downscaling simples de OpenMeteo (ERA5-Land multipoint)
para escala CEMADEN por bacia, com o objetivo de melhorar a detecção de perfis
perigosos (pancada, prolongada).

Contexto: OpenMeteo/ERA5 suaviza extremos e subestima/espalha chuva convectiva.
Este script avalia métodos simples e auditáveis de correção de viés.

Métodos testados:
  1. Baseline (sem correção)
  2. Multiplicador ótimo por bacia/horizonte
  3. Quantile mapping (empírico, 100 quantis)
  4. Regressão linear (OLS)
  5. Regressão robusta (Theil-Sen)

Avaliação:
  - Métricas de erro: MAE, RMSE, Spearman ρ
  - Erro em cauda: p90, p95 absoluto e relativo
  - Recall de eventos de chuva alta (threshold por percentil CEMADEN)
  - Classificação de perfis perigosos (pancada/prolongada) por percentis CEMADEN

Saídas:
  - notebooks/dados/results/bias_correction_metrics.parquet
  - notebooks/dados/results/bias_correction_perfil.parquet
  - notebooks/dados/results/bias_correction_detalhado.parquet
  - notebooks/dados/results/bias_correction_report.md
  - notebooks/dados/results/bias_correction_scatter.png
  - notebooks/dados/results/bias_correction_boxplot.png
"""

import json
import warnings
from datetime import date, datetime
from pathlib import Path

import matplotlib
import numpy as np
import polars as pl
from scipy import stats
from sklearn.linear_model import LinearRegression, TheilSenRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# ─── Paths ──────────────────────────────────────────────────────────────────
WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ─────────────────────────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
HORIZONTES = [12, 24, 48]
T_CUT = datetime(2023, 7, 2).date()

# Thresholds de chuva intensa para recall
PERCENTIS_EVENTO = [0.80, 0.90, 0.95]

# Perfis de chuva (percentis CEMADEN por bacia, calculados no treino)
PERFIL_PANCADA_PCT = 0.90      # max_dia >= p90
PERFIL_PROLONGADA_PCT = 0.85   # acum_dia >= p85
PERFIL_MIN_HORAS = 8           # horas com chuva > 0.5 mm

# ─── 1. Carga de dados ──────────────────────────────────────────────────────

def load_cemaden():
    """Carrega CEMADEN horário e retorna df com chuva_max_mm por hora/bacia."""
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
                pl.sum_horizontal([(pl.col(c) > 0.5).cast(pl.Int16) for c in est_cols]).alias("n_chovendo"),
            ])
            .select(["hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
    return pl.concat(partes).sort(["bacia", "hora"])


def load_openmeteo():
    """Carrega ERA5-Land multipoint e retorna df horário com precipitação média por bacia."""
    with open(WORKDIR / "dados" / "weather" / "openmeteo_multipoint" / "index.json") as f:
        index = json.load(f)

    dfs = []
    for bacia, pts in index.items():
        series = []
        for pt in pts:
            lat_s = f"m{abs(pt['lat']):.6f}"
            lon_s = f"m{abs(pt['lon']):.6f}"
            fname = f"pt_{lat_s}_{lon_s}.parquet"
            fpath = WORKDIR / "dados" / "weather" / "openmeteo_multipoint" / fname
            if not fpath.exists():
                continue
            s = pl.read_parquet(fpath).select(["dt", "precipitation_mm"])
            series.append(s.rename({"precipitation_mm": f"prec_{pt['lat']:.4f}_{pt['lon']:.4f}"}))
        if not series:
            continue
        df_b = series[0]
        for s in series[1:]:
            df_b = df_b.join(s, on="dt", how="full", coalesce=True)
        pcols = [c for c in df_b.columns if c.startswith("prec_")]
        df_b = (
            df_b.with_columns(pl.mean_horizontal(pcols).alias("precipitation_mm"))
            .select(["dt", "precipitation_mm"])
            .sort("dt")
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
        dfs.append(df_b)
    return pl.concat(dfs).sort(["bacia", "dt"])


# ─── 2. Agregação diária + horizontes ───────────────────────────────────────

def build_daily_cemaden(df_cem):
    """Agrega CEMADEN em estatísticas diárias por bacia."""
    df_h = df_cem.with_columns(pl.col("hora").dt.date().alias("data"))
    return (
        df_h.group_by(["data", "bacia"])
        .agg([
            pl.col("chuva_max_mm").max().alias("max_dia"),
            pl.col("chuva_max_mm").sum().alias("acum_dia"),
            pl.col("chuva_mean_mm").mean().alias("mean_dia"),
            pl.col("chuva_std_mm").mean().alias("std_dia"),
            pl.col("n_chovendo").max().alias("n_chovendo_max"),
            pl.col("chuva_max_mm").max().alias("pico_1h"),
            (pl.col("chuva_max_mm") >= 5.0).sum().alias("horas_intensas"),
            (pl.col("chuva_max_mm") > 0.5).sum().alias("n_hours_rain"),
        ])
        .sort(["bacia", "data"])
    )


def build_horizons_openmeteo(df_om):
    """
    Para cada dia D e bacia, calcula acumulados de precipitação nas próximas
    12h, 24h e 48h a partir de D 00:00. Isso simula forecast de horizonte fixo.
    Retorna df com colunas forecast_12h, forecast_24h, forecast_48h por data/bacia.
    """
    # garante dt como datetime
    df = df_om.with_columns(pl.col("dt").alias("hora")).sort(["bacia", "hora"])

    resultados = []
    for h in HORIZONTES:
        df_h = (
            df.with_columns([
                pl.col("precipitation_mm").rolling_sum(window_size=h, min_samples=int(h * 0.8)).over("bacia").alias(f"forecast_{h}h"),
            ])
            .filter(pl.col("hora").dt.hour() == 0)
            .with_columns(pl.col("hora").dt.date().alias("data"))
            .select(["data", "bacia", f"forecast_{h}h"])
        )
        resultados.append(df_h)

    df_out = resultados[0]
    for df_r in resultados[1:]:
        df_out = df_out.join(df_r, on=["data", "bacia"], how="inner")
        for c in [c for c in df_out.columns if c.endswith("_right")]:
            df_out = df_out.drop(c)
    return df_out.sort(["bacia", "data"])


# ─── 3. Métodos de correção ─────────────────────────────────────────────────

def fit_multiplier(y_true, y_pred):
    """Fator de escala ótimo que minimiza MAE: median(y_true / y_pred)."""
    ratio = y_true / (y_pred + 1e-9)
    ratio = ratio[(ratio > 0) & np.isfinite(ratio)]
    return float(np.median(ratio)) if len(ratio) > 0 else 1.0


def fit_quantile_mapping(y_true, y_pred, n_quantiles=100):
    """Retorna função que mapeia quantis de y_pred para quantis de y_true."""
    quantiles = np.linspace(0, 1, n_quantiles)
    q_true = np.quantile(y_true, quantiles)
    q_pred = np.quantile(y_pred, quantiles)

    def mapper(x):
        # interpolação linear inversa: dado valor em escala pred, qual o quantil?
        # depois mapeia para escala true
        # evita extrapolação agressiva limitando aos quantis observados
        return np.interp(x, q_pred, q_true, left=q_true[0], right=q_true[-1])
    return mapper


def fit_linear(y_true, y_pred):
    """Regressão linear simples y_true ~ a + b * y_pred."""
    X = y_pred.reshape(-1, 1)
    model = LinearRegression().fit(X, y_true)
    return model


def fit_robust(y_true, y_pred):
    """Regressão robusta Theil-Sen."""
    X = y_pred.reshape(-1, 1)
    model = TheilSenRegressor(max_subpopulation=1e4, random_state=42)
    model.fit(X, y_true)
    return model


# ─── 4. Avaliação ───────────────────────────────────────────────────────────

def compute_metrics(y_true, y_pred):
    """Retorna dict com métricas de erro e correlação."""
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    rho, pval = stats.spearmanr(y_true, y_pred)
    return {
        "mae": float(mae),
        "rmse": float(rmse),
        "spearman_rho": float(rho),
        "spearman_p": float(pval),
    }


def compute_tail_errors(y_true, y_pred, percentis=[0.90, 0.95]):
    """Erro médio absoluto nos percentis superiores."""
    res = {}
    for p in percentis:
        thr = np.quantile(y_true, p)
        mask = y_true >= thr
        if mask.sum() == 0:
            res[f"mae_p{int(p*100):02d}"] = np.nan
            res[f"bias_p{int(p*100):02d}"] = np.nan
            res[f"recall_p{int(p*100):02d}"] = np.nan
        else:
            res[f"mae_p{int(p*100):02d}"] = float(mean_absolute_error(y_true[mask], y_pred[mask]))
            res[f"bias_p{int(p*100):02d}"] = float(np.mean(y_pred[mask] - y_true[mask]))
            # recall: quantos eventos extremos reais foram preditos acima do threshold de predição
            thr_pred = np.quantile(y_pred, p)
            res[f"recall_p{int(p*100):02d}"] = float(np.mean(y_pred[mask] >= thr_pred))
    return res


def compute_perfil_accuracy(y_true_max, y_true_acum, y_true_hours,
                            y_pred_max, y_pred_acum,
                            thr_max, thr_acum):
    """
    Classifica perfis perigosos usando thresholds derivados de CEMADEN
    e mede acurácia de recall do forecast corrigido.
    """
    # Ground truth
    gt_pancada = (y_true_max >= thr_max).astype(int)
    gt_prolong = ((y_true_acum >= thr_acum) & (y_true_hours >= PERFIL_MIN_HORAS)).astype(int)
    gt_comb = ((gt_pancada == 1) | (gt_prolong == 1)).astype(int)

    # Predito (usando mesmos thresholds em escala corrigida)
    pred_pancada = (y_pred_max >= thr_max).astype(int)
    pred_prolong = ((y_pred_acum >= thr_acum) & (y_true_hours >= PERFIL_MIN_HORAS)).astype(int)
    pred_comb = ((pred_pancada == 1) | (pred_prolong == 1)).astype(int)

    def _recall(gt, pred):
        pos = gt == 1
        return float(pred[pos].mean()) if pos.sum() > 0 else np.nan

    def _precision(gt, pred):
        pos = pred == 1
        return float(gt[pos].mean()) if pos.sum() > 0 else np.nan

    def _f1(gt, pred):
        rec = _recall(gt, pred)
        prec = _precision(gt, pred)
        if np.isnan(rec) or np.isnan(prec) or (rec + prec) == 0:
            return np.nan
        return 2 * prec * rec / (prec + rec)

    return {
        "recall_pancada": _recall(gt_pancada, pred_pancada),
        "precision_pancada": _precision(gt_pancada, pred_pancada),
        "f1_pancada": _f1(gt_pancada, pred_pancada),
        "recall_prolongada": _recall(gt_prolong, pred_prolong),
        "precision_prolongada": _precision(gt_prolong, pred_prolong),
        "f1_prolongada": _f1(gt_prolong, pred_prolong),
        "recall_combinado": _recall(gt_comb, pred_comb),
        "precision_combinado": _precision(gt_comb, pred_comb),
        "f1_combinado": _f1(gt_comb, pred_comb),
        "n_pancada": int(gt_pancada.sum()),
        "n_prolongada": int(gt_prolong.sum()),
        "n_combinado": int(gt_comb.sum()),
    }


# ─── 5. Pipeline principal ──────────────────────────────────────────────────

def main():
    print("=" * 90)
    print("BIAS CORRECTION — OpenMeteo/ERA5-Land → CEMADEN (por bacia e horizonte)")
    print("=" * 90)

    # ── 5.1 Carrega dados ──
    print("\n[1] Carregando CEMADEN...")
    df_cem = load_cemaden()
    print(f"    CEMADEN shape: {df_cem.shape}")

    print("\n[2] Carregando OpenMeteo multipoint...")
    df_om = load_openmeteo()
    print(f"    OpenMeteo shape: {df_om.shape}")

    print("\n[3] Agregando diário CEMADEN...")
    df_cem_daily = build_daily_cemaden(df_cem)
    print(f"    CEMADEN daily shape: {df_cem_daily.shape}")

    print("\n[4] Construindo horizontes de forecast OpenMeteo...")
    df_om_horiz = build_horizons_openmeteo(df_om)
    print(f"    OpenMeteo horizons shape: {df_om_horiz.shape}")

    # ── 5.2 Merge ──
    df_join = (
        df_cem_daily.join(df_om_horiz, on=["data", "bacia"], how="inner")
        .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
        .sort(["bacia", "data"])
    )
    print(f"\n[5] Join final shape: {df_join.shape}")

    bacias = sorted(df_join["bacia"].unique().to_list())
    print(f"    Bacias: {bacias}")

    # ── 5.3 Split treino/teste ──
    df_train = df_join.filter(pl.col("data") < T_CUT)
    df_test = df_join.filter(pl.col("data") >= T_CUT)
    print(f"    Treino: {df_train.shape[0]} registros | Teste: {df_test.shape[0]} registros")

    # ── 5.4 Loop de correção ──
    metodos = ["baseline", "multiplicador", "quantile_mapping", "regressao_linear", "regressao_robusta"]
    resultados = []
    detalhado = []

    for bacia in bacias:
        tr_b = df_train.filter(pl.col("bacia") == bacia).to_pandas()
        te_b = df_test.filter(pl.col("bacia") == bacia).to_pandas()

        if len(tr_b) < 30 or len(te_b) < 5:
            print(f"  {bacia}: pulado (dados insuficientes)")
            continue

        # percentis de perfil (calculados no treino CEMADEN)
        thr_pancada = tr_b["max_dia"].quantile(PERFIL_PANCADA_PCT)
        thr_prolong = tr_b["acum_dia"].quantile(PERFIL_PROLONGADA_PCT)

        for h in HORIZONTES:
            col_fc = f"forecast_{h}h"
            if col_fc not in tr_b.columns:
                continue

            y_tr = tr_b["acum_dia"].values.astype(float)
            x_tr = tr_b[col_fc].values.astype(float)
            y_te = te_b["acum_dia"].values.astype(float)
            x_te = te_b[col_fc].values.astype(float)

            # remove NaNs do treino
            valid = np.isfinite(y_tr) & np.isfinite(x_tr)
            y_tr = y_tr[valid]
            x_tr = x_tr[valid]

            # remove NaNs do teste
            valid_te = np.isfinite(y_te) & np.isfinite(x_te)
            y_te_raw = y_te.copy()
            x_te_raw = x_te.copy()
            y_te = y_te[valid_te]
            x_te = x_te[valid_te]

            # filtra outras colunas do teste para alinhamento
            te_max = te_b["max_dia"].values.astype(float)[valid_te]
            te_hours = te_b["n_hours_rain"].values.astype(float)[valid_te]
            te_b_valid = te_b[valid_te].reset_index(drop=True)

            if len(y_tr) < 10 or len(y_te) < 3:
                continue

            # garante não-negativo
            x_tr = np.maximum(x_tr, 0.0)
            x_te = np.maximum(x_te, 0.0)

            # --- ajustes ---
            # 1) multiplicador
            mult = fit_multiplier(y_tr, x_tr)

            # 2) quantile mapping
            qm_mapper = fit_quantile_mapping(y_tr, x_tr, n_quantiles=100)

            # 3) regressão linear
            lr_model = fit_linear(y_tr, x_tr)

            # 4) regressão robusta
            try:
                robust_model = fit_robust(y_tr, x_tr)
            except Exception:
                robust_model = None

            # --- predições no teste ---
            preds = {
                "baseline": x_te,
                "multiplicador": x_te * mult,
                "quantile_mapping": qm_mapper(x_te),
                "regressao_linear": lr_model.predict(x_te.reshape(-1, 1)),
            }
            if robust_model is not None:
                preds["regressao_robusta"] = robust_model.predict(x_te.reshape(-1, 1))
            else:
                preds["regressao_robusta"] = preds["regressao_linear"]

            # garante não-negativo
            for k in preds:
                preds[k] = np.maximum(preds[k], 0.0)

            # --- métricas ---
            for metodo, y_pred in preds.items():
                base = {
                    "bacia": bacia,
                    "horizonte": h,
                    "metodo": metodo,
                    "n_train": len(tr_b),
                    "n_test": len(te_b),
                    "multiplicador": mult if metodo == "multiplicador" else np.nan,
                }
                base.update(compute_metrics(y_te, y_pred))
                base.update(compute_tail_errors(y_te, y_pred, percentis=PERCENTIS_EVENTO))

                # perfis (usando max_dia e acum_dia preditos)
                # Nota: para max_dia, aplicamos a mesma correção proporcional ao acumulado
                # já que ERA5 não tem max_dia direto. Usamos razão acum_corrigido / acum_raw
                # aplicada ao max_dia_raw aproximado (que é o forecast do próprio ERA5,
                # mas não temos max_dia no OM. Vamos usar a correção no acumulado para
                # classificar prolongada e usar o forecast como proxy de pico para pancada.
                # Simplificação operacional: usamos o próprio forecast corrigido como proxy
                # de ambos max_dia e acum_dia, já que são acumulados de horizonte.
                # Para ser mais justo, vamos usar o max_dia do CEMADEN observado no teste
                # como ground truth, e o forecast corrigido como preditor.

                # Aproximação: para classificação de perfil, usamos acum_corrigido como proxy
                # de max_dia (escala similar) já que não temos pico horário do OM.
                # Alternativa mais realista: usar o próprio forecast como max_dia proxy.
                perfil = compute_perfil_accuracy(
                    y_true_max=te_max,
                    y_true_acum=y_te,
                    y_true_hours=te_hours,
                    y_pred_max=y_pred,  # proxy
                    y_pred_acum=y_pred,
                    thr_max=thr_pancada,
                    thr_acum=thr_prolong,
                )
                base.update(perfil)
                resultados.append(base)

                # detalhado: uma linha por dia/método
                for idx in range(len(te_b_valid)):
                    detalhado.append({
                        "data": te_b_valid["data"].iloc[idx],
                        "bacia": bacia,
                        "horizonte": h,
                        "metodo": metodo,
                        "cemaden_acum_dia": float(y_te[idx]),
                        "cemaden_max_dia": float(te_b_valid["max_dia"].iloc[idx]),
                        "openmeteo_raw": float(x_te[idx]),
                        "openmeteo_corrigido": float(y_pred[idx]),
                    })

        print(f"  {bacia}: OK (train={len(tr_b)}, test={len(te_b)})")

    # ── 5.5 DataFrames de resultados ──
    df_res = pl.DataFrame(resultados)
    df_det = pl.DataFrame(detalhado)

    # ── 5.6 Tabelas resumo ──
    print("\n" + "=" * 90)
    print("RESULTADOS — Métricas de erro por bacia/horizonte/método")
    print("=" * 90)

    for bacia in bacias:
        print(f"\n--- {bacia.upper()} ---")
        sub = df_res.filter(pl.col("bacia") == bacia)
        for h in HORIZONTES:
            sub_h = sub.filter(pl.col("horizonte") == h)
            if sub_h.is_empty():
                continue
            print(f"\n  Horizonte H{h}h")
            print(f"  {'Método':<20} {'MAE':>7} {'RMSE':>7} {'Spear':>7} {'MAEp90':>8} {'MAEp95':>8} {'Rec p90':>8} {'Rec p95':>8}")
            for metodo in metodos:
                row = sub_h.filter(pl.col("metodo") == metodo)
                if row.is_empty():
                    continue
                r = row.to_dicts()[0]
                print(f"  {metodo:<20} {r['mae']:>7.2f} {r['rmse']:>7.2f} {r['spearman_rho']:>7.3f} "
                      f"{r.get('mae_p90', np.nan):>8.2f} {r.get('mae_p95', np.nan):>8.2f} "
                      f"{r.get('recall_p90', np.nan):>8.3f} {r.get('recall_p95', np.nan):>8.3f}")

    print("\n" + "=" * 90)
    print("RESULTADOS — Classificação de perfis (recall)")
    print("=" * 90)
    for bacia in bacias:
        print(f"\n--- {bacia.upper()} ---")
        sub = df_res.filter(pl.col("bacia") == bacia)
        for h in HORIZONTES:
            sub_h = sub.filter(pl.col("horizonte") == h)
            if sub_h.is_empty():
                continue
            print(f"\n  Horizonte H{h}h")
            print(f"  {'Método':<20} {'RecPanc':>8} {'PrecPanc':>9} {'RecProl':>8} {'PrecProl':>9} {'RecComb':>8} {'PrecComb':>9}")
            for metodo in metodos:
                row = sub_h.filter(pl.col("metodo") == metodo)
                if row.is_empty():
                    continue
                r = row.to_dicts()[0]
                print(f"  {metodo:<20} {r.get('recall_pancada', np.nan):>8.3f} {r.get('precision_pancada', np.nan):>9.3f} "
                      f"{r.get('recall_prolongada', np.nan):>8.3f} {r.get('precision_prolongada', np.nan):>9.3f} "
                      f"{r.get('recall_combinado', np.nan):>8.3f} {r.get('precision_combinado', np.nan):>9.3f}")

    # ── 5.7 Identifica vencedor por bacia/horizonte ──
    vencedores = []
    for bacia in bacias:
        for h in HORIZONTES:
            sub = df_res.filter((pl.col("bacia") == bacia) & (pl.col("horizonte") == h))
            if sub.is_empty():
                continue
            # critério composto: minimizar MAE e maximizar recall combinado
            sub_pd = sub.to_pandas()
            sub_pd["score"] = -sub_pd["mae"] + 50 * sub_pd["recall_combinado"]
            best = sub_pd.loc[sub_pd["score"].idxmax()]
            vencedores.append({
                "bacia": bacia,
                "horizonte": h,
                "metodo": best["metodo"],
                "mae": float(best["mae"]),
                "rmse": float(best["rmse"]),
                "spearman_rho": float(best["spearman_rho"]),
                "recall_combinado": float(best["recall_combinado"]),
                "f1_combinado": float(best["f1_combinado"]),
            })
    df_venc = pl.DataFrame(vencedores)

    print("\n" + "=" * 90)
    print("MÉTODO VENCEDOR por bacia/horizonte (score = -MAE + 50*recall_combinado)")
    print("=" * 90)
    print(df_venc.to_pandas().to_string(index=False))

    # ── 5.8 Plots ──
    print("\n[6] Gerando visualizações...")

    # Scatter: CEMADEN vs OpenMeteo (baseline e melhor correção)
    fig, axes = plt.subplots(len(bacias), len(HORIZONTES), figsize=(4 * len(HORIZONTES), 4 * len(bacias)), squeeze=False)
    for i, bacia in enumerate(bacias):
        for j, h in enumerate(HORIZONTES):
            ax = axes[i][j]
            sub = df_det.filter((pl.col("bacia") == bacia) & (pl.col("horizonte") == h))
            if sub.is_empty():
                ax.set_visible(False)
                continue

            # baseline
            base = sub.filter(pl.col("metodo") == "baseline")
            # melhor método
            best_met = df_venc.filter((pl.col("bacia") == bacia) & (pl.col("horizonte") == h))
            best_metodo = best_met["metodo"].to_list()[0] if not best_met.is_empty() else "baseline"
            best = sub.filter(pl.col("metodo") == best_metodo)

            x_base = base["cemaden_acum_dia"].to_numpy()
            y_base = base["openmeteo_raw"].to_numpy()
            x_best = best["cemaden_acum_dia"].to_numpy()
            y_best = best["openmeteo_corrigido"].to_numpy()

            ax.scatter(x_base, y_base, alpha=0.3, s=15, label="baseline", color="gray")
            ax.scatter(x_best, y_best, alpha=0.5, s=15, label=f"{best_metodo}", color="darkgreen")
            max_val = max(np.nanmax(x_base), np.nanmax(y_base), np.nanmax(y_best)) * 1.05
            ax.plot([0, max_val], [0, max_val], "r--", lw=1)
            ax.set_xlim(0, max_val)
            ax.set_ylim(0, max_val)
            ax.set_xlabel("CEMADEN acum (mm)")
            ax.set_ylabel("OpenMeteo acum (mm)")
            ax.set_title(f"{bacia} H{h}h")
            ax.legend(loc="upper left", fontsize=7)
    plt.tight_layout()
    scatter_path = OUT_DIR / "bias_correction_scatter.png"
    plt.savefig(scatter_path, dpi=150)
    plt.close()
    print(f"    Scatter salvo em {scatter_path}")

    # Boxplot: erro absoluto por método
    df_err = df_det.with_columns(
        (pl.col("openmeteo_raw") - pl.col("cemaden_acum_dia")).abs().alias("err_baseline"),
        (pl.col("openmeteo_corrigido") - pl.col("cemaden_acum_dia")).abs().alias("err_corrigido"),
    )
    fig, axes = plt.subplots(len(bacias), len(HORIZONTES), figsize=(4 * len(HORIZONTES), 4 * len(bacias)), squeeze=False)
    for i, bacia in enumerate(bacias):
        for j, h in enumerate(HORIZONTES):
            ax = axes[i][j]
            sub = df_err.filter((pl.col("bacia") == bacia) & (pl.col("horizonte") == h))
            if sub.is_empty():
                ax.set_visible(False)
                continue
            data_box = []
            labels_box = []
            for metodo in metodos:
                s = sub.filter(pl.col("metodo") == metodo)
                if s.is_empty():
                    continue
                arr = s["err_corrigido"].to_numpy() if metodo != "baseline" else s["err_baseline"].to_numpy()
                data_box.append(arr)
                labels_box.append(metodo.replace("_", "\n"))
            ax.boxplot(data_box, labels=labels_box, showfliers=False)
            ax.set_ylabel("|Erro| (mm)")
            ax.set_title(f"{bacia} H{h}h")
            ax.tick_params(axis="x", labelsize=6)
    plt.tight_layout()
    box_path = OUT_DIR / "bias_correction_boxplot.png"
    plt.savefig(box_path, dpi=150)
    plt.close()
    print(f"    Boxplot salvo em {box_path}")

    # ── 5.9 Salva arquivos ──
    df_res.write_parquet(OUT_DIR / "bias_correction_metrics.parquet")
    df_det.write_parquet(OUT_DIR / "bias_correction_detalhado.parquet")
    df_venc.write_parquet(OUT_DIR / "bias_correction_vencedores.parquet")

    # Cria tabela de perfil agregada
    perfil_agg = []
    for bacia in bacias:
        for h in HORIZONTES:
            sub = df_res.filter((pl.col("bacia") == bacia) & (pl.col("horizonte") == h))
            if sub.is_empty():
                continue
            for metodo in metodos:
                r = sub.filter(pl.col("metodo") == metodo).to_dicts()
                if not r:
                    continue
                r = r[0]
                perfil_agg.append({
                    "bacia": bacia,
                    "horizonte": h,
                    "metodo": metodo,
                    "recall_pancada": r.get("recall_pancada", np.nan),
                    "precision_pancada": r.get("precision_pancada", np.nan),
                    "f1_pancada": r.get("f1_pancada", np.nan),
                    "recall_prolongada": r.get("recall_prolongada", np.nan),
                    "precision_prolongada": r.get("precision_prolongada", np.nan),
                    "f1_prolongada": r.get("f1_prolongada", np.nan),
                    "recall_combinado": r.get("recall_combinado", np.nan),
                    "precision_combinado": r.get("precision_combinado", np.nan),
                    "f1_combinado": r.get("f1_combinado", np.nan),
                    "n_pancada": r.get("n_pancada", 0),
                    "n_prolongada": r.get("n_prolongada", 0),
                    "n_combinado": r.get("n_combinado", 0),
                })
    pl.DataFrame(perfil_agg).write_parquet(OUT_DIR / "bias_correction_perfil.parquet")

    # ── 5.10 Relatório markdown ──
    report_path = OUT_DIR / "bias_correction_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Relatório: Bias Correction OpenMeteo → CEMADEN\n\n")
        f.write(f"**Data:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("## Objetivo\n\n")
        f.write("Testar correções simples e auditáveis de viés entre OpenMeteo (ERA5-Land multipoint) "
                "e CEMADEN observado por bacia e horizonte, visando melhorar a detecção de perfis "
                "de chuva perigosos (pancada e prolongada).\n\n")
        f.write("## Dados\n\n")
        f.write(f"- **Fonte forecast:** ERA5-Land multipoint (OpenMeteo), 2016-2025\n")
        f.write(f"- **Fonte observada:** CEMADEN por bacia\n")
        f.write(f"- **Período de treino:** < {T_CUT}\n")
        f.write(f"- **Período de teste:** >= {T_CUT}\n")
        f.write(f"- **Meses analisados:** {MESES_CHUVOSOS}\n")
        f.write(f"- **Horizontes:** {HORIZONTES} horas\n\n")

        f.write("## Métodos testados\n\n")
        f.write("1. **Baseline:** sem correção (OpenMeteo raw)\n")
        f.write("2. **Multiplicador:** fator de escala ótimo (mediana da razão CEMADEN/OpenMeteo)\n")
        f.write("3. **Quantile Mapping:** mapeamento empírico de 100 quantis\n")
        f.write("4. **Regressão Linear:** OLS de CEMADEN ~ OpenMeteo\n")
        f.write("5. **Regressão Robusta (Theil-Sen):** regressão robusta a outliers\n\n")

        f.write("## Resultados por bacia/horizonte\n\n")
        for bacia in bacias:
            f.write(f"### {bacia.upper()}\n\n")
            for h in HORIZONTES:
                sub = df_res.filter((pl.col("bacia") == bacia) & (pl.col("horizonte") == h))
                if sub.is_empty():
                    continue
                f.write(f"#### Horizonte H{h}h\n\n")
                f.write(f"| Método | MAE | RMSE | Spearman ρ | MAE p90 | MAE p95 | Rec p90 | Rec p95 |\n")
                f.write(f"|--------|-----|------|------------|---------|---------|---------|---------|\n")
                for metodo in metodos:
                    row = sub.filter(pl.col("metodo") == metodo).to_dicts()
                    if not row:
                        continue
                    r = row[0]
                    f.write(f"| {metodo:<20} | {r['mae']:.2f} | {r['rmse']:.2f} | {r['spearman_rho']:.3f} | "
                            f"{r.get('mae_p90', np.nan):.2f} | {r.get('mae_p95', np.nan):.2f} | "
                            f"{r.get('recall_p90', np.nan):.3f} | {r.get('recall_p95', np.nan):.3f} |\n")
                f.write("\n")

                f.write(f"**Classificação de perfis:**\n\n")
                f.write(f"| Método | Rec Panc | Prec Panc | Rec Prol | Prec Prol | Rec Comb | Prec Comb |\n")
                f.write(f"|--------|----------|-----------|----------|-----------|----------|-----------|\n")
                for metodo in metodos:
                    row = sub.filter(pl.col("metodo") == metodo).to_dicts()
                    if not row:
                        continue
                    r = row[0]
                    f.write(f"| {metodo:<20} | {r.get('recall_pancada', np.nan):.3f} | {r.get('precision_pancada', np.nan):.3f} | "
                            f"{r.get('recall_prolongada', np.nan):.3f} | {r.get('precision_prolongada', np.nan):.3f} | "
                            f"{r.get('recall_combinado', np.nan):.3f} | {r.get('precision_combinado', np.nan):.3f} |\n")
                f.write("\n")

        f.write("## Método vencedor por bacia/horizonte\n\n")
        f.write("Critério: maximizar `score = -MAE + 50 * recall_combinado` (equilibra erro global e capacidade de detectar eventos perigosos).\n\n")
        f.write("| Bacia | Horizonte | Método | MAE | RMSE | Spearman ρ | Recall Comb | F1 Comb |\n")
        f.write("|-------|-----------|--------|-----|------|------------|-------------|---------|\n")
        for row in df_venc.to_dicts():
            f.write(f"| {row['bacia']:<11} | H{row['horizonte']:>2}h | {row['metodo']:<20} | {row['mae']:.2f} | "
                    f"{row['rmse']:.2f} | {row['spearman_rho']:.3f} | {row['recall_combinado']:.3f} | {row['f1_combinado']:.3f} |\n")
        f.write("\n")

        f.write("## Limitações\n\n")
        f.write("- **Dados de forecast:** usamos ERA5-Land histórico (reanálise) como proxy de forecast perfeito. "
                "Em operação real, o forecast terá erro de emissão adicional.\n")
        f.write("- **Máximo diário:** OpenMeteo fornece precipitação horária média dos pontos da grade. "
                "Não captura picos pontuais de estações individuais do CEMADEN.\n")
        f.write("- **Correção univariada:** apenas precipitação é corrigida. Temperatura, umidade e pressão "
                "não foram incluídas neste experimento.\n")
        f.write("- **Perfis:** classificação de 'pancada' usa max_dia do CEMADEN como ground truth, mas o forecast "
                "corrigido ainda é proxy de acumulado, não de pico horário.\n\n")

        f.write("## Recomendação\n\n")
        venc_counts = df_venc.group_by("metodo").len().sort("len", descending=True)
        if not venc_counts.is_empty():
            top = venc_counts.to_dicts()[0]
            f.write(f"O método mais frequente entre os vencedores foi **{top['metodo']}** ({top['len']} de {df_venc.height} combinações).\n")
        f.write("Para uso operacional, recomenda-se:\n")
        f.write("1. Calibrar o fator multiplicador por bacia/horizonte em janela rolante (ex: últimos 90 dias).\n")
        f.write("2. Validar com dados de forecast real (GFS/ICON) assim que disponíveis.\n")
        f.write("3. Considerar ensemble de multiplicador + quantile mapping para robustez.\n")
        f.write("4. Se o objetivo for apenas classificação de perfil, quantile mapping tende a preservar melhor a cauda.\n")

    print(f"\n[7] Relatório salvo em {report_path}")
    print(f"[7] Parquets salvos em {OUT_DIR}")
    print("\n" + "=" * 90)
    print("Experimento concluído.")
    print("=" * 90)


if __name__ == "__main__":
    main()
