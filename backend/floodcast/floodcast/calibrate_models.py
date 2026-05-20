from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import polars as pl
import pytz
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from motor.motor_asyncio import AsyncIOMotorClient

from floodcast.artifact_loader import load_artifact
from floodcast.feature_assembler import FeatureAssembler
from floodcast.model_registry import get_active_models
from floodcast.weather_repository import WeatherDataRepository


REPO_ROOT = Path(__file__).resolve().parents[3] / "notebooks"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://psa:psa@localhost:16521/?authSource=admin")
DB_NAME = "floodcast"
COLLECTION_NAME = "models"
TZ = pytz.timezone("America/Sao_Paulo")


def _to_datetime(d: date) -> datetime:
    return TZ.localize(datetime.combine(d, time(12, 0)))


async def calibrate_models_quick():
    models = await get_active_models()
    repository = WeatherDataRepository()
    assembler = FeatureAssembler(repository)

    client = AsyncIOMotorClient(MONGO_URI)
    collection = client[DB_NAME][COLLECTION_NAME]

    # Dates in 2025 for which we have data in MongoDB
    dates_2025 = [
        date(2025, 3, 12),
        date(2025, 3, 15),
        date(2025, 3, 31),
        date(2025, 4, 12),
        date(2025, 4, 19),
        date(2025, 4, 20),
    ]

    print(f"Recalibrando com {len(dates_2025)} datas de 2025")
    print("="*60)

    for model_config in models:
        bacia = model_config["bacia"]
        name = model_config["name"]

        print(f"\n--- {name} ({bacia}) ---")

        model = load_artifact(model_config["artifact_uri"])
        features = model_config.get("features") or getattr(model, "features", [])

        # Get predictions for each date
        probs_raw = []
        for target_date in dates_2025:
            try:
                frame = await assembler.assemble(bacia, _to_datetime(target_date))
                if frame is None or frame.empty:
                    continue
                X = frame[features]
                if hasattr(model, 'pipelines') and 1 in model.pipelines:
                    prob = model.pipelines[1].predict_proba(X)[:, 1][0]
                    probs_raw.append({
                        'date': target_date,
                        'prob_raw': prob,
                        'total_mm': None,  # Will fill from inference
                    })
            except Exception as e:
                print(f"    Erro em {target_date}: {e}")

        if len(probs_raw) < 3:
            print(f"  Poucas amostras válidas: {len(probs_raw)}")
            continue

        # Get forecast summary for each date
        for item in probs_raw:
            try:
                summary = await repository.summarize_forecast(bacia, item['date'])
                item['total_mm'] = summary.get('total_mm', 0)
            except:
                item['total_mm'] = 0

        # Separate by rain intensity
        heavy = [p for p in probs_raw if p['total_mm'] >= 20]  # Heavy rain
        moderate = [p for p in probs_raw if 5 <= p['total_mm'] < 20]  # Moderate rain
        light = [p for p in probs_raw if p['total_mm'] < 5]  # Light rain

        heavy_probs = [p["prob_raw"] for p in heavy]
        moderate_probs = [p["prob_raw"] for p in moderate]
        light_probs = [p["prob_raw"] for p in light]
        print(f"  Heavy rain (>=20mm): {len(heavy)} days, prob_range: {[f'{pr:.3f}' for pr in heavy_probs]}")
        print(f"  Moderate (5-20mm): {len(moderate)} days, prob_range: {[f'{pr:.3f}' for pr in moderate_probs]}")
        print(f"  Light (<5mm): {len(light)} days, prob_range: {[f'{pr:.3f}' for pr in light_probs]}")

        # For calibration, we need labels. Since we don't have historical flood data for 2025
        # in the MongoDB, we'll use a heuristic: days with >=20mm are considered positive,
        # days with <5mm are considered negative
        train_probs = []
        train_labels = []

        for p in heavy:
            train_probs.append(p['prob_raw'])
            train_labels.append(1)

        for p in light:
            train_probs.append(p['prob_raw'])
            train_labels.append(0)

        if len(train_probs) < 3:
            print(f"  Poucas amostras para calibração: {len(train_probs)}")
            continue

        train_probs = np.array(train_probs)
        train_labels = np.array(train_labels)

        # Train calibrator
        calibrator = IsotonicRegression(out_of_bounds='clip')
        calibrator.fit(train_probs, train_labels)

        # Show calibration effect
        cal_heavy = calibrator.predict(np.array([p['prob_raw'] for p in heavy]))
        cal_light = calibrator.predict(np.array([p['prob_raw'] for p in light]))

        if len(cal_heavy) > 0:
            print(f"  Calibrated heavy: mean={cal_heavy.mean():.3f}, min={cal_heavy.min():.3f}, max={cal_heavy.max():.3f}")
        if len(cal_light) > 0:
            print(f"  Calibrated light: mean={cal_light.mean():.3f}, min={cal_light.min():.3f}, max={cal_light.max():.3f}")

        # Save calibration parameters
        calibration_params = {
            "type": "isotonic",
            "X_thresholds": calibrator.X_thresholds_.tolist() if hasattr(calibrator, 'X_thresholds_') else None,
            "y_thresholds": calibrator.y_thresholds_.tolist() if hasattr(calibrator, 'y_thresholds_') else None,
        }

        await collection.update_one(
            {"name": name, "bacia": bacia},
            {"$set": {"calibration": calibration_params}}
        )

        print(f"  Calibração salva no registry")

    await repository.close()
    client.close()
    print("\nRecalibração completa!")


def main_sync():
    asyncio.run(calibrate_models_quick())


if __name__ == "__main__":
    main_sync()
