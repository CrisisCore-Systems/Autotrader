from __future__ import annotations

import argparse
import multiprocessing
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

import pandas as pd


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = Path("Autotrader/data/historical/dukascopy")
DEFAULT_REPORTS_DIR = Path("reports")
DEFAULT_SLICE_CACHE_DIR = DEFAULT_REPORTS_DIR / "hour_slice_cache"

TEMPORAL_SLICE_LABELS = {
    "12-14": "US_OPEN_IGNITION",
    "12-16": "US_OPEN_WINDOW",
    "7-12": "LONDON_MORNING",
    "7-16": "LIQUID_SESSION",
}


@dataclass(frozen=True)
class ValidationJob:
    symbol: str
    direction: str
    spread_mode: str
    bar_frequency: str | None
    hour_range: str
    start_date: date
    end_date: date
    data_dir: Path
    slice_cache_dir: Path
    use_hour_slice_cache: bool
    spread_thresholds: str
    max_spread_bps: float | None
    imbalance_cutoffs: str
    fast_ema_lengths: str
    slow_ema_lengths: str
    min_trend_separation_bps_values: str
    imbalance_velocity_lookbacks: str
    imbalance_velocity_thresholds: str
    min_trades: int
    exit_time_decay_ticks: int | None
    exit_trailing_vol_multiplier: float | None
    exit_vol_lookback_ticks: int
    train_max_workers: int
    raw_output_path: Path
    evaluation_output_path: Path
    temporal_slice: str


def _parse_date(raw: str) -> date:
    return datetime.strptime(str(raw).strip(), "%Y-%m-%d").date()


def _clean_symbol(symbol: str) -> str:
    return "".join(ch for ch in str(symbol).upper() if ch.isalnum())


def _normalize_hour_range(hour_range: str) -> str:
    return str(hour_range).strip()


def _parse_symbol_list(raw: str) -> list[str]:
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def _default_worker_count() -> int:
    return max(1, (multiprocessing.cpu_count() or 1) - 1)


def _resolve_path(raw: str | None, *, default: Path) -> Path:
    if raw is None:
        return (WORKSPACE_ROOT / default).resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    return path.resolve()


def _parse_hour_bounds(hour_range: str) -> tuple[int, int]:
    text = str(hour_range).strip()
    if "-" not in text:
        raise ValueError("hour_range must use start-end format, for example 7-16")
    start_text, end_text = text.split("-", 1)
    start_hour = int(start_text.strip())
    end_hour = int(end_text.strip())
    if not 0 <= start_hour <= 23 or not 0 <= end_hour <= 23:
        raise ValueError("hour_range hours must be between 0 and 23")
    if start_hour == end_hour:
        raise ValueError("hour_range start and end hour must differ")
    return start_hour, end_hour


def _extract_shard_date(path: Path, clean_symbol: str) -> date | None:
    prefix = f"{clean_symbol}_"
    if not path.name.upper().startswith(prefix):
        return None
    remainder = path.stem[len(prefix) :]
    date_text = remainder.split("_", 1)[0]
    if len(date_text) != 8 or not date_text.isdigit():
        return None
    return datetime.strptime(date_text, "%Y%m%d").date()


def _list_existing_symbol_shards(data_dir: Path, clean_symbol: str) -> list[Path]:
    return sorted(data_dir.glob(f"*{clean_symbol}*.parquet"))


def _select_symbol_shards_in_date_range(
    data_dir: Path,
    clean_symbol: str,
    start_date: date,
    end_date: date,
) -> list[Path]:
    selected: list[Path] = []
    for path in _list_existing_symbol_shards(data_dir, clean_symbol):
        shard_date = _extract_shard_date(path, clean_symbol)
        if shard_date is None:
            continue
        if start_date <= shard_date < end_date:
            selected.append(path)
    return selected


