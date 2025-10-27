"""
Phase 7: Backtesting and Execution Simulation
==============================================

Production-grade backtesting engine with:
- Realistic execution simulation (quote-based + LOB)
- Comprehensive cost models (fees, slippage, spread, overnight)
- Walk-forward evaluation
- Performance analytics and tear sheets

Academic References:
- Lopez de Prado (2018): "Advances in Financial Machine Learning"
- Almgren & Chriss (2000): "Optimal Execution of Portfolio Transactions"
- Kyle (1985): "Continuous Auctions and Insider Trading"
"""

from autotrader.backtesting.simulator import (
    OrderSimulator,
    LatencyModel,
    FillSimulation,
    LOBSnapshot
)

from autotrader.backtesting.costs import (
    FeeModel,
    SlippageModel,
    SpreadModel,
    OvernightCostModel,
    TotalCostModel
)

from autotrader.backtesting.engine import (
    BacktestEngine,
    Portfolio,
    RiskManager,
    Trade,
    Position,
    BacktestResults,
    OrderStatus
)

from autotrader.backtesting.evaluation import (
    WalkForwardEvaluator,
    WalkForwardWindow,
    StabilityMetrics,
    RegimeAnalyzer
)

from autotrader.backtesting.reporting import (
    TearSheet,
    PerformanceMetrics,
    MetricsCalculator,
    TradeAnalyzer
)

__all__ = [
    # Simulator
    'OrderSimulator',
    'LatencyModel',
    'FillSimulation',
    'LOBSnapshot',
    
    # Costs
    'FeeModel',
    'SlippageModel',
    'SpreadModel',
    'OvernightCostModel',
    'TotalCostModel',
    
    # Engine
    'BacktestEngine',
    'Portfolio',
    'RiskManager',
    'Trade',
    'Position',
    'BacktestResults',
    'OrderStatus',
    
    # Evaluation
    'WalkForwardEvaluator',
    'WalkForwardWindow',
    'StabilityMetrics',
    'RegimeAnalyzer',
    
    # Reporting
    'TearSheet',
    'PerformanceMetrics',
    'MetricsCalculator',
    'TradeAnalyzer'
]

__version__ = '7.0.0'
