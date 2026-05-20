"""
Prova de contrato: candidato combinador_mean + piecewise calibrado
pode virar artefato servível no backend floodcast?

Objetivo:
  1. Encapsular o pipeline em uma classe serializável (joblib).
  2. Verificar se a interface exigida pelo runner existe.
  3. Mapear gaps de features entre o que o candidato precisa e o que o
     FeatureAssembler/WeatherRepository montam hoje.
  4. Emitir evidências objetivas (sem alterar backend/champions).
"""
from __future__ import annotations

import json
import tempfile
import warnings
from pathlib import Path

import joblib
import numpy as np
import polars as pl

warnings.filterwarnings("ignore")

# ─── Paths ───────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
# Script está em PSA/notebooks/scripts/experiments/
WORKDIR = SCRIPT_DIR.parents[2]  # sobe para PSA/notebooks
RESULTS_DIR = WORKDIR / "dados" / "results"
# Fallback se __file__ não resolver corretamente
if not RESULTS_DIR.exists():
    WORKDIR = Path.cwd() / "notebooks"
    RESULTS_DIR = WORKDIR / "dados" / "results"

PARAMS_JSON = RESULTS_DIR / "calibracao_scores_serving_params.json"
COMB_PARQUET = RESULTS_DIR / "combinador_risco_meteorologico.parquet"
CAL_PARQUET = RESULTS_DIR / "calibracao_scores_serving.parquet"

# ─── Constantes do backend (copiadas para não importar) ──────────────────
FEATURES_V4 = (
    ["api_070", "api_085", "api_095"]
    + [f"acc_6h_lag_{i}" for i in range(1, 13)]
    + ["max_day_lag1", "max_day_lag2", "max_day_lag3"]
    + ["mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1"]
    + ["pico_1h_lag1", "horas_intensas_lag1"]
    + ["acum_7d", "acum_30d"]
    + ["mes_sin", "mes_cos"]
)

# ─── Features que o candidato realmente usa (auditado nos scripts) ───────
FEATURES_CANDIDATO = set(FEATURES_V4) | {
    # derivadas V2 usadas pelo classificador cauda e especialistas
    "acc_24h_lag1",
    "acc_48h_lag1",
    "razao_7d_30d",
    "pico_vs_media",
    "max_vs_media",
    "tendencia_chuva",
    "max_dia_rel",
    "chuva_persistente",
    "n_chovendo_lag2",
    "n_chovendo_lag3",
    "inter_max_acum7d",
    "inter_max_std",
    # forecast detector H48 (OpenWeather forecast history)
    "fc_rain_sum_h24",
    "fc_rain_max_h24",
    "fc_prob_mean_h24",
    "fc_prob_max_h24",
    "fc_temp_mean_h24",
    "fc_humidity_mean_h24",
    "fc_wind_max_h24",
    "fc_rain_sum_h48",
    "fc_rain_max_h48",
    "fc_prob_mean_h48",
    "fc_prob_max_h48",
    "fc_temp_mean_h48",
    "fc_humidity_mean_h48",
    "fc_wind_max_h48",
    # OpenMeteo multipoint (lag1)
    "om_precip_sum_lag1",
    "om_temp_max_lag1",
    "om_temp_min_lag1",
    "om_temp_mean_lag1",
    "om_humidity_max_lag1",
    "om_pressure_mean_lag1",
    "om_wind_max_lag1",
    # similaridade de perfis (requer KMeans + OpenMeteo futuro)
    "score_similaridade",  # não é feature bruta; é output de outro modelo
}


