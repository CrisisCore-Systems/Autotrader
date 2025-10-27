"""
Analytics Module - Post-Trade Performance Analysis
Phase 12: PnL attribution, slippage decomposition, regime analysis
"""

from autotrader.analytics.pnl_attribution import (
    Trade,
    PnLAttributor,
    load_trades_from_audit
)

from autotrader.analytics.slippage import (
    OrderExecution,
    SlippageBreakdown,
    SlippageAnalyzer,
    load_executions_from_audit
)

from autotrader.analytics.regime import (
    TrendRegime,
    VolatilityRegime,
    RiskRegime,
    RegimeLabel,
    RegimePerformance,
    RegimeAnalyzer
)


__all__ = [
    'Trade',
    'PnLAttributor',
    'load_trades_from_audit',
    'OrderExecution',
    'SlippageBreakdown',
    'SlippageAnalyzer',
    'load_executions_from_audit',
    'TrendRegime',
    'VolatilityRegime',
    'RiskRegime',
    'RegimeLabel',
    'RegimePerformance',
    'RegimeAnalyzer',
]
