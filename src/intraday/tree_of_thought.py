"""
Tree of Thought Reasoning for Long/Short Decision Making

Implements multi-path reasoning to evaluate whether conditions favor:
- LONG positions (bullish signals)
- SHORT positions (bearish signals)
- NEUTRAL (unclear/mixed signals)

Each reasoning path evaluates different market dimensions:
1. Momentum Path: Trend strength and direction
2. Microstructure Path: Order flow and liquidity
3. Volatility Path: Risk regime and stability
4. Regime Path: Market phase and sentiment
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DirectionBias(Enum):
    """Market direction bias from reasoning."""
    STRONG_LONG = 3
    WEAK_LONG = 2
    NEUTRAL = 1
    WEAK_SHORT = -1
    STRONG_SHORT = -2


@dataclass
class ReasoningPath:
    """Single reasoning path evaluation."""
    name: str
    bias: DirectionBias
    confidence: float  # 0-1
    evidence: List[str]
    score: float  # -1 to +1


@dataclass
class ToTDecision:
    """Final decision from Tree of Thought."""
    direction: DirectionBias
    confidence: float
    reasoning_paths: List[ReasoningPath]
    consensus_score: float  # -1 to +1
    action_recommendation: int  # 0-7 (action space)


class TreeOfThoughtReasoner:
    """
    Multi-path reasoning engine for long/short decisions.
    
    Analyzes market state across multiple dimensions and synthesizes
    a consensus direction with confidence levels.
    """
    
    def __init__(
        self,
        momentum_weight: float = 0.35,
        microstructure_weight: float = 0.30,
        volatility_weight: float = 0.20,
        regime_weight: float = 0.15,
    ):
        """
        Initialize ToT reasoner with path weights.
        
        Args:
            momentum_weight: Weight for momentum path
            microstructure_weight: Weight for microstructure path
            volatility_weight: Weight for volatility path
            regime_weight: Weight for regime path
        """
        self.weights = {
            'momentum': momentum_weight,
            'microstructure': microstructure_weight,
            'volatility': volatility_weight,
            'regime': regime_weight,
        }
        
        # Normalize weights
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}
        
        logger.info(f"TreeOfThought initialized with weights: {self.weights}")
    
    def reason(
        self,
        momentum_features: np.ndarray,
        microstructure_features: np.ndarray,
        volatility_features: np.ndarray,
        regime_features: np.ndarray,
        position_features: np.ndarray,
    ) -> ToTDecision:
        """
        Execute Tree of Thought reasoning across all paths.
        
        Args:
            momentum_features: Momentum indicators (12-dim)
            microstructure_features: Microstructure signals (15 or 25-dim)
            volatility_features: Volatility measures (8-dim)
            regime_features: Market regime (6-dim)
            position_features: Current position state (6-dim)
        
        Returns:
            ToTDecision with direction, confidence, and reasoning
        """
        # Execute all reasoning paths
        paths = [
            self._momentum_path(momentum_features, position_features),
            self._microstructure_path(microstructure_features, position_features),
            self._volatility_path(volatility_features, position_features),
            self._regime_path(regime_features, position_features),
        ]
        
        # Synthesize consensus
        consensus_score = self._synthesize_consensus(paths)
        direction = self._score_to_direction(consensus_score)
        confidence = self._calculate_confidence(paths, consensus_score)
        action = self._direction_to_action(direction, confidence, position_features)
        
        return ToTDecision(
            direction=direction,
            confidence=confidence,
            reasoning_paths=paths,
            consensus_score=consensus_score,
            action_recommendation=action,
        )
    
    def _momentum_path(
        self,
        features: np.ndarray,
        position: np.ndarray,
    ) -> ReasoningPath:
        """
        Reasoning Path 1: Momentum Analysis
        
        Features (12-dim):
        - RSI (0-100)
        - MACD line
        - MACD signal
        - MACD histogram
        - Volume ratio
        - Price vs VWAP
        - Bollinger %B
        - Bollinger width
        - ATR
        - Recent return
        - Volume trend
        - Price momentum
        """
        evidence = []
        signals = []
        
        rsi = features[0] * 100  # Denormalize
        macd_hist = features[3]
        volume_ratio = features[4]
        price_vs_vwap = features[5]
        bb_pct = features[6]
        recent_return = features[9]
        price_momentum = features[11]
        
        # RSI signals
        if rsi < 30:
            evidence.append(f"RSI oversold ({rsi:.1f})")
            signals.append(2.0)  # Strong long
        elif rsi < 40:
            evidence.append(f"RSI weak ({rsi:.1f})")
            signals.append(1.0)  # Weak long
        elif rsi > 70:
            evidence.append(f"RSI overbought ({rsi:.1f})")
            signals.append(-2.0)  # Strong short
        elif rsi > 60:
            evidence.append(f"RSI elevated ({rsi:.1f})")
            signals.append(-1.0)  # Weak short
        else:
            evidence.append(f"RSI neutral ({rsi:.1f})")
            signals.append(0.0)
        
        # MACD signals
        if macd_hist > 0.02:
            evidence.append("MACD strong bullish crossover")
            signals.append(2.0)
        elif macd_hist > 0:
            evidence.append("MACD weak bullish")
            signals.append(1.0)
        elif macd_hist < -0.02:
            evidence.append("MACD strong bearish crossover")
            signals.append(-2.0)
        elif macd_hist < 0:
            evidence.append("MACD weak bearish")
            signals.append(-1.0)
        
        # Price vs VWAP (institutional reference)
        if price_vs_vwap > 0.005:
            evidence.append(f"Price above VWAP (+{price_vs_vwap*100:.2f}%)")
            signals.append(1.5)  # Institutions buying
        elif price_vs_vwap < -0.005:
            evidence.append(f"Price below VWAP ({price_vs_vwap*100:.2f}%)")
            signals.append(-1.5)  # Institutions selling
        
        # Volume confirmation
        if volume_ratio > 1.5:
            evidence.append(f"High volume ({volume_ratio:.2f}x)")
            # Amplify existing trend
            if recent_return > 0:
                signals.append(1.0)
            elif recent_return < 0:
                signals.append(-1.0)
        
        # Price momentum
        if price_momentum > 0.01:
            evidence.append("Strong upward momentum")
            signals.append(1.5)
        elif price_momentum < -0.01:
            evidence.append("Strong downward momentum")
            signals.append(-1.5)
        
        # Synthesize momentum path
        if len(signals) > 0:
            score = np.clip(np.mean(signals) / 2.0, -1.0, 1.0)
        else:
            score = 0.0
        
        confidence = min(abs(score), 1.0)
        
        if score > 0.5:
            bias = DirectionBias.STRONG_LONG
        elif score > 0.2:
            bias = DirectionBias.WEAK_LONG
        elif score < -0.5:
            bias = DirectionBias.STRONG_SHORT
        elif score < -0.2:
            bias = DirectionBias.WEAK_SHORT
        else:
            bias = DirectionBias.NEUTRAL
        
        return ReasoningPath(
            name="Momentum",
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            score=score,
        )
    
    def _microstructure_path(
        self,
        features: np.ndarray,
        position: np.ndarray,
    ) -> ReasoningPath:
        """
        Reasoning Path 2: Microstructure Analysis
        
        Focuses on order flow, liquidity, and market impact signals.
        """
        evidence = []
        signals = []
        
        # Extract key microstructure features (assuming 15 or 25-dim)
        # Base 15: spread, depth, imbalance, pressure, flow, etc.
        spread = features[0] if len(features) > 0 else 0
        depth_imbalance = features[2] if len(features) > 2 else 0
        buy_pressure = features[3] if len(features) > 3 else 0
        order_flow = features[4] if len(features) > 4 else 0
        
        # Extended features (if available)
        if len(features) >= 25:
            volume_cluster = features[15] if len(features) > 15 else 0
            liquidity_regime = features[20] if len(features) > 20 else 0
        else:
            volume_cluster = 0
            liquidity_regime = 0
        
        # Spread analysis (tight spread = healthy liquidity)
        if spread < 0.0005:  # < 5 bps
            evidence.append("Tight spread (good liquidity)")
            signals.append(0.5)  # Slightly positive (can enter safely)
        elif spread > 0.0020:  # > 20 bps
            evidence.append("Wide spread (poor liquidity)")
            signals.append(-0.5)  # Caution
        
        # Order flow imbalance (buying vs selling pressure)
        if depth_imbalance > 0.3:
            evidence.append(f"Strong bid depth ({depth_imbalance:.2f})")
            signals.append(2.0)  # Buyers dominant
        elif depth_imbalance > 0.1:
            evidence.append(f"Moderate bid depth ({depth_imbalance:.2f})")
            signals.append(1.0)
        elif depth_imbalance < -0.3:
            evidence.append(f"Strong ask depth ({depth_imbalance:.2f})")
            signals.append(-2.0)  # Sellers dominant
        elif depth_imbalance < -0.1:
            evidence.append(f"Moderate ask depth ({depth_imbalance:.2f})")
            signals.append(-1.0)
        
        # Buy pressure
        if buy_pressure > 0.6:
            evidence.append(f"Heavy buy pressure ({buy_pressure:.2f})")
            signals.append(2.0)
        elif buy_pressure > 0.55:
            evidence.append(f"Moderate buy pressure ({buy_pressure:.2f})")
            signals.append(1.0)
        elif buy_pressure < 0.4:
            evidence.append(f"Heavy sell pressure ({buy_pressure:.2f})")
            signals.append(-2.0)
        elif buy_pressure < 0.45:
            evidence.append(f"Moderate sell pressure ({buy_pressure:.2f})")
            signals.append(-1.0)
        
        # Order flow direction
        if order_flow > 0.02:
            evidence.append("Positive order flow (institutional buying)")
            signals.append(1.5)
        elif order_flow < -0.02:
            evidence.append("Negative order flow (institutional selling)")
            signals.append(-1.5)
        
        # Synthesize microstructure path
        if len(signals) > 0:
            score = np.clip(np.mean(signals) / 2.0, -1.0, 1.0)
        else:
            score = 0.0
        
        confidence = min(abs(score), 1.0)
        
        if score > 0.5:
            bias = DirectionBias.STRONG_LONG
        elif score > 0.2:
            bias = DirectionBias.WEAK_LONG
        elif score < -0.5:
            bias = DirectionBias.STRONG_SHORT
        elif score < -0.2:
            bias = DirectionBias.WEAK_SHORT
        else:
            bias = DirectionBias.NEUTRAL
        
        return ReasoningPath(
            name="Microstructure",
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            score=score,
        )
    
    def _volatility_path(
        self,
        features: np.ndarray,
        position: np.ndarray,
    ) -> ReasoningPath:
        """
        Reasoning Path 3: Volatility & Risk Analysis
        
        Evaluates risk regime and whether conditions favor directional bets.
        """
        evidence = []
        signals = []
        
        # Extract volatility features (8-dim)
        close_to_high = features[0] if len(features) > 0 else 0.5
        close_to_low = features[1] if len(features) > 1 else 0.5
        atr_norm = features[2] if len(features) > 2 else 0
        bb_width = features[3] if len(features) > 3 else 0
        
        # Price position in range
        if close_to_high > 0.9:
            evidence.append("Price near session high")
            signals.append(1.5)  # Strength (but watch for reversal)
        elif close_to_high < 0.2:
            evidence.append("Price near session low")
            signals.append(-1.5)  # Weakness (or oversold)
        
        if close_to_low < 0.1:
            evidence.append("Price at/near low (potential bounce)")
            signals.append(1.0)  # Contrarian long
        elif close_to_low > 0.8:
            evidence.append("Price at/near high (potential pullback)")
            signals.append(-1.0)  # Contrarian short
        
        # ATR (volatility level)
        if atr_norm > 0.03:
            evidence.append(f"High volatility (ATR={atr_norm:.3f})")
            # High vol favors mean reversion, not trend following
            signals.append(0.0)  # Neutral in high vol
        elif atr_norm < 0.01:
            evidence.append(f"Low volatility (ATR={atr_norm:.3f})")
            # Low vol favors breakout trades
            if close_to_high > 0.8:
                signals.append(1.5)  # Breakout long
            elif close_to_high < 0.2:
                signals.append(-1.5)  # Breakdown short
        
        # Bollinger width (expansion/contraction)
        if bb_width > 0.04:
            evidence.append("Bollinger bands wide (trending)")
            # Favor momentum in trend direction
            if close_to_high > 0.6:
                signals.append(1.0)
            elif close_to_high < 0.4:
                signals.append(-1.0)
        elif bb_width < 0.01:
            evidence.append("Bollinger bands tight (consolidation)")
            # Prepare for breakout, but wait for direction
            signals.append(0.0)
        
        # Synthesize volatility path
        if len(signals) > 0:
            score = np.clip(np.mean(signals) / 2.0, -1.0, 1.0)
        else:
            score = 0.0
        
        confidence = min(abs(score) * 0.8, 1.0)  # Lower confidence (volatility path less directional)
        
        if score > 0.4:
            bias = DirectionBias.WEAK_LONG
        elif score < -0.4:
            bias = DirectionBias.WEAK_SHORT
        else:
            bias = DirectionBias.NEUTRAL
        
        return ReasoningPath(
            name="Volatility",
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            score=score,
        )
    
    def _regime_path(
        self,
        features: np.ndarray,
        position: np.ndarray,
    ) -> ReasoningPath:
        """
        Reasoning Path 4: Market Regime Analysis
        
        Evaluates time of day, trend regime, and market phase.
        """
        evidence = []
        signals = []
        
        # Extract regime features (6-dim)
        trend_strength = features[0] if len(features) > 0 else 0
        trend_direction = int(features[1]) if len(features) > 1 else 0
        time_since_open = features[2] if len(features) > 2 else 0
        time_until_close = features[3] if len(features) > 3 else 390
        vol_regime = int(features[4]) if len(features) > 4 else 1
        market_phase = int(features[5]) if len(features) > 5 else 1
        
        # Trend analysis
        if abs(trend_strength) > 0.5:
            if trend_direction > 0:
                evidence.append(f"Strong uptrend (strength={trend_strength:.2f})")
                signals.append(2.0)
            elif trend_direction < 0:
                evidence.append(f"Strong downtrend (strength={trend_strength:.2f})")
                signals.append(-2.0)
        elif abs(trend_strength) > 0.3:
            if trend_direction > 0:
                evidence.append(f"Moderate uptrend (strength={trend_strength:.2f})")
                signals.append(1.0)
            elif trend_direction < 0:
                evidence.append(f"Moderate downtrend (strength={trend_strength:.2f})")
                signals.append(-1.0)
        else:
            evidence.append("No clear trend")
            signals.append(0.0)
        
        # Time of day (market phase)
        if market_phase == 0:  # Open (first hour)
            evidence.append("Market open (high volatility)")
            # Favor momentum trades in open
            if trend_direction != 0:
                signals.append(float(trend_direction) * 1.5)
        elif market_phase == 2:  # Close (last hour)
            evidence.append("Market close (position unwinding)")
            # Caution near close, prefer flattening
            if time_until_close < 30:
                signals.append(0.0)  # Neutral near close
        else:  # Midday
            evidence.append("Midday (lower volatility)")
            # Favor mean reversion in midday
            if abs(trend_strength) < 0.2:
                signals.append(0.0)
        
        # Volatility regime
        if vol_regime == 2:  # High vol
            evidence.append("High volatility regime")
            # Be more selective in high vol
            if abs(trend_strength) > 0.6:
                signals.append(float(trend_direction) * 1.0)
            else:
                signals.append(0.0)
        elif vol_regime == 0:  # Low vol
            evidence.append("Low volatility regime")
            # Can be more aggressive in low vol
            if abs(trend_strength) > 0.3:
                signals.append(float(trend_direction) * 1.5)
        
        # Synthesize regime path
        if len(signals) > 0:
            score = np.clip(np.mean(signals) / 2.0, -1.0, 1.0)
        else:
            score = 0.0
        
        confidence = min(abs(score) * 0.9, 1.0)
        
        if score > 0.5:
            bias = DirectionBias.STRONG_LONG
        elif score > 0.2:
            bias = DirectionBias.WEAK_LONG
        elif score < -0.5:
            bias = DirectionBias.STRONG_SHORT
        elif score < -0.2:
            bias = DirectionBias.WEAK_SHORT
        else:
            bias = DirectionBias.NEUTRAL
        
        return ReasoningPath(
            name="Regime",
            bias=bias,
            confidence=confidence,
            evidence=evidence,
            score=score,
        )
    
    def _synthesize_consensus(self, paths: List[ReasoningPath]) -> float:
        """
        Synthesize consensus score from all reasoning paths.
        
        Uses weighted average of path scores, with confidence weighting.
        
        Returns:
            consensus_score: -1 (strong short) to +1 (strong long)
        """
        weighted_scores = []
        
        for path in paths:
            weight = self.weights.get(path.name.lower(), 0.25)
            # Weight by both path importance and confidence
            effective_weight = weight * path.confidence
            weighted_scores.append(path.score * effective_weight)
        
        if len(weighted_scores) > 0:
            consensus = np.sum(weighted_scores) / max(sum(self.weights.values()), 1.0)
        else:
            consensus = 0.0
        
        return np.clip(consensus, -1.0, 1.0)
    
    def _score_to_direction(self, score: float) -> DirectionBias:
        """Convert consensus score to direction bias."""
        if score > 0.6:
            return DirectionBias.STRONG_LONG
        elif score > 0.3:
            return DirectionBias.WEAK_LONG
        elif score < -0.6:
            return DirectionBias.STRONG_SHORT
        elif score < -0.3:
            return DirectionBias.WEAK_SHORT
        else:
            return DirectionBias.NEUTRAL
    
    def _calculate_confidence(
        self,
        paths: List[ReasoningPath],
        consensus: float,
    ) -> float:
        """
        Calculate overall confidence in decision.
        
        High confidence when:
        - Multiple paths agree
        - Individual path confidences are high
        - Consensus is strong
        """
        # Path agreement: how aligned are the path biases?
        bias_values = [p.bias.value for p in paths]
        agreement = 1.0 - (np.std(bias_values) / 3.0)  # Normalize by max std
        
        # Average path confidence
        avg_confidence = np.mean([p.confidence for p in paths])
        
        # Consensus strength
        consensus_strength = abs(consensus)
        
        # Combine factors
        confidence = (agreement * 0.4 + avg_confidence * 0.3 + consensus_strength * 0.3)
        
        return np.clip(confidence, 0.0, 1.0)
    
    def _direction_to_action(
        self,
        direction: DirectionBias,
        confidence: float,
        position: np.ndarray,
    ) -> int:
        """
        Convert direction bias and confidence to action.
        
        Actions:
        0=CLOSE, 1=HOLD, 2=LONG_SMALL, 3=LONG_MED, 4=LONG_LARGE,
        5=SHORT_SMALL, 6=SHORT_MED, 7=SHORT_LARGE
        """
        current_position = position[0] if len(position) > 0 else 0
        
        # If already in position, check if we should hold or close
        if current_position != 0:
            current_side = 1 if current_position > 0 else -1
            bias_side = 1 if direction.value > 0 else (-1 if direction.value < 0 else 0)
            
            # If direction reversed with high confidence, close
            if current_side != bias_side and confidence > 0.7:
                return 0  # CLOSE
            
            # If direction aligned but weak, hold
            if current_side == bias_side and direction == DirectionBias.NEUTRAL:
                return 1  # HOLD
            
            # If direction aligned and strong, hold (could add logic to add to position)
            if current_side == bias_side:
                return 1  # HOLD
            
            # Mixed signals with position: hold
            return 1  # HOLD
        
        # No position: decide whether to enter and size
        if direction == DirectionBias.NEUTRAL or confidence < 0.4:
            return 1  # HOLD (wait for clearer signal)
        
        # Strong signals: larger size
        if direction == DirectionBias.STRONG_LONG:
            if confidence > 0.8:
                return 4  # LONG_LARGE
            elif confidence > 0.6:
                return 3  # LONG_MED
            else:
                return 2  # LONG_SMALL
        
        elif direction == DirectionBias.WEAK_LONG:
            if confidence > 0.7:
                return 3  # LONG_MED
            else:
                return 2  # LONG_SMALL
        
        elif direction == DirectionBias.STRONG_SHORT:
            if confidence > 0.8:
                return 7  # SHORT_LARGE
            elif confidence > 0.6:
                return 6  # SHORT_MED
            else:
                return 5  # SHORT_SMALL
        
        elif direction == DirectionBias.WEAK_SHORT:
            if confidence > 0.7:
                return 6  # SHORT_MED
            else:
                return 5  # SHORT_SMALL
        
        # Default: hold
        return 1
    
    def explain_decision(self, decision: ToTDecision) -> str:
        """Generate human-readable explanation of decision."""
        lines = [
            f"\n{'='*70}",
            f"Tree of Thought Decision: {decision.direction.name}",
            f"Confidence: {decision.confidence:.2%}",
            f"Consensus Score: {decision.consensus_score:+.3f}",
            f"Recommended Action: {decision.action_recommendation}",
            f"{'='*70}",
        ]
        
        for path in decision.reasoning_paths:
            lines.append(f"\n[{path.name}] {path.bias.name} (conf={path.confidence:.2f}, score={path.score:+.3f})")
            for evidence in path.evidence:
                lines.append(f"  • {evidence}")
        
        lines.append(f"{'='*70}\n")
        
        return "\n".join(lines)
