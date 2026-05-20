"""
Exportação do Risk Model V1 — Station Contract ROBUST para artefato joblib
=======================================================================

Script autônomo que:
1. Reconstroi o pipeline de feature engineering do robust model
2. Treina modelos finais por (bacia, label) usando cutoff honesto ate 2023-07-02
   e expande para treino final ate 2025-12-31 (sem 2026)
3. Seleciona a variante mais conservadora por bacia/label com base no relatorio
4. Exporta classe serializavel unica em joblib
5. Emite metadata JSON e smoke test

Nao altera backend runtime.
"""

from __future__ import annotations

import json
import warnings
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import polars as pl
from scipy.signal import lfilter
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_recall_curve
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

# ─── Paths ────────────────────────────────────────────────────────────────
WORKDIR = Path(__file__).resolve().parents[2]
OUT_DIR = WORKDIR / "dados" / "results"
MODEL_DIR = WORKDIR / "modelos"
OUT_DIR.mkdir(exist_ok=True)
MODEL_DIR.mkdir(exist_ok=True)

# ─── Config ──────────────────────────────────────────────────────────────
MESES_CHUVOSOS = [11, 12, 1, 2, 3, 4]
T_CUT = datetime(2023, 7, 2).date()
K_APIS = [0.70, 0.85, 0.95]
LIM_INTENSO_MM = 5.0
HORIZONTES_FC = [24, 48]

PCT_PANCADA = 0.95
PCT_PROLONGADA = 0.90
PCT_SATURANTE = 0.90

LABELS = ["pancada", "prolongada", "saturante", "perigoso_any"]

# Decisao conservadora: escolhas por (bacia, label) baseadas no relatorio robusto.
# Em caso de ambiguidade, preferimos CEMADEN_ONLY (menos dependencia externa)
# e gradboost_cons (mais estavel que logreg_cons).
# Mapeia (bacia, label) -> (variante, modelo)
CONSERVATIVE_SELECTION: Dict[Tuple[str, str], Tuple[str, str]] = {
    # guarara
    ("guarara", "pancada"): ("CEMADEN_ONLY", "gradboost_cons"),
    ("guarara", "prolongada"): ("CEMADEN_ONLY", "gradboost_cons"),
    ("guarara", "saturante"): ("CEMADEN_ONLY", "gradboost_cons"),
    ("guarara", "perigoso_any"): ("CEMADEN_OM", "gradboost_cons"),
    # oratorio
    ("oratorio", "pancada"): ("CEMADEN_ONLY", "gradboost_cons"),
    ("oratorio", "prolongada"): ("CEMADEN_OM", "gradboost_cons"),
    ("oratorio", "saturante"): ("CEMADEN_ONLY", "gradboost_cons"),
    ("oratorio", "perigoso_any"): ("CEMADEN_ONLY", "gradboost_cons"),
    # meninos
    ("meninos", "pancada"): ("CEMADEN_ONLY", "gradboost_cons"),
    ("meninos", "prolongada"): ("CEMADEN_OM", "gradboost_cons"),
    ("meninos", "saturante"): ("ALL", "gradboost_cons"),
    ("meninos", "perigoso_any"): ("CEMADEN_OM", "gradboost_cons"),
    # tamanduatei
    ("tamanduatei", "pancada"): ("CEMADEN_ONLY", "gradboost_cons"),
    ("tamanduatei", "prolongada"): ("CEMADEN_OM", "gradboost_cons"),
    ("tamanduatei", "saturante"): ("CEMADEN_OM", "gradboost_cons"),
    ("tamanduatei", "perigoso_any"): ("CEMADEN_OM", "gradboost_cons"),
}


def load_station_contract() -> dict:
    with open(WORKDIR / "dados" / "estacoes_bacia.json") as f:
        return json.load(f)


