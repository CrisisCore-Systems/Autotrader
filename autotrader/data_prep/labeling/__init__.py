"""
Cost-aware labeling pipeline for ML training.

Provides classification and regression labeling with:
- Transaction cost modeling (fees, spread, slippage)
- Microprice-based returns (volume-weighted fair value)
- Robust outlier handling (percentile clipping)
- Horizon optimization (grid search for best prediction window)

Example (Classification):
    >>> from autotrader.data_prep.labeling import LabelFactory, CostModel
    >>> 
    >>> # Create cost-aware classification labels
    >>> cost_model = CostModel(maker_fee=0.02, taker_fee=0.04)
    >>> labels = LabelFactory.create(
    ...     bars,
    ...     method="classification",
    ...     horizon_seconds=60,
    ...     cost_model=cost_model
    ... )
    >>> # labels: {-1, 0, +1} for sell/hold/buy

Example (Regression):
    >>> # Create continuous regression targets
    >>> labels = LabelFactory.create(
    ...     bars,
    ...     method="regression",
    ...     horizon_seconds=60,
    ...     use_microprice=True,
    ...     clip_percentiles=(5, 95)
    ... )
    >>> # labels: cost-adjusted returns in bps

Example (Horizon Optimization):
    >>> from autotrader.data_prep.labeling import HorizonOptimizer
    >>> 
    >>> optimizer = HorizonOptimizer(
    ...     horizons_seconds=[5, 10, 15, 30, 60, 120, 180, 300],
    ...     labeling_method="classification"
    ... )
    >>> best, all_results, df = optimizer.optimize(bars, symbol="EUR/USD")
    >>> report = optimizer.generate_report(df, "EUR/USD", "horizon_report.txt")
"""

from .base import CostModel, BaseLabeler, estimate_capacity, calculate_sharpe_ratio, calculate_information_ratio
from .classification import ClassificationLabeler
from .regression import RegressionLabeler
from .horizon_optimizer import HorizonOptimizer, HorizonResult
from .factory import LabelFactory

__all__ = [
    # Core classes
    "CostModel",
    "BaseLabeler",
    "ClassificationLabeler",
    "RegressionLabeler",
    "HorizonOptimizer",
    "HorizonResult",
    "LabelFactory",
    
    # Utility functions
    "estimate_capacity",
    "calculate_sharpe_ratio",
    "calculate_information_ratio",
]
