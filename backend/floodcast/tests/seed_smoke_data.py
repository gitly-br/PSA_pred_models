"""
Seed minimal data for smoke test directly into MongoDB.
Faster than full bootstrap for testing purposes.
"""
import asyncio
import json
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytz
from pymongo import MongoClient

MONGO_URI = os.getenv("MONGO_URI", "mongodb://psa:psa@localhost:16521/?authSource=admin")
SP_TZ = pytz.timezone("America/Sao_Paulo")

def get_client():
    return MongoClient(MONGO_URI)


def seed_models():
    """Register champion models."""
    client = get_client()
    db = client.floodcast
    
    models = [
        {
            "name": "champion_guarara",
            "bacia": "guarara",
            "region": "guarara",
            "subregion": "guarara",
            "artifact_uri": "minio://psa/models/champion_guarara.joblib",
            "features": ["api_070", "api_085", "api_095", "acc_6h_lag_1", "acc_6h_lag_2", "acc_6h_lag_3", "acc_6h_lag_4", "acc_6h_lag_5", "acc_6h_lag_6", "acc_6h_lag_7", "acc_6h_lag_8", "acc_6h_lag_9", "acc_6h_lag_10", "acc_6h_lag_11", "acc_6h_lag_12", "max_day_lag1", "max_day_lag2", "max_day_lag3", "mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1", "pico_1h_lag1", "horas_intensas_lag1", "acum_7d", "acum_30d", "mes_sin", "mes_cos"],
            "thresholds": {"1": 0.6, "2": 0.5, "3": 0.7},
            "station_ids": ["352940105A", "354780901A", "354780907A", "354780903A", "354780905A", "354780910A", "354780912A", "354780914A", "354780915A", "354780916A", "354780918A", "354870810A", "354870805A", "354870803G", "354870817A", "354870818A", "354870822A"],
            "modeling_family": "psa_v7_ordinal",
            "obj_version": "0.3",
            "is_champion": True,
            "active": True,
        },
        {
            "name": "champion_meninos",
            "bacia": "meninos",
            "region": "meninos",
            "subregion": "meninos",
            "artifact_uri": "minio://psa/models/champion_meninos.joblib",
            "features": ["api_070", "api_085", "api_095", "acc_6h_lag_1", "acc_6h_lag_2", "acc_6h_lag_3", "acc_6h_lag_4", "acc_6h_lag_5", "acc_6h_lag_6", "acc_6h_lag_7", "acc_6h_lag_8", "acc_6h_lag_9", "acc_6h_lag_10", "acc_6h_lag_11", "acc_6h_lag_12", "max_day_lag1", "max_day_lag2", "max_day_lag3", "mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1", "pico_1h_lag1", "horas_intensas_lag1", "acum_7d", "acum_30d", "mes_sin", "mes_cos"],
            "thresholds": {"1": 0.6, "2": 0.5, "3": 0.7},
            "station_ids": ["354780901A", "354780903A", "354780905A", "354780910A", "354780912A", "354780914A", "354780915A", "354780916A", "354780918A", "354870810A"],
            "modeling_family": "psa_v7_ordinal",
            "obj_version": "0.3",
            "is_champion": True,
            "active": True,
        },
        {
            "name": "champion_oratorio",
            "bacia": "oratorio",
            "region": "oratorio",
            "subregion": "oratorio",
            "artifact_uri": "minio://psa/models/champion_oratorio.joblib",
            "features": ["api_070", "api_085", "api_095", "acc_6h_lag_1", "acc_6h_lag_2", "acc_6h_lag_3", "acc_6h_lag_4", "acc_6h_lag_5", "acc_6h_lag_6", "acc_6h_lag_7", "acc_6h_lag_8", "acc_6h_lag_9", "acc_6h_lag_10", "acc_6h_lag_11", "acc_6h_lag_12", "max_day_lag1", "max_day_lag2", "max_day_lag3", "mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1", "pico_1h_lag1", "horas_intensas_lag1", "acum_7d", "acum_30d", "mes_sin", "mes_cos"],
            "thresholds": {"1": 0.6, "2": 0.5, "3": 0.7},
            "station_ids": ["352940105A", "354780901A", "354780907A", "354780903A", "354780905A", "354780910A", "354780912A", "354780914A", "354780915A", "354780916A", "354780918A"],
            "modeling_family": "psa_v7_ordinal",
            "obj_version": "0.3",
            "is_champion": True,
            "active": True,
        },
        {
            "name": "champion_tamanduatei",
            "bacia": "tamanduatei",
            "region": "tamanduatei",
            "subregion": "tamanduatei",
            "artifact_uri": "minio://psa/models/champion_tamanduatei.joblib",
            "features": ["api_070", "api_085", "api_095", "acc_6h_lag_1", "acc_6h_lag_2", "acc_6h_lag_3", "acc_6h_lag_4", "acc_6h_lag_5", "acc_6h_lag_6", "acc_6h_lag_7", "acc_6h_lag_8", "acc_6h_lag_9", "acc_6h_lag_10", "acc_6h_lag_11", "acc_6h_lag_12", "max_day_lag1", "max_day_lag2", "max_day_lag3", "mean_day_lag1", "std_day_lag1", "n_chovendo_max_lag1", "pico_1h_lag1", "horas_intensas_lag1", "acum_7d", "acum_30d", "mes_sin", "mes_cos"],
            "thresholds": {"1": 0.6, "2": 0.5, "3": 0.7},
            "station_ids": ["352940105A", "354780901A", "354780907A", "354780903A", "354780905A", "354780910A", "354780912A", "354780914A", "354780915A", "354780916A", "354780918A", "354870810A", "354870805A", "354870803G", "354870817A", "354870818A", "354870822A", "354880702A", "354880703A"],
            "modeling_family": "psa_v7_ordinal",
            "obj_version": "0.3",
            "is_champion": True,
            "active": True,
        },
    ]
    
    for model in models:
        db.models.update_one(
            {"name": model["name"]},
            {"$set": model},
            upsert=True
        )
    print(f"Seeded {len(models)} models")
    client.close()


