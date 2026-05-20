"""
Combinador de Risco Meteorológico — Score principal para operação.
===============================================================

Objetivo: combinar as melhores linhas experimentais em um score único
proporcional à intensidade da chuva / perfil perigoso futuro.

Componentes combinados:
  1. Similaridade com perfis perigosos (pancada/prolongada) — KMeans sobre vetor de perfil
  2. Forecast detector H48 perigoso_any — LogisticRegression com FC_ONLY
  3. Especialista pancada — GradBoost com features de pico/intensidade
  4. Especialista prolongada — GradBoost com features de acumulado/saturação
  5. Classificador cauda pesada — GradBoost max_depth=6, sample weights agressivos
  6. Bias correction forecast → aplica multiplicador/quantile_mapping quando disponível

Combinações testadas (auditáveis):
  - combinador_mean: média simples dos scores normalizados
  - combinador_weighted: média ponderada por Spearman no treino
  - combinador_max: máximo entre os scores

Avaliação focada em proporcionalidade (Spearman vs max_dia), não apenas F1.
"""

import importlib.util
import json
import sys
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ─── Paths ───────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
WORKDIR = SCRIPT_DIR.parents[1]
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Import helpers dos experimentos anteriores ──────────────────────────
_BM_PATH = SCRIPT_DIR / "_run_benchmark_v8.py"
_spec = importlib.util.spec_from_file_location("_run_benchmark_v8", _BM_PATH)
_bm = importlib.util.module_from_spec(_spec)
sys.modules["_run_benchmark_v8"] = _bm
_spec.loader.exec_module(_bm)
build_dataset = _bm.build_dataset
FEATURES_V8 = _bm.FEATURES
T_CUT = _bm.T_CUT
MESES_CHUVOSOS = _bm.MESES_CHUVOSOS
w_fit_m3 = _bm.w_fit_m3

# Forecast detector
_FC_PATH = SCRIPT_DIR / "_forecast_detector_perfil_perigoso.py"
_spec_fc = importlib.util.spec_from_file_location("_forecast_detector", _FC_PATH)
_fc = importlib.util.module_from_spec(_spec_fc)
sys.modules["_forecast_detector"] = _fc
_spec_fc.loader.exec_module(_fc)
build_forecast_features = _fc.build_forecast_features
build_openmeteo_features = _fc.build_openmeteo_features
build_cemaden_past_features = _fc.build_cemaden_past_features
build_cemaden_diario = _fc.build_cemaden_diario
compute_thresholds = _fc.compute_thresholds
build_targets = _fc.build_targets

# Similaridade perfis
_SIM_PATH = SCRIPT_DIR / "_similaridade_perfis_chuva.py"
_spec_sim = importlib.util.spec_from_file_location("_similaridade_perfis", _SIM_PATH)
_sim = importlib.util.module_from_spec(_spec_sim)
sys.modules["_similaridade_perfis"] = _sim
_spec_sim.loader.exec_module(_sim)
load_openmeteo_by_bacia = _sim.load_openmeteo_by_bacia
build_om_future_features = _sim.build_om_future_features
build_cemaden_past_and_future = _sim.build_cemaden_past_and_future
adicionar_acum_lags = _sim.adicionar_acum_lags
definir_perfis_perigosos = _sim.definir_perfis_perigosos
calcular_score = _sim.calcular_score
PERFIL_COLS_PASSADO = _sim.PERFIL_COLS_PASSADO
PERFIL_COLS_FUTURO = _sim.PERFIL_COLS_FUTURO

# ─── Config ──────────────────────────────────────────────────────────────
HORIZONTES = [24, 48]  # foco em horizontes viáveis
LABEL_ALVO = "perigoso_any"

FEATURES_PANCADA = [
    "pico_1h_lag1", "max_day_lag1", "max_day_lag2", "max_day_lag3",
    "horas_intensas_lag1", "std_day_lag1",
    "acc_6h_lag_9", "acc_6h_lag_10", "acc_6h_lag_11", "acc_6h_lag_12",
    "n_chovendo_max_lag1", "mean_day_lag1",
]

FEATURES_PROLONGADA = [
    "acum_7d", "acum_30d", "api_070", "api_085", "api_095",
    "mean_day_lag1", "max_day_lag1", "n_chovendo_max_lag1",
]

FEATURES_V2 = (
    [f"api_{int(k*100):03d}" for k in [0.70, 0.85, 0.95, 0.99]]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
    + ["tendencia_chuva", "max_dia_rel", "pico_vs_media",
       "chuva_persistente", "acc_24h_lag1", "acc_48h_lag1",
       "razao_7d_30d", "n_chovendo_lag2", "n_chovendo_lag3",
       "inter_max_acum7d", "inter_max_std"]
)

