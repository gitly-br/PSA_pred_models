from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import yaml

@dataclass(slots=True, frozen=True)
class SourceConfig:
    type: str
    city: str
    params: dict
    ttl_days: int

class ConfigLoader:
    def __init__(self, yaml_path: Path) -> None:
        self.yaml_path = yaml_path

    def load(self) -> list[SourceConfig]:
        raw = yaml.safe_load(self.yaml_path.read_text())
        out: list[SourceConfig] = []
        for src_id, meta in raw.items():
            for city in meta:
                out.append(
                    SourceConfig(
                        type=src_id,
                        city=city["name"],
                        params={
                            k: v
                            for k, v in city.items()
                            if k not in ("name", "ttl_days")
                        },
                        ttl_days=city.get("ttl_days", 7),
                    )
                )
        return out