def build_hourly_data(estacoes_bacia: dict) -> pl.DataFrame:
    """Concatena chuva_bacias historicas com dados mensais CEMADEN 2026 (filtrados ate 2025)."""
    parts = []
    for bacia, stations in estacoes_bacia.items():
        df_hist = pl.read_parquet(WORKDIR / "dados" / "chuva_bacias" / f"chuva_{bacia}.parquet")
        cols_keep = ["hora"] + [s for s in stations if s in df_hist.columns]
        df_hist = df_hist.select(cols_keep)
        parts.append(df_hist.with_columns(pl.lit(bacia).alias("bacia")))

    all_cols = set()
    for p in parts:
        all_cols.update(p.columns)
    for i in range(len(parts)):
        for c in all_cols:
            if c not in parts[i].columns:
                parts[i] = parts[i].with_columns(pl.lit(None).cast(pl.Float64).alias(c))
        parts[i] = parts[i].select(sorted(all_cols))
    df_h = pl.concat(parts).sort(["bacia", "hora"])

    # Dados 2026 existem mas NAO usamos para treino; mantemos so se houver necessidade
    # de estrutura, mas filtramos fora do range de treino mais adiante.
    meses_2026 = ["2026_01", "2026_02", "2026_03", "2026_04", "2026_05"]
    dfs_2026 = []
    for m in meses_2026:
        path = WORKDIR / "dados" / "weather" / "monthly" / "historic" / f"cemaden_{m}.parquet"
        if path.exists():
            dfs_2026.append(pl.read_parquet(path))
    if dfs_2026:
        df_2026_raw = pl.concat(dfs_2026)
    else:
        df_2026_raw = pl.DataFrame(
            schema={
                "municipio": pl.String,
                "codEstacao": pl.String,
                "nomeEstacao": pl.String,
                "latitude": pl.Float64,
                "longitude": pl.Float64,
                "dt": pl.Datetime("us"),
                "valor_mm": pl.Float64,
            }
        )

    df_2026_wide = (
        df_2026_raw.select(["dt", "codEstacao", "valor_mm"])
        .pivot(index="dt", on="codEstacao", values="valor_mm", aggregate_function="first")
    )

    parts_2026 = []
    for bacia, stations in estacoes_bacia.items():
        cols = [s for s in stations if s in df_2026_wide.columns]
        if not cols:
            continue
        sub = df_2026_wide.select(["dt"] + cols).rename({"dt": "hora"})
        parts_2026.append(sub.with_columns(pl.lit(bacia).alias("bacia")))

    if parts_2026:
        all_cols_2026 = set()
        for p in parts_2026:
            all_cols_2026.update(p.columns)
        for i in range(len(parts_2026)):
            for c in all_cols_2026:
                if c not in parts_2026[i].columns:
                    parts_2026[i] = parts_2026[i].with_columns(
                        pl.lit(None).cast(pl.Float64).alias(c)
                    )
            parts_2026[i] = parts_2026[i].select(sorted(all_cols_2026))
        df_2026 = pl.concat(parts_2026).sort(["bacia", "hora"])
    else:
        df_2026 = pl.DataFrame(schema={"hora": pl.Datetime("us"), "bacia": pl.String})

    all_station_cols = set()
    for c in df_h.columns:
        if c not in ("hora", "bacia"):
            all_station_cols.add(c)
    for c in df_2026.columns:
        if c not in ("hora", "bacia"):
            all_station_cols.add(c)

    for col in all_station_cols:
        if col not in df_h.columns:
            df_h = df_h.with_columns(pl.lit(None).cast(pl.Float64).alias(col))
        if col not in df_2026.columns:
            df_2026 = df_2026.with_columns(pl.lit(None).cast(pl.Float64).alias(col))

    df_full = pl.concat([df_h, df_2026.select(df_h.columns)], how="vertical").sort(["bacia", "hora"])
    return df_full


def build_daily_cemaden(df_hourly: pl.DataFrame, estacoes_bacia: dict) -> pl.DataFrame:
    parts = []
    for bacia, stations in estacoes_bacia.items():
        sub = df_hourly.filter(pl.col("bacia") == bacia).drop("bacia")
        est_cols = [s for s in stations if s in sub.columns]
        if not est_cols:
            continue
        sub = sub.with_columns(
            [
                pl.max_horizontal(est_cols).alias("chuva_max_mm"),
                pl.mean_horizontal(est_cols).alias("chuva_mean_mm"),
                pl.concat_list([pl.col(c) for c in est_cols]).list.std().alias("chuva_std_mm"),
                pl.sum_horizontal([(pl.col(c) > 1.0).cast(pl.Int8) for c in est_cols]).alias("n_chovendo"),
            ]
        )
        parts.append(
            sub.select(["hora", "chuva_max_mm", "chuva_mean_mm", "chuva_std_mm", "n_chovendo"])
            .with_columns(pl.lit(bacia).alias("bacia"))
        )

    df_h = pl.concat(parts).sort(["bacia", "hora"])
    df_h = df_h.with_columns(pl.col("hora").dt.date().alias("data"))
    df_diario = (
        df_h.group_by(["data", "bacia"])
        .agg(
            [
                pl.col("chuva_max_mm").max().alias("max_dia"),
                pl.col("chuva_max_mm").sum().alias("acum_dia"),
                pl.col("chuva_mean_mm").mean().alias("mean_dia"),
                pl.col("chuva_std_mm").mean().alias("std_dia"),
                pl.col("n_chovendo").max().alias("n_chovendo_max"),
                pl.col("chuva_max_mm").max().alias("pico_1h"),
                (pl.col("chuva_max_mm") >= LIM_INTENSO_MM).sum().alias("horas_intensas"),
            ]
        )
        .sort(["bacia", "data"])
    )
    return df_diario