class ServingRiskScoreModel:
    """
    Wrapper experimental para servir o combinador_mean calibrado.

    Interface mínima exigida pelo backend::
        model.predict(X)        -> array int (0..3)
        model.predict_proba(X)  -> array float (n, 4)  [soma 1 por linha]
        model.alarm_level(X)    -> array int (0..3)
        model.features          -> list[str]
        model.bacia             -> str
        model.modeling_family   -> str
        model.obj_version       -> str

    Atributos extras propostos para shadow mode::
        model.risk_score(X)     -> array float [0,1]  (score calibrado)
        model.risk_components(X)-> dict[str, array]
        model.profile(X)        -> array str (perfil dominante)
    """

    def __init__(
        self,
        bacia: str,
        piecewise_params: dict,
        norm_stats: dict,
        modeling_family: str = "psa_combinador_v1",
        obj_version: str = "0.1-exp",
    ):
        self.bacia = bacia
        self.modeling_family = modeling_family
        self.obj_version = obj_version
        self.piecewise_params = piecewise_params
        self.norm_stats = norm_stats
        # Features que o backend V4 consegue montar hoje (subset do candidato)
        self.features = list(FEATURES_V4)

    # ── Interface obrigatória do backend ─────────────────────────────────

    def predict(self, X):
        """Mapeia score calibrado para classes 0..3 (ordinal fake)."""
        rs = self.risk_score(X)
        # thresholds operacionais do dashboard
        return np.where(
            rs < 0.30, 0, np.where(rs < 0.70, 1, np.where(rs < 0.90, 2, 3))
        )

    def predict_proba(self, X):
        """
        Retorna matriz (n,4) compatível com ChampionOrdinalModel.
        Distribuição heurística centrada na classe predita.
        """
        rs = self.risk_score(X)
        n = len(rs)
        probs = np.zeros((n, 4))
        # heurística: classe 0 = 1-rs; classe 1 = rs * 0.6; classe 2 = rs*0.3; classe 3 = rs*0.1
        probs[:, 0] = np.clip(1.0 - rs, 0.0, 1.0)
        probs[:, 1] = np.clip(rs * 0.6, 0.0, 1.0)
        probs[:, 2] = np.clip(rs * 0.25, 0.0, 1.0)
        probs[:, 3] = np.clip(rs * 0.15, 0.0, 1.0)
        probs = np.clip(probs, 1e-9, 1.0)
        probs = probs / probs.sum(axis=1, keepdims=True)
        return probs

    def alarm_level(self, X):
        """Alias semântico para predict (o backend usa alarm_level se existir)."""
        return self.predict(X)

    # ── Interface proposta para shadow mode ───────────────────────────────

    def risk_score(self, X):
        """
        Score calibrado [0,1].
        Como não temos os 6 componentes treinados aqui, usamos
        o piecewise apenas como demonstração de contrato.
        """
        # Placeholder: usa a primeira coluna numérica como proxy do score bruto
        if hasattr(X, "values"):
            raw = X.iloc[:, 0].values.astype(float)
        else:
            raw = np.asarray(X)[:, 0].astype(float)
        # aplica piecewise linear simples (demonstração)
        return self._apply_piecewise(raw)

    def risk_components(self, X):
        """Retorna dict com os 6 scores normalizados (placeholder)."""
        n = len(X) if hasattr(X, "__len__") else 1
        return {
            "fc_detector": np.zeros(n),
            "saturacao": np.zeros(n),
            "pancada": np.zeros(n),
            "prolongada": np.zeros(n),
            "cauda": np.zeros(n),
            "similaridade": np.zeros(n),
        }

    def profile(self, X):
        """Perfil dominante (placeholder)."""
        n = len(X) if hasattr(X, "__len__") else 1
        return np.full(n, "unknown", dtype=object)

    # ── Interno ───────────────────────────────────────────────────────────

    def _apply_piecewise(self, raw):
        pp = self.piecewise_params
        n_bins = pp.get("n_bins", 5)
        mn, mx = float(np.nanmin(raw)), float(np.nanmax(raw))
        if mx <= mn:
            return np.full_like(raw, 0.5)
        edges = np.linspace(mn, mx, n_bins + 1)
        centers = (edges[:-1] + edges[1:]) / 2.0
        targets = np.linspace(0.0, 1.0, n_bins)
        out = np.zeros_like(raw)
        for i in range(n_bins):
            mask = (raw >= edges[i]) & (raw < edges[i + 1])
            if i == n_bins - 1:
                mask = (raw >= edges[i]) & (raw <= edges[i + 1])
            out[mask] = targets[i]
        return np.clip(out, 0.0, 1.0)


def audit_feature_gap() -> dict:
    """Compara features do candidato com features montadas pelo backend hoje."""
    backend_features = set(FEATURES_V4)
    candidato_features = FEATURES_CANDIDATO
    disponiveis = candidato_features & backend_features
    faltantes = candidato_features - backend_features
    return {
        "backend_n": len(backend_features),
        "candidato_n": len(candidato_features),
        "disponiveis_n": len(disponiveis),
        "faltantes_n": len(faltantes),
        "disponiveis": sorted(disponiveis),
        "faltantes": sorted(faltantes),
    }


