"""Paper signal intake - validates and forwards to paper harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .contract import PaperSignalContract, validate_paper_signal, ALLOWED_PORT, ALLOWED_HOSTS


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def write_acceptance_artifact(signal: PaperSignalContract, journal_path: Optional[Path] = None) -> None:
    """Write acceptance artifact for validated signal."""
    journal_path = journal_path or (PROJECT_ROOT / "reports" / "paper_trades" / "paper_trade_journal.jsonl")
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "accepted": True,
        "signal_id": signal.signal_id,
        "strategy_id": signal.strategy_id,
        "symbol": signal.symbol,
        "notional": float(signal.quantity) * float(signal.limit_price),
        "broker_mode": signal.broker_mode,
        "next_step": "eligible_for_paper_harness",
    }

    with journal_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(artifact, sort_keys=True))
        f.write("\n")


def write_rejection_artifact(signal: PaperSignalContract, rejection_reason: str) -> None:
    """Write rejection artifact for invalid signal."""
    reject_path = PROJECT_ROOT / "reports" / "signals" / "rejected"
    reject_path.mkdir(parents=True, exist_ok=True)

    artifact = {
        "accepted": False,
        "signal_id": signal.signal_id,
        "rejection_reason": rejection_reason,
        "broker_mode": signal.broker_mode,
        "live_routing_attempted": False,
    }

    reject_file = reject_path / f"{signal.signal_id}.json"
    with reject_file.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)
        f.write("\n")


def intake_paper_signal(signal: PaperSignalContract) -> tuple[bool, list[str]]:
    """Validate and intake a paper signal. Returns (accepted, issues)."""
    issues = validate_paper_signal(signal)
    if issues:
        for issue in issues:
            write_rejection_artifact(signal, issue)
        return False, issues

    write_acceptance_artifact(signal)
    return True, []


__all__ = ["intake_paper_signal", "write_acceptance_artifact", "write_rejection_artifact"]