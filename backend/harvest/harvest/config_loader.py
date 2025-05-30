"""Loads source-centric YAML configs and expands to per-city SourceConfig objects."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml

# ──────────────────────────────────────────────────────────────────────────────
@dataclass(slots=True, frozen=True)
class SourceConfig:
    source_id: str          # e.g. "openweather"
    type: str               # "api" (scraper later)
    city: str
    dedup_key: str
    params: dict            # everything city-specific (lat, lon, etc.)
    ttl_days: int


# ──────────────────────────────────────────────────────────────────────────────
class ConfigLoader:
    """Parses YAML into SourceConfig objects."""

    def __init__(self, yaml_path: Path) -> None:
        self.yaml_path = yaml_path
        self._raw: dict = {}

    def load(self) -> list[SourceConfig]:
        self._raw = yaml.safe_load(self.yaml_path.read_text())
        configs: list[SourceConfig] = []
        for source_id, meta in self._raw.items():
            for city in meta["cities"]:
                configs.append(
                    SourceConfig(
                        source_id=source_id,
                        type=meta["type"],
                        city=city["name"],
                        dedup_key=meta["dedup_key"],
                        params={k: v for k, v in city.items() if k not in ("name", "ttl_days")},
                        ttl_days=city.get("ttl_days", 7),
                    )
                )
        return configs
