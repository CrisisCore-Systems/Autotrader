"""Dataset reconciliation script for validation artifacts.

This module generates a reconciliation summary comparing the expected
pipeline outputs (raw market data, cleaned bars, engineered features)
and writes both a JSON artifact and a human-readable log file.

The script is intentionally lightweight so it can run in CI/DVC environments
without requiring heavy dependencies. It inspects file counts, total sizes,
and detects mismatches between the available bar and feature datasets.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Iterable


logger = logging.getLogger("reconcile_datasets")


def _collect_files(directory: Path, patterns: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(directory.glob(pattern))
    return sorted(files)


def _human_bytes(num_bytes: int) -> str:
    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        if value < step:
            return f"{value:.1f} {unit}"
        value /= step
    return f"{value:.1f} PB"


def build_summary(
    raw_dir: Path,
    historical_dir: Path,
    bars_dir: Path,
    features_dir: Path,
) -> dict:
    raw_files = _collect_files(raw_dir, ["**/*.json", "**/*.parquet"])
    historical_files = _collect_files(historical_dir, ["**/*.parquet"])
    bar_files = _collect_files(bars_dir, ["**/*.parquet"])
    feature_files = _collect_files(features_dir, ["**/*.parquet", "**/*.json"])

    def describe_files(files: list[Path]) -> dict:
        sizes = [f.stat().st_size for f in files if f.exists()]
        return {
            "count": len(files),
            "total_size_bytes": sum(sizes),
            "total_size_readable": _human_bytes(sum(sizes)) if sizes else "0 B",
            "files": [str(f) for f in files],
        }

    # Detect discrepancies between bars and features by filename stem
    bar_stems = {f.stem for f in bar_files}
    feature_stems = {Path(f).stem for f in feature_files}
    missing_features = sorted(bar_stems - feature_stems)
    missing_bars = sorted(feature_stems - bar_stems)

    summary = {
        "raw_market_data": describe_files(raw_files),
        "historical_reference": describe_files(historical_files),
        "constructed_bars": describe_files(bar_files),
        "engineered_features": describe_files(feature_files),
        "diff": {
            "bars_without_features": missing_features,
            "features_without_bars": missing_bars,
        },
        "environment": {
            "cwd": os.getcwd(),
        },
    }
    return summary


def write_log(summary: dict, log_path: Path) -> None:
    lines = ["DATASET RECONCILIATION SUMMARY", "=" * 40]

    for key in [
        "raw_market_data",
        "historical_reference",
        "constructed_bars",
        "engineered_features",
    ]:
        section = summary[key]
        lines.append(f"\n[{key}]")
        lines.append(f"count: {section['count']}")
        lines.append(f"total_size: {section['total_size_readable']}")

    diff = summary["diff"]
    lines.append("\n[diff]")
    lines.append(f"bars_without_features: {len(diff['bars_without_features'])}")
    lines.append(f"features_without_bars: {len(diff['features_without_bars'])}")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate dataset reconciliation artifacts")
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/market"))
    parser.add_argument("--historical-dir", type=Path, default=Path("data/historical"))
    parser.add_argument("--bars-dir", type=Path, default=Path("data/bars"))
    parser.add_argument("--features-dir", type=Path, default=Path("data/processed/features"))
    parser.add_argument("--output-json", type=Path, default=Path("reports/reconciliation/latest.json"))
    parser.add_argument("--output-log", type=Path, default=Path("reports/reconciliation/latest.log"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    summary = build_summary(
        raw_dir=args.raw_dir,
        historical_dir=args.historical_dir,
        bars_dir=args.bars_dir,
        features_dir=args.features_dir,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    write_log(summary, args.output_log)
    logger.info("Reconciliation artifacts written", extra={"json": str(args.output_json), "log": str(args.output_log)})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s - %(message)s")
    main()
