from __future__ import annotations

import csv
from pathlib import Path

import pytest

from scripts.validation.validate_paper_trades import validate_csv


@pytest.fixture
def schema_path() -> Path:
    return Path("reports") / "validation" / "paper_trading" / "paper_trade_schema.json"


@pytest.fixture
def example_csv_path() -> Path:
    return Path("reports") / "validation" / "paper_trading" / "paper_trades.example.csv"


@pytest.fixture
def base_row() -> dict[str, str]:
    return {
        "trade_id": "PT-0001",
        "opened_at": "2026-05-01T13:31:00Z",
        "closed_at": "2026-05-01T14:12:00Z",
        "ticker": "EXMPL",
        "strategy": "BounceHunter",
        "mode": "paper",
        "broker": "PaperBroker",
        "entry_price": "10.00",
        "exit_price": "10.50",
        "shares": "100",
        "gross_pnl": "50.00",
        "fees": "1.00",
        "net_pnl": "49.00",
        "return_pct": "0.0500",
        "regime": "normal",
        "signal_quality": "0.78",
        "gap_pct": "0.084",
        "volume_ratio": "1.9",
        "stop_price": "9.70",
        "target_price": "10.80",
        "exit_reason": "TARGET",
        "memory_ejected_before_trade": "false",
        "notes": "Example row for validation",
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_missing_required_column_fails(tmp_path: Path, schema_path: Path, base_row: dict[str, str]) -> None:
    csv_path = tmp_path / "missing_column.csv"
    fieldnames = [key for key in base_row if key != "fees"]
    row = {key: value for key, value in base_row.items() if key != "fees"}
    write_csv(csv_path, fieldnames, [row])

    with pytest.raises(ValueError, match="Missing required columns: fees"):
        validate_csv(csv_path, schema_path)


def test_extra_unexpected_column_fails(tmp_path: Path, schema_path: Path, base_row: dict[str, str]) -> None:
    csv_path = tmp_path / "extra_column.csv"
    fieldnames = list(base_row) + ["unexpected_field"]
    row = dict(base_row)
    row["unexpected_field"] = "noise"
    write_csv(csv_path, fieldnames, [row])

    with pytest.raises(ValueError, match="Unexpected columns present: unexpected_field"):
        validate_csv(csv_path, schema_path)


def test_mode_not_paper_fails(tmp_path: Path, schema_path: Path, base_row: dict[str, str]) -> None:
    csv_path = tmp_path / "bad_mode.csv"
    row = dict(base_row)
    row["mode"] = "live"
    write_csv(csv_path, list(base_row), [row])

    with pytest.raises(ValueError, match="mode must be 'paper'"):
        validate_csv(csv_path, schema_path)


def test_malformed_timestamp_fails(tmp_path: Path, schema_path: Path, base_row: dict[str, str]) -> None:
    csv_path = tmp_path / "bad_timestamp.csv"
    row = dict(base_row)
    row["opened_at"] = "not-a-timestamp"
    write_csv(csv_path, list(base_row), [row])

    with pytest.raises(ValueError, match="Field 'opened_at' must be a valid ISO 8601 date-time"):
        validate_csv(csv_path, schema_path)


def test_invalid_numeric_field_fails(tmp_path: Path, schema_path: Path, base_row: dict[str, str]) -> None:
    csv_path = tmp_path / "bad_numeric.csv"
    row = dict(base_row)
    row["fees"] = "abc"
    write_csv(csv_path, list(base_row), [row])

    with pytest.raises(ValueError, match="Field 'fees' must be numeric"):
        validate_csv(csv_path, schema_path)


def test_valid_example_csv_passes(example_csv_path: Path, schema_path: Path) -> None:
    result = validate_csv(example_csv_path, schema_path)

    assert result["trade_count"] == 1
    assert result["win_count"] == 1
    assert result["loss_count"] == 0
    assert result["net_pnl_total"] == pytest.approx(49.0)
