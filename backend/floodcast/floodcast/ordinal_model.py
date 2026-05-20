"""
Ordinal severity model for PSA floodcast.

Encapsulates 3 binary classifiers (≥1, ≥2, ≥3) with thresholds
optimized for F1 via time-series CV.
"""

import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin


class ChampionOrdinalModel(BaseEstimator, ClassifierMixin):
    """
    Modelo ordinal de severidade com 3 classificadores binários em cascata.

    - m1: prob(severidade >= 1)
    - m2: prob(severidade >= 2)
    - m3: prob(severidade >= 3)

    predict() retorna o nível ordinal (0..3).
    predict_proba() retorna matriz (n, 4) de probabilidades para cada classe.
    """

    def __init__(self, pipelines: dict, thresholds: dict, features: list,
                 bacia: str, modeling_family: str, obj_version: str,
                 metadata: dict | None = None):
        self.pipelines = pipelines          # {1: clf, 2: clf, 3: clf}
        self.thresholds = thresholds      # {1: thr, 2: thr, 3: thr}
        self.features = features
        self.bacia = bacia
        self.modeling_family = modeling_family
        self.obj_version = obj_version
        self.metadata = metadata or {}

    def _prob_matrix(self, X):
        """Retorna (n_samples, 4) com P(sev=k)."""
        n = len(X)
        probs = np.zeros((n, 4))
        p_ge = {}
        for k in [1, 2, 3]:
            p_ge[k] = self.pipelines[k].predict_proba(X)[:, 1]
        probs[:, 0] = 1.0 - p_ge[1]
        probs[:, 1] = p_ge[1] - p_ge[2]
        probs[:, 2] = p_ge[2] - p_ge[3]
        probs[:, 3] = p_ge[3]
        probs = np.clip(probs, 0.0, 1.0)
        probs = probs / probs.sum(axis=1, keepdims=True)
        return probs

    def predict(self, X):
        probs = self._prob_matrix(X)
        return probs.argmax(axis=1)

    def predict_proba(self, X):
        return self._prob_matrix(X)

    def predict_severity(self, X):
        """Alias para predict() com nome semântico."""
        return self.predict(X)

    def alarm_level(self, X):
        """Retorna nível de alarme (maior k com prob >= thr)."""
        alarme = np.zeros(len(X), dtype=int)
        for k in [1, 2, 3]:
            p = self.pipelines[k].predict_proba(X)[:, 1]
            alarme = np.where(p >= self.thresholds[k], k, alarme)
        return alarme

    def risk_score(self, X):
        """Retorna probabilidade de evento P(severidade >= 1)."""
        probs = self._prob_matrix(X)
        # P(sev >= 1) = 1 - P(sev = 0)
        return 1.0 - probs[:, 0]
