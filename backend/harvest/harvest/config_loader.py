from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

from harvest.constants import DEFAULT_DEDUP_WINDOW_MIN

@dataclass(slots=True, frozen=True)
class SourceConfig:
    source_id: str
    type: str
    city: str
    dedup_key: str
    dedup_window_minutes: int
    params: dict
    ttl_days: int

class ConfigLoader:
    def __init__(self, yaml_path: Path) -> None:
        self.yaml_path = yaml_path

    def load(self) -> list[SourceConfig]:
        raw = yaml.safe_load(self.yaml_path.read_text())
        out: list[SourceConfig] = []
        for src_id, meta in raw.items():
            for city in meta["cities"]:
                out.append(
                    SourceConfig(
                        source_id=src_id,
                        type=meta["type"],
                        city=city["name"],
                        dedup_key=meta["dedup_key"],
                        dedup_window_minutes=meta.get(
                            "dedup_window_minutes", DEFAULT_DEDUP_WINDOW_MIN
                        ),
                        params={
                            k: v
                            for k, v in city.items()
                            if k not in ("name", "ttl_days", "dedup_window_minutes")
                        },
                        ttl_days=city.get("ttl_days", 7),
                    )
                )
        return out
