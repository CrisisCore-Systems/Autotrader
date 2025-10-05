"""Safety heuristics and static checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SafetyReport:
    score: float
    severity: str
    findings: List[str]
    flags: Dict[str, bool]


CRITICAL_FLAGS = {
    "honeypot": 1.0,
    "owner_can_mint": 0.8,
    "owner_can_withdraw": 0.8,
    "unverified": 0.6,
}


def evaluate_contract(findings: Dict[str, bool], severity: str) -> SafetyReport:
    """Convert contract analyzer findings into normalized safety score."""

    deductions = 0.0
    active_flags: Dict[str, bool] = {}
    for flag, weight in CRITICAL_FLAGS.items():
        state = bool(findings.get(flag, False))
        active_flags[flag] = state
        if state:
            deductions += weight

    score = max(0.0, 1.0 - deductions)
    severity = severity.lower()
    if severity == "high":
        score = 0.0
    elif severity == "medium":
        score = min(score, 0.4)
    elif severity == "low":
        score = min(score, 0.7)

    return SafetyReport(score=score, severity=severity, findings=[k for k, v in active_flags.items() if v], flags=active_flags)


def liquidity_guardrail(liquidity_usd: float, threshold: float = 50_000) -> bool:
    """Check whether liquidity exceeds minimum viable threshold."""

    return liquidity_usd >= threshold


def apply_penalties(features: Dict[str, float], safety_report: SafetyReport, *, liquidity_ok: bool) -> Dict[str, float]:
    """Mutate feature vector with safety penalties."""

    adjusted = dict(features)
    adjusted["ContractSafety"] = safety_report.score
    if not liquidity_ok:
        adjusted["LiquidityDepth"] = min(adjusted.get("LiquidityDepth", 0.0), 0.3)
    if "owner_can_mint" in safety_report.findings:
        adjusted["TokenomicsRisk"] = min(adjusted.get("TokenomicsRisk", 1.0), 0.4)
    return adjusted
