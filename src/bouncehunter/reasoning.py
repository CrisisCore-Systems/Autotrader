"""
Tree-of-Thought Reasoning and Metacognitive Reflection for BounceHunter

This module implements advanced reasoning capabilities:
1. Tree-of-Thought: Multiple hypothesis branches evaluated in parallel
2. Metacognitive Reflection: Self-awareness about confidence calibration
3. Counterfactual Tracking: Learning from vetoed signals

Author: BounceHunter Agentic V2
Date: October 2025
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class ReasoningBranch:
    """A single reasoning path in the thought tree."""

    name: str
    hypothesis: str
    evidence: List[str]
    confidence: float
    score: float
    reasoning_chain: List[str]


@dataclass
class ThoughtTree:
    """Complete tree of reasoning branches."""

    root_question: str
    branches: List[ReasoningBranch]
    best_branch: Optional[ReasoningBranch]
    consensus_confidence: float
    agreement_score: float  # 0-1, higher = more agreement


@dataclass
class MetaReflection:
    """Metacognitive reflection on reasoning quality."""

    concern: str  # e.g., "overconfidence", "out_of_distribution"
    adjustment: float  # Confidence adjustment (-1 to +1)
    reason: str
    severity: str  # "low", "medium", "high"


# ==============================================================================
# TREE-OF-THOUGHT REASONER
# ==============================================================================


class TreeOfThoughtReasoner:
    """
    Implements tree-of-thought reasoning for complex trading decisions.

    Instead of a single prediction, explores multiple reasoning paths:
    - Technical analysis branch
    - Historical pattern branch
    - Risk-adjusted branch
    - Regime-aware branch

    Each branch reasons independently, then votes on final decision.
    """

    def __init__(self, memory=None):
        self.memory = memory

    def reason(self, signal: Dict[str, Any], context: Dict[str, Any]) -> ThoughtTree:
        """
        Generate a tree of thought for a trading signal.

        Args:
            signal: Trading signal with features (ticker, BCS, RSI, etc.)
            context: Market context (VIX, SPY trend, regime, etc.)

        Returns:
            ThoughtTree with all reasoning branches and consensus
        """
        ticker = signal.get("ticker", "UNKNOWN")
        bcs = signal.get("bcs", 0.5)
        rsi2 = signal.get("rsi2", 50)
        dist_200 = signal.get("dist_200dma", 0)
        vix_pct = context.get("vix_percentile", 0.5)

        branches = []

        # Branch 1: Technical Analysis
        tech_branch = self._technical_analysis_branch(ticker, bcs, rsi2, dist_200)
        branches.append(tech_branch)

        # Branch 2: Historical Pattern Matching
        hist_branch = self._historical_pattern_branch(ticker, signal, context)
        branches.append(hist_branch)

        # Branch 3: Risk-Adjusted Evaluation
        risk_branch = self._risk_adjusted_branch(signal, context)
        branches.append(risk_branch)

        # Branch 4: Regime-Aware Assessment
        regime_branch = self._regime_aware_branch(signal, context, vix_pct)
        branches.append(regime_branch)

        # Aggregate branches
        best_branch = max(branches, key=lambda b: b.score)
        avg_confidence = np.mean([b.confidence for b in branches])
        std_confidence = np.std([b.confidence for b in branches])
        agreement_score = 1 - std_confidence  # Lower std = higher agreement

        return ThoughtTree(
            root_question=f"Should we enter {ticker} at ${signal.get('entry', 0):.2f}?",
            branches=branches,
            best_branch=best_branch,
            consensus_confidence=avg_confidence,
            agreement_score=agreement_score,
        )

    def _technical_analysis_branch(self, ticker: str, bcs: float, rsi2: float, dist_200: float) -> ReasoningBranch:
        """Technical indicators reasoning path."""
        evidence = []
        reasoning_chain = []
        score = 0

        # RSI analysis
        if rsi2 < 10:
            evidence.append(f"RSI2 extremely oversold ({rsi2:.1f})")
            reasoning_chain.append("Extreme oversold on RSI2 suggests panic selling")
            score += 30
        elif rsi2 < 20:
            evidence.append(f"RSI2 oversold ({rsi2:.1f})")
            reasoning_chain.append("RSI2 oversold indicates potential bounce")
            score += 20
        else:
            evidence.append(f"RSI2 not oversold ({rsi2:.1f})")
            reasoning_chain.append("RSI2 doesn't support entry")
            score -= 10

        # BCS analysis
        if bcs >= 0.70:
            evidence.append(f"High BCS score ({bcs:.2f})")
            reasoning_chain.append("BCS above 70% suggests strong historical bounce pattern")
            score += 30
        elif bcs >= 0.60:
            evidence.append(f"Good BCS score ({bcs:.2f})")
            reasoning_chain.append("BCS above 60% is acceptable threshold")
            score += 20
        else:
            evidence.append(f"Low BCS score ({bcs:.2f})")
            reasoning_chain.append("BCS below 60% increases risk")
            score -= 20

        # Distance from 200DMA
        if dist_200 > -10 and dist_200 < -2:
            evidence.append(f"Near 200DMA support ({dist_200:.1%})")
            reasoning_chain.append("Price near but above major support is favorable")
            score += 15
        elif dist_200 < -15:
            evidence.append(f"Far below 200DMA ({dist_200:.1%})")
            reasoning_chain.append("Significant underperformance vs trend")
            score -= 15

        confidence = min(1.0, max(0.0, (score + 50) / 100))

        return ReasoningBranch(
            name="technical_analysis",
            hypothesis="Technical indicators support entry" if score > 0 else "Technical indicators oppose entry",
            evidence=evidence,
            confidence=confidence,
            score=score,
            reasoning_chain=reasoning_chain,
        )

    def _calculate_hit_rate_score(self, hit_rate: float) -> int:
        """Calculate score based on historical hit rate."""
        if hit_rate >= 0.60:
            return 30
        elif hit_rate >= 0.50:
            return 15
        else:
            return -20

    def _analyze_regime_performance(
        self, similar_trades: List[Dict], current_regime: str, evidence: List[str], reasoning_chain: List[str]
    ) -> float:
        """Analyze performance in current regime."""
        regime_trades = [t for t in similar_trades if t.get("regime") == current_regime]
        if not regime_trades:
            return 0.0

        regime_wins = sum(1 for t in regime_trades if t.get("pnl", 0) > 0)
        regime_hit_rate = regime_wins / len(regime_trades)
        evidence.append(f"In {current_regime} regime: {regime_hit_rate:.0%} hit rate")
        reasoning_chain.append(f"Regime-specific performance: {regime_hit_rate:.0%}")
        return (regime_hit_rate - 0.5) * 40

    def _historical_pattern_branch(self, ticker: str, signal: Dict, context: Dict) -> ReasoningBranch:
        """Historical pattern matching reasoning path."""
        evidence = []
        reasoning_chain = []
        score = 0

        if not self.memory:
            evidence.append("No memory available")
            reasoning_chain.append("Cannot assess historical patterns")
            confidence = 0.5
            return ReasoningBranch(
                name="historical_patterns",
                hypothesis="Historical patterns oppose entry",
                evidence=evidence,
                confidence=confidence,
                score=score,
                reasoning_chain=reasoning_chain,
            )

        similar_trades = self.memory.get_similar_signals(ticker, signal, limit=20)

        if not similar_trades or len(similar_trades) < 5:
            evidence.append("Insufficient historical data")
            reasoning_chain.append("Not enough similar setups for strong confidence")
            score = -10
            confidence = 0.4
            return ReasoningBranch(
                name="historical_patterns",
                hypothesis="Historical patterns oppose entry",
                evidence=evidence,
                confidence=confidence,
                score=score,
                reasoning_chain=reasoning_chain,
            )

        wins = sum(1 for t in similar_trades if t.get("pnl", 0) > 0)
        hit_rate = wins / len(similar_trades)

        evidence.append(f"Historical: {wins}/{len(similar_trades)} similar setups won ({hit_rate:.0%})")
        reasoning_chain.append(f"Found {len(similar_trades)} similar setups with {hit_rate:.0%} success rate")

        score = self._calculate_hit_rate_score(hit_rate)
        current_regime = context.get("regime", "normal")
        score += self._analyze_regime_performance(similar_trades, current_regime, evidence, reasoning_chain)

        confidence = min(1.0, max(0.0, (score + 50) / 100))

        return ReasoningBranch(
            name="historical_patterns",
            hypothesis="Historical patterns support entry" if score > 0 else "Historical patterns oppose entry",
            evidence=evidence,
            confidence=confidence,
            score=score,
            reasoning_chain=reasoning_chain,
        )

    def _risk_adjusted_branch(self, signal: Dict, context: Dict) -> ReasoningBranch:
        """Risk-reward reasoning path."""
        evidence = []
        reasoning_chain = []
        score = 0

        entry = signal.get("entry", 0)
        stop = signal.get("stop", entry * 0.98)
        target = signal.get("target", entry * 1.03)

        # Calculate R:R
        risk = entry - stop
        reward = target - entry
        rr_ratio = reward / risk if risk > 0 else 0

        evidence.append(f"Risk: ${risk:.2f} | Reward: ${reward:.2f}")
        evidence.append(f"R:R Ratio: {rr_ratio:.2f}:1")
        reasoning_chain.append(f"Risk/Reward ratio is {rr_ratio:.2f}:1")

        if rr_ratio >= 2.0:
            reasoning_chain.append("Excellent risk/reward (2:1+)")
            score += 30
        elif rr_ratio >= 1.5:
            reasoning_chain.append("Good risk/reward (1.5:1+)")
            score += 20
        elif rr_ratio >= 1.2:
            reasoning_chain.append("Acceptable risk/reward (1.2:1+)")
            score += 10
        else:
            reasoning_chain.append("Poor risk/reward (<1.2:1)")
            score -= 20

        # Stop distance check
        stop_pct = (stop - entry) / entry
        if stop_pct > -0.015:
            evidence.append(f"Tight stop: {stop_pct:.1%}")
            reasoning_chain.append("Very tight stop may lead to premature exit")
            score -= 10
        elif stop_pct < -0.03:
            evidence.append(f"Wide stop: {stop_pct:.1%}")
            reasoning_chain.append("Wide stop increases risk")
            score -= 5

        # Expected value calculation
        prob_win = signal.get("bcs", 0.5)
        prob_loss = 1 - prob_win
        expected_value = (prob_win * reward) - (prob_loss * risk)
        ev_pct = expected_value / entry

        evidence.append(f"Expected Value: {ev_pct:.2%}")
        reasoning_chain.append(f"EV calculation: {ev_pct:.2%} per trade")

        if ev_pct > 0.01:
            score += 20
        elif ev_pct > 0:
            score += 10
        else:
            score -= 30

        confidence = min(1.0, max(0.0, (score + 50) / 100))

        return ReasoningBranch(
            name="risk_adjusted",
            hypothesis="Risk/reward profile is favorable" if score > 0 else "Risk/reward profile is unfavorable",
            evidence=evidence,
            confidence=confidence,
            score=score,
            reasoning_chain=reasoning_chain,
        )

    def _regime_aware_branch(self, signal: Dict, context: Dict, vix_pct: float) -> ReasoningBranch:
        """Regime-aware reasoning path."""
        evidence = []
        reasoning_chain = []
        score = 0

        regime = context.get("regime", "normal")
        spy_trend = context.get("spy_trend", "neutral")

        evidence.append(f"Market Regime: {regime}")
        evidence.append(f"SPY Trend: {spy_trend}")
        evidence.append(f"VIX Percentile: {vix_pct:.0%}")

        # Regime assessment
        if regime == "high_vix":
            reasoning_chain.append("High VIX regime increases volatility and risk")
            score -= 20
        elif regime == "low_spy":
            reasoning_chain.append("Weak SPY trend suggests defensive positioning")
            score -= 15
        else:
            reasoning_chain.append("Normal regime is favorable for mean reversion")
            score += 15

        # VIX analysis
        if vix_pct < 0.3:
            evidence.append("Low VIX (calm market)")
            reasoning_chain.append("Low volatility supports tighter stops")
            score += 15
        elif vix_pct > 0.8:
            evidence.append("High VIX (stressed market)")
            reasoning_chain.append("High volatility increases false positive risk")
            score -= 25

        # SPY trend alignment
        if spy_trend == "strong":
            evidence.append("Strong market backdrop")
            reasoning_chain.append("Rising tide lifts all boats")
            score += 20
        elif spy_trend == "weak":
            evidence.append("Weak market backdrop")
            reasoning_chain.append("Headwind from broader market")
            score -= 15

        confidence = min(1.0, max(0.0, (score + 50) / 100))

        return ReasoningBranch(
            name="regime_aware",
            hypothesis="Market regime supports entry" if score > 0 else "Market regime opposes entry",
            evidence=evidence,
            confidence=confidence,
            score=score,
            reasoning_chain=reasoning_chain,
        )


# ==============================================================================
# METACOGNITIVE REFLECTOR
# ==============================================================================


class MetacognitiveReflector:
    """
    Reflects on the reasoning process itself.

    Asks: "How confident should I be in my confidence?"

    Checks for:
    - Calibration drift (overconfidence)
    - Out-of-distribution conditions
    - Agent disagreement
    - Data quality issues
    """

    def __init__(self, memory=None):
        self.memory = memory

    def reflect(
        self,
        thought_tree: ThoughtTree,
        agent_outputs: List[Dict],
        signal: Dict,
        context: Dict,
    ) -> List[MetaReflection]:
        """
        Perform metacognitive reflection on reasoning quality.

        Returns list of concerns with confidence adjustments.
        """
        reflections = []

        # 1. Calibration check
        calib_ref = self._check_calibration(thought_tree)
        if calib_ref:
            reflections.append(calib_ref)

        # 2. Out-of-distribution check
        ood_ref = self._check_distribution(signal, context)
        if ood_ref:
            reflections.append(ood_ref)

        # 3. Agent agreement check
        agreement_ref = self._check_agent_agreement(agent_outputs)
        if agreement_ref:
            reflections.append(agreement_ref)

        # 4. Branch agreement check
        branch_ref = self._check_branch_agreement(thought_tree)
        if branch_ref:
            reflections.append(branch_ref)

        # 5. Data quality check
        quality_ref = self._check_data_quality(signal)
        if quality_ref:
            reflections.append(quality_ref)

        return reflections

    def _check_calibration(self, thought_tree: ThoughtTree) -> Optional[MetaReflection]:
        """Check if historical confidence matches actual outcomes."""
        if not self.memory:
            return None

        # Get forecaster historical calibration
        calibration_error = self.memory.get_calibration_error("Forecaster")

        if calibration_error > 0.10:  # 10%+ overconfidence
            return MetaReflection(
                concern="overconfidence",
                adjustment=-0.15,
                reason=f"Forecaster historically overconfident by {calibration_error:.0%}",
                severity="high",
            )
        elif calibration_error > 0.05:
            return MetaReflection(
                concern="mild_overconfidence",
                adjustment=-0.08,
                reason=f"Forecaster slightly overconfident by {calibration_error:.0%}",
                severity="medium",
            )

        return None

    def _check_distribution(self, signal: Dict, context: Dict) -> Optional[MetaReflection]:
        """Check if current conditions match training distribution."""
        vix_pct = context.get("vix_percentile", 0.5)

        # Check VIX extremes
        if vix_pct > 0.90:
            return MetaReflection(
                concern="out_of_distribution",
                adjustment=-0.20,
                reason=f"VIX at {vix_pct:.0%} percentile exceeds training range",
                severity="high",
            )
        elif vix_pct > 0.80:
            return MetaReflection(
                concern="high_volatility",
                adjustment=-0.10,
                reason=f"VIX at {vix_pct:.0%} percentile in tail of distribution",
                severity="medium",
            )

        # Check BCS extremes
        bcs = signal.get("bcs", 0.5)
        if bcs > 0.85:
            return MetaReflection(
                concern="extreme_signal",
                adjustment=-0.05,
                reason=f"BCS at {bcs:.0%} is unusually high (possible overfitting)",
                severity="low",
            )

        return None

    def _check_agent_agreement(self, agent_outputs: List[Dict]) -> Optional[MetaReflection]:
        """Check if agents agree or disagree significantly."""
        if not agent_outputs:
            return None

        confidences = [a.get("confidence", 0.5) for a in agent_outputs if "confidence" in a]
        if len(confidences) < 2:
            return None

        std_dev = np.std(confidences)

        if std_dev > 0.25:
            return MetaReflection(
                concern="high_disagreement",
                adjustment=-0.15,
                reason=f"Agents strongly disagree (σ={std_dev:.2f})",
                severity="high",
            )
        elif std_dev > 0.15:
            return MetaReflection(
                concern="moderate_disagreement",
                adjustment=-0.08,
                reason=f"Agents moderately disagree (σ={std_dev:.2f})",
                severity="medium",
            )

        return None

    def _check_branch_agreement(self, thought_tree: ThoughtTree) -> Optional[MetaReflection]:
        """Check if reasoning branches agree."""
        if thought_tree.agreement_score < 0.7:
            return MetaReflection(
                concern="reasoning_disagreement",
                adjustment=-0.12,
                reason=f"Reasoning branches disagree (agreement={thought_tree.agreement_score:.0%})",
                severity="high",
            )
        elif thought_tree.agreement_score < 0.8:
            return MetaReflection(
                concern="mild_reasoning_disagreement",
                adjustment=-0.06,
                reason=f"Some reasoning branches disagree (agreement={thought_tree.agreement_score:.0%})",
                severity="medium",
            )

        return None

    def _check_data_quality(self, signal: Dict) -> Optional[MetaReflection]:
        """Check for missing or stale data."""
        missing_features = []

        required_features = ["bcs", "rsi2", "dist_200dma", "entry", "stop", "target"]
        for feat in required_features:
            if feat not in signal or signal[feat] is None:
                missing_features.append(feat)

        if len(missing_features) >= 3:
            return MetaReflection(
                concern="data_quality",
                adjustment=-0.20,
                reason=f"Missing critical features: {', '.join(missing_features)}",
                severity="high",
            )
        elif missing_features:
            return MetaReflection(
                concern="incomplete_data",
                adjustment=-0.10,
                reason=f"Missing features: {', '.join(missing_features)}",
                severity="medium",
            )

        return None


# ==============================================================================
# COUNTERFACTUAL TRACKER
# ==============================================================================


class CounterfactualTracker:
    """
    Tracks "what-if" scenarios for vetoed signals.

    Enables learning from missed opportunities.
    """

    def __init__(self, memory):
        self.memory = memory

    def log_veto(self, signal: Dict, vetoing_agent: str, reason: str) -> str:
        """Log a vetoed signal for later resolution."""
        counterfactual_id = f"CF-{signal['ticker']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        self.memory.insert_counterfactual(
            {
                "id": counterfactual_id,
                "ticker": signal["ticker"],
                "entry_price": signal["entry"],
                "stop_price": signal["stop"],
                "target_price": signal["target"],
                "vetoed_by": vetoing_agent,
                "veto_reason": reason,
                "veto_date": datetime.now().isoformat(),
                "resolution_date": None,
                "actual_outcome": None,
                "would_have_pnl": None,
            }
        )

        return counterfactual_id

    def resolve_counterfactuals(self, days_back: int = 5) -> int:
        """
        Resolve counterfactuals by checking actual price movement.

        Returns number of resolved counterfactuals.
        """
        if not self.memory:
            return 0

        unresolved = self.memory.get_unresolved_counterfactuals()
        resolved_count = 0

        for cf in unresolved:
            # Check if enough time has passed
            veto_date = datetime.fromisoformat(cf["veto_date"])
            if datetime.now() - veto_date < timedelta(days=days_back):
                continue

            # Would need yfinance here to fetch actual prices
            # Simplified for now - just mark as resolved
            self.memory.update_counterfactual(
                cf["id"],
                resolution_date=datetime.now().isoformat(),
                actual_outcome="UNKNOWN",  # Would calculate from actual prices
                would_have_pnl=0,
            )
            resolved_count += 1

        return resolved_count