def build_targets(df_diario: pl.DataFrame, estacoes_bacia: dict, t_cut: date):
    df_diario = df_diario.with_columns(
        [
            pl.col("acum_dia")
            .rolling_sum(window_size=2, min_samples=1)
            .over("bacia")
            .alias("acum_48h_proxy"),
        ]
    )

    train = df_diario.filter(pl.col("data") < t_cut)
    thresholds = {}
    for bacia in estacoes_bacia:
        sub = train.filter(pl.col("bacia") == bacia)
        thresholds[bacia] = {
            "pancada": float(sub["max_dia"].quantile(PCT_PANCADA)) if sub.height > 0 else 50.0,
            "prolongada": float(sub["acum_dia"].quantile(PCT_PROLONGADA)) if sub.height > 0 else 80.0,
        }

    sat_thr = {}
    for bacia in estacoes_bacia:
        sub = train.filter(pl.col("bacia") == bacia)
        sat_thr[bacia] = (
            float(sub["acum_48h_proxy"].quantile(PCT_SATURANTE)) if sub.height > 0 else 150.0
        )

    df_thr = pl.DataFrame(
        [
            {
                "bacia": b,
                "thr_pancada": v["pancada"],
                "thr_prolongada": v["prolongada"],
                "thr_saturante": sat_thr[b],
            }
            for b, v in thresholds.items()
        ]
    )
    df_diario = df_diario.join(df_thr, on="bacia", how="left")

    df_diario = df_diario.with_columns(
        [
            (pl.col("max_dia") > pl.col("thr_pancada")).alias("pancada"),
            (pl.col("acum_dia") > pl.col("thr_prolongada")).alias("prolongada"),
            (pl.col("acum_48h_proxy") > pl.col("thr_saturante")).alias("saturante"),
        ]
    ).with_columns(
        (pl.col("pancada") | pl.col("prolongada") | pl.col("saturante")).alias("perigoso_any")
    )

    return df_diario, thresholds, sat_thr


def build_features(df_diario: pl.DataFrame) -> pl.DataFrame:
    df = df_diario.with_columns(
        [
            pl.col("max_dia").shift(1).over("bacia").alias("max_day_lag1"),
            pl.col("max_dia").shift(2).over("bacia").alias("max_day_lag2"),
            pl.col("max_dia").shift(3).over("bacia").alias("max_day_lag3"),
            pl.col("acum_dia").shift(1).over("bacia").alias("acum_dia_lag1"),
            pl.col("mean_dia").shift(1).over("bacia").alias("mean_day_lag1"),
            pl.col("std_dia").shift(1).over("bacia").alias("std_day_lag1"),
            pl.col("n_chovendo_max").shift(1).over("bacia").alias("n_chovendo_max_lag1"),
            pl.col("pico_1h").shift(1).over("bacia").alias("pico_1h_lag1"),
            pl.col("horas_intensas").shift(1).over("bacia").alias("horas_intensas_lag1"),
            pl.col("acum_dia").rolling_sum(window_size=7, min_samples=1).shift(1).over("bacia").alias("acum_7d"),
            pl.col("acum_dia").rolling_sum(window_size=30, min_samples=1).shift(1).over("bacia").alias("acum_30d"),
            (2 * np.pi * pl.col("data").dt.month() / 12).sin().alias("mes_sin"),
            (2 * np.pi * pl.col("data").dt.month() / 12).cos().alias("mes_cos"),
        ]
    )

    _api_parts = []
    for bacia in df["bacia"].unique().to_list():
        _sub = df.filter(pl.col("bacia") == bacia).sort("data")
        _vals = _sub["max_dia"].shift(1).fill_null(0).to_numpy()
        cols = {"data": _sub["data"], "bacia": _sub["bacia"]}
        for _k in K_APIS:
            cols[f"api_{int(_k*100):03d}"] = lfilter([1.0], [1.0, -_k], _vals)
        _api_parts.append(pl.DataFrame(cols))
    df_api = pl.concat(_api_parts)
    df = df.join(df_api, on=["data", "bacia"], how="left")
    return df


