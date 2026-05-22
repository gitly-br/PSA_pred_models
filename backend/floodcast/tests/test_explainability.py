"""Unit tests for the SHAP explainability module."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest

from floodcast.explainability import (
    _extract_shap_array,
    compute_shap_explanation,
    load_explainer,
)


# ---------------------------------------------------------------------------
# Fake explainers for testing
# ---------------------------------------------------------------------------

class _FakeTreeExplainerMultiClass:
    """Simulates shap.TreeExplainer for a 4-class model."""
    def __init__(self, values=None):
        self._values = values

    def shap_values(self, X):
        n_samples, n_features = X.shape
        if self._values is not None:
            return [
                np.full((n_samples, n_features), v, dtype=np.float64)
                for v in self._values
            ]
        # Default: 4 classes, each with simple SHAP values
        return [
            np.array([[0.1, -0.2, 0.3, 0.0]], dtype=np.float64),  # class 0
            np.array([[-0.1, 0.4, -0.1, 0.2]], dtype=np.float64),  # class 1
            np.array([[0.05, 0.1, 0.15, -0.05]], dtype=np.float64),  # class 2
            np.array([[0.0, 0.0, 0.0, 0.0]], dtype=np.float64),  # class 3
        ]


class _FakeTreeExplainerBinary:
    """Simulates shap.TreeExplainer for a binary model."""

    def shap_values(self, X):
        n_samples, n_features = X.shape
        return np.array([[0.5, -0.3, 0.2, 0.1]], dtype=np.float64)


class _FakeCallableExplainer:
    """Simulates newer shap.Explainer (callable, returns Explanation)."""

    class _Explanation:
        def __init__(self, values):
            self.values = values

    def __call__(self, X):
        n_samples, n_features = X.shape
        return self._Explanation(
            np.array([[0.2, -0.1, 0.4, 0.0]], dtype=np.float64)
        )


class _FakeExplainerNoShapValues:
    """Explainer without shap_values method and not callable."""
    pass


# ---------------------------------------------------------------------------
# Tests for _extract_shap_array
# ---------------------------------------------------------------------------

def test_extract_multi_class_list_default_class_zero():
    arr = _extract_shap_array([
        np.array([[0.1, -0.2]], dtype=np.float64),
        np.array([[-0.3, 0.4]], dtype=np.float64),
    ])
    assert arr.shape == (2,)
    assert arr.tolist() == [0.1, -0.2]


def test_extract_multi_class_list_specific_class():
    arr = _extract_shap_array([
        np.array([[0.1, -0.2]], dtype=np.float64),
        np.array([[-0.3, 0.4]], dtype=np.float64),
    ], predicted_class=1)
    assert arr.shape == (2,)
    assert arr.tolist() == [-0.3, 0.4]


def test_extract_multi_class_list_predicted_out_of_bounds():
    arr = _extract_shap_array([
        np.array([[1.0, 2.0]], dtype=np.float64),
    ], predicted_class=5)
    assert arr.tolist() == [1.0, 2.0]


def test_extract_single_output_2d():
    arr = _extract_shap_array(np.array([[0.5, -0.3, 0.2]], dtype=np.float64))
    assert arr.shape == (3,)
    assert arr.tolist() == [0.5, -0.3, 0.2]


def test_extract_single_output_1d():
    arr = _extract_shap_array(np.array([0.7, -0.1, 0.4], dtype=np.float64))
    assert arr.shape == (3,)
    assert arr.tolist() == [0.7, -0.1, 0.4]


def test_extract_explanation_object():
    class Expl:
        values = np.array([[0.1, 0.2, 0.3]], dtype=np.float64)
    arr = _extract_shap_array(Expl())
    assert arr.shape == (3,)
    assert arr.tolist() == [0.1, 0.2, 0.3]


# ---------------------------------------------------------------------------
# Tests for compute_shap_explanation
# ---------------------------------------------------------------------------

FEATURES = ["api_070", "api_085", "api_095", "acum_7d"]


def _make_X(values=None):
    if values is None:
        values = [10.0, 25.0, 5.0, 40.0]
    return pl.DataFrame({
        name: [v] for name, v in zip(FEATURES, values)
    })


def test_compute_shap_returns_sorted_tuples():
    """SHAP values must be sorted descending by value."""
    explainer = _FakeTreeExplainerMultiClass()
    X = _make_X()
    result = compute_shap_explanation(explainer, X, FEATURES, predicted_class=1)
    assert len(result) == 4
    assert isinstance(result, list)
    assert all(isinstance(t, tuple) and len(t) == 2 for t in result)
    # Check sorting: values must be descending
    values = [v for _, v in result]
    assert values == sorted(values, reverse=True), f"not sorted: {values}"
    # Class 1: [-0.1, 0.4, -0.1, 0.2] -> sorted: 0.4, 0.2, -0.1, -0.1
    assert result[0] == ("api_085", 0.4)
    assert result[1] == ("acum_7d", 0.2)


def test_compute_shap_binary_explainer():
    explainer = _FakeTreeExplainerBinary()
    X = _make_X()
    result = compute_shap_explanation(explainer, X, FEATURES)
    assert len(result) == 4
    # Binary explainer returns [[0.5, -0.3, 0.2, 0.1]]
    # Sorted: 0.5, 0.2, 0.1, -0.3
    assert result[0] == ("api_070", 0.5)
    assert result[1] == ("api_095", 0.2)
    assert result[2] == ("acum_7d", 0.1)
    assert result[3] == ("api_085", -0.3)


def test_compute_shap_callable_explainer():
    explainer = _FakeCallableExplainer()
    X = _make_X()
    result = compute_shap_explanation(explainer, X, FEATURES)
    assert len(result) == 4
    assert result[0] == ("api_095", 0.4)


def test_compute_shap_handles_length_mismatch():
    """When SHAP returns fewer values than features, we pad with zeros."""
    class _ShortExplainer:
        def shap_values(self, X):
            return np.array([[0.5, 0.3]], dtype=np.float64)

    explainer = _ShortExplainer()
    X = _make_X()
    result = compute_shap_explanation(explainer, X, FEATURES)
    assert len(result) == 4
    # First two come from SHAP, last two are padded (0.0)
    assert result[0] == ("api_070", 0.5)
    assert result[1] == ("api_085", 0.3)
    assert result[2] == ("api_095", 0.0)
    assert result[3] == ("acum_7d", 0.0)


def test_compute_shap_no_shap_values_no_callable_raises():
    explainer = _FakeExplainerNoShapValues()
    X = _make_X()
    with pytest.raises(TypeError, match="no shap_values method"):
        compute_shap_explanation(explainer, X, FEATURES)


def test_compute_shap_uses_predicted_class():
    """When predicted_class is given, the correct class array is selected."""
    explainer = _FakeTreeExplainerMultiClass(values=[10.0, 20.0, 30.0, 40.0])
    X = _make_X()
    # predicted_class=2 → class 2 SHAP array (all 30.0)
    result = compute_shap_explanation(explainer, X, FEATURES, predicted_class=2)
    assert all(v == 30.0 for _, v in result)

    # predicted_class=0
    result = compute_shap_explanation(explainer, X, FEATURES, predicted_class=0)
    assert all(v == 10.0 for _, v in result)


# ---------------------------------------------------------------------------
# Tests for load_explainer
# ---------------------------------------------------------------------------

def test_load_explainer_delegates_to_load_artifact(monkeypatch):
    """load_explainer must delegate to artifact_loader.load_artifact."""
    calls = []

    def fake_load(uri):
        calls.append(uri)
        return "fake_explainer"

    monkeypatch.setattr(
        "floodcast.artifact_loader.load_artifact", fake_load
    )

    result = load_explainer("file:///tmp/explainer.joblib")
    assert result == "fake_explainer"
    assert calls == ["file:///tmp/explainer.joblib"]

    result = load_explainer("minio://psa/models/explainer.joblib")
    assert result == "fake_explainer"
    assert calls == [
        "file:///tmp/explainer.joblib",
        "minio://psa/models/explainer.joblib",
    ]
