from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
from sklearn.isotonic import IsotonicRegression

from .feature_assembler import FeatureAssembler
from .inference_writer import InferenceWriter
from .logger import configure_logging, get_logger
from .model_registry import get_active_models
from .artifact_loader import load_artifact
from .weather_repository import WeatherDataRepository


class DataAvailabilityError(RuntimeError):
    pass


def _apply_calibration(raw_proba: float, calibration: dict | None) -> float:
    """Apply isotonic calibration using saved thresholds via linear interpolation."""
    if not calibration or calibration.get("type") != "isotonic":
        return raw_proba
    X_thr = calibration.get("X_thresholds")
    y_thr = calibration.get("y_thresholds")
    if not X_thr or not y_thr or len(X_thr) < 2:
        return raw_proba
    
    # Manual linear interpolation (same as IsotonicRegression)
    X = np.array(X_thr)
    y = np.array(y_thr)
    
    if raw_proba <= X[0]:
        return float(y[0])
    if raw_proba >= X[-1]:
        return float(y[-1])
    
    # Find interval
    idx = np.searchsorted(X, raw_proba)
    if idx == 0:
        return float(y[0])
    
    # Linear interpolation
    x0, x1 = X[idx - 1], X[idx]
    y0, y1 = y[idx - 1], y[idx]
    if x1 == x0:
        return float(y0)
    return float(y0 + (raw_proba - x0) * (y1 - y0) / (x1 - x0))


def _display_probability(raw_proba: float, threshold: float | None, calibrated_proba: float | None = None) -> float:
    """
    Display probability for the UI.
    
    If calibrated_proba is provided, uses it directly (already calibrated).
    Otherwise falls back to the old threshold-based rescaling.
    """
    # Use calibrated probability if available
    if calibrated_proba is not None:
        return round(calibrated_proba * 100.0, 2)
    
    # Fallback to old threshold-based rescaling
    if raw_proba <= 0:
        return 0.0
    if threshold is None or threshold <= 0 or threshold >= 1:
        return round(raw_proba * 100.0, 2)
    if raw_proba <= threshold:
        return round(50.0 * (raw_proba / threshold), 2)
    return round(50.0 + 50.0 * ((raw_proba - threshold) / (1.0 - threshold)), 2)


async def run_floodcast(target_date: datetime | None = None, debug: bool = False) -> bool:
    configure_logging(debug=debug)
    logger = get_logger(__name__)
    run_date = target_date or datetime.utcnow()

    logger.info("Starting floodcast job for date: %s", run_date.strftime("%Y-%m-%d"))
    models_config = await get_active_models()

    inference_writer = InferenceWriter(target_date=target_date)

    repository = WeatherDataRepository()
    assembler = FeatureAssembler(repository)
    all_predictions = []
    region_errors: dict[str, list[str]] = {}
    try:
        for model_config in models_config:
            bacia = model_config["bacia"]
            model = load_artifact(model_config["artifact_uri"])
            features = model_config.get("features") or getattr(model, "features", [])
            historic_docs = await repository.fetch_historic_documents(bacia, run_date.date() - timedelta(days=90), run_date.date())
            forecast_docs = await repository.fetch_forecast_documents(bacia, run_date.date())
            missing_sources: list[str] = []
            if not historic_docs:
                missing_sources.append("historico")
            if not forecast_docs:
                missing_sources.append("forecast")
            if missing_sources:
                region_errors[bacia] = missing_sources
                continue

            feature_frame = await assembler.assemble(bacia, run_date)
            forecast_summary = await repository.summarize_forecast(bacia, run_date.date())
            X = feature_frame[features]
            predict_value = int(model.predict(X)[0])
            raw_proba = float(model.predict_proba(X)[0][predict_value])
            severity_value = int(model.alarm_level(X)[0]) if hasattr(model, "alarm_level") else predict_value
            threshold_map = model_config.get("thresholds") or {}
            threshold_value = threshold_map.get(str(max(severity_value, 1))) or threshold_map.get("1")
            
            # Apply calibration if available
            calibration = model_config.get("calibration")
            calibrated_proba = _apply_calibration(raw_proba, calibration)
            
            display_proba = _display_probability(raw_proba, float(threshold_value) if threshold_value is not None else None, calibrated_proba)
            all_predictions.append(
                {
                    "model_name": model_config["name"],
                    "region": model_config.get("region", bacia),
                    "subregion": model_config.get("subregion", bacia),
                    "bacia": bacia,
                    "day": run_date.date().isoformat(),
                    "predict": predict_value,
                    "severity": severity_value,
                    "raw_proba": raw_proba,
                    "calibrated_proba": calibrated_proba,
                    "proba": display_proba,
                    "threshold": float(threshold_value) if threshold_value is not None else None,
                    "shap_explanation": None,
                    "forecast_summary": forecast_summary,
                }
            )
    finally:
        await repository.close()

    if not all_predictions:
        raise DataAvailabilityError(f"Sem dados para inferencia: {region_errors}")

    await inference_writer.write_inference_object(all_predictions, region_errors=region_errors)
    logger.info("is done")
    return True
