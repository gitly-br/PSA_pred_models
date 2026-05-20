from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from .minio_client import MinioClientWrapper, MinioSettings


def _iter_files(source: Path, recursive: bool) -> list[Path]:
    if source.is_file():
        return [source]
    if recursive:
        return [path for path in source.rglob("*") if path.is_file()]
    return [path for path in source.iterdir() if path.is_file()]


async def seed_minio(source: str, prefix: str = "", recursive: bool = True) -> list[str]:
    minio = MinioClientWrapper(
        MinioSettings(
            endpoint=os.getenv("MINIO_ENDPOINT", "localhost:19000"),
            access_key=os.getenv("MINIO_ACCESS_KEY", "psa"),
            secret_key=os.getenv("MINIO_SECRET_KEY", "psa12345"),
            bucket=os.getenv("MINIO_BUCKET", "psa"),
            secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        )
    )
    minio.ensure_bucket()

    base = Path(source)
    uploaded: list[str] = []
    for file_path in _iter_files(base, recursive=recursive):
        object_name = f"{prefix.rstrip('/')}/{file_path.name}" if prefix else file_path.name
        minio.upload_file(file_path, object_name)
        uploaded.append(object_name)
    return uploaded


async def main() -> None:
    parser = argparse.ArgumentParser(description="Upload local files to MinIO")
    parser.add_argument("source", help="File or directory to upload")
    parser.add_argument("--prefix", default="", help="Object prefix inside the bucket")
    parser.add_argument("--no-recursive", action="store_true", help="Do not recurse into directories")
    args = parser.parse_args()

    uploaded = await seed_minio(args.source, prefix=args.prefix, recursive=not args.no_recursive)
    print(f"uploaded={len(uploaded)}")


def main_sync() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    asyncio.run(main())
