from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import joblib
import numpy as np
import polars as pl
from sklearn.ensemble import GradientBoostingClassifier

from .model_registry import ChampionModelSpec, upsert_model_spec
from .ordinal_model import ChampionOrdinalModel


THRESHOLD_FLOOR = 0.1


DEFAULT_ARTIFACT_PATH = Path(
    "/workspace/notebooks/modelos/champion_guarara.joblib"
)
DEFAULT_META_PATH = Path(
    "/workspace/notebooks/modelos/champion_guarara.json"
)


def _extract_features(meta: dict[str, object]) -> list[str]:
    features = meta.get("features")
    if isinstance(features, list):
        return [str(feature) for feature in features]

    contract = meta.get("feature_contract") or meta.get("features")
    if isinstance(contract, dict):
        ordered = []
        for values in contract.values():
            if isinstance(values, list):
                ordered.extend(str(feature) for feature in values)
        return ordered

    return []


def _extract_station_ids(meta: dict[str, object], bacia: str) -> list[str]:
    bacias = meta.get("bacias")
    if isinstance(bacias, dict):
        bacia_meta = bacias.get(bacia)
        if isinstance(bacia_meta, dict):
            station_ids = bacia_meta.get("station_ids")
            if isinstance(station_ids, list):
                return [str(station_id) for station_id in station_ids]

    station_ids = meta.get("station_ids") or []
    if isinstance(station_ids, list) and station_ids:
        return [str(station_id) for station_id in station_ids]

    station_contract_path = Path(__file__).resolve().parents[3] / "notebooks" / "dados" / "estacoes_bacia.json"
    if station_contract_path.exists():
        contract = json.loads(station_contract_path.read_text(encoding="utf-8"))
        bacia_station_ids = contract.get(bacia) or []
        if isinstance(bacia_station_ids, list):
            return [str(station_id) for station_id in bacia_station_ids]

    return []


def _extract_thresholds(meta: dict[str, object], bacia: str) -> dict[str, float]:
    def _floor(value: object) -> float:
        return max(float(value), THRESHOLD_FLOOR)

    thresholds = meta.get("thresholds")
    if isinstance(thresholds, dict) and any("|" in str(key) for key in thresholds):
        if all(f"{bacia}|{label}" in thresholds for label in ("pancada", "prolongada", "saturante")):
            return {
                "1": _floor(thresholds[f"{bacia}|pancada"]),
                "2": _floor(thresholds[f"{bacia}|prolongada"]),
                "3": _floor(thresholds[f"{bacia}|saturante"]),
            }

    if isinstance(thresholds, dict) and all(str(key).isdigit() for key in thresholds):
        return {str(key): _floor(value) for key, value in thresholds.items()}

    threshold_calibration = meta.get("thresholds_calibration")
    if isinstance(threshold_calibration, dict):
        by_bacia = threshold_calibration.get("by_bacia")
        if isinstance(by_bacia, dict):
            bacia_thresholds = by_bacia.get(bacia)
            if isinstance(bacia_thresholds, dict):
                return {
                    "1": _floor(bacia_thresholds.get("pancada", 0.5)),
                    "2": _floor(bacia_thresholds.get("prolongada", 0.5)),
                    "3": _floor(bacia_thresholds.get("saturante", 0.5)),
                }

    return {}


def _build_compatible_champion(meta: dict[str, object], bacia: str) -> ChampionOrdinalModel:
    features = _extract_features(meta)
    seed = abs(hash(bacia)) % (2**32)
    rng = np.random.default_rng(seed)
    X = pl.DataFrame({feature: rng.normal(size=512) for feature in features})
    score = X.select(pl.sum_horizontal(pl.all())).to_numpy().ravel()

    thresholds = {
        1: float(_extract_thresholds(meta, bacia).get("1", 0.25)) + (seed % 7) * 0.005,
        2: float(_extract_thresholds(meta, bacia).get("2", 0.25)) + (seed % 5) * 0.005,
        3: float(_extract_thresholds(meta, bacia).get("3", 0.25)) + (seed % 3) * 0.005,
    }

    pipelines = {}
    for level, offset in ((1, -0.5), (2, 0.0), (3, 0.5)):
        y = (score > np.quantile(score, 0.55 + offset * 0.1)).astype(int)
        clf = GradientBoostingClassifier(
            n_estimators=64,
            learning_rate=0.05,
            max_depth=2,
            min_samples_leaf=4,
            random_state=42 + level,
        )
        clf.fit(X, y)
        pipelines[level] = clf

    return ChampionOrdinalModel(
        pipelines=pipelines,
        thresholds=thresholds,
        features=features,
        bacia=bacia,
        modeling_family=str(meta.get("modeling_family") or "psa_v7_ordinal"),
        obj_version=str(meta.get("obj_version") or "0.3"),
        metadata={"generated_for_compose": True},
    )


async def seed_model_registry(
    artifact_path: Path,
    meta_path: Path,
    model_name: str,
    bacia: str,
    object_name: str,
) -> ChampionModelSpec:
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    bucket = os.getenv("MINIO_BUCKET", "psa")
    from harvest.minio_client import MinioClientWrapper, MinioSettings

    minio = MinioClientWrapper(
        MinioSettings(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:19000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "psa"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "psa12345"),
            bucket=bucket,
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )
    )
    minio.ensure_bucket()

    try:
        import sklearn._loss._loss as sklearn_loss  # type: ignore[attr-defined]
        sys.modules.setdefault("_loss", sklearn_loss)
    except Exception:
        pass

    model = joblib.load(artifact_path)

    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        joblib.dump(model, tmp_path)
        minio.upload_file(tmp_path, object_name)
    finally:
        tmp_path.unlink(missing_ok=True)

    spec = ChampionModelSpec(
        name=model_name,
        bacia=bacia,
        artifact_uri=f"minio://{bucket}/{object_name}",
        features=_extract_features(meta),
        thresholds=_extract_thresholds(meta, bacia),
        station_ids=_extract_station_ids(meta, bacia),
        modeling_family=str(meta.get("modeling_family") or "psa_v7_ordinal"),
        obj_version=str(meta.get("obj_version") or "0.3"),
    )
    await upsert_model_spec(spec)
    return spec


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed champion model in MinIO and Mongo")
    parser.add_argument("--artifact-path", default=str(DEFAULT_ARTIFACT_PATH))
    parser.add_argument("--meta-path", default=str(DEFAULT_META_PATH))
    parser.add_argument("--model-name", default="champion_guarara")
    parser.add_argument("--bacia", default="guarara")
    parser.add_argument("--object-name", default="models/champion_guarara.joblib")
    args = parser.parse_args()

    spec = await seed_model_registry(
        artifact_path=Path(args.artifact_path),
        meta_path=Path(args.meta_path),
        model_name=args.model_name,
        bacia=args.bacia,
        object_name=args.object_name,
    )
    print(json.dumps({"name": spec.name, "bacia": spec.bacia, "artifact_uri": spec.artifact_uri}, ensure_ascii=False))


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
