#!/usr/bin/env python3
"""Minimal CLI wrapper for Stage 1."""
from __future__ import annotations
import argparse
import asyncio

from harvest.config_loader import ConfigLoader
from harvest.utils import resolve_config
from harvest.harvester import Harvester


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run Harvest Stage 1 (dummy).")
    p.add_argument("--city", required=True, help="City name, e.g. 'SãoPaulo'")
    p.add_argument("--config", help="Path to YAML config (defaults sample_configs.yml)")
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    cfg_path = resolve_config(args.config)
    loader = ConfigLoader(cfg_path)
    configs = loader.load()

    harv = Harvester(configs, city=args.city)
    counts = await harv.run_all()

    print(f"\nHarvest summary for {args.city}:")
    for src, n in counts.items():
        print(f"  {src:<15}  {n:>3} docs")
    print()


if __name__ == "__main__":
    asyncio.run(main())