def test_serializacao() -> dict:
    """Testa se o wrapper pode ser serializado em joblib e recuperado."""
    model = ServingRiskScoreModel(
        bacia="guarara",
        piecewise_params={"n_bins": 5},
        norm_stats={},
    )
    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
        path = f.name
    joblib.dump(model, path)
    loaded = joblib.load(path)

    # sanity check interface
    checks = {
        "has_predict": hasattr(loaded, "predict"),
        "has_predict_proba": hasattr(loaded, "predict_proba"),
        "has_alarm_level": hasattr(loaded, "alarm_level"),
        "has_features": hasattr(loaded, "features"),
        "has_bacia": hasattr(loaded, "bacia"),
        "has_modeling_family": hasattr(loaded, "modeling_family"),
        "has_obj_version": hasattr(loaded, "obj_version"),
        "has_risk_score": hasattr(loaded, "risk_score"),
        "has_risk_components": hasattr(loaded, "risk_components"),
        "has_profile": hasattr(loaded, "profile"),
    }

    # shape check
    X_dummy = np.zeros((3, len(FEATURES_V4)))
    preds = loaded.predict(X_dummy)
    probs = loaded.predict_proba(X_dummy)
    alarm = loaded.alarm_level(X_dummy)
    rs = loaded.risk_score(X_dummy)
    comps = loaded.risk_components(X_dummy)
    prof = loaded.profile(X_dummy)

    checks["predict_shape_ok"] = preds.shape == (3,)
    checks["predict_range_ok"] = all(0 <= p <= 3 for p in preds)
    checks["proba_shape_ok"] = probs.shape == (3, 4)
    checks["proba_sum_ok"] = np.allclose(probs.sum(axis=1), 1.0, atol=1e-5)
    checks["alarm_shape_ok"] = alarm.shape == (3,)
    checks["risk_score_range_ok"] = (rs.min() >= 0.0) and (rs.max() <= 1.0)
    checks["risk_components_keys_ok"] = set(comps.keys()) == {
        "fc_detector", "saturacao", "pancada", "prolongada", "cauda", "similaridade"
    }
    checks["profile_shape_ok"] = prof.shape == (3,)

    Path(path).unlink(missing_ok=True)
    return checks


def main():
    print("=" * 80)
    print("SERVING VALIDATOR — Combinador Mean + Piecewise Calibrado")
    print("=" * 80)

    # 1. Gap de features
    print("\n[1] AUDITORIA DE FEATURES")
    gap = audit_feature_gap()
    print(f"  Backend features hoje : {gap['backend_n']}")
    print(f"  Candidato requer      : {gap['candidato_n']}")
    print(f"  Disponíveis hoje      : {gap['disponiveis_n']}")
    print(f"  FALTANTES             : {gap['faltantes_n']}")
    print("\n  Features faltantes no backend:")
    for f in gap["faltantes"]:
        print(f"    - {f}")

    # 2. Serialização
    print("\n[2] TESTE DE SERIALIZAÇÃO (joblib)")
    checks = test_serializacao()
    ok = sum(1 for v in checks.values() if v is True)
    total = len(checks)
    print(f"  Checks passaram: {ok}/{total}")
    for k, v in checks.items():
        status = "OK" if v else "FAIL"
        print(f"    [{status}] {k}")

    # 3. Dados do candidato
    print("\n[3] INSPEÇÃO DOS DADOS GERADOS")
    df_comb = pl.read_parquet(COMB_PARQUET)
    df_cal = pl.read_parquet(CAL_PARQUET)
    print(f"  combinador.parquet   : {df_comb.shape} rows")
    print(f"  calibracao.parquet   : {df_cal.shape} rows")
    if "risk_score_raw_mean_serving" in df_cal.columns:
        s = df_cal["risk_score_raw_mean_serving"].to_numpy()
        print(f"  Score calibrado range: [{s.min():.4f}, {s.max():.4f}]")
        print(f"  Score calibrado mean : {s.mean():.4f}")
    else:
        print("  Coluna risk_score_raw_mean_serving NÃO encontrada!")

    # 4. Parâmetros JSON
    print("\n[4] PARÂMETROS DO CALIBRADOR")
    with open(PARAMS_JSON) as f:
        params = json.load(f)
    print(f"  Calibrador recomendado: {params.get('calibrador_recomendado')}")
    print(f"  Candidato primário    : {params.get('candidato_primario')}")

    # 5. Veredito resumido
    print("\n" + "=" * 80)
    print("RESUMO OBJETIVO")
    print("=" * 80)
    print(f"  - Interface estável serializável: {'SIM' if ok == total else 'PARCIAL'}")
    print(f"  - Features disponíveis no backend: {gap['disponiveis_n']}/{gap['candidato_n']}")
    print(f"  - Features faltantes críticas   : {gap['faltantes_n']}")
    print(f"  - Gap inclui forecast/OpenMeteo : SIM (dados não montados hoje)")
    print("=" * 80)


if __name__ == "__main__":
    main()
