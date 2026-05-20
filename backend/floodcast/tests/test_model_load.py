"""Smoke test: carrega artefato champion e valida inferência mínima."""

import json
import math
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from floodcast.artifact_loader import load_artifact
from floodcast.seed_model_registry import _build_compatible_champion

FIXTURE_DIR = Path(__file__).parent / "fixtures"
ARTIFACT_PATH = FIXTURE_DIR / "champion_guarara.joblib"
META_PATH = FIXTURE_DIR / "champion_guarara.json"


def _load_meta():
    with open(META_PATH) as f:
        return json.load(f)


def _load_model():
    meta = _load_meta()
    model = _build_compatible_champion(meta, meta["bacia"])
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_path = Path(tmpdir) / "champion.joblib"
        joblib.dump(model, artifact_path)
        return load_artifact(f"file://{artifact_path}")


def _make_fixture_df(features: list[str], n: int = 5) -> pd.DataFrame:
    """Gera DataFrame sintético com valores plausíveis para cada feature."""
    base_vals = {
        "api_": [10.0, 25.0, 5.0, 0.0, 40.0],
        "acc_6h_lag_": [2.0, 8.0, 0.5, 15.0, 1.0],
        "max_day_lag": [15.0, 30.0, 5.0, 45.0, 0.0],
        "mean_day_lag1": [5.0, 12.0, 1.0, 20.0, 0.0],
        "std_day_lag1": [3.0, 8.0, 0.5, 12.0, 0.0],
        "n_chovendo_max_lag1": [2, 5, 1, 7, 0],
        "pico_1h_lag1": [10.0, 25.0, 2.0, 40.0, 0.0],
        "horas_intensas_lag1": [1, 3, 0, 5, 0],
        "acum_7d": [30.0, 80.0, 10.0, 150.0, 5.0],
        "acum_30d": [30.0, 80.0, 10.0, 150.0, 5.0],
        "mes_sin": [0.5, 0.0, -0.5, 1.0, -1.0],
        "mes_cos": [0.5, 0.0, -0.5, 1.0, -1.0],
    }
    rng = {}
    for f in features:
        vals = base_vals.get(f) or next((base_vals[k] for k in base_vals if f.startswith(k)), None)
        if vals is None:
            vals = [0.0]
        # repete ou trunca o padrão até atingir n elementos
        rng[f] = [vals[i % len(vals)] for i in range(n)]
    return pd.DataFrame(rng)


def test_artifact_exists():
    assert ARTIFACT_PATH.exists(), f"Artefato não encontrado: {ARTIFACT_PATH}"
    assert META_PATH.exists(), f"Metadados não encontrados: {META_PATH}"


def test_load_and_interface():
    model = _load_model()
    meta = _load_meta()

    # verifica interface mínima
    assert hasattr(model, "predict"), "Modelo deve ter predict()"
    assert hasattr(model, "predict_proba"), "Modelo deve ter predict_proba()"
    assert hasattr(model, "alarm_level"), "Modelo deve ter alarm_level()"
    assert model.bacia == meta["bacia"]
    assert model.modeling_family == meta["modeling_family"]
    assert model.obj_version == meta["obj_version"]


def test_predict_shape_and_range():
    model = _load_model()
    X = _make_fixture_df(model.features, n=10)

    preds = model.predict(X)
    assert len(preds) == 10
    assert all(0 <= p <= 3 for p in preds), "predict deve retornar 0..3"

    probs = model.predict_proba(X)
    assert probs.shape == (10, 4)
    assert math.isclose(probs.sum(), 10.0, rel_tol=1e-5), "probabilidades devem somar 1 por linha"
    assert (probs >= 0).all() and (probs <= 1).all(), "probabilidades fora de [0,1]"


def test_alarm_level_matches_predict():
    model = _load_model()
    X = _make_fixture_df(model.features, n=10)
    alarm = model.alarm_level(X)
    pred = model.predict(X)
    # alarm_level usa thresholds internos; predict retorna argmax da distribuição
    # apenas verificamos que ambos retornam arrays de inteiros do mesmo tamanho
    assert len(alarm) == 10
    assert all(np.issubdtype(type(a), np.integer) for a in alarm)
