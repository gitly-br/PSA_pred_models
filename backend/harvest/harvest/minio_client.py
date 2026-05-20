from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from minio import Minio
from urllib3 import PoolManager, Timeout


DEFAULT_MINIO_ENDPOINT = "localhost:19000"
DEFAULT_MINIO_ACCESS_KEY = "psa"
DEFAULT_MINIO_SECRET_KEY = "psa12345"
DEFAULT_MINIO_BUCKET = "psa"


@dataclass(frozen=True)
class MinioSettings:
    endpoint: str = DEFAULT_MINIO_ENDPOINT
    access_key: str = DEFAULT_MINIO_ACCESS_KEY
    secret_key: str = DEFAULT_MINIO_SECRET_KEY
    bucket: str = DEFAULT_MINIO_BUCKET
    secure: bool = False


def _normalize_endpoint(endpoint: str) -> tuple[str, bool]:
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        parsed = urlparse(endpoint)
        return parsed.netloc or parsed.path, parsed.scheme == "https"
    return endpoint, False


class MinioClientWrapper:
    def __init__(self, settings: MinioSettings | None = None):
        self.settings = settings or MinioSettings()
        endpoint, secure = _normalize_endpoint(self.settings.endpoint)
        http_client = PoolManager(
            timeout=Timeout(connect=3.0, read=3.0),
            retries=False,
        )
        self.client = Minio(
            endpoint,
            access_key=self.settings.access_key,
            secret_key=self.settings.secret_key,
            secure=self.settings.secure or secure,
            http_client=http_client,
        )

    def ensure_bucket(self) -> None:
        exists = self.client.bucket_exists(self.settings.bucket)
        if not exists:
            self.client.make_bucket(self.settings.bucket)

    def list_objects(self, prefix: str = "") -> list[str]:
        objects = self.client.list_objects(self.settings.bucket, prefix=prefix, recursive=True)
        return [obj.object_name for obj in objects]

    def get_object_bytes(self, object_name: str) -> bytes:
        response = self.client.get_object(self.settings.bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def upload_file(self, file_path: str | Path, object_name: str, content_type: str | None = None) -> None:
        self.client.fput_object(
            self.settings.bucket,
            object_name,
            str(file_path),
            content_type=content_type,
        )

    def upload_bytes(self, object_name: str, data: bytes, content_type: str | None = None) -> None:
        from io import BytesIO

        self.client.put_object(
            self.settings.bucket,
            object_name,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    def delete_prefix(self, prefix: str) -> None:
        for obj in self.client.list_objects(self.settings.bucket, prefix=prefix, recursive=True):
            self.client.remove_object(self.settings.bucket, obj.object_name)
