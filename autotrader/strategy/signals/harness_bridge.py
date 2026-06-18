"""Bridge from PaperSignalContract to harness-compatible JSON fixture."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .contract import PaperSignalContract, utc_now


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def contract_to_harness_fixture(contract: PaperSignalContract) -> dict[str, Any]:
    """Convert PaperSignalContract to harness v1 JSON fixture format.

    Maps source to 'simulated_signal' for harness compatibility while
    preserving paper-only rails through explicit validation.
    """
    return {
        "signal_id": contract.signal_id,
        "symbol": contract.symbol,
        "sec_type": contract.sec_type,
        "currency": contract.currency,
        "exchange": contract.exchange,
        "side": contract.side,
        "quantity": contract.quantity,
        "order_type": contract.order_type,
        "limit_price": contract.limit_price,
        "confidence": contract.confidence,
        "source": "simulated_signal",  # Bridge to harness-expected source
        "bridge_metadata": {
            "original_source": contract.source,
            "strategy_id": contract.strategy_id,
            "broker_mode": contract.broker_mode,
            "broker_host": contract.broker_host,
            "broker_port": contract.broker_port,
        },
    }


def write_harness_fixture(
    contract: PaperSignalContract,
    output_path: Optional[Path] = None,
) -> Path:
    """Write harness-compatible JSON fixture to disk.

    Returns the path to the written fixture.
    """
    if output_path is None:
        output_path = PROJECT_ROOT / "scripts" / "fixtures" / "ibkr" / f"{contract.signal_id}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fixture = contract_to_harness_fixture(contract)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(fixture, f, indent=2, sort_keys=True)
        f.write("\n")

    return output_path


__all__ = ["contract_to_harness_fixture", "write_harness_fixture"]