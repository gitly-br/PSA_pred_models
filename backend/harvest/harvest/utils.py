"""Tiny helpers that are safe for Stage 1."""

from __future__ import annotations
from pathlib import Path


def resolve_config(path: str | None) -> Path:
    """Return absolute Path to the YAML config (or default)."""
    from .constants import DEFAULT_CONFIG_FILE

    p = Path(path or DEFAULT_CONFIG_FILE).expanduser()
    if not p.is_file():
        raise FileNotFoundError(p)
    return p.resolve()