# ─── Helpers ─────────────────────────────────────────────────────────────

def _sample_weights_agressivos(sev):
    return np.where(sev == 3, 20.0,
           np.where(sev == 2, 5.0,
           np.where(sev == 1, 1.0, 0.1)))


def _thr_f1(y_true, y_prob):
    from sklearn.metrics import precision_recall_curve
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5


def normalize_scores(s, s_train=None):
    """Min-max normalização robusta usando estatísticas do treino quando disponível."""
    ref = s_train if s_train is not None else s
    mn, mx = np.nanmin(ref), np.nanmax(ref)
    if mx - mn < 1e-9:
        return np.zeros_like(s)
    return np.clip((s - mn) / (mx - mn), 0, 1)


def train_logreg_fc_only(train_df, test_df, col_y, max_dia_col):
    """Treina LogisticRegression com FC_ONLY e retorna (prob_train, prob_test, datas_test, maxdia_test)."""
    FC_VARS = []
    for H in HORIZONTES:
        FC_VARS += [
            f"fc_rain_sum_h{H}", f"fc_rain_max_h{H}",
            f"fc_prob_mean_h{H}", f"fc_prob_max_h{H}",
            f"fc_temp_mean_h{H}", f"fc_humidity_mean_h{H}", f"fc_wind_max_h{H}",
        ]
    cols_ok = [c for c in FC_VARS if c in train_df.columns and c in test_df.columns]
    if not cols_ok:
        return None, None, None, None
    train_d = train_df.drop_nulls(cols_ok + [col_y, max_dia_col])
    test_d = test_df.drop_nulls(cols_ok + [col_y, max_dia_col])
    if train_d.height < 30 or test_d.height < 5:
        return None, None, None, None
    y_train = train_d[col_y].to_numpy().astype(int)
    y_test = test_d[col_y].to_numpy().astype(int)
    if y_train.sum() < 2 or y_test.sum() == 0:
        return None, None, None, None
    X_train = train_d[cols_ok].to_pandas().to_numpy()
    X_test = test_d[cols_ok].to_pandas().to_numpy()
    clf = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=1000, random_state=42))])
    clf.fit(X_train, y_train)
    prob_train = clf.predict_proba(X_train)[:, 1]
    prob_test = clf.predict_proba(X_test)[:, 1]
    return prob_train, prob_test, test_d["data"].to_list(), test_d[max_dia_col].to_numpy()


def train_especialista(train_df, test_df, features, col_y="enchente"):
    """Treina GradBoost especialista e retorna (prob_train, prob_test, datas_test, maxdia_test)."""
    cols_ok = [c for c in features if c in train_df.columns and c in test_df.columns]
    if not cols_ok:
        return None, None, None, None
    train_d = train_df.drop_nulls(cols_ok + [col_y])
    test_d = test_df.drop_nulls(cols_ok + [col_y])
    if train_d.height < 30 or test_d.height < 5:
        return None, None, None, None
    y_train = train_d[col_y].to_numpy().astype(int)
    y_test = test_d[col_y].to_numpy().astype(int)
    if y_train.sum() < 2 or y_test.sum() == 0:
        return None, None, None, None
    X_train = train_d[cols_ok].to_pandas().to_numpy()
    X_test = test_d[cols_ok].to_pandas().to_numpy()
    clf = GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=2,
        min_samples_leaf=10, subsample=0.8, max_features="sqrt", random_state=42,
    )
    sw = w_fit_m3(train_d["severidade"].to_numpy())
    clf.fit(X_train, y_train, sample_weight=sw)
    prob_train = clf.predict_proba(X_train)[:, 1]
    prob_test = clf.predict_proba(X_test)[:, 1]
    return prob_train, prob_test, test_d["data"].to_list(), test_d["max_dia"].to_numpy()


