"""CLI entrypoint for local historical market data ingestion."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, time
from pathlib import Path
from typing import Sequence

WORKSPACE_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
if str(WORKSPACE_PACKAGE_ROOT) not in sys.path:
    sys.path.append(str(WORKSPACE_PACKAGE_ROOT))

from orchestration.flows.ingest_dukascopy import ingest_dukascopy_range


def _parse_date(raw: str) -> date:
    return datetime.strptime(str(raw), "%Y-%m-%d").date()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest local historical market data into Parquet payloads.")
    parser.add_argument("--symbol", dest="symbols", action="append", required=True, help="Symbol to ingest, e.g. EUR/USD. Repeatable.")
    parser.add_argument("--start-date", required=True, help="Inclusive UTC start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", required=True, help="Exclusive UTC end date in YYYY-MM-DD format.")
    parser.add_argument("--output-dir", default="Autotrader/data/historical/dukascopy", help="Output directory for generated Parquet files.")
    return parser


async def _async_main(args: argparse.Namespace) -> int:
    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)
    if end_date <= start_date:
        raise ValueError("--end-date must be later than --start-date")

    start_time = datetime.combine(start_date, time.min)
    end_time = datetime.combine(end_date, time.min)
    written_files = await ingest_dukascopy_range(
        instruments=list(args.symbols),
        start_time=start_time,
        end_time=end_time,
        output_dir=Path(args.output_dir),
    )
    print(f"Wrote {len(written_files)} parquet file(s) to {Path(args.output_dir)}")
    for path in written_files:
        print(path)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())