"""Shared helpers."""
from __future__ import annotations
from unidecode import unidecode
from pathlib import Path
from datetime import datetime, timezone, timedelta

def resolve_config(path: str | None, default_name: str = "sample_configs.yml") -> Path:
    p = Path(path or default_name).expanduser()
    if not p.is_file():
        raise FileNotFoundError(p)
    return p.resolve()

def slugify(s: str) -> str:
    """São Paulo → sao_paulo, Santo André → santo_andre"""
    return (
        unidecode(s)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace(".", "")
    )

def bucketize(ts: datetime, window: timedelta) -> datetime:
    """Floor ts to the start-of-window (UTC)."""
    if window.total_seconds() == 0:
        return ts
    seconds = int(window.total_seconds())
    floored = ts.replace(tzinfo=timezone.utc)
    floored_epoch = int(floored.timestamp()) // seconds * seconds
    return datetime.fromtimestamp(floored_epoch, tz=timezone.utc)
