"""Alert evaluation engine that feeds the outbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, List, Mapping, MutableMapping, Sequence

from .repo import AlertOutboxEntry, AlertOutboxRepo
from .rules import AlertRule, DEFAULT_RULES


@dataclass(slots=True)
class AlertCandidate:
    """Minimum data required to evaluate alert rules for a token window."""

    symbol: str
    window_start: str
    gem_score: float
    confidence: float
    safety_ok: bool
    metadata: Mapping[str, object] = field(default_factory=dict)

    def to_payload(self) -> MutableMapping[str, object]:
        payload: MutableMapping[str, object] = {
            "symbol": self.symbol,
            "window_start": self.window_start,
            "score": float(self.gem_score),
            "confidence": float(self.confidence),
            "safety_ok": bool(self.safety_ok),
        }
        payload.update(self.metadata)
        return payload


def evaluate_and_enqueue(
    candidates: Iterable[AlertCandidate],
    *,
    now: datetime,
    outbox: AlertOutboxRepo,
    rules: Sequence[AlertRule] | None = None,
) -> List[AlertOutboxEntry]:
    """Evaluate GemScore candidates and enqueue matching alerts."""

    materialised_rules = tuple(rules or DEFAULT_RULES)
    enqueued: List[AlertOutboxEntry] = []

    for candidate in candidates:
        base_payload = candidate.to_payload()
        for rule in materialised_rules:
            if not rule.matches(
                score=candidate.gem_score,
                confidence=candidate.confidence,
                safety_ok=candidate.safety_ok,
            ):
                continue

            key = rule.key(token=candidate.symbol, window_start=candidate.window_start)
            if outbox.seen_recently(key, within=timedelta(minutes=rule.cool_off_minutes)):
                continue

            payload = dict(base_payload)
            payload.update(
                {
                    "rule": rule.id,
                    "version": rule.version,
                    "evaluated_at": now.isoformat(),
                    "channels": list(rule.channels),
                }
            )
            enqueued.append(outbox.enqueue(key=key, payload=payload))

    return enqueued


__all__ = ["AlertCandidate", "evaluate_and_enqueue"]
