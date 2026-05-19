import marimo

__generated_with = "0.20.4"
app = marimo.App(width="full")


@app.cell
def _():
    import boto3
    import pandas as pd
    import io
    from botocore.client import Config

    return Config, boto3


@app.cell
def _():
    from dotenv import load_dotenv
    import os

    load_dotenv(override=True)

    minio_endpoint = os.getenv("MINIO_ENDPOINT")
    minio_access_key = os.getenv("MINIO_ACCESS_KEY")
    minio_secret_key = os.getenv("MINIO_SECRET_KEY")
    minio_bucket = os.getenv("MINIO_BUCKET")
    return minio_access_key, minio_bucket, minio_endpoint, minio_secret_key


@app.cell
def _(minio_endpoint):
    minio_endpoint
    return


@app.cell
def _(minio_bucket):
    minio_bucket
    return


@app.cell
def _(Config, boto3, minio_access_key, minio_endpoint, minio_secret_key):
    s3 = boto3.client(
        "s3",
        endpoint_url=minio_endpoint,
        aws_access_key_id=minio_access_key,
        aws_secret_access_key=minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",                # qualquer valor funciona no MinIO
    )
    return (s3,)


@app.cell
def _(s3):
    def lista_csv(bucket: str, prefixo: str = "") -> list[str]:
        """Retorna lista de chaves de arquivos .csv no bucket."""
        paginator = s3.get_paginator("list_objects_v2")
        chaves = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefixo):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".csv"):
                    chaves.append(obj["Key"])
        return chaves

    return (lista_csv,)


@app.cell
def _(minio_endpoint):
    import socket
    import urllib.request
    import urllib.error
    from urllib.parse import urlparse

    def check_port(host: str, port: int, timeout: float = 3.0) -> str:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return f"✅ Port {port} is OPEN"
        except (socket.timeout, TimeoutError):
            return f"⏳ Port {port} TIMED OUT (blocked or not listening)"
        except ConnectionRefusedError:
            return f"❌ Port {port} REFUSED (host reachable, nothing listening)"
        except Exception as e:
            return f"❓ Port {port} error: {e}"

    parsed = urlparse(minio_endpoint)
    host = parsed.hostname

    results = []
    for port in [80, 443, 9000, 9001]:
        results.append(f"{check_port(host, port)}")

    print(f"Host: {host}")
    print("\n".join(results))
    return


@app.cell
def _(lista_csv, minio_bucket):
    lista_csv(bucket=minio_bucket)
    return


if __name__ == "__main__":
    app.run()
