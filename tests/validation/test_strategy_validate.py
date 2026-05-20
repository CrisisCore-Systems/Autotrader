from __future__ import annotations

import json

import pandas as pd
import pytest

from autotrader.strategy.train import build_arg_parser as build_train_arg_parser
from autotrader.strategy.validate import build_arg_parser as build_validate_arg_parser, generate_standardized_report, materialize_hour_slice_cache


def test_materialize_hour_slice_cache_filters_and_reuses(tmp_path):
    source_dir = tmp_path / "source"
    cache_root = tmp_path / "cache"
    source_dir.mkdir()

    ticks = pd.DataFrame(
        {
            "timestamp": [
                pd.Timestamp("2024-10-21 06:59:00"),
                pd.Timestamp("2024-10-21 07:00:00"),
                pd.Timestamp("2024-10-21 15:59:00"),
                pd.Timestamp("2024-10-21 16:00:00"),
            ],
            "symbol": ["EUR/USD"] * 4,
            "bid": [1.0850, 1.0851, 1.0852, 1.0853],
            "ask": [1.0852, 1.0853, 1.0854, 1.0855],
        }
    )
    source_path = source_dir / "EURUSD_20241021_12.parquet"
    ticks.to_parquet(source_path, index=False)

    cache_dir, cached_paths = materialize_hour_slice_cache(
        symbol="EUR/USD",
        hour_range="7-16",
        data_dir=source_dir,
        cache_root=cache_root,
    )

    assert cache_dir.exists()
    assert len(cached_paths) == 1
    cached_path = cached_paths[0]
    assert cached_path.exists()

    filtered = pd.read_parquet(cached_path)
    assert filtered["timestamp"].tolist() == [
        pd.Timestamp("2024-10-21 07:00:00"),
        pd.Timestamp("2024-10-21 15:59:00"),
    ]

    first_mtime = cached_path.stat().st_mtime

    _, cached_paths_second = materialize_hour_slice_cache(
        symbol="EUR/USD",
        hour_range="7-16",
        data_dir=source_dir,
        cache_root=cache_root,
    )

    assert cached_paths_second == cached_paths
    assert cached_path.stat().st_mtime == first_mtime


def test_generate_standardized_report_emits_side_asymmetry_metrics(tmp_path):
    raw_winner_path = tmp_path / "raw_winner.json"
    final_eval_path = tmp_path / "eval.json"
    raw_winner_path.write_text(
        json.dumps(
            {
                "direction": "both",
                "spread_mode": "absolute",
                "max_spread_bps": 0.5,
                "bar_frequency": "5m",
                "model_mode": "bar-absolute-v2",
                "fitness": -0.4432,
                "baseline": {
                    "net_return": -0.4432,
                    "matched_orders": 5,
                    "diagnostics": {
                        "feature_quotes": 100,
                        "spread_rejections": 10,
                        "imbalance_rejections": 20,
                        "dominant_kill_gate": "imbalance",
                    },
                },
                "stress_surge": {"net_return": -0.2216},
                "side_metrics": {
                    "long": {
                        "fitness": 0.4432,
                        "baseline": {
                            "net_return": 0.3521,
                            "matched_orders": 3,
                            "diagnostics": {"dominant_kill_gate": "spread"},
                        },
                        "stress_surge": {"net_return": 0.1205},
                    },
                    "short": {
                        "fitness": -1.8864,
                        "baseline": {
                            "net_return": -0.7953,
                            "matched_orders": 2,
                            "diagnostics": {"dominant_kill_gate": "imbalance"},
                        },
                        "stress_surge": {"net_return": -0.9911},
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    report = generate_standardized_report(
        symbol="EUR/USD",
        hour_range="12-14",
        raw_winner_path=raw_winner_path,
        final_eval_path=final_eval_path,
        temporal_slice="US_OPEN_IGNITION",
    )

    assert report["metrics"]["composite_fitness"] == -0.4432
    assert report["spread_mode"] == "absolute"
    assert report["bar_frequency"] == "5m"
    assert report["model_mode"] == "bar-absolute-v2"
    assert report["metrics"]["max_spread_bps"] == 0.5
    assert report["metrics"]["long_side"]["fitness"] == 0.4432
    assert report["metrics"]["long_side"]["matched_orders"] == 3
    assert report["metrics"]["short_side"]["fitness"] == -1.8864
    assert report["telemetry"]["long_dominant_gate"] == "spread"
    assert report["telemetry"]["short_dominant_gate"] == "imbalance"
    assert report["verdict"] == "LONG_ONLY_ASYMMETRIC"


def test_train_cli_requires_max_spread_bps_for_absolute_mode():
    parser = build_train_arg_parser()
    args = parser.parse_args(["--dataset-glob", "data.parquet", "--symbol", "EUR/USD", "--spread-mode", "absolute"])

    with pytest.raises(SystemExit):
        if args.spread_mode == "absolute" and args.max_spread_bps is None:
            parser.error("--max-spread-bps is required when --spread-mode absolute")


def test_validate_cli_requires_max_spread_bps_for_absolute_mode():
    parser = build_validate_arg_parser()
    args = parser.parse_args(["--symbol", "EUR/USD", "--spread-mode", "absolute"])

    with pytest.raises(SystemExit):
        if args.spread_mode == "absolute" and args.max_spread_bps is None:
            parser.error("--max-spread-bps is required when --spread-mode absolute")