def seed_inference_for_date(target_date: date):
    """Create a cached inference for scenario 1."""
    client = get_client()
    db = client.floodcast
    
    dt_key = SP_TZ.localize(datetime.combine(target_date, time.min))
    
    inference = {
        "obj_version": "0.3",
        "dt_inference": datetime.now(SP_TZ),
        "dt_key": dt_key,
        "region": "all",
        "timezone": "America/Sao_Paulo",
        "timezone_offset": -10800,
        "region_errors": {},
        "results": {
            target_date.isoformat(): {
                "guarara": {
                    "predict": 3,
                    "severity": 3,
                    "proba": 71.01,
                    "raw_proba": 0.71,
                    "explanation": "Modelo ordinal V7 sem explicabilidade local exportada.",
                    "rain_today": {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0},
                    "forecast_summary": {"point_count": 1, "total_mm": 15.0, "max_point_total_mm": 15.0, "min_point_total_mm": 15.0},
                    "models": {"champion_guarara": {"predict": 3, "severity": 3, "proba": 71.01}}
                },
                "meninos": {
                    "predict": 2,
                    "severity": 2,
                    "proba": 55.0,
                    "raw_proba": 0.55,
                    "explanation": "Modelo ordinal V7 sem explicabilidade local exportada.",
                    "rain_today": {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0},
                    "forecast_summary": {"point_count": 1, "total_mm": 12.0, "max_point_total_mm": 12.0, "min_point_total_mm": 12.0},
                    "models": {"champion_meninos": {"predict": 2, "severity": 2, "proba": 55.0}}
                },
                "oratorio": {
                    "predict": 1,
                    "severity": 1,
                    "proba": 45.0,
                    "raw_proba": 0.45,
                    "explanation": "Modelo ordinal V7 sem explicabilidade local exportada.",
                    "rain_today": {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0},
                    "forecast_summary": {"point_count": 1, "total_mm": 8.0, "max_point_total_mm": 8.0, "min_point_total_mm": 8.0},
                    "models": {"champion_oratorio": {"predict": 1, "severity": 1, "proba": 45.0}}
                },
                "tamanduatei": {
                    "predict": 3,
                    "severity": 3,
                    "proba": 68.0,
                    "raw_proba": 0.68,
                    "explanation": "Modelo ordinal V7 sem explicabilidade local exportada.",
                    "rain_today": {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0},
                    "forecast_summary": {"point_count": 1, "total_mm": 14.0, "max_point_total_mm": 14.0, "min_point_total_mm": 14.0},
                    "models": {"champion_tamanduatei": {"predict": 3, "severity": 3, "proba": 68.0}}
                },
                "all": {
                    "predict": 3,
                    "severity": 3,
                    "proba": 71.01,
                    "raw_proba": 0.71,
                    "explanation": "Modelo ordinal V7 sem explicabilidade local exportada.",
                    "rain_today": {"night": 0.0, "morning": 0.0, "afternoon": 0.0, "evening": 0.0},
                    "winner_region": "guarara",
                    "forecast_summary": {"point_count": 1, "total_mm": 15.0, "max_point_total_mm": 15.0, "min_point_total_mm": 15.0},
                    "models": {
                        "guarara": {"champion_guarara": {"predict": 3, "severity": 3, "proba": 71.01}},
                        "meninos": {"champion_meninos": {"predict": 2, "severity": 2, "proba": 55.0}},
                        "oratorio": {"champion_oratorio": {"predict": 1, "severity": 1, "proba": 45.0}},
                        "tamanduatei": {"champion_tamanduatei": {"predict": 3, "severity": 3, "proba": 68.0}}
                    }
                }
            }
        }
    }
    
    db.inference.update_one(
        {"dt_key": dt_key, "region": "all"},
        {"$set": inference},
        upsert=True
    )
    print(f"Seeded inference for {target_date}")
    client.close()