def build_openmeteo_forecast_features() -> pl.DataFrame:
    # Carrega forecast disponivel ate 2025 (nao 2026 para treino)
    dfs = []
    for y in range(2024, 2026):
        for m in range(1, 13):
            path = WORKDIR / "dados" / "weather" / "monthly" / "forecast" / f"openmeteo_{y}_{m:02d}.parquet"
            if path.exists():
                dfs.append(pl.read_parquet(path))
    # Tambem tenta 2023
    for m in range(7, 13):
        path = WORKDIR / "dados" / "weather" / "monthly" / "forecast" / f"openmeteo_2023_{m:02d}.parquet"
        if path.exists():
            dfs.append(pl.read_parquet(path))

    if not dfs:
        return pl.DataFrame(schema={"data": pl.Date})

    df_raw = pl.concat(dfs)
    df_h = (
        df_raw.group_by("dt")
        .agg(
            [
                pl.col("precipitation_mm").mean().alias("precipitation_mm"),
                pl.col("rain_mm").mean().alias("rain_mm"),
                pl.col("temperature_c").mean().alias("temperature_c"),
                pl.col("humidity_pct").mean().alias("humidity_pct"),
                pl.col("wind_speed_kmh").max().alias("wind_max_kmh"),
                pl.col("pressure_hpa").mean().alias("pressure_hpa"),
            ]
        )
        .sort("dt")
    )
    df_h = df_h.with_columns(pl.col("dt").dt.date().alias("data"))

    rows = []
    for data in df_h["data"].unique().sort().to_list():
        row = {"data": data}
        dt_start = datetime.combine(data, datetime.min.time())
        for H in HORIZONTES_FC:
            dt_end = dt_start + timedelta(hours=H)
            janela = df_h.filter((pl.col("dt") >= dt_start) & (pl.col("dt") < dt_end))
            if janela.height == 0:
                row[f"om_precip_sum_h{H}"] = 0.0
                row[f"om_rain_max_h{H}"] = 0.0
                row[f"om_temp_mean_h{H}"] = None
                row[f"om_humidity_mean_h{H}"] = None
                row[f"om_wind_max_h{H}"] = None
                row[f"om_pressure_mean_h{H}"] = None
                continue
            row[f"om_precip_sum_h{H}"] = float(janela["precipitation_mm"].sum())
            row[f"om_rain_max_h{H}"] = float(janela["rain_mm"].max())
            row[f"om_temp_mean_h{H}"] = float(janela["temperature_c"].mean())
            row[f"om_humidity_mean_h{H}"] = float(janela["humidity_pct"].mean())
            row[f"om_wind_max_h{H}"] = float(janela["wind_max_kmh"].max())
            row[f"om_pressure_mean_h{H}"] = float(janela["pressure_hpa"].mean())
        rows.append(row)

    return pl.DataFrame(rows)


def add_openmeteo_features(df: pl.DataFrame, df_om: pl.DataFrame) -> pl.DataFrame:
    return df.join(df_om, on="data", how="left")


def add_risk_components(df: pl.DataFrame) -> pl.DataFrame:
    df = df.with_columns(
        [
            (pl.col("max_day_lag1") + pl.col("pico_1h_lag1")).alias("comp_pancada_raw"),
            (pl.col("api_070") + pl.col("api_085") + pl.col("api_095")).alias("api_sum"),
        ]
    )
    df = df.with_columns(
        (pl.col("comp_pancada_raw") * (1 + pl.col("api_sum") / 100)).alias("comp_pancada")
    )
    df = df.with_columns(
        (
            pl.col("acum_7d")
            + pl.col("acum_dia_lag1")
            + pl.col("mean_day_lag1") * pl.col("n_chovendo_max_lag1")
        ).alias("comp_prolongada")
    )
    df = df.with_columns(
        pl.when(pl.col("om_humidity_mean_h24").is_not_null())
        .then(pl.col("acum_30d") * (1 + pl.col("om_humidity_mean_h24") / 100))
        .otherwise(pl.col("acum_30d"))
        .alias("comp_saturacao")
    )
    return df


def get_model(modelo: str):
    if modelo == "logreg_std":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=1000, C=1.0, random_state=42)),
            ]
        )
    elif modelo == "logreg_cons":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=1000, C=0.1, random_state=42)),
            ]
        )
    elif modelo == "gradboost_std":
        return GradientBoostingClassifier(
            n_estimators=150,
            learning_rate=0.05,
            max_depth=4,
            min_samples_leaf=5,
            subsample=0.8,
            max_features="sqrt",
            random_state=42,
        )
    elif modelo == "gradboost_cons":
        return GradientBoostingClassifier(
            n_estimators=200,
            learning_rate=0.08,
            max_depth=2,
            min_samples_leaf=20,
            subsample=0.9,
            max_features="sqrt",
            random_state=42,
        )
    else:
        raise ValueError(f"Modelo desconhecido: {modelo}")


