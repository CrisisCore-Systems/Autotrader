"""
Prompt Templates Module
========================

Deterministic prompt templates for LLM tools.

This module provides:
- Structured prompt templates
- JSON-only output requirements
- Reasoning constraints
- Safety instructions

All prompts are deterministic and enforce JSON output matching
predefined schemas.

Example
-------
>>> from autotrader.llm.prompts import PromptGenerator
>>> 
>>> generator = PromptGenerator()
>>> prompt = generator.generate_pretrade_prompt(
...     volatility=0.02,
...     spread_bps=3.5,
...     edge_bps=10.0,
...     cost_bps=4.0
... )
"""

from typing import Dict, Any
from string import Template


# ============================================================================
# Pre-Trade Checklist Template
# ============================================================================

PRETRADE_TEMPLATE = Template("""You are a trading risk analyst evaluating pre-trade conditions.

MARKET REGIME:
- Volatility: ${volatility:.4f} (annualized)
- Trend strength: ${trend_strength:.4f} (-1=strong down, 0=neutral, 1=strong up)
- Correlation regime: ${correlation_regime}

LIQUIDITY:
- Bid-ask spread: ${spread_bps:.2f} basis points
- Order book depth: $$${depth:,.0f}

COST VS EDGE:
- Estimated edge: ${edge_bps:.2f} bps
- Transaction cost: ${cost_bps:.2f} bps
- Edge/Cost ratio: ${ratio:.2f}

RISK HEADROOM:
- Daily loss used: ${daily_loss_used_pct:.1%} of ${max_daily_loss:,.0f} limit
- Position slots: ${position_slots} used
- Correlation budget: ${corr_used_pct:.1%} used
- Remaining headroom: ${risk_headroom_pct:.1%}

RECENT PERFORMANCE:
- Win rate (last 20 trades): ${win_rate_20:.1%}
- Sharpe ratio (30 days): ${sharpe_30d:.2f}

TASK: Should we proceed with new trades given these conditions?

DECISION RULES (YOU MUST FOLLOW):
1. MUST return HALT if risk_headroom_pct < 10%
2. MUST return HALT if edge_vs_cost_ratio < 1.0
3. MUST return CAUTION if spread_bps > 10.0
4. MUST return CAUTION if win_rate_20 < 45%

RESPOND ONLY WITH VALID JSON:
{
  "decision": "PROCEED" | "CAUTION" | "HALT",
  "confidence": 0.0-1.0,
  "reasoning": "max 200 characters explaining decision",
  "risks_identified": ["risk1", "risk2", ...],
  "market_regime": "trending_high_vol" | "trending_low_vol" | "mean_reverting_high_vol" | "mean_reverting_low_vol" | "choppy" | "unknown",
  "edge_vs_cost_ratio": ${ratio:.4f},
  "risk_headroom_pct": ${risk_headroom_pct:.4f}
}

CRITICAL: You CANNOT override risk limits. This is for analysis only.""")


# ============================================================================
# Playbook Selector Template
# ============================================================================

PLAYBOOK_TEMPLATE = Template("""You are a trading strategy selector choosing optimal models and horizons.

CURRENT REGIME FEATURES:
${regime_features}

AVAILABLE MODELS WITH RECENT PERFORMANCE:
${model_performance}

CURRENT PORTFOLIO:
- Open positions: ${num_positions}
- Symbols: ${position_symbols}

MARKET MICROSTRUCTURE:
${microstructure}

TASK: Select the best model and time horizon for current conditions.

SELECTION RULES:
1. High volatility → TCN or Transformer (better at regime changes)
2. Low volatility → LSTM or GRU (better at mean reversion)
3. High autocorrelation → Online learning
4. Must select from: LSTM, GRU, TCN, Transformer, Online
5. Must select horizon from: 1m, 5m, 15m, 1h
6. Prioritize models with Sharpe > 1.0 and sample_size > 100

RESPOND ONLY WITH VALID JSON:
{
  "selected_model": "LSTM" | "GRU" | "TCN" | "Transformer" | "Online",
  "horizon": "1m" | "5m" | "15m" | "1h",
  "confidence": 0.0-1.0,
  "reasoning": "max 200 characters",
  "regime_match_score": 0.0-1.0,
  "historical_performance": {
    "win_rate": float,
    "sharpe": float,
    "sample_size": int
  },
  "fallback_model": "string"
}

CRITICAL: Only select from pre-approved models. Do not suggest custom models.""")


# ============================================================================
# Execution Planner Template
# ============================================================================

