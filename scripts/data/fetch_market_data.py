"""Placeholder fetch script for DVC pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def load_config(path: Path) -> dict:
    return yaml.safe_load(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    output = Path(cfg["output"]["path"])
    output.mkdir(parents=True, exist_ok=True)
    (output / "placeholder.json").write_text(json.dumps({"status": "fetched"}, indent=2))


if __name__ == "__main__":
    main()