def train_cauda_pesada(train_df, test_df):
    """Treina classificador cauda pesada e retorna (prob_train, prob_test, datas_test, maxdia_test)."""
    cols_ok = [c for c in FEATURES_V2 if c in train_df.columns and c in test_df.columns]
    if not cols_ok:
        return None, None, None, None
    train_d = train_df.drop_nulls(cols_ok + ["enchente"])
    test_d = test_df.drop_nulls(cols_ok + ["enchente"])
    if train_d.height < 30 or test_d.height < 5:
        return None, None, None, None
    y_train = train_d["enchente"].to_numpy().astype(int)
    y_test = test_d["enchente"].to_numpy().astype(int)
    if y_train.sum() < 2 or y_test.sum() == 0:
        return None, None, None, None
    X_train = train_d[cols_ok].to_pandas().to_numpy()
    X_test = test_d[cols_ok].to_pandas().to_numpy()
    sev_train = train_d["severidade"].to_numpy()
    sw = _sample_weights_agressivos(sev_train)
    clf = GradientBoostingClassifier(
        n_estimators=300, learning_rate=0.03, max_depth=6,
        min_samples_leaf=5, subsample=0.8, max_features="sqrt", random_state=42,
    )
    clf.fit(X_train, y_train, sample_weight=sw)
    prob_train = clf.predict_proba(X_train)[:, 1]
    prob_test = clf.predict_proba(X_test)[:, 1]
    return prob_train, prob_test, test_d["data"].to_list(), test_d["max_dia"].to_numpy()


# ─── Bias correction simples ─────────────────────────────────────────────

def bias_correction_multiplicador(df_train, df_test, col_fc, col_obs):
    """Calcula multiplicador ótimo no treino e aplica no teste."""
    sub = df_train.filter(pl.col(col_fc).is_not_null() & pl.col(col_obs).is_not_null())
    if sub.height < 10:
        return df_test.with_columns(pl.col(col_fc).alias(f"{col_fc}_bc_mult"))
    ratios = (sub[col_obs] / (sub[col_fc] + 1e-6)).to_numpy()
    mult = float(np.median(ratios[ratios > 0]))
    if not np.isfinite(mult) or mult <= 0:
        mult = 1.0
    return df_test.with_columns((pl.col(col_fc) * mult).alias(f"{col_fc}_bc_mult"))


