"""Safety heuristics and static checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Any


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
    if adjusted.get("UpcomingUnlockRisk", features.get("UpcomingUnlockRisk", 0.0)) >= 0.5:
        adjusted["TokenomicsRisk"] = min(adjusted.get("TokenomicsRisk", 1.0), 0.4)
    return adjusted


class SafetyAnalyzer:
    """Safety analyzer for contract analysis."""

    def __init__(self):
        """Initialize safety analyzer."""
        pass

    def analyze_contract(self, contract_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze contract safety.

        Args:
            contract_data: Contract data dictionary

        Returns:
            Analysis result with score, severity, and findings
        """
        # Extract findings from contract data
        findings = {}

        # Check if contract is verified
        is_verified = str(contract_data.get("IsVerified", "false")).lower() == "true"
        findings["unverified"] = not is_verified

        # Check source code for dangerous patterns
        source = str(contract_data.get("SourceCode", "")).lower()
        abi = str(contract_data.get("ABI", "")).lower()

        findings["owner_can_mint"] = "function mint" in source or "mint(" in abi
        findings["owner_can_withdraw"] = "withdraw" in source or "withdraw" in abi

        # Check for honeypot indicators
        tags = str(contract_data.get("SecurityTag", "")).lower()
        findings["honeypot"] = "honeypot" in tags

        # Get severity
        severity = str(contract_data.get("SecuritySeverity",
                       contract_data.get("severity", "none"))).lower()

        # Evaluate contract
        report = evaluate_contract(findings, severity=severity)

        return {
            "score": report.score,
            "severity": report.severity,
            "findings": report.findings,
        }
