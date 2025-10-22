"""Alert evaluation engine that feeds the outbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

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
    # Optional feature comparison for templated messages
    feature_diff: Optional[Dict[str, Any]] = None
    prior_period: Optional[Dict[str, Any]] = None

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
    
    def to_context(self) -> Dict[str, Any]:
        """Convert to evaluation context for compound conditions."""
        context = {
            "symbol": self.symbol,
            "gem_score": self.gem_score,
            "confidence": self.confidence,
            "safety_ok": self.safety_ok,
        }
        # Merge metadata
        if isinstance(self.metadata, dict):
            context.update(self.metadata)
        return context


def _format_message(template: str, context: Dict[str, Any], candidate: AlertCandidate) -> str:
    """Format alert message with context and feature diffs."""
    if not template:
        return f"Alert for {candidate.symbol}: score={candidate.gem_score}, confidence={candidate.confidence}"
    
    try:
        # Add feature diff and prior period info if available
        formatted_context = dict(context)
        if candidate.feature_diff:
            formatted_context["feature_diff"] = candidate.feature_diff
        if candidate.prior_period:
            formatted_context["prior_period"] = candidate.prior_period
        
        return template.format(**formatted_context)
    except (KeyError, ValueError) as e:
        # Fallback to basic message if template formatting fails
        return f"Alert for {candidate.symbol}: {template}"


def evaluate_and_enqueue(
    candidates: Iterable[AlertCandidate],
    *,
    now: datetime,
    outbox: AlertOutboxRepo,
    rules: Sequence[AlertRule] | None = None,
) -> List[AlertOutboxEntry]:
    """Evaluate GemScore candidates and enqueue matching alerts.
    
    Supports both v1 (simple threshold) and v2 (compound condition) rules.
    Includes templated message formatting with feature diffs and prior period comparison.
    """

    materialised_rules = tuple(rules or DEFAULT_RULES)
    enqueued: List[AlertOutboxEntry] = []

    for candidate in candidates:
        base_payload = candidate.to_payload()
        context = candidate.to_context()
        
        for rule in materialised_rules:
            # Evaluate rule based on version
            matched = False
            if rule.version == "v2" and rule.condition is not None:
                # Use compound condition evaluation
                matched = rule.matches_v2(context)
            else:
                # Use v1 simple threshold matching
                matched = rule.matches(
                    score=candidate.gem_score,
                    confidence=candidate.confidence,
                    safety_ok=candidate.safety_ok,
                )
            
            if not matched:
                continue

            # Check suppression/cool-off
            suppression_minutes = rule.cool_off_minutes if rule.version == "v1" else (rule.suppression_duration // 60)
            key = rule.key(token=candidate.symbol, window_start=candidate.window_start)
            if outbox.seen_recently(key, within=timedelta(minutes=suppression_minutes)):
                continue

            # Format message with template
            message = _format_message(rule.message_template or rule.description, context, candidate)
            
            payload = dict(base_payload)
            payload.update(
                {
                    "rule": rule.id,
                    "version": rule.version,
                    "evaluated_at": now.isoformat(),
                    "channels": list(rule.channels),
                    "severity": rule.severity,
                    "message": message,
                    "escalation_policy": rule.escalation_policy,
                    "tags": list(rule.tags),
                }
            )
            
            # Include feature diff and prior period if available
            if candidate.feature_diff:
                payload["feature_diff"] = candidate.feature_diff
            if candidate.prior_period:
                payload["prior_period"] = candidate.prior_period
            
            enqueued.append(outbox.enqueue(key=key, payload=payload))

    return enqueued


__all__ = ["AlertCandidate", "evaluate_and_enqueue"]
