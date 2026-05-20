"""
Forecast Detector de Perfil Perigoso
====================================

Objetivo: testar se dados de forecast (OpenWeather histórico + OpenMeteo/ERA5
como proxy meteorológico) conseguem prever perfis meteorológicos perigosos
futuros medidos no CEMADEN, SEM usar chamados como alvo principal.

Pergunta correta: forecast não substitui CEMADEN histórico; forecast deve
antecipar se a próxima janela terá perfil perigoso.

Labels meteorológicos futuros (CEMADEN observado):
  - pancada:       pico de chuva alto em janela curta
  - prolongada:    acumulado alto em janela longa
  - saturante:     acumulado 48h futuro alto (proxy de saturação)
  - perigoso_any:  OR dos três acima

Thresholds por bacia definidos via percentis históricos no treino.
Features de forecast: OpenWeather forecast history agregado em janelas H6/H12/H24/H48.
Features meteorológicas: OpenMeteo/ERA5 multipoint do dia anterior (lag1).

Avaliação por bacia e horizonte:
  - PR-AUC
  - Recall / Precision em threshold operacional
  - Spearman com intensidade futura (max_dia nas próximas H horas)

ATENÇÃO: este script trata leak temporal como falha crítica. Todas as features
são estritamente anteriores ao período de target.
"""

import json
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ─── Paths ────────────────────────────────────────────────────────────────
WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
HORIZONTES = [6, 12, 24, 48]
T_CUT = datetime(2023, 7, 2).date()
K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0

# Percentis para thresholds de perfil (calculados no treino)
PCT_PANCADA = 0.95   # p95 de max_dia na janela
PCT_PROLONGADA = 0.90  # p90 de acumulado na janela
PCT_SATURANTE = 0.90   # p90 de acum_48h futuro

# ─── 1. CEMADEN: diários por bacia + targets futuros ─────────────────────

def build_cemaden_diario():
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

    # Diários
    df_h = df_chuva_h.with_columns([
        pl.col("hora").dt.date().alias("data"),
    ])
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

    # API com leak corrigido (shift 1 antes do lfilter)
    from scipy.signal import lfilter
    _api_parts = []
    for _bacia in df_diario["bacia"].unique().to_list():
        _sub = df_diario.filter(pl.col("bacia") == _bacia).sort("data")
        _vals = _sub["max_dia"].shift(1).fill_null(0).to_numpy()
        cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS:
            cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
        _api_parts.append(pl.DataFrame(cols))
    df_api = pl.concat(_api_parts)
    df_diario = df_diario.join(df_api, on=["data", "bacia"], how="left")

    # Acumulados passados (para feature de saturação passada)
    df_diario = df_diario.with_columns([
        pl.col("acum_dia").rolling_sum(window_size=7, min_samples=1).shift(1).over("bacia").alias("acum_7d_past"),
        pl.col("acum_dia").rolling_sum(window_size=30, min_samples=1).shift(1).over("bacia").alias("acum_30d_past"),
    ])

    return df_diario, estacoes_bacia


def compute_thresholds(df_diario: pl.DataFrame, t_cut: date):
    """Calcula thresholds por bacia usando apenas dados de treino (pré-t_cut)."""
    train = df_diario.filter(pl.col("data") < t_cut)
    thresholds = {}
    for bacia in train["bacia"].unique().to_list():
        sub = train.filter(pl.col("bacia") == bacia)
        thresholds[bacia] = {
            "pancada": float(sub["max_dia"].quantile(PCT_PANCADA)),
            "prolongada": float(sub["acum_dia"].quantile(PCT_PROLONGADA)),
            # saturante: usamos acum_48h futuro; threshold será calculado depois
        }
    return thresholds


