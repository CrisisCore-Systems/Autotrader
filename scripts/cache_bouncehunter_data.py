"""Utility to prefetch BounceHunter training data for offline backtests."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path
from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd
    from src.bouncehunter.config import BounceHunterConfig


def _parse_tickers(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    tickers = [token.strip().upper() for token in raw.split(",") if token.strip()]
    return tickers or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Download price history, engineered features, and earnings calendars "
            "used by BounceHunter so they can be replayed without internet access."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("exports/bouncehunter_cache"),
        help="Directory where cached CSV artifacts will be written.",
    )
    parser.add_argument(
        "--tickers",
        type=str,
        help="Optional comma-separated universe override (defaults to BounceHunterConfig.tickers)",
    )
    parser.add_argument(
        "--start",
        type=str,
        help="Override the historical start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--include-earnings",
        action="store_true",
        help="Include signals that fall inside the earnings blackout window when caching data.",
    )
    return parser


def prepare_config(args: argparse.Namespace) -> "BounceHunterConfig":
    from src.bouncehunter.config import BounceHunterConfig

    config = BounceHunterConfig()
    if args.start:
        config = replace(config, start=args.start)
    if args.include_earnings:
        config = replace(config, skip_earnings=False)
    tickers = _parse_tickers(args.tickers)
    if tickers:
        config = config.with_tickers(tickers)
    return config


def write_frame(frame: "pd.DataFrame", path: Path) -> None:
    frame.to_csv(path, index=True)


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    config = prepare_config(args)

    from src.bouncehunter.engine import BounceHunter

    hunter = BounceHunter(config)

    output_dir = args.output
    histories_dir = output_dir / "histories"
    features_dir = output_dir / "features"
    earnings_dir = output_dir / "earnings"
    aux_dir = output_dir / "auxiliary"

    for directory in (output_dir, histories_dir, features_dir, earnings_dir, aux_dir):
        directory.mkdir(parents=True, exist_ok=True)

    train_df = hunter.fit()

    metadata = {
        "tickers": list(config.tickers),
        "start": config.start,
        "skip_earnings": config.skip_earnings,
        "generated_rows": len(train_df),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    write_frame(train_df, output_dir / "training_events.csv")

    for ticker, artifact in hunter._artifacts.items():  # noqa: SLF001 - intentional utility access
        history_path = histories_dir / f"{ticker}.csv"
        features_path = features_dir / f"{ticker}.csv"
        earnings_path = earnings_dir / f"{ticker}.json"

        write_frame(artifact.history, history_path)
        write_frame(artifact.features, features_path)
        earnings_payload = [ts.date().isoformat() for ts in artifact.earnings]
        earnings_path.write_text(json.dumps(earnings_payload, indent=2), encoding="utf-8")

    if hunter._vix_cache is not None:  # noqa: SLF001 - cache populated during fit()
        vix_frame = hunter._vix_cache.to_frame(name="vix_percentile").reset_index()
        vix_frame.rename(columns={"index": "date"}, inplace=True)
        write_frame(vix_frame.set_index("date"), aux_dir / "vix_percentile.csv")

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
