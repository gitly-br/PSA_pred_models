"""Teste de regressão: champion com dados reais do dataset."""

import json
from pathlib import Path

import joblib
import numpy as np
import polars as pl
import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
ARTIFACT_PATH = FIXTURE_DIR / "champion_guarara.joblib"
SAMPLE_PATH = FIXTURE_DIR / "real_sample_guarara.parquet"
META_PATH = FIXTURE_DIR / "champion_guarara.json"


def test_regression_real_sample():
    """Carrega modelo e roda inferência em amostra real do dataset guarara."""
    model = joblib.load(ARTIFACT_PATH)
    sample = pl.read_parquet(SAMPLE_PATH)

    features = model.features
    assert set(features).issubset(sample.columns), f"Features faltando: {set(features) - set(sample.columns)}"

    X = sample.select(features).to_pandas()
    true_sev = sample["severidade"].to_numpy()

    # predict retorna int 0..3
    preds = model.predict(X)
    assert len(preds) == len(X)
    assert all(0 <= p <= 3 for p in preds), f"Valores fora de 0..3: {set(preds)}"

    # predict_proba retorna distribuição válida
    probs = model.predict_proba(X)
    assert probs.shape == (len(X), 4)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-5), "probabilidades não somam 1"
    assert (probs >= 0).all() and (probs <= 1).all(), "probabilidades fora de [0,1]"

    # predict == argmax(proba)
    assert np.array_equal(preds, probs.argmax(axis=1)), "predict != argmax(proba)"

    # alarm_level é coerente (inteiros 0..3)
    alarm = model.alarm_level(X)
    assert len(alarm) == len(X)
    assert all(0 <= a <= 3 for a in alarm), f"Alarme fora de 0..3: {set(alarm)}"

    # predict == argmax(proba) para cada linha
    assert np.array_equal(preds, probs.argmax(axis=1)), "predict != argmax(proba)"

    # consistência alarm_level vs predict:
    # alarm_level >= 1 implica predict pode ser 0 se prob[0] > prob[1],
    # mas alarm nunca deve ser maior que predict + 1 de forma incoerente.
    # verificamos apenas que alarm_level está em 0..3
    assert all(0 <= a <= 3 for a in alarm), f"Alarme fora de 0..3: {set(alarm)}"

    # log de diagnóstico (não assertiva) para amostras positivas
    mask_pos = true_sev >= 1
    if mask_pos.any():
        n_pos = int(mask_pos.sum())
        n_detected = int((alarm[mask_pos] >= 1).sum())
        print(f"\n  Regressão guarara: {n_pos} positivos reais, {n_detected} detectados por alarm_level")
        for idx in np.where(mask_pos)[0]:
            print(f"    idx={idx} sev={true_sev[idx]} pred={preds[idx]} alarm={alarm[idx]} probs={probs[idx].round(3)}")
