"""Tests for safety heuristics."""

from __future__ import annotations

from src.core import safety


def test_evaluate_contract_applies_deductions() -> None:
    report = safety.evaluate_contract(
        {"honeypot": True, "owner_can_mint": False, "unverified": True},
        severity="low",
    )
    assert report.score < 1.0
    assert report.flags["honeypot"] is True


def test_liquidity_guardrail_threshold() -> None:
    assert safety.liquidity_guardrail(60_000) is True
    assert safety.liquidity_guardrail(10_000) is False


def test_apply_penalties_adjusts_feature_vector() -> None:
    base = {"LiquidityDepth": 0.9, "TokenomicsRisk": 0.9, "ContractSafety": 1.0}
    report = safety.SafetyReport(score=0.3, severity="medium", findings=["owner_can_mint"], flags={})
    adjusted = safety.apply_penalties(base, report, liquidity_ok=False)
    assert adjusted["ContractSafety"] == 0.3
    assert adjusted["LiquidityDepth"] <= 0.3
    assert adjusted["TokenomicsRisk"] <= 0.4
