"""
_perfis_chuva_forecast.py

Analisa dados de forecast do OpenMeteo para prever perfis de chuva preocupantes:
- PANCADA: evento pontual com pico alto e razão pico/média alta
- PROLONGADA: evento de longa duração com chuva moderada persistente

Usa dados históricos do OpenMeteo como proxy de forecast perfeito.
Ground truth (chuva real) vem dos dados CEMADEN por bacia.
"""

import json
import warnings
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit

warnings.filterwarnings("ignore")

WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
THRESHOLD_RAIN_HOUR = 0.5  # mm/h para contar como "hora chovendo"


def load_openmeteo_by_bacia():
    """Carrega dados multipoint do OpenMeteo e agrega por bacia (média)."""
    with open(WORKDIR / "dados" / "weather" / "openmeteo_multipoint" / "index.json") as f:
        index = json.load(f)

    dfs = []
    for bacia, pts in index.items():
        partes = []
        for pt in pts:
            lat_s = f"m{abs(pt['lat']):.6f}"
            lon_s = f"m{abs(pt['lon']):.6f}"
            fname = f"pt_{lat_s}_{lon_s}.parquet"
            fpath = WORKDIR / "dados" / "weather" / "openmeteo_multipoint" / fname
            if not fpath.exists():
                continue
            partes.append(pl.read_parquet(fpath))
        if not partes:
            continue
        df_concat = pl.concat(partes)
        df_b = (
            df_concat.group_by("dt")
            .agg([
                pl.col("precipitation_mm").mean().alias("precipitation_mm"),
                pl.col("temperature_c").mean().alias("temperature_c"),
                pl.col("humidity_pct").mean().alias("humidity_pct"),
                pl.col("wind_speed_kmh").mean().alias("wind_speed_kmh"),
                pl.col("pressure_hpa").mean().alias("pressure_hpa"),
            ])
            .sort("dt")
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
        dfs.append(df_b)
    return pl.concat(dfs).sort(["bacia", "dt"])


def load_cemaden_by_bacia():
    """Carrega dados CEMADEN e calcula chuva horária agregada por bacia."""
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        estacoes_bacia = json.load(f)

    partes = []
    for bacia, estacoes in estacoes_bacia.items():
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
    return pl.concat(partes).sort(["bacia", "hora"])


def build_forecast_features(df_om):
    """
    Para cada dia/bacia, calcula estatísticas de forecast nas próximas 24h, 48h, 72h.
    Usa dados futuros do OpenMeteo como proxy de forecast perfeito.
    
    Otimizado com operação de janela (rolling) no Polars.
    """
    df_h = df_om.with_columns(pl.col("dt").dt.date().alias("data"))

    resultados = []
    for janela_h in [24, 48, 72]:
        df_j = (
            df_h.sort(["bacia", "dt"])
            .with_columns([
                pl.col("precipitation_mm").rolling_max(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"max_precip_{janela_h}h"),
                pl.col("precipitation_mm").rolling_mean(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"mean_precip_{janela_h}h"),
                pl.col("precipitation_mm").rolling_std(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"std_precip_{janela_h}h"),
                pl.col("precipitation_mm").rolling_sum(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"acum_precip_{janela_h}h"),
                (pl.col("precipitation_mm") > THRESHOLD_RAIN_HOUR).cast(pl.Int32).rolling_sum(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"n_hours_rain_{janela_h}h"),
                pl.col("temperature_c").rolling_mean(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"mean_temp_{janela_h}h"),
                pl.col("humidity_pct").rolling_mean(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"mean_humidity_{janela_h}h"),
                pl.col("wind_speed_kmh").rolling_mean(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"mean_wind_{janela_h}h"),
                pl.col("pressure_hpa").rolling_mean(window_size=janela_h, min_samples=int(janela_h * 0.8)).over("bacia").alias(f"mean_pressure_{janela_h}h"),
            ])
            .filter(pl.col("dt").dt.hour() == 0)  # uma linha por dia (referência 00:00)
            .select([
                "data", "bacia",
                f"max_precip_{janela_h}h", f"mean_precip_{janela_h}h", f"std_precip_{janela_h}h",
                f"acum_precip_{janela_h}h", f"n_hours_rain_{janela_h}h",
                f"mean_temp_{janela_h}h", f"mean_humidity_{janela_h}h",
                f"mean_wind_{janela_h}h", f"mean_pressure_{janela_h}h",
            ])
        )
        resultados.append(df_j)

    df_out = resultados[0]
    for df_r in resultados[1:]:
        df_out = df_out.join(df_r, on=["data", "bacia"], how="inner")
        # remove possíveis colunas _right deixadas por joins anteriores
        for c in [c for c in df_out.columns if c.endswith("_right")]:
            df_out = df_out.drop(c)

    # Calcula razão max/mean
    for janela_h in [24, 48, 72]:
        df_out = df_out.with_columns(
            (pl.col(f"max_precip_{janela_h}h") / (pl.col(f"mean_precip_{janela_h}h") + 1e-9)).alias(f"razao_max_mean_{janela_h}h")
        )

    return df_out.sort(["bacia", "data"])


def build_real_rain_features(df_cem):
    """Calcula estatísticas diárias de chuva real (CEMADEN) por bacia."""
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
            (pl.col("chuva_max_mm") > THRESHOLD_RAIN_HOUR).sum().alias("n_hours_rain_real"),
        ])
        .sort(["bacia", "data"])
    )


