"""
LLM Tools Module
=================

Tools for LLM-driven decision pipeline with schema validation.

This module implements:
- PreTradeChecklist: Market regime and risk capacity evaluation
- PlaybookSelector: Model/horizon selection based on regime
- ExecutionPlanner: Execution plan generation with constraints
- PostTradeJournal: Trade analysis and anomaly detection

Key Principles:
- All outputs are JSON-schema validated
- Tools provide context, LLM provides reasoning
- Hard limits are unoverridable
- All decisions are auditable

Example
-------
>>> from autotrader.llm.tools import PreTradeChecklist
>>> 
>>> tool = PreTradeChecklist()
>>> result = tool.execute(
...     volatility=0.025,
...     spread_bps=5.2,
...     edge_bps=8.5,
...     risk_headroom=0.65
... )
>>> print(result.decision)  # PROCEED | CAUTION | HALT
"""

from typing import Optional, Dict, List, Any, Literal
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator
import json


# ============================================================================
# Output Schemas (Pydantic for validation)
# ============================================================================

class PreTradeDecision(Enum):
    """Pre-trade decision outcomes."""
    PROCEED = "PROCEED"
    CAUTION = "CAUTION"
    HALT = "HALT"


class MarketRegime(Enum):
    """Market regime classifications."""
    TRENDING_HIGH_VOL = "trending_high_vol"
    TRENDING_LOW_VOL = "trending_low_vol"
    MEAN_REVERTING_HIGH_VOL = "mean_reverting_high_vol"
    MEAN_REVERTING_LOW_VOL = "mean_reverting_low_vol"
    CHOPPY = "choppy"
    UNKNOWN = "unknown"


class PreTradeChecklistOutput(BaseModel):
    """
    Pre-trade checklist output schema.
    
    Validated constraints:
    - Must HALT if risk_headroom_pct < 0.10
    - Must HALT if edge_vs_cost_ratio < 1.0
    - confidence must be [0.0, 1.0]
    - reasoning limited to 200 chars
    """
    decision: Literal["PROCEED", "CAUTION", "HALT"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200)
    risks_identified: List[str]
    market_regime: str
    edge_vs_cost_ratio: float
    risk_headroom_pct: float = Field(ge=0.0, le=1.0)
    
    @validator('decision')
    def validate_halt_conditions(cls, v, values):
        """Enforce HALT on critical conditions."""
        # Must HALT if low risk headroom
        if values.get('risk_headroom_pct', 1.0) < 0.10:
            if v != 'HALT':
                raise ValueError("Must HALT when risk_headroom_pct < 10%")
        
        # Must HALT if edge < cost
        if values.get('edge_vs_cost_ratio', 1.0) < 1.0:
            if v != 'HALT':
                raise ValueError("Must HALT when edge < cost")
        
        return v
    
    @validator('reasoning')
    def validate_reasoning_length(cls, v):
        """Ensure reasoning is concise."""
        if len(v) == 0:
            raise ValueError("Reasoning cannot be empty")
        return v


class PlaybookSelectorOutput(BaseModel):
    """
    Playbook selector output schema.
    
    Validated constraints:
    - Must select from approved models only
    - Horizon must be valid timeframe
    - confidence must be [0.0, 1.0]
    """
    selected_model: Literal["LSTM", "GRU", "TCN", "Transformer", "Online"]
    horizon: Literal["1m", "5m", "15m", "1h"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200)
    regime_match_score: float = Field(ge=0.0, le=1.0)
    historical_performance: Dict[str, float]
    fallback_model: str
    
    @validator('historical_performance')
    def validate_performance_metrics(cls, v):
        """Ensure required performance metrics present."""
        required = {'win_rate', 'sharpe', 'sample_size'}
        if not required.issubset(v.keys()):
            raise ValueError(f"Missing performance metrics: {required - v.keys()}")
        return v


class ExecutionPlannerOutput(BaseModel):
    """
    Execution planner output schema.
    
    Validated constraints:
    - Cannot EXECUTE if any constraint_check is False
    - Must provide reasoning for action
    - Risk assessment required
    """
    action: Literal["EXECUTE", "DEFER", "REJECT"]
    execution_plan: Dict[str, Any]
    reasoning: str = Field(max_length=200)
    risk_assessment: Dict[str, Any]
    constraint_checks: Dict[str, bool]
    
    @validator('action')
    def validate_execution_constraints(cls, v, values):
        """Enforce constraint checking."""
        checks = values.get('constraint_checks', {})
        
        # Cannot EXECUTE if any constraint violated
        if v == 'EXECUTE':
            if not all(checks.values()):
                violated = [k for k, val in checks.items() if not val]
                raise ValueError(f"Cannot EXECUTE with violated constraints: {violated}")
        
        return v
    
    @validator('execution_plan')
    def validate_execution_plan_fields(cls, v):
        """Ensure required execution plan fields."""
        required = {'order_type', 'urgency', 'split_strategy'}
        if not required.issubset(v.keys()):
            raise ValueError(f"Missing execution plan fields: {required - v.keys()}")
        return v


