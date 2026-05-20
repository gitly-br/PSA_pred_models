from __future__ import annotations

from datetime import datetime, timedelta
import inspect

import numpy as np

from .logger import configure_logging, get_logger
from .model_registry import get_active_models
from .artifact_loader import load_artifact
from .minio_weather_fallback import WeatherDataUnavailableError

try:
    from .inference_writer import InferenceWriter
except ModuleNotFoundError:
    InferenceWriter = None

try:
    from .weather_repository import WeatherDataRepository
except ModuleNotFoundError:
    WeatherDataRepository = None


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


def _call_model_method(model, method_name: str, bacia: str, X):
    method = getattr(model, method_name)
    params = list(inspect.signature(method).parameters)
    if params and params[0] == "bacia":
        return method(bacia, X)
    return method(X)


def _first_scalar(value) -> float:
    array = np.asarray(value)
    if array.ndim == 0:
        return float(array)
    return float(array.ravel()[0])


def _align_features(frame, features: list[str]):
    if not features:
        return frame
    return frame.reindex(columns=features, fill_value=0.0).fillna(0.0)


async def run_floodcast(target_date: datetime | None = None, debug: bool = False) -> bool:
    configure_logging(debug=debug)
    logger = get_logger(__name__)
    run_date = target_date or datetime.utcnow()
    from .feature_assembler import FeatureAssembler

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
            station_ids = model_config.get("station_ids") or getattr(model, "station_ids", [])
            features = model_config.get("features") or getattr(model, "features", None) or getattr(model, "all_feature_order", [])
            historic_docs = []
            forecast_docs = []
            missing_sources: list[str] = []
            try:
                historic_docs = await repository.fetch_historic_documents(bacia, run_date.date() - timedelta(days=90), run_date.date())
            except WeatherDataUnavailableError:
                missing_sources.append("historico")
            if not historic_docs and "historico" not in missing_sources:
                missing_sources.append("historico")
            try:
                forecast_docs = await repository.fetch_forecast_documents(bacia, run_date.date())
            except WeatherDataUnavailableError:
                missing_sources.append("forecast")
            if not forecast_docs and "forecast" not in missing_sources:
                missing_sources.append("forecast")
            if missing_sources:
                region_errors[bacia] = missing_sources
                continue

            feature_frame = await assembler.assemble(
                bacia,
                run_date,
                station_ids=station_ids,
                documents=historic_docs,
            )
            forecast_summary = repository.summarize_forecast_documents(forecast_docs)
            X = _align_features(feature_frame, features)
            if hasattr(model, "predict_severity") and inspect.signature(getattr(model, "predict_severity")).parameters:
                predict_value = int(_first_scalar(_call_model_method(model, "predict_severity", bacia, X)))
            else:
                predict_value = int(_first_scalar(_call_model_method(model, "predict", bacia, X)))

            if hasattr(model, "alarm_level"):
                severity_value = int(_first_scalar(_call_model_method(model, "alarm_level", bacia, X)))
            else:
                severity_value = predict_value

            if hasattr(model, "risk_score"):
                raw_proba = float(_first_scalar(_call_model_method(model, "risk_score", bacia, X)))
            else:
                proba_output = _call_model_method(model, "predict_proba", bacia, X)
                raw_proba = float(np.asarray(proba_output)[0][predict_value])
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