def seed_api_data_for_date(target_date: date, bacia: str = "guarara"):
    """Create minimal historic and forecast data for a specific date."""
    client = get_client()
    db = client.api_data
    
    # Historic data: 90 days of hourly data
    historic_docs = []
    start_date = target_date - timedelta(days=90)
    current = start_date
    station_id = "354780901A"
    
    while current <= target_date:
        for hour in range(24):
            dt = SP_TZ.localize(datetime.combine(current, time(hour, 0))).astimezone(pytz.utc)
            # Simulate some rainfall
            precipitation = 2.5 if current == target_date else 0.5
            historic_docs.append({
                "provider": "cemaden",
                "station_id": station_id,
                "station_name": "Test Station",
                "municipio": "Santo Andre",
                "bacia": bacia,
                "bacias": [bacia],
                "latitude": -23.65,
                "longitude": -46.53,
                "dt": dt,
                "precipitation_mm": precipitation,
                "source_file": "test.parquet",
                "loaded_at": datetime.now(pytz.utc)
            })
        current += timedelta(days=1)
    
    # Use bulk insert for historic
    if historic_docs:
        db.historic.insert_many(historic_docs, ordered=False)
        print(f"Seeded {len(historic_docs)} historic docs for {target_date}")
    
    # Forecast data for the target date
    dt_request = SP_TZ.localize(datetime.combine(target_date, time.min)).astimezone(pytz.utc)
    forecast_doc = {
        "provider": "openmeteo",
        "point_id": "-23.65_-46.53",
        "bacia": bacia,
        "bacias": [bacia],
        "dt_request": dt_request,
        "timezone": "UTC",
        "hourly": [
            {"dt": dt_request + timedelta(hours=h), "temperature": 25.0, "dew_point": 20.0, 
             "pressure": 1013.0, "humidity": 80.0, "wind_speed": 10.0, 
             "rain": 1.0, "precipitation_mm": 1.0}
            for h in range(24)
        ],
        "source_file": "test_forecast.parquet",
        "loaded_at": datetime.now(pytz.utc),
        "latitude": -23.65,
        "longitude": -46.53
    }
    
    db.forecast.insert_one(forecast_doc)
    print(f"Seeded forecast for {target_date}")
    client.close()


def main():
    print("Seeding minimal data for smoke test...")
    seed_models()
    
    # Scenario 1: cached inference
    seed_inference_for_date(date(2025, 4, 21))
    
    # Scenario 2: data for on-demand (2025-04-01)
    seed_api_data_for_date(date(2025, 4, 1), bacia="guarara")
    seed_api_data_for_date(date(2025, 4, 1), bacia="meninos")
    seed_api_data_for_date(date(2025, 4, 1), bacia="oratorio")
    seed_api_data_for_date(date(2025, 4, 1), bacia="tamanduatei")
    
    print("Done!")


if __name__ == "__main__":
    main()
