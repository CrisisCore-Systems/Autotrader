"""Rule definitions for GemScore alerts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import yaml


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


def _normalise_rule(raw: Mapping[str, object]) -> AlertRule:
    where = raw.get("where", {})
    channels = tuple(raw.get("channels", ()))
    return AlertRule(
        id=str(raw["id"]),
        description=str(raw.get("description", "")),
        score_min=float(where.get("gem_score_min", 0.0)),
        confidence_min=float(where.get("confidence_min", 0.0)),
        safety_ok=bool(where.get("safety_ok", True)),
        cool_off_minutes=int(raw.get("cool_off_minutes", 60)),
        channels=channels,
        version=str(raw.get("version", "v1")),
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


__all__ = ["AlertRule", "DEFAULT_RULES", "load_rules"]
