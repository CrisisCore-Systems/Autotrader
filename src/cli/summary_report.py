"""CLI summary report generator for GemScore analysis.

Provides a simple, trust-building summary of:
- Overall score
- Top positive drivers
- Top negative drivers
- Risk flags and warnings
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.core.scoring import GemScoreResult, WEIGHTS
from src.core.safety import SafetyReport


@dataclass
class SummaryReport:
    """Summary report data structure."""
    
    token_symbol: str
    gem_score: float
    confidence: float
    final_score: float
    top_positive_drivers: List[tuple[str, float]]
    top_negative_drivers: List[tuple[str, float]]
    risk_flags: List[str]
    warnings: List[str]
    recommendations: List[str]
    timestamp: str
    metadata: Dict[str, Any]


class SummaryReportGenerator:
    """Generate trust-building summary reports."""
    
    def __init__(self, color_enabled: bool = True):
        """Initialize report generator.
        
        Args:
            color_enabled: Enable terminal colors
        """
        self.color_enabled = color_enabled and sys.stdout.isatty()
    
    def generate_report(
        self,
        token_symbol: str,
        gem_score: GemScoreResult,
        features: Dict[str, float],
        safety_report: SafetyReport,
        final_score: float,
        sentiment_metrics: Optional[Dict[str, float]] = None,
        technical_metrics: Optional[Dict[str, float]] = None,
        security_metrics: Optional[Dict[str, float]] = None,
        flagged: bool = False,
        debug_info: Optional[Dict[str, float]] = None,
    ) -> SummaryReport:
        """Generate a summary report from scan results.
        
        Args:
            token_symbol: Token symbol
            gem_score: GemScore result
            features: Feature dictionary
            safety_report: Safety report
            final_score: Final composite score
            sentiment_metrics: Sentiment metrics (NVI, etc.)
            technical_metrics: Technical metrics (APS, RRR, etc.)
            security_metrics: Security metrics (ERR, etc.)
            flagged: Whether asset is flagged for review
            debug_info: Additional debug information
        
        Returns:
            Summary report
        """
        # Analyze top drivers
        top_positive, top_negative = self._analyze_drivers(
            gem_score.contributions,
            features,
        )
        
        # Extract risk flags
        risk_flags = self._extract_risk_flags(
            safety_report,
            features,
            flagged,
        )
        
        # Generate warnings
        warnings = self._generate_warnings(
            gem_score,
            features,
            safety_report,
            sentiment_metrics or {},
            technical_metrics or {},
            security_metrics or {},
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            gem_score,
            features,
            safety_report,
            top_negative,
        )
        
        # Build metadata
        metadata = {
            "flagged": flagged,
            "safety_score": safety_report.score,
            "safety_severity": safety_report.severity,
            "sentiment_metrics": sentiment_metrics or {},
            "technical_metrics": technical_metrics or {},
            "security_metrics": security_metrics or {},
            "debug": debug_info or {},
        }
        
        return SummaryReport(
            token_symbol=token_symbol,
            gem_score=gem_score.score,
            confidence=gem_score.confidence,
            final_score=final_score,
            top_positive_drivers=top_positive,
            top_negative_drivers=top_negative,
            risk_flags=risk_flags,
            warnings=warnings,
            recommendations=recommendations,
            timestamp=datetime.now().isoformat(),
            metadata=metadata,
        )
    
    def _analyze_drivers(
        self,
        contributions: Dict[str, float],
        features: Dict[str, float],
    ) -> tuple[List[tuple[str, float]], List[tuple[str, float]]]:
        """Analyze top positive and negative drivers.
        
        Args:
            contributions: Feature contributions to score
            features: Raw feature values
        
        Returns:
            (top_positive_drivers, top_negative_drivers)
        """
        # Calculate normalized impact for each feature
        driver_impacts = []
        
        for feature_name, contribution in contributions.items():
            feature_value = features.get(feature_name, 0.0)
            weight = WEIGHTS.get(feature_name, 0.0)
            
            # Impact is the contribution relative to potential maximum
            potential_max = weight * 1.0  # If feature was 1.0
            impact_score = contribution / potential_max if potential_max > 0 else 0.0
            
            driver_impacts.append((
                feature_name,
                contribution,
                impact_score,
                feature_value,
            ))
        
        # Sort by contribution (absolute value)
        driver_impacts.sort(key=lambda x: abs(x[1]), reverse=True)
        
        # Split into positive and negative
        positive = [(name, contrib) for name, contrib, _, val in driver_impacts if contrib > 0][:5]
        
        # For negative, find features with low values relative to their weight
        negative_candidates = []
        for feature_name, weight in WEIGHTS.items():
            feature_value = features.get(feature_name, 0.0)
            # Opportunity loss = what we could have gained
            potential_contribution = weight * 1.0
            actual_contribution = contributions.get(feature_name, 0.0)
            loss = potential_contribution - actual_contribution
            
            if loss > 0.01:  # Threshold for significance
                negative_candidates.append((feature_name, loss, feature_value))
        
        negative_candidates.sort(key=lambda x: x[1], reverse=True)
        negative = [(name, loss) for name, loss, _ in negative_candidates[:5]]
        
        return positive, negative
    
    def _extract_risk_flags(
        self,
        safety_report: SafetyReport,
        features: Dict[str, float],
        flagged: bool,
    ) -> List[str]:
        """Extract risk flags from safety report and features.
        
        Args:
            safety_report: Safety report
            features: Feature values
            flagged: Whether flagged for review
        
        Returns:
            List of risk flag messages
        """
        flags = []
        
        # Safety flags
        if safety_report.flags:
            for flag_name, flag_value in safety_report.flags.items():
                if flag_value:
                    flags.append(f"⚠️  Contract: {flag_name.replace('_', ' ').title()}")
        
        # Low safety score
        if safety_report.score < 0.5:
            flags.append(f"🔴 Low safety score: {safety_report.score:.2f}")
        elif safety_report.score < 0.7:
            flags.append(f"🟡 Moderate safety score: {safety_report.score:.2f}")
        
        # Severity warnings
        if safety_report.severity in ("high", "critical"):
            flags.append(f"🚨 {safety_report.severity.upper()} severity issues detected")
        
        # Low liquidity
        liquidity_depth = features.get("LiquidityDepth", 0.0)
        if liquidity_depth < 0.3:
            flags.append("💧 Low liquidity - high slippage risk")
        
        # High tokenomics risk
        tokenomics_risk = features.get("TokenomicsRisk", 0.0)
        if tokenomics_risk < 0.4:
            flags.append("📊 High tokenomics risk - potential unlock pressure")
        
        # Low confidence
        # (handled in warnings)
        
        return flags
    
    def _generate_warnings(
        self,
        gem_score: GemScoreResult,
        features: Dict[str, float],
        safety_report: SafetyReport,
        sentiment_metrics: Dict[str, float],
        technical_metrics: Dict[str, float],
        security_metrics: Dict[str, float],
    ) -> List[str]:
        """Generate warning messages.
        
        Args:
            gem_score: GemScore result
            features: Feature values
            safety_report: Safety report
            sentiment_metrics: Sentiment metrics
            technical_metrics: Technical metrics
            security_metrics: Security metrics
        
        Returns:
            List of warnings
        """
        warnings = []
        
        # Low confidence warning
        if gem_score.confidence < 50:
            warnings.append(f"⚡ Low confidence ({gem_score.confidence:.1f}%) - data may be stale or incomplete")
        elif gem_score.confidence < 70:
            warnings.append(f"⚡ Moderate confidence ({gem_score.confidence:.1f}%) - verify with additional sources")
        
        # Data completeness
        completeness = features.get("DataCompleteness", 0.0)
        if completeness < 0.6:
            warnings.append(f"📊 Limited data coverage ({completeness*100:.0f}%)")
        
        # High volatility
        volatility = features.get("Volatility", 0.0)
        if volatility > 0.7:
            warnings.append("📈 High volatility detected - expect significant price swings")
        
        # Negative sentiment
        sentiment_score = features.get("SentimentScore", 0.5)
        if sentiment_score < 0.3:
            warnings.append(f"💬 Negative sentiment ({sentiment_score:.2f})")
        
        # Low on-chain activity
        onchain_activity = features.get("OnchainActivity", 0.0)
        if onchain_activity < 0.2:
            warnings.append("⛓️  Low on-chain activity - limited network usage")
        
        # High ERR (Exploit Risk Rating)
        err = security_metrics.get("ERR", 0.0)
        if err > 0.7:
            warnings.append(f"🔒 High exploit risk rating ({err:.2f})")
        
        return warnings
    
    def _generate_recommendations(
        self,
        gem_score: GemScoreResult,
        features: Dict[str, float],
        safety_report: SafetyReport,
        top_negative_drivers: List[tuple[str, float]],
    ) -> List[str]:
        """Generate actionable recommendations.
        
        Args:
            gem_score: GemScore result
            features: Feature values
            safety_report: Safety report
            top_negative_drivers: Top negative drivers
        
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # Score-based recommendations
        if gem_score.score >= 80:
            recommendations.append("✅ Strong overall score - continue monitoring")
        elif gem_score.score >= 60:
            recommendations.append("⚠️  Moderate score - review risk flags before proceeding")
        else:
            recommendations.append("❌ Low score - high risk, extensive due diligence required")
        
        # Safety-based recommendations
        if safety_report.score < 0.7:
            recommendations.append("🔍 Contract safety concerns - verify with independent audit")
        
        # Feature-specific recommendations
        for feature_name, _ in top_negative_drivers[:3]:
            if feature_name == "LiquidityDepth":
                recommendations.append("💧 Consider deeper liquidity pools to reduce slippage risk")
            elif feature_name == "ContractSafety":
                recommendations.append("🔐 Review contract code and obtain security audit")
            elif feature_name == "AccumulationScore":
                recommendations.append("📊 Monitor whale activity and accumulation patterns")
            elif feature_name == "SentimentScore":
                recommendations.append("💬 Review recent news and community sentiment")
            elif feature_name == "OnchainActivity":
                recommendations.append("⛓️  Track on-chain metrics for activity trends")
        
        # Always recommend verification
        recommendations.append("🔬 Always verify findings with independent research")
        
        return recommendations
    
    def print_report(self, report: SummaryReport) -> None:
        """Print report to console with formatting.
        
        Args:
            report: Summary report
        """
        # Header
        self._print_header(f"📊 GemScore Summary Report: {report.token_symbol}")
        print()
        
        # Scores section
        self._print_section("SCORES")
        self._print_score_bar("GemScore", report.gem_score, 100, threshold=70)
        self._print_score_bar("Confidence", report.confidence, 100, threshold=70)
        self._print_score_bar("Final Score", report.final_score, 100, threshold=70)
        print()
        
        # Top drivers section
        self._print_section("TOP POSITIVE DRIVERS")
        if report.top_positive_drivers:
            for i, (name, value) in enumerate(report.top_positive_drivers, 1):
                self._print_driver(f"{i}. {self._format_feature_name(name)}", value, is_positive=True)
        else:
            print("  No significant positive drivers")
        print()
        
        self._print_section("TOP IMPROVEMENT AREAS")
        if report.top_negative_drivers:
            for i, (name, value) in enumerate(report.top_negative_drivers, 1):
                self._print_driver(f"{i}. {self._format_feature_name(name)}", value, is_positive=False)
        else:
            print("  No significant improvement areas")
        print()
        
        # Risk flags section
        self._print_section("RISK FLAGS")
        if report.risk_flags:
            for flag in report.risk_flags:
                print(f"  {flag}")
        else:
            print("  ✅ No critical risk flags")
        print()
        
        # Warnings section
        if report.warnings:
            self._print_section("WARNINGS")
            for warning in report.warnings:
                print(f"  {warning}")
            print()
        
        # Recommendations section
        self._print_section("RECOMMENDATIONS")
        for rec in report.recommendations:
            print(f"  {rec}")
        print()
        
        # Footer
        self._print_footer(report.timestamp)
    
    def _print_header(self, text: str) -> None:
        """Print section header."""
        separator = "=" * 80
        print(separator)
        print(text.center(80))
        print(separator)
    
    def _print_section(self, title: str) -> None:
        """Print section title."""
        print(self._color(f"▶ {title}", "cyan", bold=True))
    
    def _print_footer(self, timestamp: str) -> None:
        """Print report footer."""
        print("-" * 80)
        print(f"Generated: {timestamp}".center(80))
        print("CrisisCore AutoTrader Hidden-Gem Scanner".center(80))
        print("-" * 80)
    
    def _print_score_bar(
        self,
        label: str,
        value: float,
        max_value: float,
        threshold: float = 50,
    ) -> None:
        """Print a score with visual bar.
        
        Args:
            label: Score label
            value: Score value
            max_value: Maximum value
            threshold: Threshold for color coding
        """
        # Normalize to 0-100 scale
        normalized = (value / max_value) * 100
        bar_width = 40
        filled = int((normalized / 100) * bar_width)
        
        # Choose color
        if normalized >= threshold:
            color = "green"
            icon = "✓"
        elif normalized >= threshold * 0.7:
            color = "yellow"
            icon = "!"
        else:
            color = "red"
            icon = "✗"
        
        # Build bar
        bar = "█" * filled + "░" * (bar_width - filled)
        bar_colored = self._color(bar, color)
        
        # Print
        print(f"  {icon} {label:15s} {value:6.1f} [{bar_colored}] {normalized:5.1f}%")
    
    def _print_driver(self, label: str, value: float, is_positive: bool) -> None:
        """Print a driver with impact indicator.
        
        Args:
            label: Driver label
            value: Driver value/impact
            is_positive: Whether this is a positive or negative driver
        """
        # Format value
        if is_positive:
            icon = "↑"
            color = "green"
            formatted_value = f"+{value:.3f}"
        else:
            icon = "↓"
            color = "red"
            formatted_value = f"-{value:.3f}"
        
        # Print with color
        colored_icon = self._color(icon, color)
        colored_value = self._color(formatted_value, color)
        print(f"  {colored_icon} {label:35s} {colored_value}")
    
    def _format_feature_name(self, name: str) -> str:
        """Format feature name for display.
        
        Args:
            name: Feature name
        
        Returns:
            Formatted name
        """
        # Add spaces before capitals
        formatted = ""
        for i, char in enumerate(name):
            if i > 0 and char.isupper():
                formatted += " "
            formatted += char
        
        return formatted
    
    def _color(self, text: str, color: str, bold: bool = False) -> str:
        """Apply color to text if colors are enabled.
        
        Args:
            text: Text to color
            color: Color name
            bold: Whether to make bold
        
        Returns:
            Colored text
        """
        if not self.color_enabled:
            return text
        
        colors = {
            "red": "\033[91m",
            "green": "\033[92m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "magenta": "\033[95m",
            "cyan": "\033[96m",
            "white": "\033[97m",
        }
        
        reset = "\033[0m"
        bold_code = "\033[1m" if bold else ""
        color_code = colors.get(color, "")
        
        return f"{bold_code}{color_code}{text}{reset}"
    
    def export_json(self, report: SummaryReport) -> Dict[str, Any]:
        """Export report as JSON-serializable dictionary.
        
        Args:
            report: Summary report
        
        Returns:
            JSON-serializable dictionary
        """
        return {
            "token_symbol": report.token_symbol,
            "timestamp": report.timestamp,
            "scores": {
                "gem_score": report.gem_score,
                "confidence": report.confidence,
                "final_score": report.final_score,
            },
            "drivers": {
                "top_positive": [
                    {"name": name, "value": value}
                    for name, value in report.top_positive_drivers
                ],
                "top_negative": [
                    {"name": name, "value": value}
                    for name, value in report.top_negative_drivers
                ],
            },
            "risk_flags": report.risk_flags,
            "warnings": report.warnings,
            "recommendations": report.recommendations,
            "metadata": report.metadata,
        }


def generate_summary_cli(
    token_symbol: str,
    gem_score: GemScoreResult,
    features: Dict[str, float],
    safety_report: SafetyReport,
    final_score: float,
    **kwargs,
) -> None:
    """Generate and print summary report (convenience function).
    
    Args:
        token_symbol: Token symbol
        gem_score: GemScore result
        features: Feature dictionary
        safety_report: Safety report
        final_score: Final composite score
        **kwargs: Additional arguments for report generation
    """
    generator = SummaryReportGenerator()
    report = generator.generate_report(
        token_symbol=token_symbol,
        gem_score=gem_score,
        features=features,
        safety_report=safety_report,
        final_score=final_score,
        **kwargs,
    )
    generator.print_report(report)