def _missing_dates_for_symbol(data_dir: Path, clean_symbol: str, start_date: date, end_date: date) -> list[date]:
    observed_dates = {
        shard_date
        for shard_date in (
            _extract_shard_date(path, clean_symbol)
            for path in _list_existing_symbol_shards(data_dir, clean_symbol)
        )
        if shard_date is not None and start_date <= shard_date < end_date
    }
    missing_dates: list[date] = []
    current = start_date
    while current < end_date:
        if current not in observed_dates:
            missing_dates.append(current)
        current += timedelta(days=1)
    return missing_dates


def _run_module(module_name: str, args: Sequence[str]) -> None:
    cmd = [sys.executable, "-m", module_name, *[str(arg) for arg in args]]
    subprocess.run(cmd, check=True, cwd=str(WORKSPACE_ROOT))


def check_or_ingest_data(symbol: str, start_date: date, end_date: date, data_dir: Path) -> list[Path]:
    clean_symbol = _clean_symbol(symbol)
    data_dir.mkdir(parents=True, exist_ok=True)
    missing_dates = _missing_dates_for_symbol(data_dir, clean_symbol, start_date, end_date)
    if missing_dates:
        print(
            f"[-] Missing local shards for {symbol} on {len(missing_dates)} UTC day(s) in {data_dir}. Triggering ingestion pipeline..."
        )
        _run_module(
            "autotrader.data.ingest",
            [
                "--symbol",
                symbol,
                "--start-date",
                start_date.isoformat(),
                "--end-date",
                end_date.isoformat(),
                "--output-dir",
                str(data_dir),
            ],
        )
        print("[+] Ingestion cycle completed successfully.")
    else:
        existing = _list_existing_symbol_shards(data_dir, clean_symbol)
        print(f"[+] Found {len(existing)} localized parquet shard(s) for {symbol}. Ingestion skipped.")
    return _list_existing_symbol_shards(data_dir, clean_symbol)


def _build_slice_cache_dir(
    *,
    symbol: str,
    hour_range: str,
    base_dir: Path,
) -> Path:
    clean_symbol = _clean_symbol(symbol).lower()
    hour_token = hour_range.replace("-", "")
    return base_dir / f"{clean_symbol}_{hour_token}"


def _cache_is_current(source_path: Path, cached_path: Path) -> bool:
    return cached_path.exists() and cached_path.stat().st_mtime >= source_path.stat().st_mtime


def _filter_frame_to_hour_range(frame: pd.DataFrame, hour_range: str) -> pd.DataFrame:
    if "timestamp" not in frame.columns:
        raise ValueError("Expected a 'timestamp' column when building hour-slice cache")
    start_hour, end_hour = _parse_hour_bounds(hour_range)
    timestamps = pd.to_datetime(frame["timestamp"], utc=True)
    hours = timestamps.dt.hour
    if start_hour <= end_hour:
        mask = (hours >= start_hour) & (hours < end_hour)
    else:
        mask = (hours >= start_hour) | (hours < end_hour)
    filtered = frame.loc[mask].copy()
    if not filtered.empty:
        filtered.loc[:, "timestamp"] = timestamps.loc[mask].dt.tz_localize(None)
    return filtered