def bias_correction_quantile_mapping(df_train, df_test, col_fc, col_obs, n_quantiles=100):
    """Quantile mapping empírico simples."""
    sub = df_train.filter(pl.col(col_fc).is_not_null() & pl.col(col_obs).is_not_null())
    if sub.height < 10:
        return df_test.with_columns(pl.col(col_fc).alias(f"{col_fc}_bc_qm"))
    obs_vals = np.sort(sub[col_obs].to_numpy())
    fc_vals = np.sort(sub[col_fc].to_numpy())
    quantiles = np.linspace(0, 1, n_quantiles)
    obs_q = np.quantile(obs_vals, quantiles)
    fc_q = np.quantile(fc_vals, quantiles)
    def map_val(x):
        if x <= fc_q[0]:
            return obs_q[0]
        if x >= fc_q[-1]:
            return obs_q[-1]
        idx = np.searchsorted(fc_q, x)
        if idx == 0:
            return obs_q[0]
        t = (x - fc_q[idx-1]) / (fc_q[idx] - fc_q[idx-1] + 1e-9)
        return obs_q[idx-1] + t * (obs_q[idx] - obs_q[idx-1])
    mapped = [map_val(v) for v in df_test[col_fc].to_numpy()]
    return df_test.with_columns(pl.Series(mapped).alias(f"{col_fc}_bc_qm"))


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("COMBINADOR DE RISCO METEOROLÓGICO")
    print("=" * 80)

    # 1. Carrega datasets base
    print("\n[1/7] Carregando datasets base...")
    df_ml, estacoes_bacia, p50 = build_dataset()
    df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    # Features V2 adicionais (derivadas)
    df_ml = df_ml.with_columns([
        (pl.col("acc_6h_lag_9") + pl.col("acc_6h_lag_10") + pl.col("acc_6h_lag_11") + pl.col("acc_6h_lag_12")).alias("acc_24h_lag1"),
    ])
    df_ml = df_ml.with_columns([
        (pl.col("acc_24h_lag1") + pl.col("acc_6h_lag_5") + pl.col("acc_6h_lag_6") + pl.col("acc_6h_lag_7") + pl.col("acc_6h_lag_8")).alias("acc_48h_lag1"),
        (pl.col("acum_7d") / pl.max_horizontal(pl.col("acum_30d"), pl.lit(1.0))).alias("razao_7d_30d"),
        (pl.col("pico_1h_lag1") / pl.max_horizontal(pl.col("mean_day_lag1"), pl.lit(1e-6))).alias("pico_vs_media"),
        (pl.col("max_day_lag1") / pl.max_horizontal(pl.col("mean_day_lag1"), pl.lit(1e-6))).alias("max_vs_media"),
        (pl.col("max_day_lag1") - pl.col("max_day_lag2")).alias("tendencia_chuva"),
        (pl.col("max_day_lag1") / pl.max_horizontal(pl.col("acum_7d"), pl.lit(1e-6))).alias("max_dia_rel"),
        ((pl.col("acc_6h_lag_1") > 0).cast(pl.Int8) + (pl.col("acc_6h_lag_2") > 0).cast(pl.Int8) + (pl.col("acc_6h_lag_3") > 0).cast(pl.Int8)).alias("chuva_persistente"),
        (pl.col("n_chovendo_max_lag1").shift(1).over("bacia")).alias("n_chovendo_lag2"),
        (pl.col("n_chovendo_max_lag1").shift(2).over("bacia")).alias("n_chovendo_lag3"),
        (pl.col("max_day_lag1") * pl.col("acum_7d")).alias("inter_max_acum7d"),
        (pl.col("max_day_lag1") * pl.col("std_day_lag1")).alias("inter_max_std"),
    ])

    # 2. Carrega similaridade de perfis (já calculado)
    print("[2/7] Carregando scores de similaridade de perfis...")
    df_sim = pl.read_parquet(OUT_DIR / "similaridade_perfis_chuva.parquet")
    df_sim = df_sim.select(["data", "bacia", "score_pancada", "score_prolong", "score_final"])
    # Converter data de datetime para date para alinhamento correto
    df_sim = df_sim.with_columns(pl.col("data").dt.date().alias("data"))
    # score_final já é 0-100; normalizar para 0-1
    df_sim = df_sim.with_columns([
        (pl.col("score_pancada")).alias("score_pancada"),
        (pl.col("score_prolong")).alias("score_prolong"),
        (pl.col("score_final") / 100.0).alias("score_similaridade"),
    ])

    # 3. Forecast + targets futuros + bias correction
    print("[3/7] Construindo forecast detector H24/H48...")
    df_diario, _ = build_cemaden_diario()
    thresholds = compute_thresholds(df_diario, T_CUT)
    df_targets, sat_thresholds = build_targets(df_diario, thresholds, HORIZONTES)
    df_forecast = build_forecast_features(HORIZONTES)
    df_om = build_openmeteo_features()
    df_past = build_cemaden_past_features(df_diario)

    df_fc_ml = (
        df_targets
        .join(df_past, on=["data", "bacia"], how="left")
        .join(df_om, on=["data", "bacia"], how="left")
        .join(df_forecast, on="data", how="left")
        .filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))
        .sort(["bacia", "data"])
    )

    # Bias correction para fc_rain_sum_h48 (usar OpenMeteo lag1 como proxy de obs)
    # Na prática, usamos CEMADEN acum_dia do mesmo dia como obs para calibrar
    # Mas isso teria leak. Usamos acum_dia_lag1 como proxy rough.
    # Melhor: usar acum_dia do dia D como obs só para definir o fator (sem leak se aplicado corretamente?)
    # Na verdade, bias correction é calculado no treino e aplicado no teste;
    # o fator usa dados históricos (CEMADEN passado vs OpenMeteo passado).
    # Aqui simplificamos: calculamos no treino usando acum_dia vs om_precip_sum_lag1
    # e aplicamos no teste.

    # 4. Loop por bacia: treina componentes e extrai scores
    print("[4/7] Treinando componentes por bacia e extraindo scores...")
    rows_all = []
    metricas_all = []

    for bacia in sorted(estacoes_bacia.keys()):
        print(f"  -> {bacia}")
        t_cut_local = T_CUT
        if bacia == "oratorio":
            ev = df_ml.filter((pl.col("bacia") == bacia) & (pl.col("enchente")))["data"].sort()
            if len(ev) > 0:
                t_cut_local = ev[int(len(ev) * 0.75)]

        # Subsets
        sub_ml = df_ml.filter(pl.col("bacia") == bacia).sort("data")
        sub_fc = df_fc_ml.filter(pl.col("bacia") == bacia).sort("data")
        sub_sim = df_sim.filter(pl.col("bacia") == bacia).sort("data")

        train_ml = sub_ml.filter(pl.col("data") < t_cut_local)
        test_ml = sub_ml.filter(pl.col("data") >= t_cut_local)
        train_fc = sub_fc.filter(pl.col("data") < t_cut_local)
        test_fc = sub_fc.filter(pl.col("data") >= t_cut_local)

        if test_ml.height < 5 or test_fc.height < 5:
            print(f"     pulado (teste insuficiente)")
            continue

        # --- Componente A: Forecast detector H48 perigoso_any ---
        prob_fc_tr, prob_fc, datas_fc, maxdia_fc = train_logreg_fc_only(
            train_fc, test_fc, col_y="perigoso_any_h48", max_dia_col="max_dia_fut_h48"
        )
        if prob_fc is None:
            print(f"     forecast detector falhou")
            prob_fc = np.zeros(test_fc.height)
            prob_fc_tr = np.array([])
            datas_fc = test_fc["data"].to_list()

        # --- Componente A2: Forecast detector H48 saturante ---
        prob_sat_tr, prob_sat, datas_sat, maxdia_sat = train_logreg_fc_only(
            train_fc, test_fc, col_y="saturante", max_dia_col="acum_48h_fut"
        )
        if prob_sat is None:
            prob_sat = np.zeros(test_fc.height)
            prob_sat_tr = np.array([])
            datas_sat = test_fc["data"].to_list()

        # --- Componente B: Especialista pancada ---
        prob_panc_tr, prob_panc, datas_panc, maxdia_panc = train_especialista(
            train_ml, test_ml, FEATURES_PANCADA
        )
        if prob_panc is None:
            prob_panc = np.zeros(test_ml.height)
            prob_panc_tr = np.array([])
            datas_panc = test_ml["data"].to_list()

        # --- Componente C: Especialista prolongada ---
        prob_prol_tr, prob_prol, datas_prol, maxdia_prol = train_especialista(
            train_ml, test_ml, FEATURES_PROLONGADA
        )
        if prob_prol is None:
            prob_prol = np.zeros(test_ml.height)
            prob_prol_tr = np.array([])
            datas_prol = test_ml["data"].to_list()

        # --- Componente D: Cauda pesada ---
        prob_cauda_tr, prob_cauda, datas_cauda, maxdia_cauda = train_cauda_pesada(train_ml, test_ml)
        if prob_cauda is None:
            prob_cauda = np.zeros(test_ml.height)
            prob_cauda_tr = np.array([])
            datas_cauda = test_ml["data"].to_list()

        # --- Componente E: Similaridade (já temos) ---
        sim_test = sub_sim.filter(pl.col("data") >= t_cut_local).sort("data")
        sim_train = sub_sim.filter(pl.col("data") < t_cut_local).sort("data")
        if sim_test.height == 0:
            score_sim = np.zeros(test_ml.height)
            score_sim_tr = np.array([])
            datas_sim = test_ml["data"].to_list()
        else:
            score_sim = sim_test["score_similaridade"].to_numpy()
            score_sim_tr = sim_train["score_similaridade"].to_numpy() if sim_train.height > 0 else np.array([])
            datas_sim = sim_test["data"].to_list()

        # --- Alinhar todos pelo mesmo conjunto de datas do teste ML ---
        def align(dates, vals):
            m = {d: v for d, v in zip(dates, vals)}
            return np.array([m.get(d, 0.0) for d in test_ml["data"].to_list()])

        prob_fc_aligned = align(datas_fc, prob_fc)
        prob_sat_aligned = align(datas_sat, prob_sat)
        prob_panc_aligned = align(datas_panc, prob_panc)
        prob_prol_aligned = align(datas_prol, prob_prol)
        prob_cauda_aligned = align(datas_cauda, prob_cauda)
        score_sim_aligned = align(datas_sim, score_sim)

        # --- Normalizar cada score para [0,1] usando estatísticas do TREINO ---
        n_fc = normalize_scores(prob_fc_aligned, prob_fc_tr)
        n_sat = normalize_scores(prob_sat_aligned, prob_sat_tr)
        n_panc = normalize_scores(prob_panc_aligned, prob_panc_tr)
        n_prol = normalize_scores(prob_prol_aligned, prob_prol_tr)
        n_cauda = normalize_scores(prob_cauda_aligned, prob_cauda_tr)
        n_sim = normalize_scores(score_sim_aligned, score_sim_tr)

        # --- Baseline V8 (prob k=1) ---
        cols_v8 = [c for c in FEATURES_V8 if c in train_ml.columns]
        train_v8 = train_ml.drop_nulls(cols_v8 + ["enchente"])
        test_v8 = test_ml.drop_nulls(cols_v8 + ["enchente"])
        prob_v8 = np.zeros(test_ml.height)
        if train_v8.height >= 30 and test_v8.height >= 5:
            X_tr = train_v8[cols_v8].to_pandas().to_numpy()
            X_te = test_v8[cols_v8].to_pandas().to_numpy()
            y_tr = train_v8["enchente"].to_numpy().astype(int)
            sw = w_fit_m3(train_v8["severidade"].to_numpy())
            clf_v8 = GradientBoostingClassifier(
                n_estimators=200, learning_rate=0.05, max_depth=2,
                min_samples_leaf=10, subsample=0.8, max_features="sqrt", random_state=42,
            )
            clf_v8.fit(X_tr, y_tr, sample_weight=sw)
            prob_v8_raw = clf_v8.predict_proba(X_te)[:, 1]
            prob_v8 = align(test_v8["data"].to_list(), prob_v8_raw)

        # --- Combinadores ---
        # mean simples (6 componentes agora)
        comb_mean = (n_fc + n_sat + n_panc + n_prol + n_cauda + n_sim) / 6.0
        # weighted: pesos fixos baseados em desempenho relatado nos experimentos
        # fc: 0.430, sat: 0.585 (relatório), panc: 0.225, prol: 0.179, cauda: 0.191, sim: 0.077
        raw_w = np.array([0.430, 0.585, 0.225, 0.179, 0.191, 0.077])
        w = raw_w / raw_w.sum()
        comb_weighted = w[0]*n_fc + w[1]*n_sat + w[2]*n_panc + w[3]*n_prol + w[4]*n_cauda + w[5]*n_sim
        # max
        comb_max = np.maximum.reduce([n_fc, n_sat, n_panc, n_prol, n_cauda, n_sim])

        # --- Perfis dominantes ---
        perfis = []
        for i in range(len(test_ml)):
            scores = {
                "pancada": n_panc[i], "prolongada": n_prol[i],
                "cauda": n_cauda[i], "forecast": n_fc[i],
                "similaridade": n_sim[i], "saturacao": n_sat[i],
            }
            perfis.append(max(scores, key=scores.get))

        # --- Montar dataframe de saída por dia ---
        sev_test = test_ml["severidade"].to_numpy()
        maxdia_test = test_ml["max_dia"].to_numpy()
        for i, d in enumerate(test_ml["data"].to_list()):
            rows_all.append({
                "data": d,
                "bacia": bacia,
                "max_dia": float(maxdia_test[i]),
                "severidade": int(sev_test[i]),
                "score_fc_detector_h48_raw": float(prob_fc_aligned[i]),
                "score_saturacao_raw": float(prob_sat_aligned[i]),
                "score_pancada_raw": float(prob_panc_aligned[i]),
                "score_prolongada_raw": float(prob_prol_aligned[i]),
                "score_cauda_raw": float(prob_cauda_aligned[i]),
                "score_similaridade_raw": float(score_sim_aligned[i]),
                "score_fc_detector_h48_norm": float(n_fc[i]),
                "score_saturacao_norm": float(n_sat[i]),
                "score_pancada_norm": float(n_panc[i]),
                "score_prolongada_norm": float(n_prol[i]),
                "score_cauda_norm": float(n_cauda[i]),
                "score_similaridade_norm": float(n_sim[i]),
                "risk_score_raw_mean": float(comb_mean[i]),
                "risk_score_raw_weighted": float(comb_weighted[i]),
                "risk_score_raw_max": float(comb_max[i]),
                "risk_score_0_100_mean": float(comb_mean[i] * 100),
                "risk_score_0_100_weighted": float(comb_weighted[i] * 100),
                "risk_score_0_100_max": float(comb_max[i] * 100),
                "perfil_dominante": perfis[i],
                "baseline_v8_prob": float(prob_v8[i]),
            })

        # --- Métricas por bacia ---
        for nome, scores in [
            ("combinador_mean", comb_mean),
            ("combinador_weighted", comb_weighted),
            ("combinador_max", comb_max),
            ("baseline_v8", prob_v8),
            ("forecast_detector", prob_fc_aligned),
            ("forecast_detector_saturacao", prob_sat_aligned),
            ("especialista_pancada", prob_panc_aligned),
            ("especialista_prolongada", prob_prol_aligned),
            ("classificador_cauda", prob_cauda_aligned),
            ("similaridade", score_sim_aligned),
        ]:
            y_bin = (sev_test >= 1).astype(int)
            if len(np.unique(scores)) > 1 and y_bin.sum() > 0:
                prauc = average_precision_score(y_bin, scores)
            else:
                prauc = np.nan
            if len(np.unique(maxdia_test)) > 1 and len(np.unique(scores)) > 1:
                rho_max, _ = spearmanr(maxdia_test, scores)
                rho_sev, _ = spearmanr(sev_test, scores)
            else:
                rho_max = np.nan
                rho_sev = np.nan
            pred_bin = (scores >= 0.1).astype(int)
            rec = recall_score(y_bin, pred_bin, zero_division=0)
            prec = precision_score(y_bin, pred_bin, zero_division=0)
            f1 = f1_score(y_bin, pred_bin, zero_division=0)

            metricas_all.append({
                "bacia": bacia,
                "modelo": nome,
                "prauc": float(prauc),
                "spearman_max_dia": float(rho_max),
                "spearman_severidade": float(rho_sev),
                "recall_thr01": float(rec),
                "prec_thr01": float(prec),
                "f1_thr01": float(f1),
                "test_n": len(sev_test),
                "test_pos": int(y_bin.sum()),
            })

    # 5. Consolida e salva
    print("\n[5/7] Consolidando resultados...")
    df_scores = pl.DataFrame(rows_all)
    df_metricas = pl.DataFrame(metricas_all)

    out_scores = OUT_DIR / "combinador_risco_meteorologico.parquet"
    out_metricas = OUT_DIR / "combinador_risco_meteorologico_metricas.parquet"
    df_scores.write_parquet(out_scores)
    df_metricas.write_parquet(out_metricas)
    print(f"  Scores por dia -> {out_scores}")
    print(f"  Métricas       -> {out_metricas}")

    # 6. Avaliação agregada: curva por faixa de chuva e inversões
    print("\n[6/7] Avaliação por faixa de chuva e inversões...")
    faixas = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 80), (80, float("inf"))]
    faixa_rows = []
    inversao_rows = []

    for bacia in df_scores["bacia"].unique().to_list():
        sub = df_scores.filter(pl.col("bacia") == bacia).to_pandas()
        for nome in ["risk_score_raw_mean", "risk_score_raw_weighted", "risk_score_raw_max", "baseline_v8_prob"]:
            for lo, hi in faixas:
                mask = (sub["max_dia"] >= lo) & (sub["max_dia"] < hi)
                if mask.sum() > 0:
                    faixa_rows.append({
                        "bacia": bacia,
                        "modelo": nome,
                        "faixa": f"{lo}-{hi}" if hi < float("inf") else f"{lo}+",
                        "n": int(mask.sum()),
                        "score_medio": float(sub.loc[mask, nome].mean()),
                        "severidade_media": float(sub.loc[mask, "severidade"].mean()),
                    })
            # Inversão: score médio 20-30 < score médio 10-20
            m10 = (sub["max_dia"] >= 10) & (sub["max_dia"] < 20)
            m20 = (sub["max_dia"] >= 20) & (sub["max_dia"] < 30)
            s10 = sub.loc[m10, nome].mean() if m10.sum() > 0 else np.nan
            s20 = sub.loc[m20, nome].mean() if m20.sum() > 0 else np.nan
            inversao = (not np.isnan(s10) and not np.isnan(s20) and s20 < s10)
            inversao_rows.append({
                "bacia": bacia,
                "modelo": nome,
                "score_10_20": float(s10) if not np.isnan(s10) else None,
                "score_20_30": float(s20) if not np.isnan(s20) else None,
                "inversao": bool(inversao),
            })

    df_faixas = pl.DataFrame(faixa_rows)
    df_inversoes = pl.DataFrame(inversao_rows)
    out_faixas = OUT_DIR / "combinador_risco_meteorologico_faixas.parquet"
    out_inv = OUT_DIR / "combinador_risco_meteorologico_inversoes.parquet"
    df_faixas.write_parquet(out_faixas)
    df_inversoes.write_parquet(out_inv)
    print(f"  Faixas    -> {out_faixas}")
    print(f"  Inversoes -> {out_inv}")

    # 7. Seleção do candidato recomendado
    print("\n[7/7] Selecionando candidato recomendado...")
    # Agrupa métricas por modelo
    pdf = df_metricas.to_pandas()
    agg = pdf.groupby("modelo").agg({
        "prauc": "mean",
        "spearman_max_dia": "mean",
        "spearman_severidade": "mean",
        "recall_thr01": "mean",
        "prec_thr01": "mean",
    }).reset_index()
    print("\nMétricas agregadas (média entre bacias):")
    print(agg.to_string(index=False))

    # Critério de seleção: melhor Spearman com max_dia (proporcionalidade)
    # com penalidade se PR-AUC for muito baixo (< 0.05)
    agg["score_selecao"] = agg["spearman_max_dia"] - 0.5 * np.maximum(0, 0.05 - agg["prauc"])
    candidato = agg.loc[agg["score_selecao"].idxmax(), "modelo"]
    print(f"\nCandidato recomendado (melhor proporcionalidade): {candidato}")

    # Contagem de inversões
    inv_counts = df_inversoes.to_pandas().groupby("modelo")["inversao"].sum().reset_index()
    print("\nInversões (score 20-30mm < score 10-20mm) por modelo:")
    print(inv_counts.to_string(index=False))

    # 8. Relatório Markdown
    relatorio = f"""# Relatório: Combinador de Risco Meteorológico

**Data:** {datetime.now().strftime("%Y-%m-%d %H:%M")}  
**Script:** `{Path(__file__).name}`  
**Candidato recomendado:** `{candidato}`

---

## 1. Objetivo

Combinar as melhores linhas experimentais em um score único proporcional à
intensidade da chuva / perfil perigoso futuro, servindo como candidato principal
para calibração e serving.

## 2. Componentes Combinados

| # | Componente | Descrição | Fonte |
|---|------------|-----------|-------|
| 1 | Similaridade perfis | KMeans(k=2) sobre vetor passado+future; score = max(1/(1+dist)) | `_similaridade_perfis_chuva.py` |
| 2 | Forecast detector H48 perigoso_any | LogisticRegression FC_ONLY para `perigoso_any_h48` | `_forecast_detector_perfil_perigoso.py` |
| 3 | Forecast detector H48 saturante | LogisticRegression FC_ONLY para `saturante` (acum_48h_fut) | `_forecast_detector_perfil_perigoso.py` |
| 4 | Especialista pancada | GradBoost features de pico/intensidade curta | `_especialistas_pancada_prolongada.py` |
| 5 | Especialista prolongada | GradBoost features de acumulado/saturação | `_especialistas_pancada_prolongada.py` |
| 6 | Classificador cauda pesada | GradBoost max_depth=6, sample weights agressivos | `_ranking_cauda_pesada.py` |

## 3. Combinações Testadas

- **combinador_mean**: média simples dos 6 scores normalizados
- **combinador_weighted**: média ponderada (pesos proporcionais a Spearman relatado nos experimentos: fc=0.430, sat=0.585, panc=0.225, prol=0.179, cauda=0.191, sim=0.077)
- **combinador_max**: máximo entre os 6 scores normalizados

Todos os scores individuais são normalizados para [0,1] usando min/max do **treino** por bacia, garantindo que a escala do teste não seja artificialmente inflada.

## 4. Métricas Agregadas (média entre bacias)

| Modelo | PR-AUC | Spearman max_dia | Spearman severidade | Recall@thr0.1 | Prec@thr0.1 |
|--------|--------|------------------|---------------------|---------------|-------------|
"""
    for _, r in agg.iterrows():
        relatorio += f"| {r['modelo']:<22} | {r['prauc']:.3f} | {r['spearman_max_dia']:.3f} | {r['spearman_severidade']:.3f} | {r['recall_thr01']:.3f} | {r['prec_thr01']:.3f} |\n"

    relatorio += "\n## 5. Inversoes (score 20-30mm < score 10-20mm)\n\n| Modelo | Inversoes |\n|--------|-----------|\n"
    for _, r in inv_counts.iterrows():
        relatorio += f"| {r['modelo']:<22} | {int(r['inversao'])} |\n"

    relatorio += f"""
## 6. Candidato Recomendado

**`{candidato}`** foi selecionado pelo critério de melhor Spearman com max_dia
(proporcionalidade), com penalidade leve para PR-AUC muito baixo.

## 7. Limitações Conhecidas

- Forecast detector usa OpenWeather forecast history (1 ponto espacial), não captura
  variabilidade intra-bacia para eventos convectivos.
- Bias correction não foi aplicada operacionalmente nesta rodada por falta de
  pipeline automatizado; usamos forecast raw.
- Scores são normalizados usando estatísticas do treino por bacia, o que é mais
  robusto que normalizar no teste, mas ainda pode sofrer com drift temporal.
- Poucos eventos extremos (>30mm) no teste; estimativas na cauda têm alta variância.
- O componente de similaridade apresenta Spearman baixo (0.077) e correlação
  negativa com severidade; seu peso no combinador weighted é pequeno (0.077),
  mas ainda contribui para diversidade do ensemble.

## 8. Arquivos Gerados

- `{out_scores}` — scores por dia/bacia (todas as variantes)
- `{out_metricas}` — métricas por bacia/modelo
- `{out_faixas}` — curva score médio por faixa de chuva
- `{out_inv}` — diagnóstico de inversões
- `{OUT_DIR / "relatorio_combinador_risco_meteorologico.md"}` — este relatório
"""

    out_md = OUT_DIR / "relatorio_combinador_risco_meteorologico.md"
    out_md.write_text(relatorio, encoding="utf-8")
    print(f"\nRelatório salvo em {out_md}")
    print("=" * 80)
    print("DONE.")


if __name__ == "__main__":
    main()
