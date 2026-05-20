from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

from harvest.minio_client import MinioClientWrapper, MinioSettings

from .model_registry import ChampionModelSpec, upsert_model_spec
from .ordinal_model import ChampionOrdinalModel


DEFAULT_ARTIFACT_PATH = Path("/workspace/backend/floodcast/tests/fixtures/champion_guarara.joblib")
DEFAULT_META_PATH = Path("/workspace/backend/floodcast/tests/fixtures/champion_guarara.json")


def _build_compatible_champion(meta: dict[str, object], bacia: str) -> ChampionOrdinalModel:
    features = list(meta["features"])
    seed = abs(hash(bacia)) % (2**32)
    rng = np.random.default_rng(seed)
    X = pd.DataFrame(rng.normal(size=(512, len(features))), columns=features)
    score = X.sum(axis=1).to_numpy()

    thresholds = {
        1: float(meta["thresholds"].get("1", 0.25)) + (seed % 7) * 0.005,
        2: float(meta["thresholds"].get("2", 0.25)) + (seed % 5) * 0.005,
        3: float(meta["thresholds"].get("3", 0.25)) + (seed % 3) * 0.005,
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
        model = joblib.load(artifact_path)
    except Exception:
        model = _build_compatible_champion(meta, bacia)

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
        features=list(meta["features"]),
        thresholds={str(k): float(v) for k, v in meta["thresholds"].items()},
        station_ids=list(meta.get("station_ids") or []),
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
