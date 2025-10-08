"""Tests for summary report functionality."""

from __future__ import annotations

import pytest
from src.cli.summary_report import SummaryReportGenerator, SummaryReport
from src.core.scoring import GemScoreResult
from src.core.safety import SafetyReport


@pytest.fixture
def sample_gem_score() -> GemScoreResult:
    """Create a sample GemScore result."""
    return GemScoreResult(
        score=75.0,
        confidence=82.0,
        contributions={
            "AccumulationScore": 0.16,
            "SentimentScore": 0.10,
            "OnchainActivity": 0.08,
            "LiquidityDepth": 0.05,
            "TokenomicsRisk": 0.08,
            "ContractSafety": 0.09,
            "NarrativeMomentum": 0.06,
            "CommunityGrowth": 0.05,
        },
    )


@pytest.fixture
def sample_features() -> dict[str, float]:
    """Create sample feature values."""
    return {
        "AccumulationScore": 0.80,
        "SentimentScore": 0.70,
        "OnchainActivity": 0.55,
        "LiquidityDepth": 0.50,
        "TokenomicsRisk": 0.65,
        "ContractSafety": 0.75,
        "NarrativeMomentum": 0.75,
        "CommunityGrowth": 0.60,
        "Recency": 0.85,
        "DataCompleteness": 0.80,
        "Volatility": 0.45,
    }


@pytest.fixture
def sample_safety_report() -> SafetyReport:
    """Create a sample safety report."""
    return SafetyReport(
        score=0.75,
        severity="low",
        flags={
            "unverified": False,
            "owner_can_mint": False,
            "owner_can_withdraw": True,
            "honeypot": False,
        },
    )


def test_generate_report_basic(
    sample_gem_score: GemScoreResult,
    sample_features: dict[str, float],
    sample_safety_report: SafetyReport,
) -> None:
    """Test basic report generation."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    report = generator.generate_report(
        token_symbol="TEST",
        gem_score=sample_gem_score,
        features=sample_features,
        safety_report=sample_safety_report,
        final_score=72.5,
    )
    
    assert report.token_symbol == "TEST"
    assert report.gem_score == 75.0
    assert report.confidence == 82.0
    assert report.final_score == 72.5
    assert len(report.top_positive_drivers) > 0
    assert len(report.recommendations) > 0


def test_analyze_drivers(
    sample_gem_score: GemScoreResult,
    sample_features: dict[str, float],
) -> None:
    """Test driver analysis."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    top_positive, top_negative = generator._analyze_drivers(
        sample_gem_score.contributions,
        sample_features,
    )
    
    # Should have positive drivers
    assert len(top_positive) > 0
    # AccumulationScore should be top positive
    assert top_positive[0][0] == "AccumulationScore"
    # Should have negative drivers
    assert len(top_negative) > 0


def test_extract_risk_flags(sample_safety_report: SafetyReport) -> None:
    """Test risk flag extraction."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    features = {
        "LiquidityDepth": 0.25,  # Low liquidity
        "TokenomicsRisk": 0.35,  # High risk
    }
    
    flags = generator._extract_risk_flags(
        sample_safety_report,
        features,
        flagged=False,
    )
    
    # Should detect low liquidity
    assert any("liquidity" in flag.lower() for flag in flags)
    # Should detect tokenomics risk
    assert any("tokenomics" in flag.lower() for flag in flags)


def test_generate_warnings(
    sample_gem_score: GemScoreResult,
    sample_features: dict[str, float],
    sample_safety_report: SafetyReport,
) -> None:
    """Test warning generation."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    # Create low confidence score
    low_confidence_score = GemScoreResult(
        score=75.0,
        confidence=45.0,
        contributions=sample_gem_score.contributions,
    )
    
    warnings = generator._generate_warnings(
        low_confidence_score,
        sample_features,
        sample_safety_report,
        {},
        {},
        {},
    )
    
    # Should warn about low confidence
    assert any("confidence" in warning.lower() for warning in warnings)


def test_generate_recommendations(
    sample_gem_score: GemScoreResult,
    sample_features: dict[str, float],
    sample_safety_report: SafetyReport,
) -> None:
    """Test recommendation generation."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    top_negative = [
        ("LiquidityDepth", 0.05),
        ("ContractSafety", 0.03),
    ]
    
    recommendations = generator._generate_recommendations(
        sample_gem_score,
        sample_features,
        sample_safety_report,
        top_negative,
    )
    
    # Should have recommendations
    assert len(recommendations) > 0
    # Should recommend liquidity improvement
    assert any("liquidity" in rec.lower() for rec in recommendations)
    # Should always recommend verification
    assert any("verify" in rec.lower() for rec in recommendations)


def test_export_json(
    sample_gem_score: GemScoreResult,
    sample_features: dict[str, float],
    sample_safety_report: SafetyReport,
) -> None:
    """Test JSON export."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    report = generator.generate_report(
        token_symbol="TEST",
        gem_score=sample_gem_score,
        features=sample_features,
        safety_report=sample_safety_report,
        final_score=72.5,
    )
    
    json_data = generator.export_json(report)
    
    assert json_data["token_symbol"] == "TEST"
    assert "scores" in json_data
    assert "drivers" in json_data
    assert "risk_flags" in json_data
    assert "warnings" in json_data
    assert "recommendations" in json_data
    assert json_data["scores"]["gem_score"] == 75.0


def test_format_feature_name() -> None:
    """Test feature name formatting."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    assert generator._format_feature_name("AccumulationScore") == "Accumulation Score"
    assert generator._format_feature_name("LiquidityDepth") == "Liquidity Depth"
    assert generator._format_feature_name("OnchainActivity") == "Onchain Activity"


def test_color_disabled() -> None:
    """Test that colors are disabled when requested."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    colored = generator._color("test", "red")
    assert colored == "test"  # No ANSI codes


def test_color_enabled() -> None:
    """Test that colors work when enabled."""
    generator = SummaryReportGenerator(color_enabled=True)
    
    colored = generator._color("test", "red", bold=True)
    assert "\033[" in colored  # Contains ANSI codes
    assert colored != "test"


def test_high_risk_score() -> None:
    """Test report generation with high risk score."""
    generator = SummaryReportGenerator(color_enabled=False)
    
    # Create high risk scenario
    low_safety = SafetyReport(
        score=0.35,
        severity="high",
        flags={
            "unverified": True,
            "owner_can_mint": True,
            "owner_can_withdraw": True,
            "honeypot": False,
        },
    )
    
    low_gem_score = GemScoreResult(
        score=45.0,
        confidence=60.0,
        contributions={"AccumulationScore": 0.09},
    )
    
    features = {"ContractSafety": 0.35, "LiquidityDepth": 0.20}
    
    report = generator.generate_report(
        token_symbol="RISKY",
        gem_score=low_gem_score,
        features=features,
        safety_report=low_safety,
        final_score=40.0,
    )
    
    # Should have multiple risk flags
    assert len(report.risk_flags) > 0
    # Should recommend caution
    assert any("high risk" in rec.lower() or "caution" in rec.lower() 
               for rec in report.recommendations)
