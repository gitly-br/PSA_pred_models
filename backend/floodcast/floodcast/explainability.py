"""
SHAP explainability module.

Loads SHAP explainer artifacts and computes local explanations
for a single prediction row (Polars DataFrame).

The module isolates any data-format conversion needed by SHAP
(currently numpy). No pandas is used directly.
"""

from __future__ import annotations

import numpy as np
import polars as pl

from .logger import get_logger

logger = get_logger(__name__)


def load_explainer(explainer_uri: str):
    """Load a SHAP explainer from a file:// or minio:// URI.

    Delegates to artifact_loader.load_artifact (handles joblib artifacts
    from local path or MinIO).
    """
    from .artifact_loader import load_artifact

    return load_artifact(explainer_uri)


def _extract_shap_array(shap_out, predicted_class: int | None = None) -> np.ndarray:
    """Normalise the output of explainer.shap_values / explainer() to a 1D array.

    Handles:
      - Multi-class: list of (n_samples, n_features) arrays
      - Single-output: (n_samples, n_features) array
      - shap.Explanation object (newer API)
    """
    # shap.Explanation object (newer shap API)
    if hasattr(shap_out, "values"):
        shap_out = shap_out.values

    if isinstance(shap_out, list):
        # Multi-class: pick the requested class or class 0
        idx = predicted_class if predicted_class is not None else 0
        if idx >= len(shap_out):
            idx = 0
        arr = np.asarray(shap_out[idx], dtype=np.float64)
    else:
        arr = np.asarray(shap_out, dtype=np.float64)

    # Flatten to 1-D (single sample)
    if arr.ndim == 2:
        arr = arr[0]
    elif arr.ndim > 2:
        arr = arr.reshape(-1)

    return arr


def compute_shap_explanation(
    explainer,
    X: pl.DataFrame,
    features: list[str],
    predicted_class: int | None = None,
) -> list[tuple[str, float]]:
    """Compute SHAP explanation for a single prediction.

    Args:
        explainer: A SHAP explainer with ``shap_values`` method or callable.
        X: Feature frame (Polars) – a single row whose columns match
           *features*.
        features: Ordered feature names.
        predicted_class: If the model is multi-class, the predicted
           class index used to select the relevant SHAP array.

    Returns:
        List of ``(feature_name, shap_value)`` tuples sorted by SHAP
        value descending (most positive first), matching the legacy
        contract consumed by ``InferenceWriter._get_explanation``.
    """
    # Convert to NumPy – SHAP TreeExplainer accepts ndarray / DataFrame.
    # Polars directly is not guaranteed, so we isolate the conversion here.
    X_np = X.select(features).to_numpy().astype(np.float64)

    if hasattr(explainer, "shap_values"):
        shap_out = explainer.shap_values(X_np)
    elif callable(explainer):
        shap_out = explainer(X_np)
    else:
        raise TypeError(
            f"Explainer of type {type(explainer)} has no shap_values method "
            f"and is not callable"
        )

    shap_array = _extract_shap_array(shap_out, predicted_class=predicted_class)

    if len(shap_array) != len(features):
        logger.warning(
            "SHAP array length %d != features length %d – truncating/padding",
            len(shap_array),
            len(features),
        )
        # Truncate or pad to match feature count
        if len(shap_array) < len(features):
            shap_array = np.pad(shap_array, (0, len(features) - len(shap_array)))
        else:
            shap_array = shap_array[: len(features)]

    values = [float(v) for v in shap_array]
    paired = list(zip(features, values))
    # Sort by SHAP value descending (most positive contributor first)
    paired.sort(key=lambda x: x[1], reverse=True)

    return paired
