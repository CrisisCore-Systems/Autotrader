"""Command-line interface for the BounceHunter scanner."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

from .config import BounceHunterConfig
from .engine import BounceHunter
from .report import SignalReport


def parse_tickers(raw: Optional[str]) -> Optional[list[str]]:
    if raw is None:
        return None
    tickers = [token.strip().upper() for token in raw.split(",") if token.strip()]
    return tickers or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan for mean-reversion bounce candidates")
    parser.add_argument("--tickers", type=str, help="Comma-separated universe (default: large-cap tech + ETFs)")
    parser.add_argument("--start", type=str, default="2018-01-01", help="Historical start date (YYYY-MM-DD)")
    parser.add_argument("--rebound", type=float, default=0.03, help="Target rebound percentage (decimal)")
    parser.add_argument("--horizon", type=int, default=5, help="Lookahead window for the label (trading days)")
    parser.add_argument("--stop", type=float, default=0.03, help="Stop-loss percentage (decimal)")
    parser.add_argument("--threshold", type=float, default=0.62, help="Minimum bounce credibility score")
    parser.add_argument(
        "--output",
        choices=("table", "markdown", "json", "csv"),
        default="table",
        help="How to display the signal list",
    )
    parser.add_argument("--export", type=Path, help="Optional path to persist the signals as CSV/JSON")
    parser.add_argument("--as-of", type=str, help="Override the evaluation date (YYYY-MM-DD)")
    return parser


def configure(args: argparse.Namespace) -> BounceHunterConfig:
    config = BounceHunterConfig(
        start=args.start,
        rebound_pct=args.rebound,
        horizon_days=args.horizon,
        stop_pct=args.stop,
        bcs_threshold=args.threshold,
    )
    tickers = parse_tickers(args.tickers)
    if tickers:
        config = config.with_tickers(tickers)
    return config


def render(signals: list[SignalReport], mode: str) -> str:
    if not signals:
        return "No signals satisfied the current thresholds."
    frame = SignalReport.to_frame(signals)
    frame["probability"] = frame["probability"].apply(lambda p: f"{p:.3f}")
    frame["dist_200dma"] = frame["dist_200dma"].apply(lambda p: f"{p:.1f}%")
    frame["adv_usd"] = frame["adv_usd"].apply(lambda v: f"${v/1_000_000:.1f}M")

    if mode == "json":
        return json.dumps([s.as_dict() for s in signals], indent=2)
    if mode == "csv":
        return frame.to_csv(index=False)
    if mode == "markdown":
        return frame.to_markdown(index=False)
    return frame.to_string(index=False)


def maybe_export(signals: list[SignalReport], path: Optional[Path]) -> None:
    if not signals or path is None:
        return
    frame = SignalReport.to_frame(signals)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(json.dumps([signal.as_dict() for signal in signals], indent=2), encoding="utf-8")
    else:
        frame.to_csv(path, index=False)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = configure(args)

    hunter = BounceHunter(config)
    try:
        train_df = hunter.fit()
    except RuntimeError as exc:
        parser.error(str(exc))
        return 2

    as_of = pd.Timestamp(args.as_of) if args.as_of else None
    signals = hunter.scan(as_of=as_of)
    output = render(signals, args.output)
    print(output)
    maybe_export(signals, args.export)

    success_rate = train_df["label"].mean() if not train_df.empty else float("nan")
    print()
    print(f"Training events: {len(train_df):,}")
    if not math.isnan(success_rate := float(success_rate)):
        print(f"Historical bounce rate: {success_rate:.1%}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