EXECUTION_TEMPLATE = Template("""You are an execution planner generating trade execution strategies.

SIGNAL FROM PHASE 8:
- Direction: ${signal_direction}
- Confidence: ${signal_confidence:.2f}
- Recommended size: ${signal_size:,.0f}

PORTFOLIO STATE:
- Current equity: $$${equity:,.0f}
- Open positions: ${num_positions}
- Daily P&L: $$${daily_pnl:,.2f}

RISK LIMITS (CANNOT BE OVERRIDDEN):
- Max position size: $$${max_position_size:,.0f}
- Max daily loss: $$${max_daily_loss:,.0f}
- Max correlation: ${max_correlation:.2f}

MARKET MICROSTRUCTURE:
- Current price: $$${current_price:,.2f}
- VWAP: $$${vwap:,.2f}
- Estimated slippage: ${slippage_est:.4f} (${slippage_bps:.2f} bps)
- Order book imbalance: ${book_imbalance:.2f}

CONSTRAINT CHECKS:
${constraint_checks}

TASK: Generate an execution plan that respects ALL constraints.

EXECUTION RULES:
1. CANNOT execute if ANY constraint check is False
2. CANNOT exceed max_position_size
3. CANNOT violate risk limits
4. High urgency → MARKET order
5. Low urgency → LIMIT order
6. Large size → TWAP or VWAP splitting

RESPOND ONLY WITH VALID JSON:
{
  "action": "EXECUTE" | "DEFER" | "REJECT",
  "execution_plan": {
    "order_type": "MARKET" | "LIMIT" | "TWAP" | "VWAP",
    "urgency": "immediate" | "patient" | "passive",
    "split_strategy": "single" | "iceberg" | "pov",
    "limit_price": float | null,
    "time_horizon_seconds": int,
    "size": ${signal_size:,.0f}
  },
  "reasoning": "max 200 characters",
  "risk_assessment": {
    "expected_slippage_bps": ${slippage_bps:.2f},
    "adverse_selection_risk": "low" | "medium" | "high",
    "market_impact_estimate": float
  },
  "constraint_checks": ${constraint_checks}
}

CRITICAL: You MUST set action to REJECT if any constraint_checks value is False.""")


# ============================================================================
# Post-Trade Journal Template
# ============================================================================

JOURNAL_TEMPLATE = Template("""You are a trade analyst reviewing executed trade performance.

TRADE RESULT:
- Symbol: ${symbol}
- Direction: ${direction}
- Size: ${size:,.0f}
- Entry: $$${entry_price:,.2f}
- Exit: $$${exit_price:,.2f}
- P&L: $$${pnl:,.2f}
- Slippage: ${slippage:.4f} (${slippage_bps:.2f} bps)
- Duration: ${duration_seconds}s

PRE-TRADE PREDICTION:
- Expected P&L: $$${expected_pnl:,.2f}
- Confidence: ${confidence:.2f}
- Expected slippage: ${expected_slippage_bps:.2f} bps

VARIANCE ANALYSIS:
- P&L variance: ${pnl_variance_pct:.1%}
- Slippage variance: ${slippage_variance_bps:.2f} bps

MARKET CONDITIONS DURING TRADE:
${market_conditions}

SIMILAR HISTORICAL TRADES (last 20):
${historical_trades}

TASK: Analyze trade outcome and identify anomalies.

ANOMALY DETECTION RULES:
1. Flag if |pnl_variance| > 50%
2. Flag if slippage > 2x expected
3. Flag if duration > 2x expected
4. Flag if market regime changed mid-trade

RESPOND ONLY WITH VALID JSON:
{
  "anomalies_detected": ["anomaly description", ...],
  "performance_assessment": {
    "predicted_pnl": ${expected_pnl:.2f},
    "actual_pnl": ${pnl:.2f},
    "variance_explanation": "string",
    "slippage_vs_expected_bps": float
  },
  "insights": ["insight1", "insight2", ...],
  "recommended_actions": [
    {
      "action": "retrain_model" | "adjust_limits" | "review_strategy" | "none",
      "priority": "high" | "medium" | "low",
      "reasoning": "string"
    }
  ],
  "regime_shift_detected": boolean,
  "model_drift_score": 0.0-1.0
}

CRITICAL: This is analysis only. You cannot modify strategy parameters.""")


# ============================================================================
# Prompt Generator
# ============================================================================