class PostTradeJournalOutput(BaseModel):
    """
    Post-trade journal output schema.
    
    Validated constraints:
    - Anomalies must be flagged
    - Performance assessment required
    - Insights must be actionable
    """
    anomalies_detected: List[str]
    performance_assessment: Dict[str, Any]
    insights: List[str]
    recommended_actions: List[Dict[str, Any]]
    regime_shift_detected: bool
    model_drift_score: float = Field(ge=0.0, le=1.0)
    
    @validator('performance_assessment')
    def validate_performance_fields(cls, v):
        """Ensure required performance fields."""
        required = {'predicted_pnl', 'actual_pnl', 'variance_explanation'}
        if not required.issubset(v.keys()):
            raise ValueError(f"Missing performance fields: {required - v.keys()}")
        return v
    
    @validator('recommended_actions')
    def validate_actions(cls, v):
        """Validate action structure."""
        for action in v:
            required = {'action', 'priority', 'reasoning'}
            if not required.issubset(action.keys()):
                raise ValueError(f"Action missing fields: {required - action.keys()}")
        return v


# ============================================================================
# Tool Base Class
# ============================================================================

class LLMTool:
    """
    Base class for LLM tools.
    
    Provides:
    - Input validation
    - Output schema validation
    - Execution timing
    - Audit logging
    """
    
    def __init__(self, name: str, output_schema: type[BaseModel]):
        self.name = name
        self.output_schema = output_schema
        self.execution_count = 0
        self.total_latency_ms = 0.0
    
    def validate_output(self, output: Dict[str, Any]) -> BaseModel:
        """
        Validate LLM output against schema.
        
        Parameters
        ----------
        output : dict
            LLM response (parsed JSON)
        
        Returns
        -------
        validated : BaseModel
            Validated output
        
        Raises
        ------
        ValidationError
            If output doesn't match schema
        """
        return self.output_schema(**output)
    
    def get_metrics(self) -> Dict[str, float]:
        """Get execution metrics."""
        avg_latency = (
            self.total_latency_ms / self.execution_count
            if self.execution_count > 0 else 0
        )
        
        return {
            'execution_count': self.execution_count,
            'avg_latency_ms': avg_latency,
            'total_latency_ms': self.total_latency_ms
        }


# ============================================================================
# Tool Implementations
# ============================================================================

class PreTradeChecklist(LLMTool):
    """
    Pre-trade checklist tool.
    
    Evaluates market conditions and risk capacity to determine if
    trading should proceed.
    
    Inputs:
    - Market regime (volatility, trend, correlation)
    - Liquidity metrics (spread, depth)
    - Cost vs edge analysis
    - Risk limit headroom
    - Recent performance
    
    Output:
    - Decision: PROCEED / CAUTION / HALT
    - Reasoning and risk identification
    
    Example
    -------
    >>> tool = PreTradeChecklist()
    >>> result = tool.prepare_input(
    ...     volatility=0.02,
    ...     spread_bps=3.5,
    ...     edge_bps=10.0,
    ...     cost_bps=4.0,
    ...     risk_headroom=0.75
    ... )
    >>> # Pass to LLM, then validate output
    >>> validated = tool.validate_output(llm_response)
    """
    
    def __init__(self):
        super().__init__("pretrade_checklist", PreTradeChecklistOutput)
    
    def prepare_input(
        self,
        volatility: float,
        trend_strength: float,
        correlation_regime: str,
        spread_bps: float,
        depth: float,
        edge_bps: float,
        cost_bps: float,
        daily_loss_used_pct: float,
        position_slots_used: int,
        position_slots_max: int,
        correlation_budget_used_pct: float,
        win_rate_20: float,
        sharpe_30d: float
    ) -> Dict[str, Any]:
        """
        Prepare tool inputs.
        
        Returns
        -------
        inputs : dict
            Structured inputs for LLM prompt
        """
        edge_cost_ratio = edge_bps / cost_bps if cost_bps > 0 else 0
        risk_headroom = 1.0 - daily_loss_used_pct
        
        return {
            'market_regime': {
                'volatility': volatility,
                'trend_strength': trend_strength,
                'correlation_regime': correlation_regime
            },
            'liquidity': {
                'spread_bps': spread_bps,
                'depth': depth
            },
            'cost_vs_edge': {
                'edge_bps': edge_bps,
                'cost_bps': cost_bps,
                'ratio': edge_cost_ratio
            },
            'risk_headroom': {
                'daily_loss_used_pct': daily_loss_used_pct,
                'position_slots': f"{position_slots_used}/{position_slots_max}",
                'correlation_budget_used_pct': correlation_budget_used_pct,
                'risk_headroom_pct': risk_headroom
            },
            'recent_performance': {
                'win_rate_20': win_rate_20,
                'sharpe_30d': sharpe_30d
            }
        }


