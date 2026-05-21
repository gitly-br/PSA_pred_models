import os
from datetime import datetime
import pytz
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict
from .logger import get_logger

logger = get_logger(__name__)

FEATURE_DICT = {
    "rain": "precipitação",
    "temp": "temperatura",
    "wind_speed": "velocidade do vento",
    "dew_point": "ponto de orvalho"
}

AGG_DICT = {
    "sum": "quantidade acumulada",
    "delta": "variação"
}

class InferenceWriter:
    def __init__(self, target_date: datetime = None):
        self.mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = "floodcast"
        self.collection_name = "inference"
        self.target_date = target_date

    def _calculate_distribution(self, rain_distribution: dict, proba: float) -> dict:
        distribution = {}
        window = rain_distribution.get("today") if isinstance(rain_distribution.get("today"), dict) else None
        if window is None:
            window = next(iter(rain_distribution.values()), {}) if rain_distribution else {}

        value_total = window.get("total", 0.0)
        value_night = window.get("night", 0.0)
        value_morning = window.get("morning", 0.0)
        value_afternoon = window.get("afternoon", 0.0)
        value_evening = window.get("evening", 0.0)
        if value_total <= 0:
            return {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0}
        distribution["night"] = (value_night / value_total) * proba
        distribution["morning"] = (value_morning / value_total) * proba
        distribution["afternoon"] = (value_afternoon / value_total) * proba
        distribution["evening"] = (value_evening / value_total) * proba
        return distribution

    def _forecast_period_totals(self, forecast_summary: dict) -> dict:
        rain_by_period = forecast_summary.get("rain_by_period_mm") or {}
        return {
            "night": float(rain_by_period.get("night") or 0.0),
            "morning": float(rain_by_period.get("morning") or 0.0),
            "afternoon": float(rain_by_period.get("afternoon") or 0.0),
            "evening": float(rain_by_period.get("evening") or 0.0),
        }

    @staticmethod
    def _day_color_cap(proba: float | None) -> float:
        value = float(proba or 0.0)
        if value >= 0.5:
            return 14.9
        if value >= 0.25:
            return 9.9
        return 4.9

    def _forecast_period_display(self, forecast_summary: dict, proba: float | None) -> dict[str, float]:
        totals = self._forecast_period_totals(forecast_summary)
        total_mm = sum(totals.values())
        if total_mm <= 0:
            return {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0}
        p = float(proba or 0.0)
        if p <= 0:
            return {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0}
        return {
            period: round((value / total_mm) * p, 4)
            for period, value in totals.items()
        }

    def _get_explanation(self, shap_values: list[tuple]) -> str:
        most_important_feature = shap_values[0][0]
        split_feature_name = most_important_feature.split("_")
        agg, start, end = split_feature_name[-3::1]
        feature = "_".join(split_feature_name[:-3])
        if feature in FEATURE_DICT:
            feature_translated = FEATURE_DICT[feature]
        else:
            feature_translated = feature
        if agg in AGG_DICT:
            agg_translated = AGG_DICT[agg]
        else:
            agg_translated = agg
        return f"O modelo deu mais importância para a {agg_translated} de {feature_translated} entre {start}h e {end}h"

    def _get_current_rounded_hour(self) -> datetime:
        now_utc = datetime.now(pytz.utc)
        return now_utc.replace(minute=0, second=0, microsecond=0)

    async def _build_inference_object(self, all_predictions: list[dict], region_errors: dict[str, list[str]] | None = None) -> dict:
        if not all_predictions:
            logger.error("No predictions provided to build inference object.")
            raise ValueError("--- No predictions provided to build inference object.")

        top_level_region = "all"
        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        dt_inference = datetime.now(sao_paulo_tz)
        if self.target_date:
            dt_key = sao_paulo_tz.localize(self.target_date)
        else:
            dt_key = datetime(dt_inference.year, dt_inference.month, dt_inference.day, tzinfo=sao_paulo_tz)

        results_by_day_and_subregion = defaultdict(lambda: defaultdict(lambda: {"predicts": [], "probas": [], "shaps": [], "models": {}}))

        for pred in all_predictions:
            day = pred.get("day")
            if not day:
                logger.error("--- Prediction object missing 'day' key.")
                raise ValueError("--- Prediction object missing 'day' key.")
            subregion = pred.get("subregion", "unknown_subregion")
            if subregion == "unknown_subregion":
                subregion = pred.get("bacia", "unknown_subregion")
            model_name = pred.get("model_name", "unknown_model")
            predict_value = pred.get("predict")
            severity_value = int(pred.get("severity") or predict_value or 0)
            proba_value = pred.get("proba")
            raw_proba_value = pred.get("raw_proba")
            calibrated_proba_value = pred.get("calibrated_proba")
            shap_explanation = pred.get("shap_explanation")
            forecast_summary = pred.get("forecast_summary") or {}

            model_result = {"predict": predict_value}
            model_result["severity"] = severity_value
            model_result["shap"] = shap_explanation
            if proba_value is not None:
                model_result["proba"] = proba_value
            if raw_proba_value is not None:
                model_result["raw_proba"] = raw_proba_value
            if calibrated_proba_value is not None:
                model_result["calibrated_proba"] = calibrated_proba_value
            model_result["forecast_summary"] = forecast_summary
            results_by_day_and_subregion[day][subregion]["models"][model_name] = model_result

            results_by_day_and_subregion[day][subregion]["predicts"].append(predict_value)
            if shap_explanation is not None:
                results_by_day_and_subregion[day][subregion]["shaps"].append(shap_explanation)
            if proba_value is not None:
                results_by_day_and_subregion[day][subregion]["probas"].append(proba_value)
            results_by_day_and_subregion[day][subregion].setdefault("severities", []).append(severity_value)

        final_results_by_day = defaultdict(dict)
        for day, subregions_data in results_by_day_and_subregion.items():
            for subregion, data in subregions_data.items():
                subregion_predict = int(sum(data["predicts"]) / len(data["predicts"])) if data["predicts"] else 0
                subregion_proba = sum(data["probas"]) / len(data["probas"]) if data["probas"] else None
                subregion_shap = data["shaps"][0] if data["shaps"] else None
                subregion_severity = max(data.get("severities") or [subregion_predict])

                # Aggregate raw/calibrated proba per model for this subregion
                subregion_raw_probas = []
                subregion_cal_probas = []
                subregion_forecast_total_mm = 0.0
                subregion_forecast_summary = {}
                for mr in data["models"].values():
                    if mr.get("raw_proba") is not None:
                        subregion_raw_probas.append(mr["raw_proba"])
                    if mr.get("calibrated_proba") is not None:
                        subregion_cal_probas.append(mr["calibrated_proba"])
                    forecast_summary = mr.get("forecast_summary", {})
                    total_mm = float(forecast_summary.get("total_mm") or 0.0)
                    if total_mm:
                        subregion_forecast_total_mm = total_mm
                        subregion_forecast_summary = forecast_summary

                subregion_raw_proba = (sum(subregion_raw_probas) / len(subregion_raw_probas)) if subregion_raw_probas else None
                subregion_cal_proba = (sum(subregion_cal_probas) / len(subregion_cal_probas)) if subregion_cal_probas else None

                if subregion_forecast_total_mm < 3.5:
                    explanation = "Não há precipitação significativa prevista para o período"
                    rain_today = self._forecast_period_display(subregion_forecast_summary, 0.0)
                    subregion_predict = 0
                    subregion_proba = 0.0
                    subregion_severity = 0
                elif subregion_predict == 0:
                    explanation = "Há previsão de chuva, mas o modelo não detectou nenhuma condição preocupante na previsão."
                    rain_today = self._forecast_period_display(subregion_forecast_summary, subregion_proba)
                else:
                    if subregion_shap:
                        explanation = self._get_explanation(subregion_shap)
                    else:
                        explanation = "Modelo ordinal V7 sem explicabilidade local exportada."
                    rain_today = self._forecast_period_display(subregion_forecast_summary, subregion_proba)
                
                final_results_by_day[day][subregion] = {
                    "predict": subregion_predict,
                    "severity": subregion_severity,
                    "proba": subregion_proba,
                    "raw_proba": subregion_raw_proba,
                    "calibrated_proba": subregion_cal_proba,
                    "explanation": explanation,
                    "rain_today": rain_today,
                    "forecast_summary": subregion_forecast_summary,
                    "models": data["models"]
                }

            regional_items = [(name, result) for name, result in final_results_by_day[day].items() if name != "all"]
            positive_items = [
                item for item in regional_items
                if int(item[1].get("severity") or item[1].get("predict") or 0) > 0
            ]
            if positive_items:
                winner_name, winner = max(
                    positive_items,
                    key=lambda item: (
                        int(item[1].get("severity") or item[1].get("predict") or 0),
                        float(item[1].get("proba") or 0.0),
                        int(item[1].get("predict") or 0),
                    ),
                )
                max_proba_name, max_proba_item = max(
                    regional_items,
                    key=lambda item: (
                        float(item[1].get("proba") or 0.0),
                        int(item[1].get("predict") or 0),
                    ),
                )
                final_results_by_day[day]["all"] = {
                    "predict": int(winner.get("predict") or 0),
                    "severity": int(winner.get("severity") or winner.get("predict") or 0),
                    "proba": float(max_proba_item.get("proba") or 0.0),
                    "raw_proba": max_proba_item.get("raw_proba") or winner.get("raw_proba"),
                    "calibrated_proba": max_proba_item.get("calibrated_proba") or winner.get("calibrated_proba"),
                    "explanation": winner.get("explanation", ""),
                    "rain_today": max_proba_item.get("rain_today", {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0}),
                    "winner_region": winner_name,
                    "forecast_summary": max_proba_item.get("forecast_summary", {}),
                    "models": {name: result["models"] for name, result in regional_items},
                }
            else:
                best_name, best = max(
                    regional_items,
                    key=lambda item: (
                        float(item[1].get("proba") or 0.0),
                        int(item[1].get("predict") or 0),
                    ),
                ) if regional_items else (None, None)
                final_results_by_day[day]["all"] = {
                    "predict": int(best.get("predict") or 0) if best else 0,
                    "severity": int(best.get("severity") or best.get("predict") or 0) if best else 0,
                    "proba": float(best.get("proba") or 0.0) if best else 0.0,
                    "raw_proba": best.get("raw_proba") if best else 0.0,
                    "calibrated_proba": best.get("calibrated_proba") if best else None,
                    "explanation": best.get("explanation") if best else "Não há precipitação significativa prevista para o período",
                    "rain_today": best.get("rain_today", {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0}) if best else {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0},
                    "winner_region": best_name,
                    "forecast_summary": best.get("forecast_summary", {"point_count": 0, "total_mm": 0.0, "max_point_total_mm": 0.0, "min_point_total_mm": 0.0}) if best else {"point_count": 0, "total_mm": 0.0, "max_point_total_mm": 0.0, "min_point_total_mm": 0.0},
                    "models": {name: result["models"] for name, result in regional_items},
                }
        
        inference_object = {
            "obj_version": "0.3",
            "dt_inference": dt_inference,
            "dt_key": dt_key,
            "region": top_level_region,
            "timezone": "America/Sao_Paulo",
            "timezone_offset": int(dt_inference.utcoffset().total_seconds()),
            "region_errors": region_errors or {},
            "results": final_results_by_day
        }
        return inference_object

    async def write_inference_object(self, all_predictions: list[dict], region_errors: dict[str, list[str]] | None = None):
        inference_object = await self._build_inference_object(all_predictions, region_errors=region_errors)
        dt_key = inference_object["dt_key"]
        region = inference_object["region"]

        client = AsyncIOMotorClient(self.mongo_uri)
        collection = client[self.db_name][self.collection_name]

        existing_record = await collection.find_one({
            "dt_key": dt_key,
            "region": region
        })

        if existing_record:
            logger.debug(f"Inference record for {region} on {dt_key.date()} already exists. Skipping write.")
        else:
            try:
                await collection.insert_one(inference_object)
                logger.debug(f"Successfully wrote inference record for {region} on {dt_key.date()} to MongoDB.")
            except Exception as e:
                logger.error(f"Error writing inference record to MongoDB: {e}")
    
    async def check_inference_needed(self, models_config: list[dict]) -> list[dict]:
        client = AsyncIOMotorClient(self.mongo_uri)
        collection = client[self.db_name][self.collection_name]
        sao_paulo_tz = pytz.timezone('America/Sao_Paulo')
        
        if self.target_date:
            dt_key = sao_paulo_tz.localize(self.target_date)
        else:
            dt_inference = datetime.now(sao_paulo_tz)
            dt_key = datetime(dt_inference.year, dt_inference.month, dt_inference.day, tzinfo=sao_paulo_tz)

        models_by_region = defaultdict(list)
        for model in models_config:
            models_by_region[model['region']].append(model)

        needed_models = []
        for region, models in models_by_region.items():
            existing_record = await collection.find_one({
                "dt_key": dt_key,
                "region": region
            })
            if not existing_record:
                needed_models.extend(models)
            else:
                logger.debug(f"Inference record for {region} on {dt_key.date()} already exists. Skipping...")

        return needed_models
