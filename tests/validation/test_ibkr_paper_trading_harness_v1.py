from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts.ibkr_paper_harness_v1 import (
    CONFIRM_PHRASE,
    assert_paper_only_config,
    evaluate_fixture,
    run_harness,
)


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        paper_only=True,
        ibkr_host="127.0.0.1",
        ibkr_port=7497,
        ibkr_client_id=90,
        min_confidence=0.7,
        max_order_notional=5.0,
        cancel_after_seconds=0.0,
        signals_json="scripts/fixtures/ibkr/simulated_signal_fixture_v1.json",
        submit_paper_order=False,
        i_understand_this_submits_a_paper_order=CONFIRM_PHRASE,
        status_output=str(tmp_path / "harness_status.json"),
    )


def _valid_signal() -> dict[str, object]:
    return {
        "signal_id": "sim-v1-001",
        "symbol": "SNDL",
        "sec_type": "STK",
        "currency": "USD",
        "exchange": "SMART",
        "side": "BUY",
        "quantity": 1,
        "order_type": "LMT",
        "limit_price": 1.0,
        "confidence": 0.72,
        "source": "simulated_signal",
    }


def test_guard_rejects_without_paper_only(tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.paper_only = False

    with pytest.raises(SystemExit, match="--paper-only is required"):
        assert_paper_only_config(args)


def test_guard_rejects_live_port(tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.ibkr_port = 7496

    with pytest.raises(SystemExit, match="paper port 7497 required"):
        assert_paper_only_config(args)


def test_guard_rejects_non_local_host(tmp_path: Path) -> None:
    args = _args(tmp_path)
    args.ibkr_host = "10.0.0.7"

    with pytest.raises(SystemExit, match="host must be localhost"):
        assert_paper_only_config(args)


def test_fixture_market_order_is_rejected(tmp_path: Path) -> None:
    args = _args(tmp_path)
    fixture = {
        "name": "market_order",
        "expect": "reject",
        "signal": {**_valid_signal(), "order_type": "MKT"},
    }

    result = evaluate_fixture(fixture, args)
    assert result["accepted"] is False
    assert result["matched_expectation"] is True
    assert any("order_type must be LMT" in issue for issue in result["issues"])


@pytest.mark.asyncio
async def test_dry_run_writes_status_and_skips_submit(tmp_path: Path) -> None:
    args = _args(tmp_path)
    code = await run_harness(args)

    assert code == 0
    artifact = Path(args.status_output)
    assert artifact.exists()

    status = json.loads(artifact.read_text(encoding="utf-8"))
    assert status["result"]["fixtures_passed"] is True
    assert status["result"]["accepted_signal_id"] == "sim-v1-001"
    assert status["result"]["order_submission_attempted"] is False
