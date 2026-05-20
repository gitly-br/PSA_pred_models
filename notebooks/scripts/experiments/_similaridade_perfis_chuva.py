"""
_similaridade_perfis_chuva.py

Linha experimental: score de similaridade percentual (0-100) com perfis historicos
de chuva perigosa, sem prever chamados diretamente.

Metodologia:
1. Constroi vetor de perfil por (data, bacia) combinando:
   - PASSADO observado CEMADEN (features shiftadas: lags, acumulados, API).
   - FUTURO previsto OpenMeteo (proxy de forecast perfeito: acumulados, picos,
     duracao nas proximas 24h/48h/72h a partir do dia D).
2. Define automaticamente 2 perfis perigosos (pancada vs prolongada) via KMeans
   sobre os vetores de dias com evento confirmado no treino.
3. Calcula score 0-100 = similaridade maxima ao perfil mais proximo
   (distancia euclidiana normalizada, invertida e escalada).
4. Valida contra:
   - Chuva real futura (CEMADEN proximos 3 dias).
   - Severidade/target ordinal existente (benchmark V8).
5. Compara metricas com baseline V8 quando viavel (Spearman, PR-AUC).

Regras de leak:
- Features de passado CEMADEN usam apenas lags (shift >= 1).
- OpenMeteo e usado como proxy de forecast emitido no inicio do dia D,
  portanto representa informacao futura disponivel em tempo real.
- Perfis sao definidos APENAS no treino (< T_CUT); score e aplicado em todo
  o periodo, mas metricas de validacao usam holdout temporal (>= T_CUT).
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
from sklearn.cluster import KMeans
from sklearn.metrics import average_precision_score, precision_recall_curve
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ─── Paths ───────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
WORKDIR = SCRIPT_DIR.parents[1]  # notebooks/
OUT_DIR = WORKDIR / "dados" / "results"
OUT_DIR.mkdir(exist_ok=True)

# ─── Importar build_dataset do benchmark V8 (mesma engenharia de features) ─
_BM_PATH = SCRIPT_DIR / "_run_benchmark_v8.py"
_spec = importlib.util.spec_from_file_location("_run_benchmark_v8", _BM_PATH)
_bm = importlib.util.module_from_spec(_spec)
sys.modules["_run_benchmark_v8"] = _bm
_spec.loader.exec_module(_bm)

build_dataset = _bm.build_dataset
FEATURES_V8 = _bm.FEATURES
T_CUT = _bm.T_CUT
MESES_CHUVOSOS = _bm.MESES_CHUVOSOS

# ─── Config ──────────────────────────────────────────────────────────────
THRESHOLD_RAIN_HOUR = 0.5  # mm/h para contar como "hora chovendo"

# Features que compoem o vetor de perfil
PERFIL_COLS_PASSADO = [
    "max_day_lag1", "max_day_lag2", "max_day_lag3",
    "acum_7d", "acum_30d",
    "horas_intensas_lag1",
    "api_070", "api_085", "api_095",
]
PERFIL_COLS_FUTURO = [
    "om_acum_24h", "om_acum_48h", "om_acum_72h",
    "om_max_24h", "om_max_48h", "om_max_72h",
    "om_nhours_24h", "om_nhours_48h", "om_nhours_72h",
    "om_razao_24h", "om_razao_48h", "om_razao_72h",
]
PERFIL_COLS = PERFIL_COLS_PASSADO + PERFIL_COLS_FUTURO


# ─── Loaders ─────────────────────────────────────────────────────────────

def load_openmeteo_by_bacia() -> pl.DataFrame:
    """Carrega dados multipoint OpenMeteo e agrega por bacia (media)."""
    idx_path = WORKDIR / "dados" / "weather" / "openmeteo_multipoint" / "index.json"
    with open(idx_path) as f:
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
            ])
            .sort("dt")
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
        dfs.append(df_b)
    return pl.concat(dfs).sort(["bacia", "dt"])


def build_om_future_features(df_om: pl.DataFrame) -> pl.DataFrame:
    """
    Para cada dia D (referencia 00:00), calcula estatisticas de chuva
    FUTURA nas proximas 24h, 48h, 72h usando OpenMeteo como proxy de forecast.

    Usa reverse().rolling_xxx().reverse() para olhar para frente no tempo.
    """
    df_h = df_om.sort(["bacia", "dt"])
    resultados = []
    for janela_h in [24, 48, 72]:
        min_samples = int(janela_h * 0.8)
        df_j = (
            df_h.with_columns([
                pl.col("precipitation_mm")
                .reverse()
                .rolling_max(window_size=janela_h, min_samples=min_samples)
                .reverse()
                .over("bacia")
                .alias(f"om_max_{janela_h}h"),

                pl.col("precipitation_mm")
                .reverse()
                .rolling_sum(window_size=janela_h, min_samples=min_samples)
                .reverse()
                .over("bacia")
                .alias(f"om_acum_{janela_h}h"),

                (pl.col("precipitation_mm") > THRESHOLD_RAIN_HOUR)
                .cast(pl.Int32)
                .reverse()
                .rolling_sum(window_size=janela_h, min_samples=min_samples)
                .reverse()
                .over("bacia")
                .alias(f"om_nhours_{janela_h}h"),

                pl.col("precipitation_mm")
                .reverse()
                .rolling_mean(window_size=janela_h, min_samples=min_samples)
                .reverse()
                .over("bacia")
                .alias(f"om_mean_{janela_h}h"),
            ])
            .filter(pl.col("dt").dt.hour() == 0)
            .with_columns(pl.col("dt").dt.date().alias("data"))
            .select([
                "data", "bacia",
                f"om_max_{janela_h}h", f"om_acum_{janela_h}h",
                f"om_nhours_{janela_h}h", f"om_mean_{janela_h}h",
            ])
            .with_columns(
                (pl.col(f"om_max_{janela_h}h") / (pl.col(f"om_mean_{janela_h}h") + 1e-9))
                .alias(f"om_razao_{janela_h}h")
            )
        )
        resultados.append(df_j)

    df_out = resultados[0]
    for df_r in resultados[1:]:
        df_out = df_out.join(df_r, on=["data", "bacia"], how="outer")
        for c in [c for c in df_out.columns if c.endswith("_right")]:
            df_out = df_out.drop(c)
    return df_out.sort(["bacia", "data"])


def build_cemaden_past_and_future(df_cem: pl.DataFrame) -> pl.DataFrame:
    """
    Constroi diario CEMADEN com features de passado (shiftadas) e
    estatisticas de chuva real FUTURA (proximos 3 dias) para validacao.
    """
    df_h = df_cem.with_columns(pl.col("hora").dt.date().alias("data"))
    df_diario = (
        df_h.group_by(["data", "bacia"])
        .agg([
            pl.col("chuva_max_mm").max().alias("max_dia"),
            pl.col("chuva_max_mm").sum().alias("acum_dia"),
            (pl.col("chuva_max_mm") >= 5.0).sum().alias("horas_intensas"),
        ])
        .sort(["bacia", "data"])
    )

    # Futuro real (proximos 3 dias incluindo D) — para validacao
    df_diario = df_diario.with_columns([
        pl.col("max_dia")
        .reverse()
        .rolling_max(window_size=3, min_samples=1)
        .reverse()
        .over("bacia")
        .alias("future_max_3d"),

        pl.col("acum_dia")
        .reverse()
        .rolling_sum(window_size=3, min_samples=1)
        .reverse()
        .over("bacia")
        .alias("future_acum_3d"),
    ])
    return df_diario


def adicionar_acum_lags(df_feat: pl.DataFrame) -> pl.DataFrame:
    """
    O benchmark V8 nao exporta acum_dia lags diretamente.
    Recalculamos a partir do diario original embutido no build_dataset.
    Como build_dataset ja retorna df_ml com max_dia, adicionamos aqui
    os lags de acum_dia e horas_intensas extra.
    """
    # Nao precisamos refazer: build_dataset ja retorna df_ml com max_dia,
    # e df_feat (df_ml) ja contem as features V8. Vamos garantir que
    # acum_dia lags estejam disponiveis derivando de max_dia? Nao,
    # acum_dia e diferente. Como build_dataset nao exporta df_diario raw,
    # vamos recarregar e calcular lags de acum_dia aqui.
    # Para evitar duplicacao, vamos carregar chuva horaria CEMADEN de novo.
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        estacoes_bacia = json.load(f)

    partes = []
    for bacia in estacoes_bacia:
        df = pl.read_parquet(WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet")
        est_cols = [c for c in df.columns if c != "hora"]
        partes.append(
            df.with_columns([
                pl.max_horizontal(est_cols).alias("chuva_max_mm"),
            ])
            .select(["hora", "chuva_max_mm"])
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
    df_chuva_h = pl.concat(partes).sort(["bacia", "hora"])

    df_h = df_chuva_h.with_columns(pl.col("hora").dt.date().alias("data"))
    df_diario = (
        df_h.group_by(["data", "bacia"])
        .agg([
            pl.col("chuva_max_mm").sum().alias("acum_dia"),
        ])
        .sort(["bacia", "data"])
    )

    df_lags = df_diario.with_columns([
        pl.col("acum_dia").shift(1).over("bacia").alias("acum_dia_lag1"),
        pl.col("acum_dia").shift(2).over("bacia").alias("acum_dia_lag2"),
        pl.col("acum_dia").shift(3).over("bacia").alias("acum_dia_lag3"),
    ])

    return df_feat.join(df_lags.select(["data", "bacia", "acum_dia_lag1", "acum_dia_lag2", "acum_dia_lag3"]),
                        on=["data", "bacia"], how="left")


# ─── Definicao de perfis perigosos ───────────────────────────────────────

def definir_perfis_perigosos(df_train: pd.DataFrame, perfil_cols: list[str]) -> tuple[np.ndarray, dict]:
    """
    Aplica KMeans(k=2) nos vetores de perfil de dias perigosos do treino.
    Retorna centros normalizados e metadados de rotulagem.
    """
    mask_perigoso = df_train["severidade"] >= 1
    df_per = df_train.loc[mask_perigoso, perfil_cols].dropna()

    if len(df_per) < 4:
        raise ValueError(f"Apenas {len(df_per)} dias perigosos no treino. Insuficiente para 2 clusters.")

    scaler = StandardScaler()
    X_per = scaler.fit_transform(df_per.values)

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_per)

    # Rotula clusters por caracteristicas fisicas nos dados originais
    df_per_orig = df_per.copy()
    df_per_orig["cluster"] = labels

    # Metricas para rotulagem
    stats = df_per_orig.groupby("cluster").agg({
        "om_max_24h": "mean",
        "om_razao_24h": "mean",
        "om_acum_72h": "mean",
        "om_nhours_72h": "mean",
        "acum_7d": "mean",
    })

    # Heuristica: pancada = maior pico pontual + maior razao max/mean
    #             prolongada = maior acumulado 72h + maior duracao
    score_pancada = stats["om_max_24h"] + stats["om_razao_24h"]
    score_prolong = stats["om_acum_72h"] + stats["om_nhours_72h"] + stats["acum_7d"]

    cluster_pancada = int(score_pancada.idxmax())
    cluster_prolong = int(score_prolong.idxmax())

    # Se ambos deram o mesmo cluster, forca separacao pela segunda melhor
    if cluster_pancada == cluster_prolong:
        # fallback: quem tem maior razao vira pancada, outro prolongada
        cluster_pancada = int(stats["om_razao_24h"].idxmax())
        cluster_prolong = 1 - cluster_pancada

    centro_pancada = kmeans.cluster_centers_[cluster_pancada]
    centro_prolong = kmeans.cluster_centers_[cluster_prolong]

    metadados = {
        "cluster_pancada": cluster_pancada,
        "cluster_prolong": cluster_prolong,
        "stats_clusters": stats.to_dict(),
        "n_perigoso_treino": int(mask_perigoso.sum()),
        "n_amostras_cluster": {int(c): int((labels == c).sum()) for c in [0, 1]},
    }

    # Retorna centros no espaco normalizado (para distancia) e scaler
    return centro_pancada, centro_prolong, scaler, metadados


# ─── Score de similaridade ───────────────────────────────────────────────

def calcular_score(df: pd.DataFrame, perfil_cols: list[str],
                   centro_pancada: np.ndarray, centro_prolong: np.ndarray,
                   scaler: StandardScaler) -> pd.DataFrame:
    """
    Adiciona colunas 'score_pancada', 'score_prolong', 'score_final' (0-100).
    Score final = max(similaridade) * 100, onde similaridade = 1/(1+dist_euclidiana).
    """
    X = scaler.transform(df[perfil_cols].fillna(0).values)

    dist_panc = np.sqrt(((X - centro_pancada) ** 2).sum(axis=1))
    dist_prol = np.sqrt(((X - centro_prolong) ** 2).sum(axis=1))

    # Similaridade invertida: dist=0 -> 1, dist->inf -> 0
    sim_panc = 1.0 / (1.0 + dist_panc)
    sim_prol = 1.0 / (1.0 + dist_prol)

    df = df.copy()
    df["score_pancada"] = sim_panc
    df["score_prolong"] = sim_prol
    df["score_final"] = np.maximum(sim_panc, sim_prol) * 100.0
    return df


# ─── Metricas de validacao ───────────────────────────────────────────────

def calcular_metricas(df_test: pd.DataFrame) -> dict:
    """Calcula Spearman, PR-AUC e curvas por faixa de chuva."""
    res = {}

    # Spearman vs chuva real futura
    for col_target in ["future_max_3d", "future_acum_3d"]:
        mask = df_test[col_target].notna() & df_test["score_final"].notna()
        if mask.sum() > 3:
            rho, pval = spearmanr(df_test.loc[mask, col_target], df_test.loc[mask, "score_final"])
            res[f"spearman_{col_target}"] = float(rho)
            res[f"spearman_{col_target}_p"] = float(pval)
        else:
            res[f"spearman_{col_target}"] = np.nan
            res[f"spearman_{col_target}_p"] = np.nan

    # Spearman vs severidade
    mask = df_test["severidade"].notna() & df_test["score_final"].notna()
    if mask.sum() > 3:
        rho, pval = spearmanr(df_test.loc[mask, "severidade"], df_test.loc[mask, "score_final"])
        res["spearman_severidade"] = float(rho)
        res["spearman_severidade_p"] = float(pval)
    else:
        res["spearman_severidade"] = np.nan
        res["spearman_severidade_p"] = np.nan

    # PR-AUC vs target binario de chuva perigosa futura
    # Definicao: futuro perigoso = max_dia futuro >= p90 do treino OU acum_3d >= p95 do treino
    # (os percentis sao calculados no treino e passados como parametro; aqui usamos o proprio teste
    #  apenas para ilustracao, mas o ideal seria fixar threshold do treino)
    # Como a funcao e chamada apenas para teste, vamos usar thresholds fixos por bacia
    # calculados no treino e passados externamente.
    return res


def calcular_prauc_por_threshold(df: pd.DataFrame, thr_max: float, thr_acum: float) -> dict:
    """Calcula PR-AUC do score vs target binario de chuva perigosa futura."""
    y_true = (
        (df["future_max_3d"] >= thr_max) | (df["future_acum_3d"] >= thr_acum)
    ).astype(int).values
    y_score = df["score_final"].values

    if y_true.sum() == 0 or len(np.unique(y_true)) < 2:
        return {"prauc_chuva_futura": np.nan, "n_positivos": int(y_true.sum()), "n_total": len(y_true)}

    prauc = average_precision_score(y_true, y_score)
    return {
        "prauc_chuva_futura": float(prauc),
        "n_positivos": int(y_true.sum()),
        "n_total": len(y_true),
    }


def calcular_faixas_chuva(df: pd.DataFrame) -> pd.DataFrame:
    """Curva score medio por faixa de chuva real futura (max_3d)."""
    bins = [0, 5, 10, 20, 30, 50, 80, 120, float("inf")]
    labels = ["0-5", "5-10", "10-20", "20-30", "30-50", "50-80", "80-120", "120+"]
    df = df.copy()
    df["faixa"] = pd.cut(df["future_max_3d"], bins=bins, labels=labels, right=False)
    res = (
        df.groupby("faixa", observed=True)
        .agg(
            n=("score_final", "count"),
            score_medio=("score_final", "mean"),
            severidade_media=("severidade", "mean"),
        )
        .reset_index()
    )
    return res


# ─── Baseline V8 simples para comparacao ─────────────────────────────────

def rodar_baseline_v8_simples(df_ml: pl.DataFrame, bacia: str) -> dict:
    """
    Roda um unico classificador binario GradBoost (k=1) do benchmark V8
    no mesmo split temporal e retorna Spearman no test set.
    """
    from sklearn.ensemble import GradientBoostingClassifier

    sub = df_ml.filter(pl.col("bacia") == bacia).drop_nulls(FEATURES_V8).sort("data")
    t_cut_local = T_CUT
    if bacia == "oratorio":
        ev = sub.filter(pl.col("enchente"))["data"].sort()
        if len(ev) > 0:
            t_cut_local = ev[int(len(ev) * 0.75)]

    train = sub.filter(pl.col("data") < t_cut_local)
    test = sub.filter(pl.col("data") >= t_cut_local)

    if train.height < 30 or test.height < 5:
        return {"spearman_baseline": np.nan}

    X_train = train[FEATURES_V8].to_pandas().values
    X_test = test[FEATURES_V8].to_pandas().values
    y_train = (train["severidade"].to_numpy() >= 1).astype(int)

    sw = np.where(train["severidade"].to_numpy() == 3, 3.0,
          np.where(train["severidade"].to_numpy() == 2, 1.5, 1.0)).astype(float)

    clf = GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05,
        max_depth=2, min_samples_leaf=10,
        subsample=0.8, max_features="sqrt",
        random_state=42,
    )
    clf.fit(X_train, y_train, sample_weight=sw)
    prob_test = clf.predict_proba(X_test)[:, 1]

    max_dia_test = test["max_dia"].to_numpy()
    if len(np.unique(max_dia_test)) > 1 and len(np.unique(prob_test)) > 1:
        rho, _ = spearmanr(max_dia_test, prob_test)
    else:
        rho = np.nan

    # PR-AUC vs severidade>=1 no test
    y_test = (test["severidade"].to_numpy() >= 1).astype(int)
    prauc = average_precision_score(y_test, prob_test) if y_test.sum() > 0 else np.nan

    return {
        "spearman_baseline": float(rho),
        "prauc_baseline": float(prauc),
    }


# ─── Main ─────────────────────────────────────────────────────────────────

def main():
    print("=" * 80)
    print("SIMILARIDADE COM PERFIS DE CHUVA PERIGOSA")
    print("=" * 80)

    # 1. Dataset V8 (ja com features de passado shiftadas e target severidade)
    print("\n[1] Carregando dataset V8 (passado CEMADEN + target)...")
    df_ml, estacoes_bacia, _ = build_dataset()
    if "enchente" not in df_ml.columns:
        df_ml = df_ml.with_columns((pl.col("severidade") >= 1).alias("enchente"))

    # 2. Adiciona acum_dia lags (nao estao no V8 mas sao uteis para perfil)
    print("[2] Adicionando lags de acum_dia ao perfil...")
    df_ml = adicionar_acum_lags(df_ml)
    PERFIL_COLS_PASSADO_EXT = PERFIL_COLS_PASSADO + ["acum_dia_lag1", "acum_dia_lag2", "acum_dia_lag3"]
    global PERFIL_COLS
    PERFIL_COLS = PERFIL_COLS_PASSADO_EXT + PERFIL_COLS_FUTURO

    # 3. OpenMeteo futuro
    print("[3] Carregando OpenMeteo e calculando features futuras...")
    df_om = load_openmeteo_by_bacia()
    df_om_fut = build_om_future_features(df_om)

    # 4. Chuva real futura (CEMADEN) para validacao
    print("[4] Calculando chuva real futura (proximos 3 dias) para validacao...")
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        estacoes_bacia = json.load(f)
    partes = []
    for bacia in estacoes_bacia:
        df = pl.read_parquet(WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet")
        est_cols = [c for c in df.columns if c != "hora"]
        partes.append(
            df.with_columns([
                pl.max_horizontal(est_cols).alias("chuva_max_mm"),
            ])
            .select(["hora", "chuva_max_mm"])
            .with_columns(pl.lit(bacia).alias("bacia"))
        )
    df_cem = pl.concat(partes).sort(["bacia", "hora"])
    df_cem_fut = build_cemaden_past_and_future(df_cem)

    # Join tudo
    df_ml = df_ml.join(df_om_fut, on=["data", "bacia"], how="left")
    df_ml = df_ml.join(df_cem_fut.select(["data", "bacia", "future_max_3d", "future_acum_3d"]),
                       on=["data", "bacia"], how="left")

    # Filtra meses chuvosos
    df_ml = df_ml.filter(pl.col("data").dt.month().is_in(MESES_CHUVOSOS))

    # 5. Loop por bacia
    resultados_metricas = []
    resultados_faixas = []
    resultados_rows = []
    perfis_por_bacia = {}

    print("\n[5] Definindo perfis perigosos e calculando scores...")
    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_ml.filter(pl.col("bacia") == bacia).sort("data").to_pandas()
        if len(sub) < 100:
            print(f"  {bacia}: pulado (apenas {len(sub)} registros)")
            continue

        t_cut_local = T_CUT
        if bacia == "oratorio":
            ev = sub.loc[sub["enchente"], "data"].sort_values()
            if len(ev) > 0:
                t_cut_local = ev.iloc[int(len(ev) * 0.75)]

        t_cut_ts = pd.Timestamp(t_cut_local)
        train = sub[sub["data"] < t_cut_ts].copy()
        test = sub[sub["data"] >= t_cut_ts].copy()

        if train["severidade"].notna().sum() < 30 or test["severidade"].notna().sum() < 5:
            print(f"  {bacia}: pulado (train/test insuficiente)")
            continue

        # Define perfis no treino
        try:
            centro_panc, centro_prol, scaler, meta = definir_perfis_perigosos(train, PERFIL_COLS)
        except ValueError as e:
            print(f"  {bacia}: falha ao definir perfis ({e})")
            continue

        perfis_por_bacia[bacia] = meta

        # Calcula score em todo o periodo (treino + teste) para consistencia
        sub_scored = calcular_score(sub, PERFIL_COLS, centro_panc, centro_prol, scaler)
        t_cut_ts = pd.Timestamp(t_cut_local)
        train_scored = sub_scored[sub_scored["data"] < t_cut_ts]
        test_scored = sub_scored[sub_scored["data"] >= t_cut_ts]

        # Metricas no teste
        met = calcular_metricas(test_scored)

        # Thresholds de chuva perigosa futura a partir do treino
        thr_max = train["future_max_3d"].quantile(0.90) if train["future_max_3d"].notna().sum() > 0 else 80.0
        thr_acum = train["future_acum_3d"].quantile(0.95) if train["future_acum_3d"].notna().sum() > 0 else 150.0
        met_pr = calcular_prauc_por_threshold(test_scored, thr_max, thr_acum)
        met.update(met_pr)
        met["thr_max_futuro"] = float(thr_max)
        met["thr_acum_futuro"] = float(thr_acum)

        # Baseline V8 simples (Spearman)
        base_met = rodar_baseline_v8_simples(df_ml, bacia)
        met.update(base_met)

        # Faixas de chuva
        faixas = calcular_faixas_chuva(test_scored)
        faixas["bacia"] = bacia
        resultados_faixas.append(faixas)

        # Armazena linhas scored para exportacao
        sub_scored["bacia"] = bacia
        resultados_rows.append(sub_scored)

        resultados_metricas.append({
            "bacia": bacia,
            "n_treino": len(train),
            "n_teste": len(test),
            "n_perigoso_treino": meta["n_perigoso_treino"],
            **met,
        })

        print(f"  {bacia}: treino={len(train)} teste={len(test)} perigoso_treino={meta['n_perigoso_treino']}")
        print(f"    Spearman score vs future_max_3d = {met.get('spearman_future_max_3d', np.nan):.3f}")
        print(f"    Spearman score vs severidade    = {met.get('spearman_severidade', np.nan):.3f}")
        print(f"    PR-AUC chuva futura             = {met.get('prauc_chuva_futura', np.nan):.3f}")
        print(f"    Baseline V8 Spearman            = {met.get('spearman_baseline', np.nan):.3f}")

    # 6. Consolida e salva
    print("\n[6] Consolidando resultados...")
    df_metricas = pd.DataFrame(resultados_metricas)
    df_faixas = pd.concat(resultados_faixas, ignore_index=True) if resultados_faixas else pd.DataFrame()
    df_scored = pd.concat(resultados_rows, ignore_index=True) if resultados_rows else pd.DataFrame()

    out_parquet = OUT_DIR / "similaridade_perfis_chuva.parquet"
    out_faixas = OUT_DIR / "similaridade_perfis_faixas.parquet"
    out_perfis = OUT_DIR / "similaridade_perfis_centros.json"

    df_scored.to_parquet(out_parquet)
    if not df_faixas.empty:
        df_faixas.to_parquet(out_faixas)
    with open(out_perfis, "w") as f:
        json.dump(perfis_por_bacia, f, indent=2, default=str)

    print(f"  Scored data -> {out_parquet}")
    print(f"  Faixas      -> {out_faixas}")
    print(f"  Perfis JSON -> {out_perfis}")

    # 7. Relatorio final
    print("\n" + "=" * 80)
    print("RELATORIO FINAL — Similaridade com Perfis de Chuva Perigosa")
    print("=" * 80)

    print("\n## METODO")
    print("- Vetor de perfil por (data, bacia) combina:")
    print("  * PASSADO CEMADEN (shiftado): max_lags, acum_7d/30d, horas_intensas, API.")
    print("  * FUTURO OpenMeteo (proxy forecast): acum/max/duracao nas proximas 24/48/72h.")
    print("- Perfis perigosos definidos automaticamente via KMeans(k=2) sobre dias com")
    print("  severidade >= 1 no treino; rotulados heuristicamente como pancada vs prolongada.")
    print("- Score 0-100 = max( 1/(1+dist_euclidiana_normalizada) ) * 100 ao perfil mais proximo.")
    print("- Validacao holdout temporal (train < T_CUT, test >= T_CUT).")

    print("\n## ARQUIVOS GERADOS")
    print(f"- Script: {Path(__file__).name}")
    print(f"- Resultados scored: {out_parquet}")
    print(f"- Curvas por faixa:  {out_faixas}")
    print(f"- Metadados perfis:  {out_perfis}")

    print("\n## METRICAS POR BACIA")
    if not df_metricas.empty:
        cols_print = ["bacia", "n_teste", "n_perigoso_treino",
                      "spearman_future_max_3d", "spearman_severidade",
                      "prauc_chuva_futura", "spearman_baseline"]
        for _, r in df_metricas.iterrows():
            print(f"\n  {r['bacia'].upper()}:")
            for c in cols_print[1:]:
                val = r.get(c, np.nan)
                if pd.isna(val):
                    print(f"    {c:<30} = N/A")
                else:
                    print(f"    {c:<30} = {val:.3f}")
    else:
        print("  Nenhuma metrica gerada.")

    print("\n## FALHAS E LIMITES CONHECIDOS")
    print("- OpenMeteo usado e ERA5-Land reanalise (forecast 'perfeito'); em producao")
    print("  o forecast real tera gap de qualidade que reduzira o score.")
    print("- KMeans com k=2 pode nao separar bem pancada/prolongada quando n_perigoso")
    print("  e pequeno (< 20 amostras por bacia).")
    print("- O score e puramente geometrico (distancia ao centroide); nao e um modelo")
    print("  probabilistico calibrado, portanto a escala 0-100 e relativa, nao absoluta.")
    print("- Dados futuros CEMADEN usados apenas para validacao; o score em si nao os ve.")

    print("\n## DECISAO RECOMENDADA")
    if not df_metricas.empty:
        mean_spearman_max = df_metricas["spearman_future_max_3d"].mean()
        mean_spearman_sev = df_metricas["spearman_severidade"].mean()
        mean_prauc = df_metricas["prauc_chuva_futura"].mean()
        mean_base = df_metricas["spearman_baseline"].mean()

        print(f"  Spearman medio score vs future_max_3d : {mean_spearman_max:.3f}")
        print(f"  Spearman medio score vs severidade    : {mean_spearman_sev:.3f}")
        print(f"  PR-AUC medio vs chuva futura perigosa : {mean_prauc:.3f}")
        print(f"  Spearman medio baseline V8 (k=1)      : {mean_base:.3f}")

        if mean_spearman_max > (mean_base + 0.05):
            print("  -> PROMISSOR: o score de similaridade supera o baseline V8 em")
            print("     correlacao com chuva futura. Recomenda-se nova rodada com")
            print("     ensemble do score + modelo V8, ou substituicao da prob V8 pelo score.")
        elif mean_spearman_max > (mean_base - 0.05):
            print("  -> PRECISA NOVA RODADA: resultado dentro da margem do baseline.")
            print("     Testar: (a) mais features no vetor de perfil (tendencia, saturação),")
            print("     (b) clusterizacao supervisionada (ex: GMM com covariança completa),")
            print("     (c) peso diferenciado pancada vs prolongada por bacia.")
        else:
            print("  -> DESCARTAR: score de similaridade geometrico puro nao supera")
            print("     o baseline V8. A distancia ao centroide nao captura bem a")
            print("     relacao chuva-risco neste dataset.")
    else:
        print("  -> PRECISA NOVA RODADA: nenhuma metrica foi gerada (falha de dados).")

    print("\n" + "=" * 80)
    print("Done.")


if __name__ == "__main__":
    main()