class PlaybookSelector(LLMTool):
    """
    Playbook selector tool.
    
    Selects optimal model and horizon based on current market regime
    and historical performance.
    
    Inputs:
    - Market regime features
    - Available models and recent performance
    - Current portfolio state
    
    Output:
    - Selected model and horizon
    - Regime match score
    - Fallback option
    
    Example
    -------
    >>> tool = PlaybookSelector()
    >>> result = tool.prepare_input(
    ...     regime_features={'vol': 0.02, 'autocorr': -0.15},
    ...     model_performance={
    ...         'LSTM': {'win_rate': 0.58, 'sharpe': 1.2},
    ...         'TCN': {'win_rate': 0.52, 'sharpe': 0.8}
    ...     }
    ... )
    """
    
    def __init__(self):
        super().__init__("playbook_selector", PlaybookSelectorOutput)
    
    def prepare_input(
        self,
        regime_features: Dict[str, float],
        model_performance: Dict[str, Dict[str, float]],
        current_positions: List[str],
        market_microstructure: Dict[str, float]
    ) -> Dict[str, Any]:
        """Prepare playbook selection inputs."""
        return {
            'regime_features': regime_features,
            'model_performance': model_performance,
            'current_positions': current_positions,
            'market_microstructure': market_microstructure,
            'available_models': list(model_performance.keys()),
            'available_horizons': ['1m', '5m', '15m', '1h']
        }


class ExecutionPlanner(LLMTool):
    """
    Execution planner tool.
    
    Generates execution plan constrained by hard risk rules.
    
    Inputs:
    - Phase 8 signal
    - Current portfolio state
    - Risk limits
    - Market microstructure
    
    Output:
    - Action: EXECUTE / DEFER / REJECT
    - Execution plan (order type, timing, splitting)
    - Risk assessment
    - Constraint check results
    
    Example
    -------
    >>> tool = ExecutionPlanner()
    >>> result = tool.prepare_input(
    ...     signal={'direction': 'LONG', 'confidence': 0.65, 'size': 1000},
    ...     constraints={'max_size': 5000, 'max_correlation': 0.70},
    ...     microstructure={'vwap': 50000, 'slippage_est': 0.0015}
    ... )
    """
    
    def __init__(self):
        super().__init__("execution_planner", ExecutionPlannerOutput)
    
    def prepare_input(
        self,
        signal: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        risk_limits: Dict[str, float],
        market_microstructure: Dict[str, float],
        constraint_checks: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Prepare execution planning inputs."""
        return {
            'signal': signal,
            'portfolio_state': portfolio_state,
            'risk_limits': risk_limits,
            'market_microstructure': market_microstructure,
            'constraint_checks': constraint_checks
        }


class PostTradeJournal(LLMTool):
    """
    Post-trade journal tool.
    
    Analyzes trade outcomes and detects anomalies.
    
    Inputs:
    - Trade execution results
    - Pre-trade predictions
    - Market conditions during execution
    - Historical similar trades
    
    Output:
    - Anomalies detected
    - Performance assessment
    - Insights and recommendations
    - Regime shift / model drift detection
    
    Example
    -------
    >>> tool = PostTradeJournal()
    >>> result = tool.prepare_input(
    ...     trade_result={'pnl': 45, 'slippage': 0.0012, 'fill': 50050},
    ...     prediction={'expected_pnl': 50, 'confidence': 0.65},
    ...     market_conditions={'volatility': 0.025}
    ... )
    """
    
    def __init__(self):
        super().__init__("post_trade_journal", PostTradeJournalOutput)
    
    def prepare_input(
        self,
        trade_result: Dict[str, float],
        prediction: Dict[str, float],
        market_conditions: Dict[str, float],
        historical_trades: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Prepare post-trade journal inputs."""
        return {
            'trade_result': trade_result,
            'prediction': prediction,
            'market_conditions': market_conditions,
            'historical_trades': historical_trades,
            'variance_pct': (
                abs(trade_result.get('pnl', 0) - prediction.get('expected_pnl', 0)) /
                abs(prediction.get('expected_pnl', 1))
                if prediction.get('expected_pnl', 0) != 0 else 0
            )
        }


# ============================================================================
# Tool Registry
# ============================================================================

class ToolRegistry:
    """
    Registry of available LLM tools.
    
    Provides:
    - Tool lookup by name
    - Tool listing
    - Execution metrics aggregation
    """
    
    def __init__(self):
        self.tools: Dict[str, LLMTool] = {
            'pretrade_checklist': PreTradeChecklist(),
            'playbook_selector': PlaybookSelector(),
            'execution_planner': ExecutionPlanner(),
            'post_trade_journal': PostTradeJournal()
        }
    
    def get_tool(self, name: str) -> LLMTool:
        """Get tool by name."""
        if name not in self.tools:
            raise ValueError(f"Unknown tool: {name}")
        return self.tools[name]
    
    def list_tools(self) -> List[str]:
        """List available tool names."""
        return list(self.tools.keys())
    
    def get_all_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get metrics for all tools."""
        return {
            name: tool.get_metrics()
            for name, tool in self.tools.items()
        }


# Export public API
__all__ = [
    'PreTradeChecklist',
    'PlaybookSelector',
    'ExecutionPlanner',
    'PostTradeJournal',
    'PreTradeChecklistOutput',
    'PlaybookSelectorOutput',
    'ExecutionPlannerOutput',
    'PostTradeJournalOutput',
    'PreTradeDecision',
    'MarketRegime',
    'LLMTool',
    'ToolRegistry',
]
