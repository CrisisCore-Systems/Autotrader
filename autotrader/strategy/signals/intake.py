"""Paper signal intake - validates and forwards to paper harness."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .contract import PaperSignalContract, validate_paper_signal, ALLOWED_PORT, ALLOWED_HOSTS, utc_now


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def write_acceptance_artifact(signal: PaperSignalContract) -> None:
    """Write acceptance artifact for validated signal."""
    artifact_path = PROJECT_ROOT / "reports" / "signals" / "accepted" / f"{signal.signal_id}.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)

    artifact = {
        "accepted": True,
        "signal_id": signal.signal_id,
        "strategy_id": signal.strategy_id,
        "symbol": signal.symbol,
        "notional": float(signal.quantity) * float(signal.limit_price),
        "broker_mode": signal.broker_mode,
        "next_step": "eligible_for_paper_harness",
    }

    with artifact_path.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, sort_keys=True)
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


def _load_registry() -> set[str]:
    """Load seen signal IDs from persistent registry."""
    registry_path = PROJECT_ROOT / "reports" / "signals" / "seen_signal_ids.json"
    if registry_path.exists():
        try:
            content = registry_path.read_text(encoding="utf-8")
            return set(json.loads(content))
        except (json.JSONDecodeError, OSError):
            return set()
    return set()


def _save_registry(ids: set[str]) -> None:
    """Save seen signal IDs to persistent registry."""
    registry_path = PROJECT_ROOT / "reports" / "signals" / "seen_signal_ids.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2)
        f.write("\n")


def is_duplicate(signal_id: str) -> bool:
    """Check if signal ID has been seen before."""
    ids = _load_registry()
    return signal_id in ids


def mark_seen(signal_id: str) -> None:
    """Mark signal ID as seen (for duplicate prevention)."""
    ids = _load_registry()
    ids.add(signal_id)
    _save_registry(ids)


def write_paper_journal_entry(
    signal: PaperSignalContract,
    accepted: bool,
    submitted: bool = False,
    artifact_path: Optional[Path] = None,
) -> None:
    """Append entry to paper trade journal."""
    journal_path = PROJECT_ROOT / "reports" / "paper_trades" / "paper_trade_journal.jsonl"
    journal_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": utc_now(),
        "phase": "2B",
        "signal_id": signal.signal_id,
        "strategy_id": signal.strategy_id,
        "symbol": signal.symbol,
        "side": signal.side,
        "quantity": signal.quantity,
        "limit_price": signal.limit_price,
        "notional": float(signal.quantity) * float(signal.limit_price),
        "accepted": accepted,
        "submitted": submitted,
        "broker_mode": signal.broker_mode,
        "live_routing_attempted": False,
        "artifact_path": str(artifact_path) if artifact_path else None,
    }

    with journal_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True))
        f.write("\n")


def intake_paper_signal(
    signal: PaperSignalContract,
    dry_run_only: bool = True,
) -> tuple[bool, list[str]]:
    """Validate and intake a paper signal.

    Returns (accepted, issues).
    Hard rejects if signal_id already in registry.
    """
    if is_duplicate(signal.signal_id):
        issues = [f"duplicate signal_id: {signal.signal_id}"]
        write_rejection_artifact(signal, issues[0])
        write_paper_journal_entry(signal, accepted=False, submitted=False)
        return False, issues

    issues = validate_paper_signal(signal)
    if issues:
        for issue in issues:
            write_rejection_artifact(signal, issue)
        write_paper_journal_entry(signal, accepted=False, submitted=False)
        return False, issues

    mark_seen(signal.signal_id)
    write_acceptance_artifact(signal)
    write_paper_journal_entry(signal, accepted=True, submitted=False)
    return True, []


__all__ = [
    "intake_paper_signal",
    "write_acceptance_artifact",
    "write_rejection_artifact",
    "write_paper_journal_entry",
    "is_duplicate",
    "mark_seen",
]