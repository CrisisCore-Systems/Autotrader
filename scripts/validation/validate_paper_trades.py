"""Validate paper-trade CSV evidence against the intake contract.

This is intentionally small and self-contained: it checks the example/future
paper-trade CSVs against the schema contract, then prints a minimal summary.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Field '{field_name}' must be a valid ISO 8601 date-time: {value!r}") from exc


def _parse_float(value: str, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Field '{field_name}' must be numeric: {value!r}") from exc


def _parse_bool(value: str, field_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Field '{field_name}' must be boolean-like: {value!r}")


def _load_schema(schema_path: Path) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    return {"required": required, "properties": properties}


def validate_csv(csv_path: Path, schema_path: Path) -> dict[str, Any]:
    schema = _load_schema(schema_path)
    required_columns = list(schema["required"])
    properties = schema["properties"]

    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header row: {csv_path}")

        headers = list(reader.fieldnames)
        missing_columns = [column for column in required_columns if column not in headers]
        extra_columns = [column for column in headers if column not in required_columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        if extra_columns:
            raise ValueError(f"Unexpected columns present: {', '.join(extra_columns)}")

        trade_count = 0
        win_count = 0
        loss_count = 0
        net_pnl_total = 0.0
        open_dates: list[datetime] = []
        close_dates: list[datetime] = []
        exit_reasons: Counter[str] = Counter()

        for row_number, row in enumerate(reader, start=2):
            trade_count += 1

            for column in required_columns:
                if row.get(column, "") == "":
                    raise ValueError(f"Row {row_number}: required field '{column}' is empty")

            opened_at = _parse_datetime(row["opened_at"], "opened_at")
            closed_at = _parse_datetime(row["closed_at"], "closed_at")
            open_dates.append(opened_at)
            close_dates.append(closed_at)

            if row["mode"].strip().lower() != "paper":
                raise ValueError(f"Row {row_number}: mode must be 'paper', got {row['mode']!r}")

            entry_price = _parse_float(row["entry_price"], "entry_price")
            exit_price = _parse_float(row["exit_price"], "exit_price")
            shares = _parse_float(row["shares"], "shares")
            gross_pnl = _parse_float(row["gross_pnl"], "gross_pnl")
            fees = _parse_float(row["fees"], "fees")
            net_pnl = _parse_float(row["net_pnl"], "net_pnl")
            _ = _parse_float(row["return_pct"], "return_pct")
            signal_quality = _parse_float(row["signal_quality"], "signal_quality")
            _ = _parse_float(row["gap_pct"], "gap_pct")
            _ = _parse_float(row["volume_ratio"], "volume_ratio")
            _ = _parse_float(row["stop_price"], "stop_price")
            _ = _parse_float(row["target_price"], "target_price")
            _ = _parse_bool(row["memory_ejected_before_trade"], "memory_ejected_before_trade")

            if shares <= 0:
                raise ValueError(f"Row {row_number}: shares must be positive")
            if fees < 0:
                raise ValueError(f"Row {row_number}: fees must be non-negative")
            if not 0.0 <= signal_quality <= 1.0:
                raise ValueError(f"Row {row_number}: signal_quality must be between 0 and 1")
            if row["ticker"].strip() == "":
                raise ValueError(f"Row {row_number}: ticker cannot be empty")

            # Basic consistency check between gross PnL, fees, and net PnL.
            if round(gross_pnl - fees, 6) != round(net_pnl, 6):
                raise ValueError(
                    f"Row {row_number}: net_pnl must equal gross_pnl - fees "
                    f"({gross_pnl} - {fees} != {net_pnl})"
                )

            if exit_price is None or entry_price is None:
                raise ValueError(f"Row {row_number}: entry/exit prices must be numeric")

            if net_pnl > 0:
                win_count += 1
            elif net_pnl < 0:
                loss_count += 1

            net_pnl_total += net_pnl
            exit_reasons[row["exit_reason"].strip()] += 1

    if trade_count == 0:
        raise ValueError("CSV contains no data rows")

    return {
        "trade_count": trade_count,
        "win_count": win_count,
        "loss_count": loss_count,
        "net_pnl_total": net_pnl_total,
        "opened_at_range": (min(open_dates), max(open_dates)),
        "closed_at_range": (min(close_dates), max(close_dates)),
        "exit_reasons": dict(exit_reasons),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate paper-trade CSV evidence")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=Path("reports") / "validation" / "paper_trading" / "paper_trades.example.csv",
        type=Path,
        help="Path to paper-trade CSV evidence",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        default=Path("reports") / "validation" / "paper_trading" / "paper_trade_schema.json",
        help="Path to the paper-trade schema JSON",
    )
    args = parser.parse_args()

    try:
        result = validate_csv(args.csv_path, args.schema)
    except Exception as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        return 1

    opened_start, opened_end = result["opened_at_range"]
    closed_start, closed_end = result["closed_at_range"]

    print(f"Trade count: {result['trade_count']}")
    print(f"Win count: {result['win_count']}")
    print(f"Loss count: {result['loss_count']}")
    print(f"Net PnL: {result['net_pnl_total']:.2f}")
    print(f"Opened at range: {opened_start.isoformat()} -> {opened_end.isoformat()}")
    print(f"Closed at range: {closed_start.isoformat()} -> {closed_end.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