def materialize_hour_slice_cache(
    *,
    symbol: str,
    hour_range: str,
    data_dir: Path,
    cache_root: Path,
) -> tuple[Path, list[Path]]:
    clean_symbol = _clean_symbol(symbol)
    source_paths = _list_existing_symbol_shards(data_dir, clean_symbol)
    cache_dir = _build_slice_cache_dir(
        symbol=symbol,
        hour_range=hour_range,
        base_dir=cache_root,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    cached_paths: list[Path] = []
    rebuilt_count = 0
    for source_path in source_paths:
        cached_path = cache_dir / source_path.name
        cached_paths.append(cached_path)
        if _cache_is_current(source_path, cached_path):
            continue
        frame = pd.read_parquet(source_path)
        filtered = _filter_frame_to_hour_range(frame, hour_range)
        filtered.to_parquet(cached_path, index=False)
        rebuilt_count += 1

    if rebuilt_count > 0:
        print(f"[+] Built {rebuilt_count} hour-sliced parquet shard(s) for {symbol} in {cache_dir}.")
    else:
        print(f"[+] Reused cached hour-sliced parquet shards for {symbol} from {cache_dir}.")
    return cache_dir, cached_paths


def run_validation_sweep(
    *,
    symbol: str,
    direction: str,
    spread_mode: str,
    bar_frequency: str | None,
    dataset_glob: str,
    hour_range: str,
    raw_output_path: Path,
    spread_thresholds: str,
    max_spread_bps: float | None,
    imbalance_cutoffs: str,
    fast_ema_lengths: str,
    slow_ema_lengths: str,
    min_trend_separation_bps_values: str,
    imbalance_velocity_lookbacks: str,
    imbalance_velocity_thresholds: str,
    min_trades: int,
    exit_time_decay_ticks: int | None,
    exit_trailing_vol_multiplier: float | None,
    exit_vol_lookback_ticks: int,
    train_max_workers: int,
) -> None:
    print(f"[*] Launching macro sweep over window {hour_range} for {symbol}...")
    cmd = [
        "--dataset-glob",
        dataset_glob,
        "--symbol",
        symbol,
        "--direction",
        direction,
        "--spread-mode",
        spread_mode,
        "--imbalance-cutoffs",
        imbalance_cutoffs,
        "--imbalance-velocity-lookbacks",
        imbalance_velocity_lookbacks,
        "--imbalance-velocity-thresholds",
        imbalance_velocity_thresholds,
        "--spread-thresholds",
        spread_thresholds,
        "--fast-ema-lengths",
        fast_ema_lengths,
        "--slow-ema-lengths",
        slow_ema_lengths,
        "--min-trend-separation-bps-values",
        min_trend_separation_bps_values,
        "--min-trades",
        str(int(min_trades)),
        "--hour-range",
        hour_range,
        "--output-path",
        str(raw_output_path),
    ]
    if max_spread_bps is not None:
        cmd.extend(["--max-spread-bps", str(float(max_spread_bps))])
    if bar_frequency is not None:
        cmd.extend(["--bar-frequency", str(bar_frequency)])
    if exit_time_decay_ticks is not None:
        cmd.extend(["--exit-time-decay-ticks", str(int(exit_time_decay_ticks))])
    if exit_trailing_vol_multiplier is not None:
        cmd.extend(["--exit-trailing-vol-multiplier", str(float(exit_trailing_vol_multiplier))])
        cmd.extend(["--exit-vol-lookback-ticks", str(int(exit_vol_lookback_ticks))])
    cmd.extend(["--max-workers", str(int(train_max_workers))])
    _run_module("autotrader.strategy.train", cmd)


def _rejection_pct(diagnostics: dict[str, Any], key: str) -> float:
    denominator = float(diagnostics.get("feature_quotes", 0) or 0)
    if denominator <= 0.0:
        return 0.0
    return float(diagnostics.get(key, 0) or 0.0) / denominator * 100.0


def classify_verdict(fitness: float) -> str:
    if float(fitness) >= 0.0:
        return "TRANSFERABLE"
    if float(fitness) >= -1.0:
        return "LOCAL_ONLY"
    return "REJECTED"


def classify_asymmetry_verdict(*, direction: str, composite_fitness: float, long_fitness: float, short_fitness: float) -> str:
    normalized_direction = str(direction).strip().lower()
    if normalized_direction == "long":
        return "LONG_ONLY_ASYMMETRIC" if float(long_fitness) >= 0.0 else classify_verdict(composite_fitness)
    if normalized_direction == "short":
        return "SHORT_ONLY_ASYMMETRIC" if float(short_fitness) >= 0.0 else classify_verdict(composite_fitness)
    if float(long_fitness) >= 0.0 and float(short_fitness) >= 0.0:
        return "BIDIRECTIONAL"
    if float(long_fitness) >= 0.0 and float(short_fitness) < 0.0:
        return "LONG_ONLY_ASYMMETRIC"
    if float(short_fitness) >= 0.0 and float(long_fitness) < 0.0:
        return "SHORT_ONLY_ASYMMETRIC"
    return classify_verdict(composite_fitness)


def _extract_side_report(winner: dict[str, Any], side_key: str) -> dict[str, Any]:
    side_metrics = winner.get("side_metrics", {}).get(side_key, {})
    baseline = side_metrics.get("baseline", {})
    stress = side_metrics.get("stress_surge", {})
    baseline_diagnostics = baseline.get("diagnostics", {})
    return {
        "fitness": float(side_metrics.get("fitness", 0.0)),
        "net_return": float(baseline.get("net_return", 0.0)),
        "stress_net_return": float(stress.get("net_return", 0.0)),
        "matched_orders": int(baseline.get("matched_orders", 0)),
        "dominant_gate": str(baseline_diagnostics.get("dominant_kill_gate", "none")),
    }


def _build_default_output_paths(symbol: str, hour_range: str) -> tuple[Path, Path]:
    clean_symbol = _clean_symbol(symbol).lower()
    compact_hours = hour_range.replace("-", "")
    raw_output_path = _resolve_path(
        None,
        default=DEFAULT_REPORTS_DIR / f"raw_winner_{clean_symbol}_{compact_hours}.json",
    )
    evaluation_output_path = _resolve_path(
        None,
        default=DEFAULT_REPORTS_DIR / f"eval_{clean_symbol}_{compact_hours}.json",
    )
    return raw_output_path, evaluation_output_path


def run_symbol_validation(
    *,
    symbol: str,
    direction: str,
    spread_mode: str,
    bar_frequency: str | None,
    hour_range: str,
    start_date: date,
    end_date: date,
    data_dir: Path,
    slice_cache_dir: Path,
    use_hour_slice_cache: bool,
    spread_thresholds: str,
    max_spread_bps: float | None,
    imbalance_cutoffs: str,
    fast_ema_lengths: str,
    slow_ema_lengths: str,
    min_trend_separation_bps_values: str,
    imbalance_velocity_lookbacks: str,
    imbalance_velocity_thresholds: str,
    min_trades: int,
    exit_time_decay_ticks: int | None,
    exit_trailing_vol_multiplier: float | None,
    exit_vol_lookback_ticks: int,
    train_max_workers: int,
    raw_output_path: Path,
    evaluation_output_path: Path,
    temporal_slice: str,
) -> dict[str, Any]:
    clean_symbol = _clean_symbol(symbol)
    source_paths = check_or_ingest_data(symbol, start_date, end_date, data_dir)
    dataset_dir = data_dir
    if use_hour_slice_cache:
        dataset_dir, _ = materialize_hour_slice_cache(
            symbol=symbol,
            hour_range=hour_range,
            data_dir=data_dir,
            cache_root=slice_cache_dir,
        )
    elif not source_paths:
        raise FileNotFoundError(f"No local parquet shards found for {symbol} in {data_dir}")
    dataset_glob = str(dataset_dir / f"*{clean_symbol}*.parquet")
    run_validation_sweep(
        symbol=symbol,
        direction=direction,
        spread_mode=spread_mode,
        bar_frequency=bar_frequency,
        dataset_glob=dataset_glob,
        hour_range=hour_range,
        raw_output_path=raw_output_path,
        spread_thresholds=spread_thresholds,
        max_spread_bps=max_spread_bps,
        imbalance_cutoffs=imbalance_cutoffs,
        fast_ema_lengths=fast_ema_lengths,
        slow_ema_lengths=slow_ema_lengths,
        min_trend_separation_bps_values=min_trend_separation_bps_values,
        imbalance_velocity_lookbacks=imbalance_velocity_lookbacks,
        imbalance_velocity_thresholds=imbalance_velocity_thresholds,
        min_trades=min_trades,
        exit_time_decay_ticks=exit_time_decay_ticks,
        exit_trailing_vol_multiplier=exit_trailing_vol_multiplier,
        exit_vol_lookback_ticks=exit_vol_lookback_ticks,
        train_max_workers=train_max_workers,
    )
    return generate_standardized_report(
        symbol=symbol,
        hour_range=hour_range,
        raw_winner_path=raw_output_path,
        final_eval_path=evaluation_output_path,
        temporal_slice=temporal_slice,
    )


def _run_validation_job(job: ValidationJob) -> dict[str, Any]:
    return run_symbol_validation(
        symbol=job.symbol,
        direction=job.direction,
        spread_mode=job.spread_mode,
        bar_frequency=job.bar_frequency,
        hour_range=job.hour_range,
        start_date=job.start_date,
        end_date=job.end_date,
        data_dir=job.data_dir,
        slice_cache_dir=job.slice_cache_dir,
        use_hour_slice_cache=job.use_hour_slice_cache,
        spread_thresholds=job.spread_thresholds,
        max_spread_bps=job.max_spread_bps,
        imbalance_cutoffs=job.imbalance_cutoffs,
        fast_ema_lengths=job.fast_ema_lengths,
        slow_ema_lengths=job.slow_ema_lengths,
        min_trend_separation_bps_values=job.min_trend_separation_bps_values,
        imbalance_velocity_lookbacks=job.imbalance_velocity_lookbacks,
        imbalance_velocity_thresholds=job.imbalance_velocity_thresholds,
        min_trades=job.min_trades,
        exit_time_decay_ticks=job.exit_time_decay_ticks,
        exit_trailing_vol_multiplier=job.exit_trailing_vol_multiplier,
        exit_vol_lookback_ticks=job.exit_vol_lookback_ticks,
        train_max_workers=job.train_max_workers,
        raw_output_path=job.raw_output_path,
        evaluation_output_path=job.evaluation_output_path,
        temporal_slice=job.temporal_slice,
    )


def _write_batch_summary(hour_range: str, reports: Sequence[dict[str, Any]]) -> Path:
    summary_path = _resolve_path(
        None,
        default=DEFAULT_REPORTS_DIR / f"eval_batch_{hour_range.replace('-', '')}.json",
    )
    payload = {
        "batch_id": f"eval_batch_{datetime.now(UTC):%Y%m%d}_{hour_range.replace('-', '')}",
        "hour_range": hour_range,
        "symbols": [report["symbol"] for report in reports],
        "reports": list(reports),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return summary_path


def generate_standardized_report(
    *,
    symbol: str,
    hour_range: str,
    raw_winner_path: Path,
    final_eval_path: Path,
    temporal_slice: str,
) -> dict[str, Any]:
    if not raw_winner_path.exists():
        raise FileNotFoundError(f"Grid runner failed to produce {raw_winner_path}")

    with raw_winner_path.open("r", encoding="utf-8") as handle:
        winner = json.load(handle)

    baseline = winner.get("baseline", {})
    stress = winner.get("stress_surge", {})
    baseline_diagnostics = baseline.get("diagnostics", {})
    direction = str(winner.get("direction", "both"))
    spread_mode = str(winner.get("spread_mode", "relative"))
    max_spread_bps = winner.get("max_spread_bps")
    bar_frequency = winner.get("bar_frequency")
    model_mode = str(winner.get("model_mode", "tick-relative-v1"))
    long_side = _extract_side_report(winner, "long")
    short_side = _extract_side_report(winner, "short")
    clean_symbol = _clean_symbol(symbol).lower()
    compact_hours = hour_range.replace("-", "")
    evaluation_id = f"eval_{datetime.now(UTC):%Y%m%d}_{clean_symbol}_{compact_hours}"
    best_fitness = float(winner.get("fitness", -999.0))
    report_bundle = {
        "evaluation_id": evaluation_id,
        "symbol": symbol,
        "direction": direction,
        "spread_mode": spread_mode,
        "bar_frequency": bar_frequency,
        "model_mode": model_mode,
        "regime": {
            "hour_range": hour_range,
            "temporal_slice": temporal_slice,
        },
        "metrics": {
            "best_fitness": best_fitness,
            "composite_fitness": best_fitness,
            "baseline_net_return": float(baseline.get("net_return", 0.0)),
            "stress_net_return": float(stress.get("net_return", 0.0)),
            "matched_orders": int(baseline.get("matched_orders", 0)),
            "max_spread_bps": float(max_spread_bps) if max_spread_bps is not None else None,
            "long_side": {
                "fitness": long_side["fitness"],
                "net_return": long_side["net_return"],
                "stress_net_return": long_side["stress_net_return"],
                "matched_orders": long_side["matched_orders"],
            },
            "short_side": {
                "fitness": short_side["fitness"],
                "net_return": short_side["net_return"],
                "stress_net_return": short_side["stress_net_return"],
                "matched_orders": short_side["matched_orders"],
            },
        },
        "telemetry": {
            "dominant_kill_gate": str(baseline_diagnostics.get("dominant_kill_gate", "none")),
            "spread_rejection_pct": round(_rejection_pct(baseline_diagnostics, "spread_rejections"), 4),
            "imbalance_rejection_pct": round(_rejection_pct(baseline_diagnostics, "imbalance_rejections"), 4),
            "long_dominant_gate": long_side["dominant_gate"],
            "short_dominant_gate": short_side["dominant_gate"],
        },
        "verdict": classify_asymmetry_verdict(
            direction=direction,
            composite_fitness=best_fitness,
            long_fitness=long_side["fitness"],
            short_fitness=short_side["fitness"],
        ),
    }

    final_eval_path.parent.mkdir(parents=True, exist_ok=True)
    with final_eval_path.open("w", encoding="utf-8") as handle:
        json.dump(report_bundle, handle, indent=2, sort_keys=True)
    print(f"[+] Canonical evaluation report wrote cleanly to: {final_eval_path}")
    return report_bundle


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automate local strategy falsification, ingestion checks, and report normalization.")
    symbol_group = parser.add_mutually_exclusive_group(required=True)
    symbol_group.add_argument("--symbol", help="Single target pair, for example GBP/USD.")
    symbol_group.add_argument("--symbols", help="Comma-separated list of target pairs, for example GBP/USD,EUR/USD.")
    parser.add_argument("--direction", choices=["long", "short", "both"], default="both")
    parser.add_argument("--spread-mode", choices=["relative", "absolute"], default="relative")
    parser.add_argument("--bar-frequency", choices=["1m", "5m", "15m"], default=None)
    parser.add_argument("--hour-range", default="12-14", help="UTC session hour band in start-end format.")
    parser.add_argument("--start-date", default="2024-10-21", help="Inclusive UTC start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", default="2024-10-26", help="Exclusive UTC end date in YYYY-MM-DD format.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory containing local Dukascopy parquet shards.")
    parser.add_argument(
        "--slice-cache-dir",
        default=str(DEFAULT_SLICE_CACHE_DIR),
        help="Directory used to cache hour-sliced parquet shards for repeated validation sweeps.",
    )
    parser.add_argument(
        "--disable-hour-slice-cache",
        action="store_true",
        help="Disable hour-sliced parquet caching and point the trainer directly at the source shards.",
    )
    parser.add_argument("--spread-thresholds", default="0.0")
    parser.add_argument("--max-spread-bps", type=float, default=None)
    parser.add_argument("--imbalance-cutoffs", default="0.75,0.79,0.80")
    parser.add_argument("--fast-ema-lengths", default="10,12")
    parser.add_argument("--slow-ema-lengths", default="20,22")
    parser.add_argument("--min-trend-separation-bps-values", default="0.5")
    parser.add_argument("--imbalance-velocity-lookbacks", default="20")
    parser.add_argument("--imbalance-velocity-thresholds", default="0.05,0.07,0.12")
    parser.add_argument("--min-trades", type=int, default=2)
    parser.add_argument("--exit-time-decay-ticks", type=int, default=1000)
    parser.add_argument("--exit-trailing-vol-multiplier", type=float, default=None)
    parser.add_argument("--exit-vol-lookback-ticks", type=int, default=32)
    parser.add_argument(
        "--train-max-workers",
        type=int,
        default=1,
        help="Candidate-level worker count forwarded to autotrader.strategy.train.",
    )
    parser.add_argument("--raw-output-path", default=None, help="Optional path for the raw training winner artifact.")
    parser.add_argument("--evaluation-output-path", default=None, help="Optional path for the normalized evaluation report.")
    parser.add_argument("--temporal-slice", default=None, help="Optional label stored in the normalized evaluation schema.")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Optional worker count for multi-symbol batch execution. Defaults to CPU cores minus one.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.spread_mode == "absolute" and args.max_spread_bps is None:
        parser.error("--max-spread-bps is required when --spread-mode absolute")

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    if end_date <= start_date:
        raise ValueError("--end-date must be later than --start-date")

    hour_range = _normalize_hour_range(args.hour_range)
    data_dir = _resolve_path(args.data_dir, default=DEFAULT_DATA_DIR)
    slice_cache_dir = _resolve_path(args.slice_cache_dir, default=DEFAULT_SLICE_CACHE_DIR)
    temporal_slice = args.temporal_slice or TEMPORAL_SLICE_LABELS.get(hour_range, "ORCHESTRATED_VALIDATION_RUN")
    symbols = _parse_symbol_list(args.symbols) if args.symbols else [str(args.symbol)]
    if len(symbols) > 1 and (args.raw_output_path or args.evaluation_output_path):
        raise ValueError("--raw-output-path and --evaluation-output-path are only supported for single-symbol runs")

    jobs: list[ValidationJob] = []
    for symbol in symbols:
        raw_output_path, evaluation_output_path = _build_default_output_paths(symbol, hour_range)
        if len(symbols) == 1:
            raw_output_path = _resolve_path(args.raw_output_path, default=raw_output_path.relative_to(WORKSPACE_ROOT))
            evaluation_output_path = _resolve_path(
                args.evaluation_output_path,
                default=evaluation_output_path.relative_to(WORKSPACE_ROOT),
            )
        jobs.append(
            ValidationJob(
                symbol=symbol,
                direction=str(args.direction),
                spread_mode=str(args.spread_mode),
                bar_frequency=args.bar_frequency,
                hour_range=hour_range,
                start_date=start_date,
                end_date=end_date,
                data_dir=data_dir,
                slice_cache_dir=slice_cache_dir,
                use_hour_slice_cache=not bool(args.disable_hour_slice_cache),
                spread_thresholds=args.spread_thresholds,
                max_spread_bps=args.max_spread_bps,
                imbalance_cutoffs=args.imbalance_cutoffs,
                fast_ema_lengths=args.fast_ema_lengths,
                slow_ema_lengths=args.slow_ema_lengths,
                min_trend_separation_bps_values=args.min_trend_separation_bps_values,
                imbalance_velocity_lookbacks=args.imbalance_velocity_lookbacks,
                imbalance_velocity_thresholds=args.imbalance_velocity_thresholds,
                min_trades=args.min_trades,
                exit_time_decay_ticks=args.exit_time_decay_ticks,
                exit_trailing_vol_multiplier=args.exit_trailing_vol_multiplier,
                exit_vol_lookback_ticks=args.exit_vol_lookback_ticks,
                train_max_workers=args.train_max_workers,
                raw_output_path=raw_output_path,
                evaluation_output_path=evaluation_output_path,
                temporal_slice=temporal_slice,
            )
        )

    if len(jobs) == 1:
        reports = [_run_validation_job(jobs[0])]
    else:
        requested_workers = args.max_workers if args.max_workers is not None else _default_worker_count()
        max_workers = max(1, min(int(requested_workers), len(jobs)))
        print(f"[*] Spawning concurrent symbol validations across {max_workers} worker process(es)...")
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            reports = list(executor.map(_run_validation_job, jobs))

    if len(reports) == 1:
        print(json.dumps(reports[0], indent=2, sort_keys=True))
    else:
        summary_path = _write_batch_summary(hour_range, reports)
        print(f"[+] Batch evaluation summary wrote cleanly to: {summary_path}")
        print(json.dumps({"reports": reports}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())