def define_targets(df_real):
    """Define targets binários para pancada, prolongada e combinado."""
    return df_real.with_columns([
        # Perfil PANCADA: pico alto e razão pico/média alta
        (
            (pl.col("max_dia") >= 30.0) &
            (pl.col("max_dia") / (pl.col("mean_dia") + 1e-9) >= 3.0)
        ).alias("target_pancada"),
        # Perfil PROLONGADA: acumulado significativo e duração longa
        # Nota: originalmente solicitado mean>=10mm, mas como mean_dia é média horária,
        # usamos acum_dia>=10mm (acumulado diário) para viabilidade operacional.
        (
            (pl.col("acum_dia") >= 10.0) &
            (pl.col("n_hours_rain_real") >= 12)
        ).alias("target_prolongada"),
    ]).with_columns(
        (pl.col("target_pancada") | pl.col("target_prolongada")).alias("target_combinado")
    )


def train_eval_model(X_train, y_train, X_test, y_test):
    """Treina modelo e retorna métricas."""
    if y_train.sum() < 2:
        return {
            "prauc": 0.0, "recall": 0.0, "prec": 0.0, "f1": 0.0,
            "y_pred_prob": np.zeros(len(y_test)),
        }

    clf = GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05,
        max_depth=3, min_samples_leaf=10,
        subsample=0.8, max_features="sqrt",
        random_state=42,
    )
    clf.fit(X_train, y_train)
    y_prob = clf.predict_proba(X_test)[:, 1]

    prauc = average_precision_score(y_test, y_prob) if y_test.sum() > 0 else 0.0

    # threshold ótimo por F1 no train
    y_prob_train = clf.predict_proba(X_train)[:, 1]
    prec, rec, thrs = precision_recall_curve(y_train, y_prob_train)
    if len(thrs) > 0:
        f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
        thr = float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5
    else:
        thr = 0.5

    y_pred = (y_prob >= thr).astype(int)
    recall = recall_score(y_test, y_pred, zero_division=0)
    prec_sc = precision_score(y_test, y_pred, zero_division=0)
    f1_sc = f1_score(y_test, y_pred, zero_division=0)

    return {
        "prauc": float(prauc),
        "recall": float(recall),
        "prec": float(prec_sc),
        "f1": float(f1_sc),
        "thr": float(thr),
        "y_pred_prob": y_prob,
    }