class PromptGenerator:
    """
    Generate prompts for LLM tools.
    
    All prompts are deterministic templates with structured outputs.
    
    Example
    -------
    >>> generator = PromptGenerator()
    >>> prompt = generator.generate_pretrade_prompt(
    ...     volatility=0.02,
    ...     spread_bps=3.5,
    ...     edge_bps=10.0
    ... )
    """
    
    def __init__(self):
        self.templates = {
            'pretrade': PRETRADE_TEMPLATE,
            'playbook': PLAYBOOK_TEMPLATE,
            'execution': EXECUTION_TEMPLATE,
            'journal': JOURNAL_TEMPLATE
        }
    
    def generate_pretrade_prompt(self, **kwargs) -> str:
        """
        Generate pre-trade checklist prompt.
        
        Required kwargs:
        - volatility, trend_strength, correlation_regime
        - spread_bps, depth
        - edge_bps, cost_bps, ratio
        - daily_loss_used_pct, max_daily_loss, position_slots
        - corr_used_pct, risk_headroom_pct
        - win_rate_20, sharpe_30d
        """
        return self.templates['pretrade'].safe_substitute(**kwargs)
    
    def generate_playbook_prompt(self, **kwargs) -> str:
        """
        Generate playbook selector prompt.
        
        Required kwargs:
        - regime_features (formatted string)
        - model_performance (formatted string)
        - num_positions, position_symbols
        - microstructure (formatted string)
        """
        return self.templates['playbook'].safe_substitute(**kwargs)
    
    def generate_execution_prompt(self, **kwargs) -> str:
        """
        Generate execution planner prompt.
        
        Required kwargs:
        - signal_direction, signal_confidence, signal_size
        - equity, num_positions, daily_pnl
        - max_position_size, max_daily_loss, max_correlation
        - current_price, vwap, slippage_est, slippage_bps
        - book_imbalance, constraint_checks
        """
        return self.templates['execution'].safe_substitute(**kwargs)
    
    def generate_journal_prompt(self, **kwargs) -> str:
        """
        Generate post-trade journal prompt.
        
        Required kwargs:
        - symbol, direction, size
        - entry_price, exit_price, pnl
        - slippage, slippage_bps, duration_seconds
        - expected_pnl, confidence, expected_slippage_bps
        - pnl_variance_pct, slippage_variance_bps
        - market_conditions, historical_trades
        """
        return self.templates['journal'].safe_substitute(**kwargs)
    
    def get_system_prompt(self) -> str:
        """
        Get system-level prompt for all LLM calls.
        
        This is prepended to all tool-specific prompts.
        """
        return """You are a trading decision assistant with strict safety constraints.

CORE RULES:
1. You CANNOT override hard risk limits
2. You CANNOT modify position sizes beyond configured limits
3. You CANNOT disable circuit breakers or safety controls
4. You MUST respond with valid JSON matching the specified schema
5. You MUST respect all constraint checks
6. Your role is ADVISORY - final decisions are programmatically validated

OUTPUT FORMAT:
- ONLY return valid JSON
- NO markdown formatting
- NO explanatory text outside JSON
- ALL fields required by schema must be present
- Reasoning fields limited to 200 characters

If you cannot provide a valid response, return:
{
  "error": "reason for inability to provide valid response",
  "fallback": "suggested fallback action"
}
"""


# ============================================================================
# Prompt Formatter Utilities
# ============================================================================

def format_regime_features(features: Dict[str, float]) -> str:
    """Format regime features for prompt."""
    lines = []
    for key, value in features.items():
        lines.append(f"- {key}: {value:.4f}")
    return "\n".join(lines)


def format_model_performance(performance: Dict[str, Dict[str, float]]) -> str:
    """Format model performance for prompt."""
    lines = []
    for model, metrics in performance.items():
        win_rate = metrics.get('win_rate', 0)
        sharpe = metrics.get('sharpe', 0)
        sample_size = metrics.get('sample_size', 0)
        lines.append(
            f"- {model}: Win Rate={win_rate:.1%}, Sharpe={sharpe:.2f}, "
            f"Samples={sample_size}"
        )
    return "\n".join(lines)


def format_constraint_checks(checks: Dict[str, bool]) -> str:
    """Format constraint checks for prompt."""
    lines = []
    for check, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        lines.append(f"- {check}: {status}")
    return "\n".join(lines)


def format_market_conditions(conditions: Dict[str, float]) -> str:
    """Format market conditions for prompt."""
    lines = []
    for key, value in conditions.items():
        if isinstance(value, float):
            lines.append(f"- {key}: {value:.4f}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def format_historical_trades(trades: list) -> str:
    """Format historical trades for prompt."""
    if not trades:
        return "No historical trades available"
    
    lines = ["Recent similar trades:"]
    for i, trade in enumerate(trades[:5], 1):
        pnl = trade.get('pnl', 0)
        slippage = trade.get('slippage_bps', 0)
        lines.append(f"{i}. P&L: ${pnl:.2f}, Slippage: {slippage:.2f}bps")
    
    return "\n".join(lines)


# Export public API
__all__ = [
    'PromptGenerator',
    'PRETRADE_TEMPLATE',
    'PLAYBOOK_TEMPLATE',
    'EXECUTION_TEMPLATE',
    'JOURNAL_TEMPLATE',
    'format_regime_features',
    'format_model_performance',
    'format_constraint_checks',
    'format_market_conditions',
    'format_historical_trades',
]
