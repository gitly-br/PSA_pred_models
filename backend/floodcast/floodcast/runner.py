from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import inspect
import time

import numpy as np
import polars as pl

from .logger import configure_logging, get_logger
from .model_registry import get_active_models
from .artifact_loader import load_artifact
from .explainability import compute_shap_explanation
from .minio_weather_fallback import WeatherDataUnavailableError
from .prediction_explainer import generate_short_explanation

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
    Probability exposed by the API for the UI.

    The public contract is 0..1. Formatting as percent belongs to the frontend.
    Thresholds shape the apparent display scale above the alarm cutoff.
    """
    probability = calibrated_proba if calibrated_proba is not None else raw_proba
    probability = float(np.clip(probability, 0.0, 1.0))
    if threshold is None:
        return round(probability, 4)

    threshold = float(np.clip(threshold, 0.1, 1.0))
    if probability <= threshold:
        apparent = 0.5 * (probability / threshold)
        return round(float(np.clip(apparent, 0.0, 1.0)), 4)

    upper_span = 1.0 - threshold
    if upper_span <= 0.0:
        return 1.0

    normalized = (probability - threshold) / upper_span
    apparent = 0.5 + 0.5 * (1.0 - (1.0 - normalized) ** 2)
    return round(float(np.clip(apparent, 0.0, 1.0)), 4)


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
    available = set(frame.columns)
    cols = [pl.col(name) if name in available else pl.lit(0.0).alias(name) for name in features]
    return frame.select(cols).with_columns(pl.all().fill_null(0.0))


async def run_floodcast(target_date: datetime | None = None, debug: bool = False) -> bool:
    configure_logging(debug=debug)
    logger = get_logger(__name__)
    run_date = target_date or datetime.utcnow()
    from .feature_assembler import FeatureAssembler, REQUIRED_FIELDS

    t_start_total = time.perf_counter()
    logger.info("Starting floodcast job for date: %s", run_date.strftime("%Y-%m-%d"))

    t_registry = time.perf_counter()
    models_config = await get_active_models()
    dt_registry = time.perf_counter() - t_registry
    logger.info("model_registry_lookup took %.3fs (%d active models)", dt_registry, len(models_config))

    inference_writer = InferenceWriter(target_date=target_date)

    repository = WeatherDataRepository()
    assembler = FeatureAssembler(repository)
    all_predictions = []
    region_errors: dict[str, list[str]] = {}

    async def _process_single(model_config: dict) -> dict | None:
        t_bacia_start = time.perf_counter()
        bacia = model_config["bacia"]

        t_artifact = time.perf_counter()
        model = load_artifact(model_config["artifact_uri"])
        dt_artifact = time.perf_counter() - t_artifact

        station_ids = model_config.get("station_ids") or getattr(model, "station_ids", [])
        features = model_config.get("features") or getattr(model, "features", None) or getattr(model, "all_feature_order", [])
        async def _fetch_documents(fetcher, missing_source: str):
            try:
                docs = await fetcher
            except WeatherDataUnavailableError:
                return [], missing_source
            if not docs:
                return [], missing_source
            return docs, None

        t_data_fetch = time.perf_counter()
        historic_result, forecast_result = await asyncio.gather(
            _fetch_documents(
                repository.fetch_historic_documents(
                    bacia, run_date.date() - timedelta(days=90), run_date.date(),
                    station_ids=station_ids,
                    fields=list(REQUIRED_FIELDS),
                ),
                "historico",
            ),
            _fetch_documents(
                repository.fetch_forecast_documents(bacia, run_date.date()),
                "forecast",
            ),
        )
        dt_data_fetch = time.perf_counter() - t_data_fetch
        historic_docs, historic_missing = historic_result
        forecast_docs, forecast_missing = forecast_result
        missing_sources = [source for source in (historic_missing, forecast_missing) if source is not None]
        if missing_sources:
            logger.debug(
                "bacia=%s artifact_load=%.3fs data_fetch=%.3fs total=%.3fs (error: missing %s)",
                bacia, dt_artifact, dt_data_fetch, time.perf_counter() - t_bacia_start,
                ", ".join(missing_sources),
            )
            return {"type": "error", "bacia": bacia, "missing_sources": missing_sources}

        t_feature = time.perf_counter()
        feature_frame = await assembler.assemble(
            bacia,
            run_date,
            station_ids=station_ids,
            documents=historic_docs,
        )
        dt_feature = time.perf_counter() - t_feature
        forecast_summary = repository.summarize_forecast_documents(forecast_docs)

        t_predict = time.perf_counter()
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

        # Prefer semantically calibrated event probability when available
        if hasattr(model, "compute_risk_components"):
            try:
                comps = _call_model_method(model, "compute_risk_components", bacia, X)
                if isinstance(comps, dict):
                    p_event = comps.get("perigoso_any")
                    if p_event is not None:
                        raw_proba = float(_first_scalar(p_event))
            except Exception:
                pass
        threshold_map = model_config.get("thresholds") or {}
        threshold_value = threshold_map.get(str(max(severity_value, 1))) or threshold_map.get("1")
        threshold_value = float(np.clip(float(threshold_value), 0.1, 1.0)) if threshold_value is not None else None

        # Apply calibration if available
        calibration = model_config.get("calibration")
        calibrated_proba = _apply_calibration(raw_proba, calibration)

        display_proba = _display_probability(raw_proba, threshold_value, calibrated_proba)
        dt_predict = time.perf_counter() - t_predict

        feature_snapshot = {}
        if not X.is_empty():
            row = X.row(0, named=True)
            feature_snapshot = {
                key: (float(value) if value is not None else None)
                for key, value in row.items()
            }

        # --- SHAP explanation (best-effort) ---
        shap_explanation = None
        explainer_uri = model_config.get("explainer_uri")
        if explainer_uri:
            try:
                explainer = load_artifact(explainer_uri)
                shap_explanation = compute_shap_explanation(
                    explainer, X, features, predicted_class=predict_value,
                )
            except Exception:
                logger.warning(
                    "SHAP explanation failed for bacia=%s explainer_uri=%s",
                    bacia, explainer_uri, exc_info=True,
                )
        # --------------------------------------

        dt_bacia_total = time.perf_counter() - t_bacia_start

        logger.debug(
            "bacia=%s artifact_load=%.3fs data_fetch=%.3fs feature_assembly=%.3fs predict=%.3fs total=%.3fs",
            bacia, dt_artifact, dt_data_fetch, dt_feature, dt_predict, dt_bacia_total,
        )
        prediction = {
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
            "feature_snapshot": feature_snapshot,
            "shap_explanation": shap_explanation,
            "forecast_summary": forecast_summary,
        }
        try:
            prediction["short_explanation"] = await generate_short_explanation(prediction)
        except Exception:
            logger.warning("Short explanation failed for bacia=%s", bacia, exc_info=True)
            prediction["short_explanation"] = None
        return {"type": "prediction", "data": prediction}

    t_gather = time.perf_counter()
    try:
        results = await asyncio.gather(*[_process_single(mc) for mc in models_config])
        for result in results:
            if result["type"] == "error":
                region_errors[result["bacia"]] = result["missing_sources"]
            else:
                all_predictions.append(result["data"])
    finally:
        await repository.close()
    dt_gather = time.perf_counter() - t_gather

    if not all_predictions:
        raise DataAvailabilityError(f"Sem dados para inferencia: {region_errors}")

    t_write = time.perf_counter()
    await inference_writer.write_inference_object(all_predictions, region_errors=region_errors)
    dt_write = time.perf_counter() - t_write

    dt_total = time.perf_counter() - t_start_total
    logger.info(
        "run_floodcast done: total=%.3fs registry=%.3fs gather=%.3fs write=%.3fs (%d predictions, %d errors)",
        dt_total, dt_registry, dt_gather, dt_write, len(all_predictions), len(region_errors),
    )
    return True