def plot_prob_vs_rain(df_plot, out_path):
    """Plota distribuição de probabilidade predita por faixa de chuva real."""
    fig, ax = plt.subplots(figsize=(10, 6))
    faixas = [
        (0, 5, "0-5 mm"),
        (5, 20, "5-20 mm"),
        (20, 50, "20-50 mm"),
        (50, 100, "50-100 mm"),
        (100, 999, ">100 mm"),
    ]
    pos = []
    probs = []
    labels = []
    for lo, hi, lab in faixas:
        mask = (df_plot["max_dia"] >= lo) & (df_plot["max_dia"] < hi)
        if mask.sum() > 0:
            pos.append(len(pos))
            probs.append(df_plot.loc[mask, "prob_combinado"].mean())
            labels.append(lab)

    ax.bar(pos, probs, color="steelblue", edgecolor="black")
    ax.set_xticks(pos)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Prob. Predita Média (Evento Combinado)")
    ax.set_xlabel("Faixa de Chuva Real (max_dia)")
    ax.set_title("Forecast OpenMeteo: Probabilidade Predita vs Chuva Real")
    ax.set_ylim(0, max(probs) * 1.2 if probs else 1)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Plot salvo em: {out_path}")


def main():
    print("=" * 80)
    print("PERFIS DE CHUVA — FORECAST OPENMETEO")
    print("=" * 80)

    # ── 1. Carrega dados ──
    print("\n[1] Carregando dados OpenMeteo multipoint...")
    df_om = load_openmeteo_by_bacia()
    print(f"    OpenMeteo: {df_om.shape}")

    print("\n[2] Carregando dados CEMADEN (chuva real)...")
    df_cem = load_cemaden_by_bacia()
    print(f"    CEMADEN: {df_cem.shape}")

    # ── 2. Feature engineering ──
    print("\n[3] Calculando features de forecast (24h, 48h, 72h)...")
    df_forecast = build_forecast_features(df_om)
    print(f"    Forecast features: {df_forecast.shape}")

    print("\n[4] Calculando estatísticas reais de chuva por dia...")
    df_real = build_real_rain_features(df_cem)
    print(f"    Real rain features: {df_real.shape}")

    # ── 3. Define targets ──
    print("\n[5] Definindo targets (pancada, prolongada, combinado)...")
    df_real = define_targets(df_real)

    # Join: features do dia D (forecast para D) vs target do dia D (chuva real de D)
    # Isso simula um nowcast/forecast de curto prazo.
    df_ml = (
        df_forecast.with_columns(pl.col("data").cast(pl.Date))
        .join(df_real.with_columns(pl.col("data").cast(pl.Date)), on=["data", "bacia"], how="inner")
        .sort(["bacia", "data"])
    )

    # Filtra meses chuvosos
    df_ml = df_ml.with_columns(pl.col("data").dt.month().alias("mes"))
    df_ml = df_ml.filter(pl.col("mes").is_in(MESES_CHUVOSOS))

    feature_cols = [
        "max_precip_24h", "max_precip_48h", "max_precip_72h",
        "mean_precip_24h", "mean_precip_48h", "mean_precip_72h",
        "std_precip_24h", "std_precip_48h", "std_precip_72h",
        "acum_precip_24h", "acum_precip_48h", "acum_precip_72h",
        "n_hours_rain_24h", "n_hours_rain_48h", "n_hours_rain_72h",
        "razao_max_mean_24h", "razao_max_mean_48h", "razao_max_mean_72h",
        "mean_temp_24h", "mean_temp_48h", "mean_temp_72h",
        "mean_humidity_24h", "mean_humidity_48h", "mean_humidity_72h",
        "mean_wind_24h", "mean_wind_48h", "mean_wind_72h",
        "mean_pressure_24h", "mean_pressure_48h", "mean_pressure_72h",
    ]

    # ── 4. Treina e avalia por bacia ──
    print("\n[6] Treinando modelos com TimeSeriesSplit (5 splits) + holdout temporal...")
    print("-" * 80)

    all_results = []
    holdout_results = []
    plot_data = []

    for bacia in sorted(df_ml["bacia"].unique().to_list()):
        sub = df_ml.filter(pl.col("bacia") == bacia).sort("data").to_pandas()
        if len(sub) < 100:
            print(f"  {bacia}: pulado (dados insuficientes: {len(sub)})")
            continue

        X = sub[feature_cols].fillna(0).values
        y_panc = sub["target_pancada"].astype(int).values
        y_prol = sub["target_prolongada"].astype(int).values
        y_comb = sub["target_combinado"].astype(int).values
        max_dia = sub["max_dia"].values

        tscv = TimeSeriesSplit(n_splits=5)

        for target_name, y in [("pancada", y_panc), ("prolongada", y_prol), ("combinado", y_comb)]:
            oof_prob = np.full(len(y), np.nan)
            oof_pred = np.full(len(y), np.nan)

            for tr_idx, te_idx in tscv.split(X):
                X_train, X_test = X[tr_idx], X[te_idx]
                y_train, y_test = y[tr_idx], y[te_idx]

                if y_train.sum() < 2:
                    continue

                res = train_eval_model(X_train, y_train, X_test, y_test)
                oof_prob[te_idx] = res["y_pred_prob"]
                oof_pred[te_idx] = (res["y_pred_prob"] >= res["thr"]).astype(int)

            mask = ~np.isnan(oof_prob)
            if mask.sum() == 0 or y[mask].sum() == 0:
                continue

            prauc = average_precision_score(y[mask], oof_prob[mask])
            recall = recall_score(y[mask], oof_pred[mask], zero_division=0)
            prec = precision_score(y[mask], oof_pred[mask], zero_division=0)
            f1 = f1_score(y[mask], oof_pred[mask], zero_division=0)

            n_eventos = int(y[mask].sum())
            n_total = int(mask.sum())

            row = {
                "bacia": bacia,
                "perfil": target_name,
                "n_total": n_total,
                "n_eventos": n_eventos,
                "prauc": float(prauc),
                "recall": float(recall),
                "prec": float(prec),
                "f1": float(f1),
            }

            if target_name == "combinado":
                rho, pval = spearmanr(max_dia[mask], oof_prob[mask])
                row["spearman_rho"] = float(rho)
                row["spearman_p"] = float(pval)
                plot_df = sub.loc[mask].copy()
                plot_df["prob_combinado"] = oof_prob[mask]
                plot_data.append(plot_df)

            all_results.append(row)

            # ── Holdout temporal: train < 2023-07-02, test >= 2023-07-02 ──
            import pandas as pd
            T_CUT = pd.Timestamp("2023-07-02")
            train_mask = sub["data"] < T_CUT
            test_mask = sub["data"] >= T_CUT
            X_train_h = X[train_mask.values]
            X_test_h = X[test_mask.values]
            y_train_h = y[train_mask.values]
            y_test_h = y[test_mask.values]

            if y_train_h.sum() >= 2 and y_test_h.sum() > 0:
                res_h = train_eval_model(X_train_h, y_train_h, X_test_h, y_test_h)
                y_pred_h = (res_h["y_pred_prob"] >= res_h["thr"]).astype(int)
                holdout_results.append({
                    "bacia": bacia,
                    "perfil": target_name,
                    "train_n": int(train_mask.sum()),
                    "test_n": int(test_mask.sum()),
                    "test_eventos": int(y_test_h.sum()),
                    "prauc": float(average_precision_score(y_test_h, res_h["y_pred_prob"])),
                    "recall": float(recall_score(y_test_h, y_pred_h, zero_division=0)),
                    "prec": float(precision_score(y_test_h, y_pred_h, zero_division=0)),
                    "f1": float(f1_score(y_test_h, y_pred_h, zero_division=0)),
                })

        total_panc = int(y_panc.sum())
        total_prol = int(y_prol.sum())
        total_comb = int(y_comb.sum())
        print(f"  {bacia}: ok (n={len(sub)}, eventos pancada={total_panc}, prolongada={total_prol}, combinado={total_comb})")

    # ── 5. Report ──
    print("\n" + "=" * 80)
    print("RESULTADOS AGREGADOS (média por bacia)")
    print("=" * 80)

    import pandas as pd
    df_res = pd.DataFrame(all_results)
    if df_res.empty:
        print("Nenhum resultado gerado.")
        return

    for perfil in ["pancada", "prolongada", "combinado"]:
        sub_res = df_res[df_res["perfil"] == perfil]
        if sub_res.empty:
            continue
        print(f"\n  Perfil: {perfil.upper()}")
        print(f"  {'Bacia':<15} {'N':>5} {'Eventos':>8} {'PRAUC':>7} {'Recall':>7} {'Prec':>7} {'F1':>7}")
        for _, r in sub_res.iterrows():
            print(f"  {r['bacia']:<15} {r['n_total']:>5} {r['n_eventos']:>8} {r['prauc']:>7.3f} {r['recall']:>7.3f} {r['prec']:>7.3f} {r['f1']:>7.3f}")
        print(f"  {'MÉDIA':<15} {'':>5} {'':>8} {sub_res['prauc'].mean():>7.3f} {sub_res['recall'].mean():>7.3f} {sub_res['prec'].mean():>7.3f} {sub_res['f1'].mean():>7.3f}")

    # Spearman rho report
    print("\n  Spearman ρ (max_dia real vs prob predita combinada):")
    comb = df_res[df_res["perfil"] == "combinado"]
    if not comb.empty and "spearman_rho" in comb.columns:
        for _, r in comb.iterrows():
            print(f"    {r['bacia']:<15} ρ = {r.get('spearman_rho', np.nan):.3f}  (p = {r.get('spearman_p', np.nan):.3e})")
        print(f"    {'MÉDIA':<15} ρ = {comb['spearman_rho'].mean():.3f}")

    # Salva resultados
    out_parquet = OUT_DIR / "perfis_chuva_forecast.parquet"
    df_res.to_parquet(out_parquet)
    print(f"\n  Resultados salvos em: {out_parquet}")

    # ── Holdout report ──
    print("\n" + "=" * 80)
    print("HOLDOUT TEMPORAL (train < 2023-07-02, test >= 2023-07-02)")
    print("=" * 80)
    df_hold = pd.DataFrame(holdout_results)
    if not df_hold.empty:
        for perfil in ["pancada", "prolongada", "combinado"]:
            sub_h = df_hold[df_hold["perfil"] == perfil]
            if sub_h.empty:
                continue
            print(f"\n  Perfil: {perfil.upper()}")
            print(f"  {'Bacia':<15} {'Train':>5} {'Test':>5} {'TestEv':>7} {'PRAUC':>7} {'Recall':>7} {'Prec':>7} {'F1':>7}")
            for _, r in sub_h.iterrows():
                print(f"  {r['bacia']:<15} {r['train_n']:>5} {r['test_n']:>5} {r['test_eventos']:>7} {r['prauc']:>7.3f} {r['recall']:>7.3f} {r['prec']:>7.3f} {r['f1']:>7.3f}")
            print(f"  {'MÉDIA':<15} {'':>5} {'':>5} {'':>7} {sub_h['prauc'].mean():>7.3f} {sub_h['recall'].mean():>7.3f} {sub_h['prec'].mean():>7.3f} {sub_h['f1'].mean():>7.3f}")
    else:
        print("  Nenhum resultado de holdout gerado (dados insuficientes ou sem eventos no teste).")

    # ── 6. Plot ──
    if plot_data:
        df_plot = pd.concat(plot_data, ignore_index=True)
        plot_path = OUT_DIR / "prob_vs_chuva_real.png"
        plot_prob_vs_rain(df_plot, plot_path)

    # ── 7. Comparativo ──
    print("\n" + "=" * 80)
    print("COMPARAÇÃO: FORECAST vs HISTÓRICO CEMADEN")
    print("=" * 80)
    print("  Nota: este script usa OpenMeteo (forecast proxy) como features.")
    print("  O benchmark v8 usa CEMADEN histórico (API, lags, etc.) como features.")
    print("  Comparativo qualitativo:")
    print("  - Forecast OpenMeteo captura condições meteorológicas futuras (temperatura, umidade, vento, pressão).")
    print("  - CEMADEN histórico captura persistência e memória do sistema (API, acumulados).")
    print("  - Os modelos aqui são complementares: um não substitui o outro.")
    print("  - Para avaliação rigorosa, seria necessário rodar benchmark v8 no mesmo split e comparar PRAUC/F1.")


if __name__ == "__main__":
    main()
