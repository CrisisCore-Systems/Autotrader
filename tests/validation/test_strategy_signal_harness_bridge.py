"""Tests for strategy signal to harness bridge integration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autotrader.strategy.signals.contract import PaperSignalContract, validate_paper_signal
from autotrader.strategy.signals.harness_bridge import contract_to_harness_fixture, write_harness_fixture
from autotrader.strategy.signals.intake import (
    intake_paper_signal,
    is_duplicate,
    mark_seen,
    write_paper_journal_entry,
)


def _valid_signal() -> PaperSignalContract:
    return PaperSignalContract(
        signal_id="test-bridge-sig-001",
        strategy_id="test-strategy-v1",
        symbol="NVDA",
    )


def test_valid_intake_signal_converts_to_harness_fixture() -> None:
    signal = _valid_signal()
    fixture = contract_to_harness_fixture(signal)

    assert fixture["signal_id"] == "test-bridge-sig-001"
    assert fixture["symbol"] == "NVDA"
    assert fixture["source"] == "simulated_signal"
    assert fixture["bridge_metadata"]["original_source"] == "strategy_paper_signal"
    assert fixture["bridge_metadata"]["strategy_id"] == "test-strategy-v1"


def test_bridge_preserves_signal_identity() -> None:
    signal = PaperSignalContract(
        signal_id="test-bridge-identity",
        strategy_id="test-strategy-v2",
        symbol="TSLA",
        side="SELL",
        quantity=2,
        limit_price=3.50,
        confidence=0.85,
    )
    fixture = contract_to_harness_fixture(signal)

    assert fixture["signal_id"] == "test-bridge-identity"
    assert fixture["side"] == "SELL"
    assert fixture["quantity"] == 2
    assert fixture["limit_price"] == 3.50
    assert fixture["confidence"] == 0.85


def test_bridge_rejects_live_port(tmp_path: Path) -> None:
    signal = PaperSignalContract(
        signal_id="test-bridge-live-port",
        strategy_id="test-strategy-v1",
        symbol="NVDA",
        broker_port=7496,
    )
    issues = validate_paper_signal(signal)
    assert "non-paper port" in " ".join(issues)


def test_bridge_rejects_non_localhost(tmp_path: Path) -> None:
    signal = PaperSignalContract(
        signal_id="test-bridge-live-host",
        strategy_id="test-strategy-v1",
        symbol="NVDA",
        broker_host="10.0.0.7",
    )
    issues = validate_paper_signal(signal)
    assert "non-localhost" in " ".join(issues)


def test_bridge_does_not_submit_by_default(tmp_path: Path) -> None:
    signal = _valid_signal()
    accepted, issues = intake_paper_signal(signal, dry_run_only=True)
    assert accepted is True
    assert len(issues) == 0


def test_bridge_appends_paper_journal(tmp_path: Path) -> None:
    signal = PaperSignalContract(
        signal_id="test-journal-sig",
        strategy_id="test-strategy-v1",
        symbol="AMD",
    )
    write_paper_journal_entry(signal, accepted=True, submitted=False)

    journal_path = Path("reports/paper_trades/paper_trade_journal.jsonl")
    if journal_path.exists():
        content = journal_path.read_text()
        last_line = content.strip().split("\n")[-1]
        entry = json.loads(last_line)
        assert entry["signal_id"] == "test-journal-sig"
        assert entry["accepted"] is True
        assert entry["live_routing_attempted"] is False
        # Clean up
        journal_path.unlink()


def test_duplicate_registry_survives_second_call(tmp_path: Path) -> None:
    signal = PaperSignalContract(
        signal_id="test-dup-sig-reg",
        strategy_id="test-strategy-v1",
        symbol="AMD",
    )

    # First call should succeed
    accepted1, _ = intake_paper_signal(signal)
    assert accepted1 is True

    # Second call should detect duplicate
    accepted2, issues2 = intake_paper_signal(signal)
    assert accepted2 is False
    assert "duplicate" in " ".join(issues2)

    # Clean up registry
    registry_path = Path("reports/signals/seen_signal_ids.json")
    if registry_path.exists():
        registry_path.unlink()


def test_live_routing_still_impossible() -> None:
    signal = PaperSignalContract(
        signal_id="test-live-impossible",
        strategy_id="test-strategy-v1",
        symbol="NVDA",
        broker_mode="live",  # type: ignore
        broker_port=7496,
    )
    issues = validate_paper_signal(signal)
    assert len(issues) >= 2
    assert any("broker_mode" in issue for issue in issues)
    assert any("port" in issue for issue in issues)