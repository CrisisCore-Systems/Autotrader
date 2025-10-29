"""Rule definitions for GemScore alerts."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

import yaml


@dataclass(frozen=True, slots=True)
class CompoundCondition:
    """Compound condition with AND/OR/NOT logic."""
    
    operator: str  # "AND", "OR", "NOT"
    conditions: tuple[Union["CompoundCondition", "SimpleCondition"], ...] = ()
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate compound condition against context."""
        results = [cond.evaluate(context) for cond in self.conditions]
        
        if self.operator == "AND":
            return all(results)
        elif self.operator == "OR":
            return any(results)
        elif self.operator == "NOT":
            return not any(results)
        else:
            return False


@dataclass(frozen=True, slots=True)
class SimpleCondition:
    """Simple metric comparison condition."""
    
    metric: str
    operator: str  # "lt", "gt", "lte", "gte", "eq", "neq"
    threshold: Any
    
    def evaluate(self, context: Dict[str, Any]) -> bool:
        """Evaluate condition against context."""
        if self.metric not in context:
            return False
        
        value = context[self.metric]
        
        try:
            operators_map = {
                "lt": lambda v, t: v < t,
                "<": lambda v, t: v < t,
                "gt": lambda v, t: v > t,
                ">": lambda v, t: v > t,
                "lte": lambda v, t: v <= t,
                "<=": lambda v, t: v <= t,
                "le": lambda v, t: v <= t,
                "gte": lambda v, t: v >= t,
                ">=": lambda v, t: v >= t,
                "ge": lambda v, t: v >= t,
                "eq": lambda v, t: v == t,
                "==": lambda v, t: v == t,
                "neq": lambda v, t: v != t,
                "!=": lambda v, t: v != t,
            }
            
            compare_func = operators_map.get(self.operator)
            if compare_func is None:
                return False
            
            return compare_func(value, self.threshold)
        except (TypeError, ValueError):
            return False


@dataclass(frozen=True, slots=True)
class AlertRule:
    """Configuration for a GemScore alert rule."""

    id: str
    score_min: float
    confidence_min: float
    safety_ok: bool
    cool_off_minutes: int
    channels: Sequence[str] = ()
    version: str = "v1"
    description: str = ""
    # V2 fields for compound conditions
    condition: Optional[Union[CompoundCondition, SimpleCondition]] = None
    severity: str = "info"
    escalation_policy: Optional[str] = None
    suppression_duration: int = 3600  # seconds
    message_template: str = ""
    tags: Sequence[str] = ()

    def key(self, *, token: str, window_start: str) -> str:
        """Return a deterministic idempotency key for the rule."""

        return f"{token}:{window_start}:{self.id}:{self.version}"

    def matches(self, *, score: float, confidence: float, safety_ok: bool) -> bool:
        """Return ``True`` when a candidate satisfies the rule thresholds."""

        if score < self.score_min:
            return False
        if confidence < self.confidence_min:
            return False
        if safety_ok is not self.safety_ok:
            return False
        return True
    
    def matches_v2(self, context: Dict[str, Any]) -> bool:
        """Evaluate rule using v2 compound conditions if available."""
        if self.condition is not None:
            return self.condition.evaluate(context)
        
        # Fall back to v1 logic
        return self.matches(
            score=context.get("gem_score", 0),
            confidence=context.get("confidence", 0),
            safety_ok=context.get("safety_ok", False)
        )


DEFAULT_RULES: tuple[AlertRule, ...] = (
    AlertRule(
        id="high_score_gate",
        score_min=70,
        confidence_min=0.75,
        safety_ok=True,
        cool_off_minutes=240,
        channels=("telegram", "slack"),
        description="GemScore ≥ 70 & Confidence ≥ 0.75 & safety_ok",
    ),
)


def _parse_condition(cond_data: Mapping[str, Any]) -> Union[CompoundCondition, SimpleCondition]:
    """Parse condition from rule data."""
    cond_type = cond_data.get("type", "simple")
    
    if cond_type == "compound":
        operator = str(cond_data.get("operator", "AND")).upper()
        sub_conditions = []
        for sub_cond in cond_data.get("conditions", []):
            sub_conditions.append(_parse_condition(sub_cond))
        return CompoundCondition(operator=operator, conditions=tuple(sub_conditions))
    else:
        # Simple condition
        return SimpleCondition(
            metric=str(cond_data.get("metric", "")),
            operator=str(cond_data.get("operator", "eq")),
            threshold=cond_data.get("threshold")
        )


def _normalise_rule(raw: Mapping[str, object]) -> AlertRule:
    where = raw.get("where", {})
    channels = tuple(raw.get("channels", ()))
    version = str(raw.get("version", "v1"))
    
    # Parse compound condition if present (v2)
    condition = None
    if "condition" in raw:
        condition = _parse_condition(raw["condition"])
    
    # For v1 rules, extract simple thresholds
    score_min = float(where.get("gem_score_min", 0.0))
    confidence_min = float(where.get("confidence_min", 0.0))
    safety_ok = bool(where.get("safety_ok", True))
    
    return AlertRule(
        id=str(raw["id"]),
        description=str(raw.get("description", "")),
        score_min=score_min,
        confidence_min=confidence_min,
        safety_ok=safety_ok,
        cool_off_minutes=int(raw.get("cool_off_minutes", 60)),
        channels=channels,
        version=version,
        condition=condition,
        severity=str(raw.get("severity", "info")),
        escalation_policy=raw.get("escalation_policy"),
        suppression_duration=int(raw.get("suppression_duration", 3600)),
        message_template=str(raw.get("message_template", "")),
        tags=tuple(raw.get("tags", [])),
    )


def load_rules(path: str | Path | None) -> Sequence[AlertRule]:
    """Load alert rules from YAML.

    When the file is missing an empty tuple is returned so the caller can fall
    back to :data:`DEFAULT_RULES`.
    """

    if path is None:
        return DEFAULT_RULES

    rule_path = Path(path)
    if not rule_path.exists():
        return DEFAULT_RULES

    data = yaml.safe_load(rule_path.read_text()) or {}
    raw_rules: Iterable[Mapping[str, object]] = data.get("rules", [])
    rules = tuple(_normalise_rule(rule) for rule in raw_rules)
    return rules or DEFAULT_RULES


__all__ = ["AlertRule", "DEFAULT_RULES", "load_rules", "CompoundCondition", "SimpleCondition"]
