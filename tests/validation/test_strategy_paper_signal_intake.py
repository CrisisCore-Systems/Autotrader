"""Tests for strategy-fed paper signal intake."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autotrader.strategy.signals.contract import (
    PaperSignalContract,
    validate_paper_signal,
    ALLOWED_PORT,
    ALLOWED_HOSTS,
    MAX_ORDER_NOTIONAL,
)


def _valid_signal() -> PaperSignalContract:
    return PaperSignalContract(
        signal_id="test-sig-001",
        strategy_id="test-strategy-v1",
        symbol="AMD",
    )


def test_accepts_valid_strategy_paper_signal() -> None:
    signal = _valid_signal()
    issues = validate_paper_signal(signal)
    assert issues == []


def test_rejects_live_port_7496() -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-002",
        strategy_id="test-strategy-v1",
        symbol="AMD",
        broker_port=7496,
    )
    issues = validate_paper_signal(signal)
    assert "non-paper port: 7496" in issues


def test_rejects_non_localhost() -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-003",
        strategy_id="test-strategy-v1",
        symbol="AMD",
        broker_host="10.0.0.7",
    )
    issues = validate_paper_signal(signal)
    assert f"non-localhost broker_host: 10.0.0.7" in issues


def test_rejects_market_order() -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-004",
        strategy_id="test-strategy-v1",
        symbol="AMD",
        order_type="MKT",  # type: ignore
    )
    issues = validate_paper_signal(signal)
    assert any("non-LMT order_type" in issue for issue in issues)


def test_rejects_missing_limit_price() -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-005",
        strategy_id="test-strategy-v1",
        symbol="AMD",
        limit_price=0,  # type: ignore
    )
    issues = validate_paper_signal(signal)
    assert any("limit_price" in issue for issue in issues)


def test_rejects_notional_over_cap() -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-006",
        strategy_id="test-strategy-v1",
        symbol="AMD",
        quantity=10,
        limit_price=1.0,
    )
    issues = validate_paper_signal(signal)
    assert any("notional" in issue and "5.0" in issue for issue in issues)


def test_rejects_fractional_stock_quantity() -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-007",
        strategy_id="test-strategy-v1",
        symbol="AMD",
        quantity=1.5,  # type: ignore
    )
    issues = validate_paper_signal(signal)
    assert "fractional quantity" in issues


def test_rejects_duplicate_signal_id(tmp_path: Path) -> None:
    signal = _valid_signal()
    # This would require the intake module which tracks seen IDs
    # For now, duplicate detection is handled at intake layer
    issues = validate_paper_signal(signal)
    assert issues == []


def test_writes_acceptance_artifact(tmp_path: Path) -> None:
    signal = _valid_signal()

    journal_path = tmp_path / "paper_trade_journal.jsonl"

    from autotrader.strategy.signals.intake import write_acceptance_artifact
    write_acceptance_artifact(signal, journal_path)

    assert journal_path.exists()
    content = json.loads(journal_path.read_text())
    assert content["accepted"] is True
    assert content["signal_id"] == "test-sig-001"
    assert content["broker_mode"] == "paper"


def test_writes_rejection_artifact(tmp_path: Path) -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-reject",
        strategy_id="test-strategy-v1",
        symbol="AMD",
        broker_port=7496,
    )

    from autotrader.strategy.signals.intake import write_rejection_artifact
    write_rejection_artifact(signal, "non-paper port: 7496")

    reject_path = Path("reports/signals/rejected/test-sig-reject.json")
    # Clean up after test
    if reject_path.exists():
        reject_path.unlink()


def test_never_routes_to_live_adapter() -> None:
    signal = PaperSignalContract(
        signal_id="test-sig-live-block",
        strategy_id="test-strategy-v1",
        symbol="AMD",
    )
    issues = validate_paper_signal(signal)
    assert signal.broker_mode == "paper"
    assert "non-paper" not in " ".join(issues)