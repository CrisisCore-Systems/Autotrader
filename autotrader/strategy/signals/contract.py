"""Paper signal intake contract with explicit safety rails."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


ALLOWED_BROKER_MODE = "paper"
ALLOWED_PORT = 7497
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
MAX_ORDER_NOTIONAL = 5.0


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaperSignalContract:
    """Canonical paper signal contract for IBKR harness v1 intake."""

    signal_id: str
    strategy_id: str
    symbol: str
    sec_type: Literal["STK"] = "STK"
    currency: str = "USD"
    exchange: str = "SMART"
    side: Literal["BUY", "SELL"] = "BUY"
    quantity: int = 1
    order_type: Literal["LMT"] = "LMT"
    limit_price: float = 1.0
    confidence: float = 0.72
    source: Literal["strategy_paper_signal"] = "strategy_paper_signal"
    created_at: str = field(default_factory=utc_now)
    reason: Optional[str] = None
    risk_notes: list[str] = field(default_factory=list)
    broker_mode: Literal["paper"] = "paper"
    broker_host: str = "127.0.0.1"
    broker_port: int = 7497


def validate_paper_signal(signal: PaperSignalContract) -> list[str]:
    """Validate signal against paper-only rails. Returns list of rejection reasons."""
    issues: list[str] = []

    if not signal.signal_id:
        issues.append("missing signal_id")
    if not signal.strategy_id:
        issues.append("missing strategy_id")
    if not signal.symbol:
        issues.append("missing symbol")
    if signal.sec_type != "STK":
        issues.append(f"non-STK sec_type: {signal.sec_type}")
    if signal.order_type != "LMT":
        issues.append(f"non-LMT order_type: {signal.order_type}")
    if signal.limit_price is None or signal.limit_price <= 0:
        issues.append("missing or invalid limit_price")
    if signal.quantity <= 0:
        issues.append("quantity <= 0")
    if signal.quantity != float(int(signal.quantity)):
        issues.append("fractional quantity")
    if signal.confidence < 0.7:
        issues.append(f"confidence {signal.confidence:.4f} below threshold 0.7")
    notional = float(signal.quantity) * float(signal.limit_price)
    if notional > MAX_ORDER_NOTIONAL:
        issues.append(f"notional {notional:.4f} > {MAX_ORDER_NOTIONAL}")
    if signal.source != "strategy_paper_signal":
        issues.append(f"invalid source: {signal.source}")
    if signal.broker_mode != "paper":
        issues.append(f"non-paper broker_mode: {signal.broker_mode}")
    if signal.broker_host not in ALLOWED_HOSTS:
        issues.append(f"non-localhost broker_host: {signal.broker_host}")
    if signal.broker_port != ALLOWED_PORT:
        issues.append(f"non-paper port: {signal.broker_port}")

    return issues


__all__ = ["PaperSignalContract", "validate_paper_signal"]