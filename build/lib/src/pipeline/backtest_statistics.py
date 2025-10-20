"""Statistical rigor enhancements for backtest harness.

Adds:
- Bootstrapped confidence intervals for metrics
- Information Coefficient (IC) distribution reporting  
- Multiple forecast horizons support
- Risk-adjusted variance decomposition (Sharpe/Sortino ratios)
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np
from scipy import stats


@dataclass(slots=True)
class BootstrapResult:
    """Bootstrap confidence interval result."""
    
    mean: float
    std: float
    ci_lower: float  # 95% CI lower bound
    ci_upper: float  # 95% CI upper bound
    median: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "mean": round(self.mean, 4),
            "std": round(self.std, 4),
            "ci_95_lower": round(self.ci_lower, 4),
            "ci_95_upper": round(self.ci_upper, 4),
            "median": round(self.median, 4),
        }


@dataclass(slots=True)
class ICDistribution:
    """Information Coefficient distribution statistics."""
    
    mean_ic: float
    std_ic: float
    ic_ir: float  # IC Information Ratio = mean_ic / std_ic
    positive_pct: float  # % of periods with positive IC
    t_stat: float
    p_value: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "mean_ic": round(self.mean_ic, 4),
            "std_ic": round(self.std_ic, 4),
            "ic_information_ratio": round(self.ic_ir, 4),
            "positive_periods_pct": round(self.positive_pct, 2),
            "t_statistic": round(self.t_stat, 4),
            "p_value": round(self.p_value, 4),
        }


@dataclass(slots=True)
class RiskAdjustedMetrics:
    """Risk-adjusted performance metrics."""
    
    total_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    calmar_ratio: float  # Return / Max Drawdown
    win_rate: float
    profit_factor: float
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "total_return": round(self.total_return, 4),
            "volatility": round(self.volatility, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "sortino_ratio": round(self.sortino_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "calmar_ratio": round(self.calmar_ratio, 4),
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
        }


def bootstrap_confidence_interval(
    values: List[float],
    n_bootstrap: int = 10000,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapResult:
    """Compute bootstrapped confidence intervals for a metric.
    
    Args:
        values: List of metric values from backtest windows
        n_bootstrap: Number of bootstrap samples
        confidence: Confidence level (default 95%)
        seed: Random seed for reproducibility
        
    Returns:
        BootstrapResult with mean, std, and confidence intervals
    """
    if not values:
        raise ValueError("Cannot bootstrap empty values list")
    
    rng = np.random.RandomState(seed)
    values_array = np.array(values)
    
    # Bootstrap resampling
    bootstrap_means = []
    for _ in range(n_bootstrap):
        sample = rng.choice(values_array, size=len(values_array), replace=True)
        bootstrap_means.append(np.mean(sample))
    
    bootstrap_means = np.array(bootstrap_means)
    
    # Compute statistics
    mean = np.mean(bootstrap_means)
    std = np.std(bootstrap_means)
    
    # Confidence interval using percentile method
    alpha = 1 - confidence
    ci_lower = np.percentile(bootstrap_means, 100 * alpha / 2)
    ci_upper = np.percentile(bootstrap_means, 100 * (1 - alpha / 2))
    median = np.median(bootstrap_means)
    
    return BootstrapResult(
        mean=float(mean),
        std=float(std),
        ci_lower=float(ci_lower),
        ci_upper=float(ci_upper),
        median=float(median),
    )


def compute_information_coefficient(
    predictions: List[float],
    actuals: List[float],
) -> Tuple[float, float]:
    """Compute Information Coefficient (IC) between predictions and actuals.
    
    IC is the Spearman rank correlation between forecasts and realized returns.
    
    Args:
        predictions: Predicted scores/returns
        actuals: Actual realized returns
        
    Returns:
        Tuple of (IC, p-value)
    """
    if len(predictions) != len(actuals):
        raise ValueError("Predictions and actuals must have same length")
    
    if len(predictions) < 3:
        raise ValueError("Need at least 3 samples for IC computation")
    
    # Spearman rank correlation
    ic, p_value = stats.spearmanr(predictions, actuals)
    
    return float(ic), float(p_value)


def compute_ic_distribution(
    window_predictions: List[List[float]],
    window_actuals: List[List[float]],
) -> ICDistribution:
    """Compute Information Coefficient distribution across multiple windows.
    
    Args:
        window_predictions: List of prediction lists (one per backtest window)
        window_actuals: List of actual return lists (one per backtest window)
        
    Returns:
        ICDistribution with mean, std, IR, and statistical significance
    """
    if len(window_predictions) != len(window_actuals):
        raise ValueError("Predictions and actuals must have same number of windows")
    
    ics = []
    for preds, actuals in zip(window_predictions, window_actuals):
        if len(preds) >= 3:  # Minimum for correlation
            ic, _ = compute_information_coefficient(preds, actuals)
            ics.append(ic)
    
    if not ics:
        raise ValueError("No valid windows for IC computation")
    
    ics_array = np.array(ics)
    
    mean_ic = np.mean(ics_array)
    std_ic = np.std(ics_array, ddof=1)
    ic_ir = mean_ic / std_ic if std_ic > 0 else 0.0
    positive_pct = 100.0 * np.sum(ics_array > 0) / len(ics_array)
    
    # T-test for significance (H0: mean IC = 0)
    t_stat, p_value = stats.ttest_1samp(ics_array, 0.0)
    
    return ICDistribution(
        mean_ic=float(mean_ic),
        std_ic=float(std_ic),
        ic_ir=float(ic_ir),
        positive_pct=float(positive_pct),
        t_stat=float(t_stat),
        p_value=float(p_value),
    )


def compute_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Compute annualized Sharpe ratio.
    
    Args:
        returns: Period returns (e.g., daily returns)
        risk_free_rate: Risk-free rate per period
        periods_per_year: Number of periods per year (252 for daily)
        
    Returns:
        Annualized Sharpe ratio
    """
    if not returns:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate
    
    mean_excess = np.mean(excess_returns)
    std_excess = np.std(excess_returns, ddof=1)
    
    if std_excess == 0:
        return 0.0
    
    sharpe = mean_excess / std_excess
    return float(sharpe * np.sqrt(periods_per_year))