def _thr_f1(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    prec, rec, thrs = precision_recall_curve(y_true, y_prob)
    if len(thrs) == 0:
        return 0.5
    f1s = (2 * prec[:-1] * rec[:-1]) / (prec[:-1] + rec[:-1] + 1e-9)
    return float(thrs[np.nanargmax(f1s)]) if np.any(np.isfinite(f1s)) else 0.5


def train_final_model(X_train: np.ndarray, y_train: np.ndarray, modelo: str) -> Any:
    """Treina modelo final em todo o historico ate 2025 com sample_weight."""
    clf = get_model(modelo)
    sw = np.where(y_train == 1, 3.0, 0.7).astype(float)
    if "logreg" in modelo:
        clf.fit(X_train, y_train, clf__sample_weight=sw)
    else:
        clf.fit(X_train, y_train, sample_weight=sw)
    return clf


def compute_cv_threshold(X_train: np.ndarray, y_train: np.ndarray, modelo: str) -> float:
    """Computa threshold via CV temporal 3 splits no treino ate T_CUT."""
    tscv = TimeSeriesSplit(n_splits=3)
    oof = np.full(len(y_train), np.nan)
    sw = np.where(y_train == 1, 3.0, 0.7).astype(float)
    for tr_i, va_i in tscv.split(X_train):
        if y_train[tr_i].sum() == 0 or y_train[va_i].sum() == 0:
            continue
        clf_cv = get_model(modelo)
        sw_tr = sw[tr_i]
        if "logreg" in modelo:
            clf_cv.fit(X_train[tr_i], y_train[tr_i], clf__sample_weight=sw_tr)
        else:
            clf_cv.fit(X_train[tr_i], y_train[tr_i], sample_weight=sw_tr)
        oof[va_i] = clf_cv.predict_proba(X_train[va_i])[:, 1]
    mask = ~np.isnan(oof)
    thr = (
        _thr_f1(y_train[mask], oof[mask])
        if mask.sum() > 0 and y_train[mask].sum() > 0
        else 0.5
    )
    return float(thr)


# ─── Classe serializavel ─────────────────────────────────────────────────

class PSARiskV1StationContractRobust:
    """
    Artefato unico de risco meteorologico por bacia.

    Atributos expostos:
      - modeling_family: str
      - obj_version: str
      - station_ids: Dict[str, List[str]]
      - feature_contract: Dict[str, Any]
      - risk_components: List[str]
    """

    def __init__(
        self,
        models: Dict[str, Any],
        thresholds_map: Dict[str, float],
        station_ids: Dict[str, List[str]],
        feature_contract: Dict[str, Any],
        thresholds_calibration: Dict[str, Any],
        feature_names_map: Optional[Dict[str, List[str]]] = None,
        all_feature_order: Optional[List[str]] = None,
    ):
        self.modeling_family = "psa_risk_v1_station_contract_robust"
        self.obj_version = "0.2-exp"
        self.models = models  # chave: "bacia|label"
        self.thresholds_map = thresholds_map  # chave: "bacia|label"
        self.station_ids = station_ids
        self.feature_contract = feature_contract
        self.thresholds_calibration = thresholds_calibration
        self.feature_names_map = feature_names_map or {}
        self.all_feature_order = all_feature_order or []
        self.risk_components = ["pancada", "prolongada", "saturante", "perigoso_any"]
        self.forecast_horizons = [24, 48]

    def _get_key(self, bacia: str, label: str) -> str:
        return f"{bacia}|{label}"

    def _extract_features(self, key: str, X: np.ndarray) -> np.ndarray:
        """
        Extrai sub-array de X para o modelo `key`.
        Se X tem a dimensionalidade exata do modelo, retorna X.
        Se X tem a dimensionalidade de all_feature_order, faz slicing.
        Caso contrario, levanta ValueError.
        """
        expected_cols = self.feature_names_map.get(key, [])
        n_expected = len(expected_cols)
        if X.ndim == 1:
            X = X.reshape(1, -1)
        n_given = X.shape[1]
        if n_given == n_expected:
            return X
        if n_given == len(self.all_feature_order):
            # Faz slicing por nomes
            idx = [self.all_feature_order.index(c) for c in expected_cols if c in self.all_feature_order]
            if len(idx) != n_expected:
                missing = [c for c in expected_cols if c not in self.all_feature_order]
                raise ValueError(f"Features ausentes em all_feature_order para {key}: {missing}")
            return X[:, idx]
        raise ValueError(
            f"X tem {n_given} features, mas modelo {key} espera {n_expected} "
            f"ou all_feature_order com {len(self.all_feature_order)} features."
        )

    def predict_proba(
        self, bacia: str, X: np.ndarray, label: Optional[str] = None
    ) -> Dict[str, float]:
        """
        Retorna probabilidade para cada label ou para um label especifico.
        X deve ser 2D (n_samples, n_features).
        """
        if label is not None:
            key = self._get_key(bacia, label)
            if key not in self.models:
                return {label: 0.0}
            m = self.models[key]
            X_sub = self._extract_features(key, X)
            prob = m.predict_proba(X_sub)[:, 1]
            return {label: float(prob[0]) if prob.shape[0] == 1 else prob.tolist()}

        out = {}
        for lbl in self.risk_components:
            key = self._get_key(bacia, lbl)
            if key not in self.models:
                out[lbl] = 0.0
                continue
            m = self.models[key]
            X_sub = self._extract_features(key, X)
            prob = m.predict_proba(X_sub)[:, 1]
            out[lbl] = float(prob[0]) if prob.shape[0] == 1 else prob.tolist()
        return out

    def predict(self, bacia: str, X: np.ndarray, label: Optional[str] = None) -> Dict[str, int]:
        """Retorna predicao binaria (0/1) usando threshold calibrado."""
        probs = self.predict_proba(bacia, X, label=label)
        out = {}
        for lbl, prob in probs.items():
            key = self._get_key(bacia, lbl)
            thr = self.thresholds_map.get(key, 0.5)
            if isinstance(prob, list):
                out[lbl] = [1 if p >= thr else 0 for p in prob]
            else:
                out[lbl] = 1 if prob >= thr else 0
        return out

    def predict_severity(self, bacia: str, X: np.ndarray) -> int:
        """
        Alias para severidade inferida a partir das probabilidades.
        0 = baixo, 1 = moderado, 2 = alto, 3 = critico.
        """
        probs = self.predict_proba(bacia, X)
        # Usa perigoso_any como ancora; se nao existir, usa max dos componentes
        p_any = probs.get("perigoso_any", 0.0)
        if isinstance(p_any, list):
            p_any = p_any[0]
        p_sat = probs.get("saturante", 0.0)
        if isinstance(p_sat, list):
            p_sat = p_sat[0]
        p_pro = probs.get("prolongada", 0.0)
        if isinstance(p_pro, list):
            p_pro = p_pro[0]
        p_pan = probs.get("pancada", 0.0)
        if isinstance(p_pan, list):
            p_pan = p_pan[0]

        if p_any >= 0.7 or p_sat >= 0.8:
            return 3
        if p_any >= 0.5 or p_sat >= 0.6 or p_pro >= 0.6:
            return 2
        if p_any >= 0.3 or p_pan >= 0.5 or p_pro >= 0.4:
            return 1
        return 0

    def risk_score(self, bacia: str, X: np.ndarray) -> float:
        """
        Score agregado de risco [0, 1].
        Usa a probabilidade maxima entre os componentes como proxy.
        """
        probs = self.predict_proba(bacia, X)
        vals = [v for v in probs.values() if isinstance(v, (int, float))]
        if not vals:
            return 0.0
        return float(np.max(vals))

    def compute_risk_components(self, bacia: str, X: np.ndarray) -> Dict[str, float]:
        """Retorna dicionario com probabilidades de cada componente."""
        return self.predict_proba(bacia, X)


# ─── Main export ─────────────────────────────────────────────────────────


def main():
    print("=" * 80)
    print("EXPORT RISK MODEL V1 — STATION CONTRACT ROBUST (joblib)")
    print("=" * 80)

    estacoes_bacia = load_station_contract()

    print("\n[1/6] Carregando dados horarios...")
    df_hourly = build_hourly_data(estacoes_bacia)
    print(f"  Hourly shape: {df_hourly.shape}")

    print("\n[2/6] Agregando diario CEMADEN por bacia...")
    df_diario = build_daily_cemaden(df_hourly, estacoes_bacia)
    print(f"  Daily shape: {df_diario.shape}")

    print("\n[3/6] Construindo targets meteorologicos...")
    df_diario, thresholds, sat_thr = build_targets(df_diario, estacoes_bacia, T_CUT)
    print(f"  Thresholds pancada: { {k: f'{v:.1f}' for k,v in {b: thresholds[b]['pancada'] for b in thresholds}.items() } }")
    print(f"  Thresholds prolongada: { {k: f'{v:.1f}' for k,v in {b: thresholds[b]['prolongada'] for b in thresholds}.items() } }")
    print(f"  Thresholds saturante: { {k: f'{v:.1f}' for k,v in sat_thr.items() } }")

    print("\n[4/6] Feature engineering...")
    df_feat = build_features(df_diario)
    df_om = build_openmeteo_forecast_features()
    df_feat = add_openmeteo_features(df_feat, df_om)

    om_cols = [c for c in df_feat.columns if c.startswith("om_")]
    for c in om_cols:
        if "precip" in c or "rain" in c:
            df_feat = df_feat.with_columns(pl.col(c).fill_null(0))
        else:
            med = df_feat[c].median()
            df_feat = df_feat.with_columns(pl.col(c).fill_null(pl.lit(med) if med is not None else 0))

    df_feat = add_risk_components(df_feat)
    print(f"  Final feature shape: {df_feat.shape}")

    CEMADEN_VARS = (
        [f"api_{int(k*100):03d}" for k in K_APIS]
        + [
            "max_day_lag1",
            "max_day_lag2",
            "max_day_lag3",
            "acum_dia_lag1",
            "mean_day_lag1",
            "std_day_lag1",
            "n_chovendo_max_lag1",
            "pico_1h_lag1",
            "horas_intensas_lag1",
            "acum_7d",
            "acum_30d",
            "mes_sin",
            "mes_cos",
        ]
    )
    OM_VARS = []
    for H in HORIZONTES_FC:
        OM_VARS += [
            f"om_precip_sum_h{H}",
            f"om_rain_max_h{H}",
            f"om_temp_mean_h{H}",
            f"om_humidity_mean_h{H}",
            f"om_wind_max_h{H}",
            f"om_pressure_mean_h{H}",
        ]
    COMP_VARS = ["comp_pancada", "comp_prolongada", "comp_saturacao"]

    ALL_VARS = [c for c in (CEMADEN_VARS + OM_VARS + COMP_VARS) if c in df_feat.columns]

    VARIANTES = {
        "CEMADEN_ONLY": [c for c in CEMADEN_VARS if c in df_feat.columns],
        "CEMADEN_OM": [c for c in (CEMADEN_VARS + OM_VARS) if c in df_feat.columns],
        "ALL": ALL_VARS,
    }

    print("\n[5/6] Treinando modelos finais por bacia/label (conservador)...")
    models: Dict[str, Any] = {}
    thresholds_map: Dict[str, float] = {}
    feature_names_map: Dict[str, List[str]] = {}
    train_metrics_log: List[Dict[str, Any]] = []

    for bacia in sorted(estacoes_bacia.keys()):
        sub = df_feat.filter(pl.col("bacia") == bacia).sort("data")
        # Dados de treino: tudo ate 2025 (sem 2026)
        train_all = sub.filter(pl.col("data").dt.year() <= 2025)
        if train_all.height < 30:
            print(f"  {bacia}: pulado (train insuficiente)")
            continue

        for label in LABELS:
            sel = CONSERVATIVE_SELECTION.get((bacia, label))
            if sel is None:
                print(f"  {bacia}/{label}: sem selecao conservativa definida — pulado")
                continue
            variant, modelo = sel
            var_cols = VARIANTES.get(variant, [])
            cols_ok = [c for c in var_cols if c in sub.columns]

            # Drop nulos
            sub_v = sub.drop_nulls(cols_ok + [label, "max_dia"])
            train_v = sub_v.filter(pl.col("data").dt.year() <= 2025)
            # Para calibrar threshold honestamente, usamos so dados ate T_CUT
            train_cut = sub_v.filter(pl.col("data") < T_CUT)

            if train_v.height < 30:
                print(f"  {bacia}/{label}: pulado (train_v insuficiente)")
                continue

            y_train = train_v[label].to_numpy().astype(int)
            if y_train.sum() < 2:
                print(f"  {bacia}/{label}: pulado (positivos < 2)")
                continue

            X_train = train_v[cols_ok].to_pandas().to_numpy()
            # Treina modelo final
            clf = train_final_model(X_train, y_train, modelo)
            key = f"{bacia}|{label}"
            models[key] = clf
            feature_names_map[key] = cols_ok

            # Threshold honesto via CV no corte ate T_CUT
            if train_cut.height >= 30 and train_cut[label].sum() >= 2:
                X_cut = train_cut[cols_ok].to_pandas().to_numpy()
                y_cut = train_cut[label].to_numpy().astype(int)
                thr = compute_cv_threshold(X_cut, y_cut, modelo)
            else:
                thr = 0.5
            thresholds_map[key] = thr

            # Log basico de metricas no proprio treino (so para auditoria)
            prob_train = clf.predict_proba(X_train)[:, 1]
            prauc = average_precision_score(y_train, prob_train)
            train_metrics_log.append(
                {
                    "bacia": bacia,
                    "label": label,
                    "variant": variant,
                    "model": modelo,
                    "prauc_train": float(prauc),
                    "threshold": float(thr),
                    "n_train": int(len(y_train)),
                    "n_pos_train": int(y_train.sum()),
                }
            )
            print(f"  {bacia}/{label} [{variant}/{modelo}] PR-AUC(train)={prauc:.3f} thr={thr:.3f}")

    print("\n[6/6] Montando artefato e exportando...")
    feature_contract = {
        "cemaden_passado": CEMADEN_VARS,
        "openmeteo_forecast": OM_VARS,
        "componentes_risco": COMP_VARS,
    }

    thresholds_calibration = {
        "pct_pancada": PCT_PANCADA,
        "pct_prolongada": PCT_PROLONGADA,
        "pct_saturante": PCT_SATURANTE,
        "by_bacia": {
            b: {
                "pancada": thresholds[b]["pancada"],
                "prolongada": thresholds[b]["prolongada"],
                "saturante": sat_thr[b],
            }
            for b in thresholds
        },
    }

    artifact = PSARiskV1StationContractRobust(
        models=models,
        thresholds_map=thresholds_map,
        station_ids=estacoes_bacia,
        feature_contract=feature_contract,
        thresholds_calibration=thresholds_calibration,
        feature_names_map=feature_names_map,
        all_feature_order=ALL_VARS,
    )

    artifact_path = MODEL_DIR / "psa_risk_v1_station_contract_robust.joblib"
    joblib.dump(artifact, artifact_path)
    print(f"  Artefato joblib: {artifact_path}")

    # Metadata JSON
    metadata = {
        "modeling_family": artifact.modeling_family,
        "obj_version": artifact.obj_version,
        "bacias": {b: {"station_ids": s} for b, s in estacoes_bacia.items()},
        "forecast_horizons": HORIZONTES_FC,
        "risk_components": LABELS,
        "feature_contract": feature_contract,
        "artifact_path": str(artifact_path),
        "trained_on_cutoff": str(T_CUT),
        "model_selection": {f"{k[0]}|{k[1]}": {"variant": v, "model": m} for k, (v, m) in CONSERVATIVE_SELECTION.items()},
        "thresholds": {k: v for k, v in thresholds_map.items()},
        "train_metrics": train_metrics_log,
    }
    meta_path = OUT_DIR / "psa_risk_v1_station_contract_robust_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2, default=str)
    print(f"  Metadata JSON: {meta_path}")

    return artifact, artifact_path, meta_path


# ─── Smoke Test ──────────────────────────────────────────────────────────


def smoke_test(artifact_path: Path, meta_path: Path):
    print("\n" + "=" * 80)
    print("SMOKE TEST")
    print("=" * 80)

    # 1. Carrega joblib
    artifact = joblib.load(artifact_path)
    print(f"[OK] joblib carregado: {artifact_path}")
    print(f"  modeling_family: {artifact.modeling_family}")
    print(f"  obj_version: {artifact.obj_version}")
    print(f"  station_ids keys: {list(artifact.station_ids.keys())}")

    # 2. Verifica atributos obrigatorios
    required_attrs = [
        "predict",
        "predict_proba",
        "predict_severity",
        "risk_score",
        "compute_risk_components",
        "station_ids",
        "feature_contract",
        "modeling_family",
        "obj_version",
    ]
    for attr in required_attrs:
        assert hasattr(artifact, attr), f"FALTA atributo/metodo: {attr}"
        print(f"[OK] Atributo/metodo presente: {attr}")
    # risk_components e atributo (lista)
    assert hasattr(artifact, "risk_components") and isinstance(artifact.risk_components, list)
    print("[OK] Atributo presente: risk_components (lista)")

    # 3. Fixture simples por modelo individual
    for key in sorted(artifact.models.keys()):
        bacia, label = key.split("|", 1)
        cols = artifact.feature_names_map.get(key, [])
        if not cols:
            continue
        X = np.zeros((1, len(cols)), dtype=float)
        probs = artifact.predict_proba(bacia, X, label=label)
        preds = artifact.predict(bacia, X, label=label)
        print(f"\n  key={key} fixture zeros ({len(cols)} features):")
        print(f"    probs: {probs}")
        print(f"    preds: {preds}")
        assert isinstance(probs, dict) and label in probs
        assert isinstance(preds, dict) and label in preds
        p = probs[label]
        assert isinstance(p, (int, float)) and 0 <= p <= 1
        assert preds[label] in (0, 1)

    # 3b. Testa metodos agregados com all_feature_order
    n_all = len(artifact.all_feature_order)
    assert n_all > 0, "all_feature_order nao pode estar vazio"
    for bacia in artifact.station_ids.keys():
        X = np.zeros((1, n_all), dtype=float)
        probs = artifact.predict_proba(bacia, X)
        preds = artifact.predict(bacia, X)
        sev = artifact.predict_severity(bacia, X)
        score = artifact.risk_score(bacia, X)
        comps = artifact.compute_risk_components(bacia, X)

        print(f"\n  bacia={bacia} agregado (all {n_all} features):")
        print(f"    probs: {probs}")
        print(f"    preds: {preds}")
        print(f"    severity: {sev}")
        print(f"    score: {score}")
        print(f"    components: {comps}")

        # Verificacoes
        assert isinstance(probs, dict), "predict_proba deve retornar dict"
        assert isinstance(preds, dict), "predict deve retornar dict"
        assert isinstance(sev, int), "predict_severity deve retornar int"
        assert 0 <= score <= 1, "risk_score deve estar em [0,1]"
        assert isinstance(comps, dict), "compute_risk_components deve retornar dict"

        # Verifica shapes/ranges
        for lbl in artifact.risk_components:
            if lbl in probs:
                p = probs[lbl]
                assert isinstance(p, (int, float)), f"prob {lbl} deve ser scalar para n=1"
                assert 0 <= p <= 1, f"prob {lbl} deve estar em [0,1]"
            if lbl in preds:
                assert preds[lbl] in (0, 1), f"pred {lbl} deve ser 0 ou 1"

        # Testa multi-sample
        X2 = np.zeros((3, n_all), dtype=float)
        probs2 = artifact.predict_proba(bacia, X2)
        for lbl in probs2:
            p = probs2[lbl]
            if isinstance(p, list):
                assert len(p) == 3, f"predict_proba n=3 deve retornar lista de tamanho 3 para {lbl}"

    # 4. Roundtrip serializacao
    tmp_path = artifact_path.parent / "_tmp_roundtrip.joblib"
    joblib.dump(artifact, tmp_path)
    artifact2 = joblib.load(tmp_path)
    assert artifact2.modeling_family == artifact.modeling_family
    assert artifact2.obj_version == artifact.obj_version
    tmp_path.unlink()
    print("\n[OK] Serializacao roundtrip validada")

    # 5. Metadata JSON check
    with open(meta_path) as f:
        meta = json.load(f)
    assert meta["modeling_family"] == artifact.modeling_family
    assert meta["obj_version"] == artifact.obj_version
    assert "bacias" in meta
    assert "artifact_path" in meta
    assert "trained_on_cutoff" in meta
    print("[OK] Metadata JSON consistente")

    print("\n[PASS] Smoke test concluido com sucesso.")
    return True


if __name__ == "__main__":
    artifact, artifact_path, meta_path = main()
    smoke_test(artifact_path, meta_path)
