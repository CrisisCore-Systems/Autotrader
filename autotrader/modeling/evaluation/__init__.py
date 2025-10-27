"""
Model Evaluation Framework
===========================

Comprehensive evaluation metrics for HFT models:
1. Classification metrics (AUC, precision@k, recall@k)
2. Cost-adjusted expected value per trade
3. Probability calibration (Brier score, ECE)
4. Trading metrics (Sharpe, Sortino, max drawdown)
5. Turnover penalty

Academic References:
- Brier (1950): "Verification of Forecasts Expressed in Terms of Probability"
- Guo et al. (2017): "On Calibration of Modern Neural Networks"
- Lopez de Prado (2018): "Advances in Financial Machine Learning"
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    f1_score,
    log_loss,
    brier_score_loss
)
from sklearn.calibration import calibration_curve
from scipy import stats
import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)


def compute_precision_at_k(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    k: Union[int, List[int]]
) -> Union[float, Dict[int, float]]:
    """
    Compute precision@k: precision among top-k predictions.
    
    Critical for trading: If precision@10 = 0.7, then 70% of top-10
    predictions are correct.
    
    Parameters
    ----------
    y_true : np.ndarray
        True labels (0/1)
    y_pred_proba : np.ndarray
        Predicted probabilities
    k : int or list of int
        Top-k values
    
    Returns
    -------
    precision : float or dict
        Precision@k for each k
    
    Example
    -------
    >>> precision = compute_precision_at_k(y_test, y_pred_proba, k=[10, 50, 100])
    >>> print(f"Precision@10: {precision[10]:.4f}")
    """
    if isinstance(k, int):
        k = [k]
    
    # Sort predictions by probability (descending)
    sorted_indices = np.argsort(-y_pred_proba)
    
    precision_dict = {}
    for k_val in k:
        if k_val > len(y_true):
            logger.warning(f"k={k_val} > len(y_true)={len(y_true)}, using len(y_true)")
            k_val = len(y_true)
        
        # Get top-k predictions
        top_k_indices = sorted_indices[:k_val]
        top_k_true = y_true[top_k_indices]
        
        # Compute precision
        precision = np.mean(top_k_true)
        precision_dict[k_val] = precision
    
    return precision_dict if len(k) > 1 else precision_dict[k[0]]


def compute_recall_at_k(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    k: Union[int, List[int]]
) -> Union[float, Dict[int, float]]:
    """
    Compute recall@k: recall among top-k predictions.
    
    Parameters
    ----------
    y_true : np.ndarray
        True labels (0/1)
    y_pred_proba : np.ndarray
        Predicted probabilities
    k : int or list of int
        Top-k values
    
    Returns
    -------
    recall : float or dict
        Recall@k for each k
    """
    if isinstance(k, int):
        k = [k]
    
    # Sort predictions by probability (descending)
    sorted_indices = np.argsort(-y_pred_proba)
    
    # Total positive samples
    total_positives = np.sum(y_true)
    
    recall_dict = {}
    for k_val in k:
        if k_val > len(y_true):
            k_val = len(y_true)
        
        # Get top-k predictions
        top_k_indices = sorted_indices[:k_val]
        top_k_true = y_true[top_k_indices]
        
        # Compute recall
        recall = np.sum(top_k_true) / total_positives if total_positives > 0 else 0.0
        recall_dict[k_val] = recall
    
    return recall_dict if len(k) > 1 else recall_dict[k[0]]


def compute_expected_value(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    returns: Optional[np.ndarray] = None,
    cost_per_trade: float = 0.0002,
    slippage: float = 0.0001,
    threshold: float = 0.5
) -> Dict[str, float]:
    """
    Compute cost-adjusted expected value per trade.
    
    Formula:
        EV = P(correct) × avg_profit - P(wrong) × avg_loss - cost_per_trade
    
    Parameters
    ----------
    y_true : np.ndarray
        True labels (0/1 for classification, or actual returns)
    y_pred_proba : np.ndarray
        Predicted probabilities (or predicted returns)
    returns : np.ndarray, optional
        Actual returns per trade (if available)
    cost_per_trade : float
        Round-trip transaction cost (e.g., 0.0002 = 2 bps)
    slippage : float
        Slippage cost (e.g., 0.0001 = 1 bp)
    threshold : float
        Prediction threshold for classification
    
    Returns
    -------
    metrics : dict
        Dictionary with keys:
        - ev_per_trade: Expected value per trade
        - win_rate: Proportion of winning trades
        - avg_profit: Average profit per winning trade
        - avg_loss: Average loss per losing trade
        - sharpe: Sharpe ratio
        - sortino: Sortino ratio
        - max_drawdown: Maximum drawdown
    
    Example
    -------
    >>> metrics = compute_expected_value(
    ...     y_test, y_pred_proba,
    ...     returns=actual_returns,
    ...     cost_per_trade=0.0002  # 2 bps
    ... )
    >>> print(f"EV per trade: ${metrics['ev_per_trade']:.4f}")
    >>> print(f"Sharpe ratio: {metrics['sharpe']:.4f}")
    """
    # Convert predictions to binary
    y_pred = (y_pred_proba >= threshold).astype(int)
    
    # If returns not provided, simulate them
    if returns is None:
        # Correct predictions = +1%, wrong = -0.5%
        returns = np.where(
            y_pred == y_true,
            0.01,  # 1% profit
            -0.005  # 0.5% loss
        )
    
    # Apply costs
    total_cost = cost_per_trade + slippage
    returns_after_cost = returns - total_cost
    
    # Compute metrics
    win_mask = returns_after_cost > 0
    wins = returns_after_cost[win_mask]
    losses = returns_after_cost[~win_mask]
    
    win_rate = np.mean(win_mask) if len(win_mask) > 0 else 0.0
    avg_profit = np.mean(wins) if len(wins) > 0 else 0.0
    avg_loss = np.mean(losses) if len(losses) > 0 else 0.0
    
    # Expected value per trade
    ev_per_trade = np.mean(returns_after_cost)
    
    # Sharpe ratio (annualized, assuming 252 trading days)
    sharpe = (
        (np.mean(returns_after_cost) * 252) / (np.std(returns_after_cost) * np.sqrt(252))
        if np.std(returns_after_cost) > 0 else 0.0
    )
    
    # Sortino ratio (only downside volatility)
    downside_returns = returns_after_cost[returns_after_cost < 0]
    downside_std = np.std(downside_returns) if len(downside_returns) > 0 else 1e-10
    sortino = (np.mean(returns_after_cost) * 252) / (downside_std * np.sqrt(252))
    
    # Maximum drawdown
    cumulative = np.cumsum(returns_after_cost)
    running_max = np.maximum.accumulate(cumulative)
    drawdown = cumulative - running_max
    max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0.0
    
    return {
        'ev_per_trade': ev_per_trade,
        'win_rate': win_rate,
        'avg_profit': avg_profit,
        'avg_loss': avg_loss,
        'sharpe': sharpe,
        'sortino': sortino,
        'max_drawdown': max_drawdown,
        'total_return': np.sum(returns_after_cost),
        'num_trades': len(returns_after_cost)
    }


def compute_turnover_penalty(
    positions: np.ndarray,
    returns: np.ndarray,
    cost_per_trade: float = 0.0002,
    penalty: float = 0.01
) -> Dict[str, float]:
    """
    Compute turnover penalty and penalized Sharpe ratio.
    
    High turnover increases transaction costs and market impact.
    
    Parameters
    ----------
    positions : np.ndarray
        Position sizes over time (-1, 0, 1 for short/flat/long)
    returns : np.ndarray
        Returns per period
    cost_per_trade : float
        Cost per trade (e.g., 0.0002 = 2 bps)
    penalty : float
        Penalty per trade (e.g., 0.01 = 1% penalty)
    
    Returns
    -------
    metrics : dict
        Dictionary with keys:
        - turnover_rate: Number of trades per period
        - total_cost: Total transaction costs
        - penalized_sharpe: Sharpe ratio after turnover penalty
        - penalized_return: Total return after costs
    """
    # Compute position changes (trades)
    position_changes = np.diff(positions, prepend=0)
    num_trades = np.sum(np.abs(position_changes) > 0)
    turnover_rate = num_trades / len(positions) if len(positions) > 0 else 0.0
    
    # Transaction costs
    total_cost = num_trades * cost_per_trade
    
    # Penalized returns
    penalized_returns = returns - turnover_rate * penalty
    
    # Penalized Sharpe
    penalized_sharpe = (
        (np.mean(penalized_returns) * 252) / (np.std(penalized_returns) * np.sqrt(252))
        if np.std(penalized_returns) > 0 else 0.0
    )
    
    return {
        'turnover_rate': turnover_rate,
        'num_trades': num_trades,
        'total_cost': total_cost,
        'penalized_sharpe': penalized_sharpe,
        'penalized_return': np.sum(penalized_returns)
    }


def calibrate_probabilities(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    method: str = 'isotonic'
) -> np.ndarray:
    """
    Calibrate predicted probabilities.
    
    Well-calibrated probabilities: predicted probability matches empirical frequency.
    Example: If model predicts 0.7, then 70% of those predictions should be correct.
    
    Parameters
    ----------
    y_true : np.ndarray
        True labels
    y_pred_proba : np.ndarray
        Predicted probabilities
    method : str
        Calibration method ('isotonic' or 'sigmoid')
        - isotonic: Non-parametric (monotonic)
        - sigmoid: Parametric (Platt scaling)
    
    Returns
    -------
    calibrated_proba : np.ndarray
        Calibrated probabilities
    
    References
    ----------
    - Platt (1999): "Probabilistic Outputs for Support Vector Machines"
    - Zadrozny & Elkan (2001): "Obtaining Calibrated Probability Estimates"
    """
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.base import BaseEstimator
    
    # Dummy estimator (already have probabilities)
    class DummyEstimator(BaseEstimator):
        def fit(self, X, y):
            return self
        def predict_proba(self, X):
            return X
    
    # Calibrate
    calibrator = CalibratedClassifierCV(
        DummyEstimator(),
        method=method,
        cv='prefit'
    )
    
    # Reshape for sklearn
    y_pred_proba_2d = np.column_stack([1 - y_pred_proba, y_pred_proba])
    calibrator.fit(y_pred_proba_2d, y_true)
    
    # Get calibrated probabilities
    calibrated_proba_2d = calibrator.predict_proba(y_pred_proba_2d)
    
    return calibrated_proba_2d[:, 1]


def compute_calibration_metrics(
    y_true: np.ndarray,
    y_pred_proba: np.ndarray,
    n_bins: int = 10
) -> Dict[str, float]:
    """
    Compute probability calibration metrics.
    
    Parameters
    ----------
    y_true : np.ndarray
        True labels
    y_pred_proba : np.ndarray
        Predicted probabilities
    n_bins : int
        Number of bins for calibration curve
    
    Returns
    -------
    metrics : dict
        Dictionary with keys:
        - brier_score: Brier score (lower is better)
        - ece: Expected Calibration Error
        - mce: Maximum Calibration Error
    
    References
    ----------
    - Brier (1950): "Verification of Forecasts Expressed in Terms of Probability"
    - Guo et al. (2017): "On Calibration of Modern Neural Networks"
    """
    # Brier score (MSE of probabilities)
    brier = brier_score_loss(y_true, y_pred_proba)
    
    # Calibration curve
    prob_true, prob_pred = calibration_curve(
        y_true, y_pred_proba,
        n_bins=n_bins,
        strategy='quantile'
    )
    
    # Expected Calibration Error (ECE)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    bin_indices = np.digitize(y_pred_proba, bin_edges) - 1
    bin_indices = np.clip(bin_indices, 0, n_bins - 1)
    
    ece = 0.0
    mce = 0.0
    for i in range(n_bins):
        bin_mask = bin_indices == i
        if np.sum(bin_mask) > 0:
            bin_acc = np.mean(y_true[bin_mask])
            bin_conf = np.mean(y_pred_proba[bin_mask])
            bin_size = np.sum(bin_mask) / len(y_true)
            
            error = np.abs(bin_acc - bin_conf)
            ece += bin_size * error
            mce = max(mce, error)
    
    return {
        'brier_score': brier,
        'ece': ece,
        'mce': mce
    }


class ModelEvaluator:
    """
    Comprehensive model evaluation for HFT.
    
    Evaluates models using:
    1. Classification metrics (AUC, precision@k, F1)
    2. Cost-adjusted expected value
    3. Probability calibration
    4. Trading metrics (Sharpe, Sortino)
    
    Example
    -------
    >>> evaluator = ModelEvaluator()
    >>> metrics = evaluator.evaluate(
    ...     model=xgb_model,
    ...     X_test=X_test,
    ...     y_test=y_test,
    ...     returns=actual_returns,
    ...     cost_per_trade=0.0002,
    ...     k=[10, 50, 100]
    ... )
    >>> print(f"AUC: {metrics['auc']:.4f}")
    >>> print(f"Precision@10: {metrics['precision@10']:.4f}")
    >>> print(f"EV per trade: ${metrics['ev_per_trade']:.4f}")
    >>> print(f"Sharpe: {metrics['sharpe']:.4f}")
    """
    
    def __init__(self):
        self.results = {}
    
    def evaluate(
        self,
        model,
        X_test: Union[np.ndarray, pd.DataFrame],
        y_test: Union[np.ndarray, pd.Series],
        returns: Optional[np.ndarray] = None,
        cost_per_trade: float = 0.0002,
        slippage: float = 0.0001,
        k: List[int] = [10, 50, 100],
        calibrate: bool = False
    ) -> Dict[str, float]:
        """
        Evaluate model comprehensively.
        
        Parameters
        ----------
        model : object
            Trained model with predict_proba method
        X_test : array-like
            Test features
        y_test : array-like
            Test labels
        returns : np.ndarray, optional
            Actual returns per trade
        cost_per_trade : float
            Transaction cost per trade
        slippage : float
            Slippage cost
        k : list of int
            Top-k values for precision/recall
        calibrate : bool
            Whether to calibrate probabilities
        
        Returns
        -------
        metrics : dict
            Comprehensive evaluation metrics
        """
        # Convert to numpy
        if isinstance(X_test, pd.DataFrame):
            X_test = X_test.values
        if isinstance(y_test, pd.Series):
            y_test = y_test.values
        
        # Get predictions
        y_pred_proba = model.predict_proba(X_test)[:, 1]
        y_pred = model.predict(X_test)
        
        # Calibrate if requested
        if calibrate:
            y_pred_proba = calibrate_probabilities(y_test, y_pred_proba)
        
        # Classification metrics
        auc = roc_auc_score(y_test, y_pred_proba)
        precision = precision_score(y_test, y_pred)
        recall = recall_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred)
        logloss = log_loss(y_test, y_pred_proba)
        
        # Precision/Recall @ k
        precision_at_k = compute_precision_at_k(y_test, y_pred_proba, k)
        recall_at_k = compute_recall_at_k(y_test, y_pred_proba, k)
        
        # Expected value metrics
        ev_metrics = compute_expected_value(
            y_test, y_pred_proba,
            returns=returns,
            cost_per_trade=cost_per_trade,
            slippage=slippage
        )
        
        # Calibration metrics
        cal_metrics = compute_calibration_metrics(y_test, y_pred_proba)
        
        # Combine all metrics
        metrics = {
            'auc': auc,
            'precision': precision,
            'recall': recall,
            'f1': f1,
            'logloss': logloss,
            **{f'precision@{k_val}': v for k_val, v in precision_at_k.items()},
            **{f'recall@{k_val}': v for k_val, v in recall_at_k.items()},
            **ev_metrics,
            **cal_metrics
        }
        
        return metrics
    
    def compare_models(
        self,
        models: Dict[str, object],
        X_test: Union[np.ndarray, pd.DataFrame],
        y_test: Union[np.ndarray, pd.Series],
        **kwargs
    ) -> pd.DataFrame:
        """
        Compare multiple models.
        
        Parameters
        ----------
        models : dict
            Dictionary of {model_name: model}
        X_test : array-like
            Test features
        y_test : array-like
            Test labels
        **kwargs : dict
            Additional arguments for evaluate()
        
        Returns
        -------
        comparison : pd.DataFrame
            Comparison table with metrics per model
        """
        results = {}
        for name, model in models.items():
            logger.info(f"Evaluating {name}...")
            metrics = self.evaluate(model, X_test, y_test, **kwargs)
            results[name] = metrics
        
        # Convert to dataframe
        comparison_df = pd.DataFrame(results).T
        
        # Sort by expected value (best metric for trading)
        comparison_df = comparison_df.sort_values('ev_per_trade', ascending=False)
        
        return comparison_df
    
    def plot_calibration_curve(
        self,
        y_true: np.ndarray,
        y_pred_proba: np.ndarray,
        y_pred_proba_calibrated: Optional[np.ndarray] = None,
        n_bins: int = 10
    ):
        """
        Plot calibration curve.
        
        Parameters
        ----------
        y_true : np.ndarray
            True labels
        y_pred_proba : np.ndarray
            Predicted probabilities (uncalibrated)
        y_pred_proba_calibrated : np.ndarray, optional
            Calibrated probabilities
        n_bins : int
            Number of bins
        """
        fig, ax = plt.subplots(figsize=(8, 8))
        
        # Perfect calibration line
        ax.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
        
        # Uncalibrated
        prob_true, prob_pred = calibration_curve(
            y_true, y_pred_proba, n_bins=n_bins, strategy='quantile'
        )
        ax.plot(prob_pred, prob_true, 's-', label='Uncalibrated')
        
        # Calibrated
        if y_pred_proba_calibrated is not None:
            prob_true_cal, prob_pred_cal = calibration_curve(
                y_true, y_pred_proba_calibrated, n_bins=n_bins, strategy='quantile'
            )
            ax.plot(prob_pred_cal, prob_true_cal, 'o-', label='Calibrated')
        
        ax.set_xlabel('Predicted probability')
        ax.set_ylabel('Empirical frequency')
        ax.set_title('Probability Calibration Curve')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig


# Convenience functions
def precision_at_k(y_true, y_pred_proba, k):
    """Alias for compute_precision_at_k."""
    return compute_precision_at_k(y_true, y_pred_proba, k)

def recall_at_k(y_true, y_pred_proba, k):
    """Alias for compute_recall_at_k."""
    return compute_recall_at_k(y_true, y_pred_proba, k)

def expected_value(y_true, y_pred_proba, **kwargs):
    """Alias for compute_expected_value."""
    return compute_expected_value(y_true, y_pred_proba, **kwargs)
