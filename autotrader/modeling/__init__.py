"""
Phase 6: Modeling Framework
============================

Comprehensive modeling suite for HFT including:
- Baseline models (linear, tree ensembles)
- Sequential models (TCN, LSTM, Transformer)
- Online learning (River, Vowpal Wabbit)
- Evaluation metrics (precision@k, cost-adjusted EV)
- Model selection (walk-forward CV, hyperparameter tuning)
- Benchmarking and model cards

Academic References:
- Lopez de Prado (2018): "Advances in Financial Machine Learning"
- Chen & Guestrin (2016): "XGBoost: A Scalable Tree Boosting System"
- Bai et al. (2018): "TCN for Sequence Modeling"
"""

from autotrader.modeling.baselines import (
    LogisticRegressionModel,
    XGBoostModel,
    LightGBMModel
)

from autotrader.modeling.evaluation import (
    ModelEvaluator,
    compute_precision_at_k,
    compute_expected_value,
    calibrate_probabilities
)

from autotrader.modeling.selection import (
    ModelSelector,
    WalkForwardCV,
    optimize_hyperparameters
)

from autotrader.modeling.benchmark import (
    BenchmarkSuite,
    ModelCard
)

__all__ = [
    # Baseline models
    'LogisticRegressionModel',
    'XGBoostModel',
    'LightGBMModel',
    
    # Evaluation
    'ModelEvaluator',
    'compute_precision_at_k',
    'compute_expected_value',
    'calibrate_probabilities',
    
    # Selection
    'ModelSelector',
    'WalkForwardCV',
    'optimize_hyperparameters',
    
    # Benchmarking
    'BenchmarkSuite',
    'ModelCard'
]

__version__ = '6.0.0'