def build_targets(df_diario: pl.DataFrame, thresholds: dict, horizontes: list):
    """
    Cria labels futuros para cada horizonte H.
    Target é calculado olhando para a FRENTE na série horária CEMADEN.
    Para cada dia T, queremos saber o perfil nas próximas H horas.
    """
    # Precisamos da série horária original para calcular targets em janelas H
    partes = []
    for bacia in thresholds:
        df = pl.read_parquet(WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet")
        est_cols = [c for c in df.columns if c != "hora"]
        partes.append(
            df.with_columns([
                pl.max_horizontal(est_cols).alias("chuva_max_mm"),
            ])
            .select(["hora", "chuva_max_mm"])
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
    df_h = pl.concat(partes).sort(["bacia", "hora"])

    result_rows = []
    for bacia in thresholds:
        sub_h = df_h.filter(pl.col("bacia") == bacia).sort("hora")
        sub_d = df_diario.filter(pl.col("bacia") == bacia).sort("data")
        datas = sub_d["data"].to_list()

        for data in datas:
            # Início da janela: data 00:00:00
            dt_start = datetime.combine(data, datetime.min.time())
            row = {"data": data, "bacia": bacia}

            for H in horizontes:
                dt_end = dt_start + pl.duration(hours=H)
                janela = sub_h.filter(
                    (pl.col("hora") >= dt_start) & (pl.col("hora") < dt_end)
                )

                if janela.height == 0:
                    row[f"max_dia_fut_h{H}"] = 0.0
                    row[f"acum_dia_fut_h{H}"] = 0.0
                    row[f"pancada_h{H}"] = False
                    row[f"prolongada_h{H}"] = False
                    continue

                max_fut = float(janela["chuva_max_mm"].max())
                acum_fut = float(janela["chuva_max_mm"].sum())
                row[f"max_dia_fut_h{H}"] = max_fut
                row[f"acum_dia_fut_h{H}"] = acum_fut
                row[f"pancada_h{H}"] = max_fut > thresholds[bacia]["pancada"]
                row[f"prolongada_h{H}"] = acum_fut > thresholds[bacia]["prolongada"]

            # saturante: acumulado 48h futuro (independente de H, mas associado ao dia)
            dt_end48 = dt_start + pl.duration(hours=48)
            janela48 = sub_h.filter(
                (pl.col("hora") >= dt_start) & (pl.col("hora") < dt_end48)
            )
            acum_48h = float(janela48["chuva_max_mm"].sum()) if janela48.height > 0 else 0.0
            row["acum_48h_fut"] = acum_48h

            result_rows.append(row)

    df_targets = pl.DataFrame(result_rows)
    # Calcular threshold de saturante por bacia (usando acum_48h futuro no treino)
    train_targets = df_targets.filter(pl.col("data") < T_CUT)
    sat_thresholds = {}
    for bacia in thresholds:
        sub = train_targets.filter(pl.col("bacia") == bacia)
        sat_thresholds[bacia] = float(sub["acum_48h_fut"].quantile(PCT_SATURANTE)) if sub.height > 0 else 100.0

    df_targets = df_targets.with_columns(
        pl.col("bacia").replace_strict(sat_thresholds, return_dtype=pl.Float64).alias("thr_saturante")
    )
    for H in horizontes:
        df_targets = df_targets.with_columns(
            (pl.col(f"pancada_h{H}") | pl.col(f"prolongada_h{H}") | (pl.col("acum_48h_fut") > pl.col("thr_saturante"))).alias(f"perigoso_any_h{H}")
        )
    df_targets = df_targets.with_columns(
        (pl.col("acum_48h_fut") > pl.col("thr_saturante")).alias("saturante")
    )

    return df_targets, sat_thresholds


# ─── 2. OpenWeather forecast features (real forecast com forecast_dt) ─────

def build_forecast_features(horizontes: list):
    """
    Agrega OpenWeather forecast history em janelas H a partir do forecast
    emitido às 00:00 de cada dia.
    """
    df_fc = pl.read_parquet(WORKDIR / "dados" / "weather" / "openweather_forecast_history.parquet")

    # Usar forecast emitido às 00:00 (ou o mais próximo anterior)
    # Cada forecast_dt tem slices futuras. Pegamos para cada dia o forecast de 00:00
    df_fc = df_fc.with_columns([
        pl.col("forecast_dt").dt.date().alias("data"),
        ((pl.col("slice_dt") - pl.col("forecast_dt")).dt.total_hours()).alias("horizon_slice_h"),
    ])

    # Filtrar apenas forecasts emitidos às 00:00
    df_fc_00 = df_fc.filter(pl.col("forecast_dt").dt.hour() == 0)

    rows = []
    for data in df_fc_00["data"].unique().sort().to_list():
        sub = df_fc_00.filter(pl.col("data") == data)
        if sub.height == 0:
            continue
        row = {"data": data}
        for H in horizontes:
            # slices no horizonte (0 <= horizon < H)
            janela = sub.filter((pl.col("horizon_slice_h") >= 0) & (pl.col("horizon_slice_h") < H))
            if janela.height == 0:
                row[f"fc_rain_sum_h{H}"] = 0.0
                row[f"fc_rain_max_h{H}"] = 0.0
                row[f"fc_prob_mean_h{H}"] = 0.0
                row[f"fc_prob_max_h{H}"] = 0.0
                row[f"fc_temp_mean_h{H}"] = None
                row[f"fc_humidity_mean_h{H}"] = None
                row[f"fc_wind_max_h{H}"] = None
                continue
            row[f"fc_rain_sum_h{H}"] = float(janela["rain"].sum())
            row[f"fc_rain_max_h{H}"] = float(janela["rain"].max())
            row[f"fc_prob_mean_h{H}"] = float(janela["probability"].mean())
            row[f"fc_prob_max_h{H}"] = float(janela["probability"].max())
            row[f"fc_temp_mean_h{H}"] = float(janela["temperature"].mean())
            row[f"fc_humidity_mean_h{H}"] = float(janela["humidity"].mean())
            row[f"fc_wind_max_h{H}"] = float(janela["wind_speed"].max())
        rows.append(row)

    return pl.DataFrame(rows)


# ─── 3. OpenMeteo/ERA5 features (proxy meteorológico, lag1) ──────────────

def build_openmeteo_features():
    """
    Usa OpenMeteo/ERA5 multipoint como proxy de condições meteorológicas atuais.
    Agrega por bacia (média dos pontos) e calcula lag1 (dia anterior).
    """
    with open(WORKDIR / "dados" / "weather" / "openmeteo_multipoint" / "index.json") as f:
        pontos_por_bacia = json.load(f)

    def _fname_pt(lat: float, lon: float) -> str:
        return f"pt_m{abs(lat):.6f}_m{abs(lon):.6f}.parquet"

    # Abordagem robusta: cada ponto agregado diariamente, depois média por bacia
    daily_parts = []
    for bacia, pontos in pontos_por_bacia.items():
        pts_daily = []
        for p in pontos:
            path = WORKDIR / "dados" / "weather" / "openmeteo_multipoint" / _fname_pt(p["lat"], p["lon"])
            s = pl.read_parquet(path)
            pts_daily.append(
                s.with_columns(pl.col("dt").dt.date().alias("data"))
                .group_by("data")
                .agg([
                    pl.col("precipitation_mm").sum().alias("precip_sum"),
                    pl.col("temperature_c").max().alias("temp_max"),
                    pl.col("temperature_c").min().alias("temp_min"),
                    pl.col("temperature_c").mean().alias("temp_mean"),
                    pl.col("humidity_pct").max().alias("humidity_max"),
                    pl.col("pressure_hpa").mean().alias("pressure_mean"),
                    pl.col("wind_speed_kmh").max().alias("wind_max"),
                ])
                .with_columns(pl.lit(bacia).alias("bacia"))
            )
        # Média dos pontos por bacia
        df_pts = pl.concat(pts_daily)
        df_bacia = (
            df_pts.group_by(["data", "bacia"])
            .agg([
                pl.col("precip_sum").mean().alias("om_precip_sum"),
                pl.col("temp_max").mean().alias("om_temp_max"),
                pl.col("temp_min").mean().alias("om_temp_min"),
                pl.col("temp_mean").mean().alias("om_temp_mean"),
                pl.col("humidity_max").mean().alias("om_humidity_max"),
                pl.col("pressure_mean").mean().alias("om_pressure_mean"),
                pl.col("wind_max").mean().alias("om_wind_max"),
            ])
        )
        daily_parts.append(df_bacia)

    df_om = pl.concat(daily_parts).sort(["bacia", "data"])

    # Lag1 (dia anterior) — sem leak temporal
    df_om = df_om.with_columns([
        pl.col("om_precip_sum").shift(1).over("bacia").alias("om_precip_sum_lag1"),
        pl.col("om_temp_max").shift(1).over("bacia").alias("om_temp_max_lag1"),
        pl.col("om_temp_min").shift(1).over("bacia").alias("om_temp_min_lag1"),
        pl.col("om_temp_mean").shift(1).over("bacia").alias("om_temp_mean_lag1"),
        pl.col("om_humidity_max").shift(1).over("bacia").alias("om_humidity_max_lag1"),
        pl.col("om_pressure_mean").shift(1).over("bacia").alias("om_pressure_mean_lag1"),
        pl.col("om_wind_max").shift(1).over("bacia").alias("om_wind_max_lag1"),
    ])

    return df_om.select([
        "data", "bacia",
        "om_precip_sum_lag1", "om_temp_max_lag1", "om_temp_min_lag1",
        "om_temp_mean_lag1", "om_humidity_max_lag1",
        "om_pressure_mean_lag1", "om_wind_max_lag1",
    ])


# ─── 4. CEMADEN passado (baseline minimal) ────────────────────────────────

def build_cemaden_past_features(df_diario: pl.DataFrame):
    """Features de CEMADEN passado: lags essenciais."""
    return df_diario.with_columns([
        pl.col("max_dia").shift(1).over("bacia").alias("max_day_lag1"),
        pl.col("max_dia").shift(2).over("bacia").alias("max_day_lag2"),
        pl.col("max_dia").shift(3).over("bacia").alias("max_day_lag3"),
        pl.col("acum_dia").shift(1).over("bacia").alias("acum_dia_lag1"),
        pl.col("acum_7d_past").alias("acum_7d"),
        pl.col("acum_30d_past").alias("acum_30d"),
        pl.col("api_070").alias("api_070"),
        pl.col("api_085").alias("api_085"),
        pl.col("api_095").alias("api_095"),
        (2 * np.pi * pl.col("data").dt.month() / 12).sin().alias("mes_sin"),
        (2 * np.pi * pl.col("data").dt.month() / 12).cos().alias("mes_cos"),
    ]).select([
        "data", "bacia", "max_day_lag1", "max_day_lag2", "max_day_lag3",
        "acum_dia_lag1", "acum_7d", "acum_30d",
        "api_070", "api_085", "api_095",
        "mes_sin", "mes_cos",
    ])


# ─── 5. Modelos e avaliação ───────────────────────────────────────────────

def _thr_f1(y_true, y_prob):
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5


def train_eval(X_train, X_test, y_train, y_test, max_dia_test, modelo="logreg"):
    """Treina modelo simples e retorna métricas."""
    if y_train.sum() < 2 or y_test.sum() == 0:
        return None

    if modelo == "logreg":
        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=42)),
        ])
    elif modelo == "gradboost":
        clf = GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=2,
            min_samples_leaf=10, subsample=0.8, max_features="sqrt",
            random_state=42,
        )
    else:
        raise ValueError(f"Modelo desconhecido: {modelo}")

    clf.fit(X_train, y_train)
    prob_test = clf.predict_proba(X_test)[:, 1]

    # Threshold por F1 no train (usando CV temporal simples)
    tscv = TimeSeriesSplit(n_splits=5)
    oof = np.full(len(y_train), np.nan)
    for tr_i, va_i in tscv.split(X_train):
        if y_train[tr_i].sum() == 0 or y_train[va_i].sum() == 0:
            continue
        clf_cv = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=42)),
        ]) if modelo == "logreg" else GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=2,
            min_samples_leaf=10, subsample=0.8, max_features="sqrt", random_state=42,
        )
        clf_cv.fit(X_train[tr_i], y_train[tr_i])
        oof[va_i] = clf_cv.predict_proba(X_train[va_i])[:, 1]
    mask = ~np.isnan(oof)
    thr = _thr_f1(y_train[mask], oof[mask]) if mask.sum() > 0 and y_train[mask].sum() > 0 else 0.5

    pred_test = (prob_test >= thr).astype(int)

    prauc = average_precision_score(y_test, prob_test)
    rec = recall_score(y_test, pred_test, zero_division=0)
    prec = precision_score(y_test, pred_test, zero_division=0)
    f1 = f1_score(y_test, pred_test, zero_division=0)

    # Spearman com intensidade futura (max_dia_test contínuo)
    rho, pval = spearmanr(max_dia_test, prob_test)

    return {
        "prauc": float(prauc),
        "recall": float(rec),
        "precision": float(prec),
        "f1": float(f1),
        "threshold": float(thr),
        "spearman_rho": float(rho),
        "spearman_p": float(pval),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "n_pos_train": int(y_train.sum()),
        "n_pos_test": int(y_test.sum()),
    }


