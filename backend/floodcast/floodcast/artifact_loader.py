from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse


def load_artifact(artifact_uri: str):
    """Load a joblib artifact from a local path or file:// URI."""
    import joblib

    if artifact_uri.startswith("minio://"):
        from harvest.minio_client import MinioClientWrapper, MinioSettings

        parsed = urlparse(artifact_uri)
        bucket = parsed.netloc
        object_name = parsed.path.lstrip("/")
        if not bucket:
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
        raw = minio.get_object_bytes(object_name)
        return joblib.load(BytesIO(raw))

    if artifact_uri.startswith("file://"):
        path = Path(urlparse(artifact_uri).path)
    else:
        path = Path(artifact_uri)
    return joblib.load(path)