def compute_sortino_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Compute annualized Sortino ratio.
    
    Sortino ratio uses downside deviation instead of total volatility.
    
    Args:
        returns: Period returns
        risk_free_rate: Risk-free rate per period
        periods_per_year: Number of periods per year
        
    Returns:
        Annualized Sortino ratio
    """
    if not returns:
        return 0.0
    
    returns_array = np.array(returns)
    excess_returns = returns_array - risk_free_rate
    
    mean_excess = np.mean(excess_returns)
    
    # Downside deviation (only negative returns)
    downside_returns = excess_returns[excess_returns < 0]
    if len(downside_returns) == 0:
        return float('inf') if mean_excess > 0 else 0.0
    
    downside_dev = np.std(downside_returns, ddof=1)
    
    if downside_dev == 0:
        return 0.0
    
    sortino = mean_excess / downside_dev
    return float(sortino * np.sqrt(periods_per_year))


def compute_max_drawdown(returns: List[float]) -> float:
    """Compute maximum drawdown from returns series.
    
    Args:
        returns: Period returns
        
    Returns:
        Maximum drawdown (positive value, e.g., 0.25 = 25% drawdown)
    """
    if not returns:
        return 0.0
    
    cumulative = np.cumprod(1 + np.array(returns))
    running_max = np.maximum.accumulate(cumulative)
    drawdown = (running_max - cumulative) / running_max
    
    return float(np.max(drawdown))


def compute_risk_adjusted_metrics(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> RiskAdjustedMetrics:
    """Compute comprehensive risk-adjusted performance metrics.
    
    Args:
        returns: Period returns
        risk_free_rate: Risk-free rate per period
        periods_per_year: Number of periods per year
        
    Returns:
        RiskAdjustedMetrics with Sharpe, Sortino, Calmar, etc.
    """
    if not returns:
        raise ValueError("Cannot compute metrics on empty returns")
    
    returns_array = np.array(returns)
    
    # Total return
    total_return = float(np.prod(1 + returns_array) - 1)
    
    # Volatility (annualized)
    volatility = float(np.std(returns_array, ddof=1) * np.sqrt(periods_per_year))
    
    # Sharpe and Sortino
    sharpe = compute_sharpe_ratio(returns, risk_free_rate, periods_per_year)
    sortino = compute_sortino_ratio(returns, risk_free_rate, periods_per_year)
    
    # Max drawdown
    max_dd = compute_max_drawdown(returns)
    
    # Calmar ratio
    annualized_return = (1 + total_return) ** (periods_per_year / len(returns)) - 1
    calmar = annualized_return / max_dd if max_dd > 0 else 0.0
    
    # Win rate
    winning_periods = np.sum(returns_array > 0)
    win_rate = winning_periods / len(returns_array)
    
    # Profit factor
    gross_profit = np.sum(returns_array[returns_array > 0])
    gross_loss = abs(np.sum(returns_array[returns_array < 0]))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    
    return RiskAdjustedMetrics(
        total_return=total_return,
        volatility=volatility,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=max_dd,
        calmar_ratio=calmar,
        win_rate=win_rate,
        profit_factor=profit_factor,
    )


def compute_variance_decomposition(
    total_returns: List[float],
    component_returns: Dict[str, List[float]],
) -> Dict[str, float]:
    """Decompose total variance into component contributions.
    
    Args:
        total_returns: Total portfolio returns
        component_returns: Dict mapping component name to returns
        
    Returns:
        Dict mapping component to % variance contribution
    """
    total_var = np.var(total_returns, ddof=1)
    
    if total_var == 0:
        return {name: 0.0 for name in component_returns}
    
    variance_contrib = {}
    
    for name, comp_returns in component_returns.items():
        # Covariance between component and total
        cov = np.cov(comp_returns, total_returns)[0, 1]
        # Marginal contribution to variance
        contrib_pct = 100.0 * cov / total_var
        variance_contrib[name] = round(contrib_pct, 2)
    
    return variance_contrib


__all__ = [
    "BootstrapResult",
    "ICDistribution",
    "RiskAdjustedMetrics",
    "bootstrap_confidence_interval",
    "compute_information_coefficient",
    "compute_ic_distribution",
    "compute_sharpe_ratio",
    "compute_sortino_ratio",
    "compute_max_drawdown",
    "compute_risk_adjusted_metrics",
    "compute_variance_decomposition",
]