def regra_calibrada_eval(X_train, X_test, y_train, y_test, max_dia_test, col_rain_idx: int):
    """
    Regra simples: threshold ótimo em uma única feature de chuva forecast.
    Retorna métricas comparáveis.
    """
    if y_train.sum() < 2 or y_test.sum() == 0:
        return None

    # Usa apenas a coluna de soma de chuva forecast
    rain_train = X_train[:, col_rain_idx]
    rain_test = X_test[:, col_rain_idx]

    # Threshold por F1 no train
    prec, rec, thrs = precision_recall_curve(y_train, rain_train)
    if len(thrs) == 0:
        return None
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    thr = float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.0

    pred_test = (rain_test >= thr).astype(int)
    prob_test = rain_test  # usar valor bruto como score para PR-AUC

    prauc = average_precision_score(y_test, prob_test)
    rec = recall_score(y_test, pred_test, zero_division=0)
    prec = precision_score(y_test, pred_test, zero_division=0)
    f1 = f1_score(y_test, pred_test, zero_division=0)
    rho, pval = spearmanr(max_dia_test, prob_test)

    return {
        "prauc": float(prauc),
        "recall": float(rec),
        "precision": float(prec),
        "f1": float(f1),
        "threshold": float(thr),
        "spearman_rho": float(rho),
        "spearman_p": float(pval),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "n_pos_train": int(y_train.sum()),
        "n_pos_test": int(y_test.sum()),
    }


# ─── 6. Main ────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("FORECAST DETECTOR DE PERFIL PERIGOSO")
    print("=" * 80)

    print("\n[1/5] Carregando CEMADEN diário...")
    df_diario, estacoes_bacia = build_cemaden_diario()

    print("[2/5] Calculando thresholds por bacia (treino apenas)...")
    thresholds = compute_thresholds(df_diario, T_CUT)
    print(f"  Thresholds: {thresholds}")

    print("[3/5] Construindo targets futuros (CEMADEN lead)...")
    df_targets, sat_thresholds = build_targets(df_diario, thresholds, HORIZONTES)
    print(f"  Thresholds saturação: {sat_thresholds}")

    print("[4/5] Carregando features de forecast e meteorológicas...")
    df_forecast = build_forecast_features(HORIZONTES)
    df_om = build_openmeteo_features()
    df_past = build_cemaden_past_features(df_diario)

    # Merge tudo
    df_ml = (
        df_targets
        .join(df_past, on=["data", "bacia"], how="left")
        .join(df_om, on=["data", "bacia"], how="left")
        .join(df_forecast, on="data", how="left")
        .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
        .sort(["bacia", "data"])
    )

    # Para comparação justa, restringir ao período onde forecast está disponível
    # (datas onde pelo menos uma feature de forecast não é nula)
    df_fc_check = df_ml.with_columns(
        pl.col("fc_rain_sum_h6").is_not_null().alias("has_forecast")
    )
    min_fc_date = df_fc_check.filter(pl.col("has_forecast"))["data"].min()
    max_fc_date = df_fc_check.filter(pl.col("has_forecast"))["data"].max()
    print(f"  Forecast disponível de {min_fc_date} a {max_fc_date}")

    # Usar apenas período de overlap para comparação justa entre variantes
    df_ml = df_ml.filter(
        (pl.col("data") >= min_fc_date) & (pl.col("data") <= max_fc_date)
    )

    print(f"  Dataset shape: {df_ml.shape}")
    print(f"  Date range: {df_ml['data'].min()} to {df_ml['data'].max()}")

    # Features sets
    FC_VARS = []
    for H in HORIZONTES:
        FC_VARS += [
            f"fc_rain_sum_h{H}", f"fc_rain_max_h{H}",
            f"fc_prob_mean_h{H}", f"fc_prob_max_h{H}",
            f"fc_temp_mean_h{H}", f"fc_humidity_mean_h{H}", f"fc_wind_max_h{H}",
        ]
    OM_VARS = [
        "om_precip_sum_lag1", "om_temp_max_lag1", "om_temp_min_lag1",
        "om_temp_mean_lag1", "om_humidity_max_lag1",
        "om_pressure_mean_lag1", "om_wind_max_lag1",
    ]
    PAST_VARS = [
        "max_day_lag1", "max_day_lag2", "max_day_lag3",
        "acum_dia_lag1", "acum_7d", "acum_30d",
        "api_070", "api_085", "api_095",
        "mes_sin", "mes_cos",
    ]

    # Todos os feature sets disponíveis
    FC_ONLY = [c for c in FC_VARS if c in df_ml.columns]
    OM_ONLY = [c for c in OM_VARS if c in df_ml.columns]
    PAST_ONLY = [c for c in PAST_VARS if c in df_ml.columns]
    FC_OM = FC_ONLY + OM_ONLY
    FC_PAST = FC_ONLY + PAST_ONLY
    ALL = FC_ONLY + OM_ONLY + PAST_ONLY

    print(f"\n  Feature sets:")
    print(f"    FC_ONLY ({len(FC_ONLY)}): {FC_ONLY[:4]}...")
    print(f"    OM_ONLY ({len(OM_ONLY)}): {OM_ONLY[:4]}...")
    print(f"    PAST_ONLY ({len(PAST_ONLY)}): {PAST_ONLY[:4]}...")

    # Loop de avaliação
    LABELS = ["pancada", "prolongada", "saturante", "perigoso_any"]
    MODELOS = ["logreg", "gradboost"]
    VARIANTES = {
        "FC_ONLY": FC_ONLY,
        "OM_ONLY": OM_ONLY,
        "PAST_ONLY": PAST_ONLY,
        "FC_OM": FC_OM,
        "FC_PAST": FC_PAST,
        "ALL": ALL,
    }

    resultados = []

    print("\n[5/5] Avaliando modelos...")
    for bacia in sorted(estacoes_bacia.keys()):
        t_cut_local = T_CUT
        if bacia == "oratorio":
            ev = df_ml.filter((pl.col("bacia") == bacia) & (pl.col("perigoso_any_h48")))["data"].sort()
            if len(ev) > 0:
                t_cut_local = ev[int(len(ev) * 0.75)]

        sub = df_ml.filter(pl.col("bacia") == bacia)
        train = sub.filter(pl.col("data") < t_cut_local)
        test = sub.filter(pl.col("data") >= t_cut_local)

        if train.height < 30 or test.height < 5:
            print(f"  {bacia}: pulado (dados insuficientes)")
            continue

        for H in HORIZONTES:
            # Selecionar target para este horizonte
            for label_base in LABELS:
                if label_base == "saturante":
                    col_y = "saturante"
                else:
                    col_y = f"{label_base}_h{H}"

                y_train = train[col_y].to_numpy().astype(int)
                y_test = test[col_y].to_numpy().astype(int)
                max_dia_test = test[f"max_dia_fut_h{H}"].to_numpy()

                if y_train.sum() < 2 or y_test.sum() == 0:
                    continue

                for var_nome, var_cols in VARIANTES.items():
                    # Garantir que todas as colunas existam e não tenham nulls
                    cols_ok = [c for c in var_cols if c in sub.columns]
                    sub_var = sub.drop_nulls(cols_ok + [col_y, f"max_dia_fut_h{H}"])
                    if sub_var.height < 30:
                        continue
                    train_v = sub_var.filter(pl.col("data") < t_cut_local)
                    test_v = sub_var.filter(pl.col("data") >= t_cut_local)
                    if train_v.height < 30 or test_v.height < 5:
                        continue

                    X_train = train_v[cols_ok].to_pandas().to_numpy()
                    X_test = test_v[cols_ok].to_pandas().to_numpy()
                    y_train_v = train_v[col_y].to_numpy().astype(int)
                    y_test_v = test_v[col_y].to_numpy().astype(int)
                    max_dia_test_v = test_v[f"max_dia_fut_h{H}"].to_numpy()

                    if y_train_v.sum() < 2 or y_test_v.sum() == 0:
                        continue

                    for modelo in MODELOS:
                        r = train_eval(X_train, X_test, y_train_v, y_test_v, max_dia_test_v, modelo=modelo)
                        if r is None:
                            continue
                        resultados.append({
                            "bacia": bacia,
                            "horizonte": H,
                            "label": label_base,
                            "variante": var_nome,
                            "modelo": modelo,
                            **r,
                        })

                    # Regra calibrada (só para FC_ONLY e quando rain_sum está presente)
                    if var_nome == "FC_ONLY":
                        rain_col = f"fc_rain_sum_h{H}"
                        if rain_col in cols_ok:
                            idx = cols_ok.index(rain_col)
                            r = regra_calibrada_eval(X_train, X_test, y_train_v, y_test_v, max_dia_test_v, idx)
                            if r is not None:
                                resultados.append({
                                    "bacia": bacia,
                                    "horizonte": H,
                                    "label": label_base,
                                    "variante": "REGRA_FC_RAIN",
                                    "modelo": "regra",
                                    **r,
                                })

    # ─── Relatório ─────────────────────────────────────────────────────────
    import pandas as pd
    df_res = pd.DataFrame(resultados)
    out_path = OUT_DIR / "forecast_detector_perfil_perigoso.parquet"
    df_res.to_parquet(out_path)
    print(f"\n  Resultados brutos salvos em: {out_path}")

    # Tabela resumo
    print("\n" + "=" * 100)
    print("RESUMO — Média PR-AUC por (Horizonte, Label, Variante, Modelo)")
    print("=" * 100)
    if not df_res.empty:
        summary = (
            df_res.groupby(["horizonte", "label", "variante", "modelo"])
            .agg({
                "prauc": "mean",
                "recall": "mean",
                "precision": "mean",
                "spearman_rho": "mean",
                "n_test": "sum",
            })
            .reset_index()
            .sort_values(["horizonte", "label", "prauc"], ascending=[True, True, False])
        )
        print(summary.to_string(index=False))

    # Melhor config por bacia/horizonte/label
    print("\n" + "=" * 100)
    print("MELHOR VARIANTE POR BACIA/HORIZONTE/LABEL (max PR-AUC)")
    print("=" * 100)
    if not df_res.empty:
        best = df_res.loc[df_res.groupby(["bacia", "horizonte", "label"])["prauc"].idxmax()]
        cols_show = ["bacia", "horizonte", "label", "variante", "modelo", "prauc", "recall", "precision", "spearman_rho"]
        print(best[cols_show].to_string(index=False))

    # Análise específica: FC_ONLY vs PAST_ONLY vs ALL
    print("\n" + "=" * 100)
    print("COMPARAÇÃO DIRETA: FC_ONLY vs PAST_ONLY vs ALL (LogisticRegression)")
    print("=" * 100)
    if not df_res.empty:
        comp = df_res[
            (df_res["modelo"] == "logreg") &
            (df_res["variante"].isin(["FC_ONLY", "PAST_ONLY", "ALL"]))
        ][["bacia", "horizonte", "label", "variante", "prauc", "spearman_rho"]]
        pivot = comp.pivot_table(index=["bacia", "horizonte", "label"], columns="variante", values="prauc").reset_index()
        print(pivot.to_string(index=False))

    # Conclusão textual
    print("\n" + "=" * 100)
    print("CONCLUSÃO")
    print("=" * 100)
    if df_res.empty:
        print("  NENHUM RESULTADO GERADO — verifique dados ou configuração.")
        return

    # FC_ONLY média
    fc_only_mean = df_res[df_res["variante"] == "FC_ONLY"]["prauc"].mean()
    past_only_mean = df_res[df_res["variante"] == "PAST_ONLY"]["prauc"].mean()
    all_mean = df_res[df_res["variante"] == "ALL"]["prauc"].mean()

    print(f"  PR-AUC médio FC_ONLY:   {fc_only_mean:.3f}")
    print(f"  PR-AUC médio PAST_ONLY: {past_only_mean:.3f}")
    print(f"  PR-AUC médio ALL:       {all_mean:.3f}")

    if fc_only_mean > 0.5:
        print("  → FC_ONLY tem sinal discriminativo razoável (PR-AUC > 0.5).")
    elif fc_only_mean > 0.3:
        print("  → FC_ONLY tem sinal fraco (PR-AUC 0.3-0.5).")
    else:
        print("  → FC_ONLY tem sinal muito fraco (PR-AUC < 0.3).")

    if all_mean > past_only_mean:
        print("  → Adicionar forecast aos dados passados melhora o resultado.")
    else:
        print("  → Forecast não melhora sobre dados passados sozinhos (possível ruído ou resolução espacial insuficiente).")

    # Horizonte que funciona melhor
    horizon_perf = df_res[df_res["variante"] == "FC_ONLY"].groupby("horizonte")["prauc"].mean().sort_values(ascending=False)
    print(f"  Melhor horizonte FC_ONLY: {horizon_perf.index[0]}h (PR-AUC={horizon_perf.iloc[0]:.3f})")

    # Perfil que funciona melhor
    label_perf = df_res[df_res["variante"] == "FC_ONLY"].groupby("label")["prauc"].mean().sort_values(ascending=False)
    print(f"  Melhor perfil FC_ONLY: {label_perf.index[0]} (PR-AUC={label_perf.iloc[0]:.3f})")

    # Spearman
    rho_fc = df_res[df_res["variante"] == "FC_ONLY"]["spearman_rho"].mean()
    print(f"  Spearman ρ médio FC_ONLY vs intensidade futura: {rho_fc:.3f}")
    if rho_fc > 0.3:
        print("  → Correlação moderada/forte entre forecast e intensidade.")
    elif rho_fc > 0.1:
        print("  → Correlação fraca.")
    else:
        print("  → Correlação muito fraca ou negativa.")

    # ─── Gráficos ─────────────────────────────────────────────────────────
    if not df_res.empty:
        print("\n[6/6] Gerando gráficos...")

        # Fig 1: PR-AUC médio por horizonte e label (FC_ONLY logreg)
        fig, ax = plt.subplots(figsize=(10, 6))
        pivot_fc = df_res[
            (df_res["variante"] == "FC_ONLY") & (df_res["modelo"] == "logreg")
        ].pivot_table(index=["horizonte"], columns="label", values="prauc", aggfunc="mean")
        pivot_fc.plot(kind="bar", ax=ax, width=0.8)
        ax.set_ylabel("PR-AUC médio")
        ax.set_xlabel("Horizonte (h)")
        ax.set_title("PR-AUC médio por horizonte e perfil — FC_ONLY (LogisticRegression)")
        ax.legend(title="Perfil", bbox_to_anchor=(1.05, 1), loc="upper left")
        ax.set_ylim(0, 1.0)
        plt.tight_layout()
        fig.savefig(OUT_DIR / "forecast_detector_prauc_por_horizonte.png", dpi=150)
        plt.close(fig)
        print(f"  Fig 1 salva: {OUT_DIR / 'forecast_detector_prauc_por_horizonte.png'}")

        # Fig 2: Comparação FC_ONLY vs PAST_ONLY vs ALL por horizonte (perigoso_any)
        fig, ax = plt.subplots(figsize=(10, 5))
        comp_data = df_res[
            (df_res["label"] == "perigoso_any") &
            (df_res["modelo"] == "logreg") &
            (df_res["variante"].isin(["FC_ONLY", "PAST_ONLY", "ALL"]))
        ]
        pivot_comp = comp_data.pivot_table(index="horizonte", columns="variante", values="prauc", aggfunc="mean")
        pivot_comp.plot(kind="bar", ax=ax, width=0.8, color=["#1f77b4", "#ff7f0e", "#2ca02c"])
        ax.set_ylabel("PR-AUC médio")
        ax.set_xlabel("Horizonte (h)")
        ax.set_title("Comparação de variantes — label='perigoso_any' (LogisticRegression)")
        ax.legend(title="Variante")
        ax.set_ylim(0, 1.0)
        plt.tight_layout()
        fig.savefig(OUT_DIR / "forecast_detector_comparacao_variantes.png", dpi=150)
        plt.close(fig)
        print(f"  Fig 2 salva: {OUT_DIR / 'forecast_detector_comparacao_variantes.png'}")

        # Fig 3: Spearman ρ vs PR-AUC (scatter por variante)
        fig, ax = plt.subplots(figsize=(8, 6))
        for var, color in zip(["FC_ONLY", "PAST_ONLY", "ALL"], ["#1f77b4", "#ff7f0e", "#2ca02c"]):
            sub = df_res[df_res["variante"] == var]
            ax.scatter(sub["spearman_rho"], sub["prauc"], label=var, alpha=0.5, s=30, color=color)
        ax.set_xlabel("Spearman ρ (forecast vs intensidade futura)")
        ax.set_ylabel("PR-AUC")
        ax.set_title("Spearman ρ vs PR-AUC por variante")
        ax.legend()
        ax.set_xlim(-0.2, 1.0)
        ax.set_ylim(0, 1.0)
        ax.axhline(0.5, color="gray", linestyle="--", linewidth=0.5)
        ax.axvline(0.3, color="gray", linestyle="--", linewidth=0.5)
        plt.tight_layout()
        fig.savefig(OUT_DIR / "forecast_detector_spearman_vs_prauc.png", dpi=150)
        plt.close(fig)
        print(f"  Fig 3 salva: {OUT_DIR / 'forecast_detector_spearman_vs_prauc.png'}")

        # Fig 4: Heatmap PR-AUC por (bacia, horizonte) para perigoso_any, FC_ONLY
        fig, ax = plt.subplots(figsize=(10, 6))
        heat = df_res[
            (df_res["label"] == "perigoso_any") &
            (df_res["variante"] == "FC_ONLY") &
            (df_res["modelo"] == "logreg")
        ].pivot_table(index="bacia", columns="horizonte", values="prauc", aggfunc="mean")
        cax = ax.imshow(heat.values, aspect="auto", cmap="RdYlGn", vmin=0, vmax=1)
        ax.set_xticks(range(len(heat.columns)))
        ax.set_xticklabels([f"{h}h" for h in heat.columns])
        ax.set_yticks(range(len(heat.index)))
        ax.set_yticklabels(heat.index)
        for i in range(len(heat.index)):
            for j in range(len(heat.columns)):
                ax.text(j, i, f"{heat.values[i, j]:.2f}", ha="center", va="center", color="black", fontsize=10)
        ax.set_title("PR-AUC por bacia e horizonte — perigoso_any (FC_ONLY, LogReg)")
        fig.colorbar(cax, ax=ax, label="PR-AUC")
        plt.tight_layout()
        fig.savefig(OUT_DIR / "forecast_detector_heatmap_bacia_horizonte.png", dpi=150)
        plt.close(fig)
        print(f"  Fig 4 salva: {OUT_DIR / 'forecast_detector_heatmap_bacia_horizonte.png'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
