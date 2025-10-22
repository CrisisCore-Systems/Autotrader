"""Extended backtest metrics for GemScore evaluation.

Provides advanced performance metrics including:
- Information Coefficient (IC): Correlation between predictions and outcomes
- Sharpe Ratio: Risk-adjusted returns
- Sortino Ratio: Downside risk-adjusted returns
- Maximum Drawdown: Peak-to-trough decline
- Hit Rate: Percentage of correct predictions
- Rank-based metrics: Spearman correlation, Kendall's Tau

These metrics help assess model quality beyond simple precision and return.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import (
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
    average_precision_score,
)


class TokenSnapshot(Protocol):
    """Protocol for token snapshot with minimal required fields."""
    
    token: str
    features: Dict[str, float]
    future_return_7d: float


@dataclass
class ClassificationMetrics:
    """Classification-based metrics (ROC/AUC, PR curves).
    
    These metrics treat the prediction task as binary classification:
    predicting whether returns will be positive or negative.
    """
    
    # ROC metrics
    roc_auc: float  # Area under ROC curve
    roc_curve_fpr: np.ndarray  # False positive rates
    roc_curve_tpr: np.ndarray  # True positive rates
    roc_curve_thresholds: np.ndarray  # Decision thresholds
    
    # Precision-Recall metrics
    pr_auc: float  # Area under PR curve (Average Precision)
    pr_curve_precision: np.ndarray  # Precision values
    pr_curve_recall: np.ndarray  # Recall values
    pr_curve_thresholds: np.ndarray  # Decision thresholds
    
    # Additional metrics
    baseline_accuracy: float  # Majority class baseline
    sample_size: int
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary (excluding curve arrays for JSON serialization)."""
        return {
            'roc_auc': self.roc_auc,
            'pr_auc': self.pr_auc,
            'baseline_accuracy': self.baseline_accuracy,
            'sample_size': self.sample_size,
            # Curve data omitted for brevity - can be stored separately if needed
        }


@dataclass
class ICMetrics:
    """Information Coefficient metrics.
    
    IC measures the correlation between predicted scores and actual returns,
    providing insight into the model's predictive power.
    """
    
    # Correlation metrics
    ic_pearson: float  # Pearson correlation coefficient
    ic_spearman: float  # Spearman rank correlation
    ic_kendall: float  # Kendall's Tau correlation
    
    # Statistical significance
    ic_pearson_pvalue: float
    ic_spearman_pvalue: float
    ic_kendall_pvalue: float
    
    # IC statistics
    ic_mean: float  # Mean IC across periods
    ic_std: float  # IC standard deviation
    ic_ir: float  # Information Ratio (IC_mean / IC_std)
    
    # Additional metrics
    hit_rate: float  # % of correct direction predictions
    sample_size: int  # Number of observations
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'ic_pearson': self.ic_pearson,
            'ic_spearman': self.ic_spearman,
            'ic_kendall': self.ic_kendall,
            'ic_pearson_pvalue': self.ic_pearson_pvalue,
            'ic_spearman_pvalue': self.ic_spearman_pvalue,
            'ic_kendall_pvalue': self.ic_kendall_pvalue,
            'ic_mean': self.ic_mean,
            'ic_std': self.ic_std,
            'ic_ir': self.ic_ir,
            'hit_rate': self.hit_rate,
            'sample_size': self.sample_size,
        }


@dataclass
class RiskMetrics:
    """Risk-adjusted performance metrics."""
    
    # Return metrics
    total_return: float
    annualized_return: float
    mean_return: float
    median_return: float
    
    # Risk metrics
    volatility: float  # Standard deviation of returns
    downside_deviation: float  # Standard deviation of negative returns
    max_drawdown: float  # Maximum peak-to-trough decline
    
    # Risk-adjusted ratios
    sharpe_ratio: float  # (Return - RiskFreeRate) / Volatility
    sortino_ratio: float  # (Return - RiskFreeRate) / DownsideDeviation
    calmar_ratio: float  # AnnualizedReturn / MaxDrawdown
    
    # Additional metrics
    win_rate: float  # % of positive returns
    profit_factor: float  # Sum of wins / Sum of losses
    sample_size: int
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'total_return': self.total_return,
            'annualized_return': self.annualized_return,
            'mean_return': self.mean_return,
            'median_return': self.median_return,
            'volatility': self.volatility,
            'downside_deviation': self.downside_deviation,
            'max_drawdown': self.max_drawdown,
            'sharpe_ratio': self.sharpe_ratio,
            'sortino_ratio': self.sortino_ratio,
            'calmar_ratio': self.calmar_ratio,
            'win_rate': self.win_rate,
            'profit_factor': self.profit_factor,
            'sample_size': self.sample_size,
        }


@dataclass
class ExtendedBacktestMetrics:
    """Comprehensive backtest metrics combining IC, risk, and classification metrics."""
    
    ic_metrics: ICMetrics
    risk_metrics: RiskMetrics
    classification_metrics: Optional[ClassificationMetrics] = None
    baseline_comparisons: Optional[Dict[str, Dict[str, float]]] = None
    metadata: Dict[str, any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to nested dictionary."""
        result = {
            'ic_metrics': self.ic_metrics.to_dict(),
            'risk_metrics': self.risk_metrics.to_dict(),
        }
        
        if self.classification_metrics:
            result['classification_metrics'] = self.classification_metrics.to_dict()
        
        if self.baseline_comparisons:
            result['baseline_comparisons'] = self.baseline_comparisons
        
        if self.metadata:
            result['metadata'] = self.metadata
        
        return result
    
    def summary_string(self) -> str:
        """Generate human-readable summary."""
        lines = []
        lines.append("=" * 70)
        lines.append("EXTENDED BACKTEST METRICS")
        lines.append("=" * 70)
        
        # IC Metrics
        lines.append("\n📊 INFORMATION COEFFICIENT")
        lines.append("-" * 70)
        lines.append(f"  Pearson IC:   {self.ic_metrics.ic_pearson:>8.4f}  "
                    f"(p={self.ic_metrics.ic_pearson_pvalue:.4f})")
        lines.append(f"  Spearman IC:  {self.ic_metrics.ic_spearman:>8.4f}  "
                    f"(p={self.ic_metrics.ic_spearman_pvalue:.4f})")
        lines.append(f"  Kendall Tau:  {self.ic_metrics.ic_kendall:>8.4f}  "
                    f"(p={self.ic_metrics.ic_kendall_pvalue:.4f})")
        lines.append(f"  IC IR:        {self.ic_metrics.ic_ir:>8.4f}  "
                    f"(Information Ratio)")
        lines.append(f"  Hit Rate:     {self.ic_metrics.hit_rate:>8.2%}  "
                    f"(Direction Accuracy)")
        
        # Risk Metrics
        lines.append("\n💰 RETURNS & RISK")
        lines.append("-" * 70)
        lines.append(f"  Total Return:       {self.risk_metrics.total_return:>10.4f}")
        lines.append(f"  Annualized Return:  {self.risk_metrics.annualized_return:>10.4f}")
        lines.append(f"  Mean Return:        {self.risk_metrics.mean_return:>10.4f}")
        lines.append(f"  Median Return:      {self.risk_metrics.median_return:>10.4f}")
        lines.append(f"  Volatility:         {self.risk_metrics.volatility:>10.4f}")
        lines.append(f"  Max Drawdown:       {self.risk_metrics.max_drawdown:>10.4f}")
        
        # Risk-Adjusted Ratios
        lines.append("\n📈 RISK-ADJUSTED PERFORMANCE")
        lines.append("-" * 70)
        lines.append(f"  Sharpe Ratio:   {self.risk_metrics.sharpe_ratio:>8.4f}  "
                    f"(Return / Volatility)")
        lines.append(f"  Sortino Ratio:  {self.risk_metrics.sortino_ratio:>8.4f}  "
                    f"(Return / Downside Risk)")
        lines.append(f"  Calmar Ratio:   {self.risk_metrics.calmar_ratio:>8.4f}  "
                    f"(Return / MaxDrawdown)")
        lines.append(f"  Win Rate:       {self.risk_metrics.win_rate:>8.2%}")
        lines.append(f"  Profit Factor:  {self.risk_metrics.profit_factor:>8.4f}")
        
        # Classification Metrics
        if self.classification_metrics:
            lines.append("\n📊 CLASSIFICATION METRICS (ROC/PR)")
            lines.append("-" * 70)
            lines.append(f"  ROC AUC:        {self.classification_metrics.roc_auc:>8.4f}  "
                        f"(Binary Classification)")
            lines.append(f"  PR AUC:         {self.classification_metrics.pr_auc:>8.4f}  "
                        f"(Average Precision)")
            lines.append(f"  Baseline Acc:   {self.classification_metrics.baseline_accuracy:>8.2%}  "
                        f"(Majority Class)")
        
        # Baseline Comparisons
        if self.baseline_comparisons:
            lines.append("\n🎯 BASELINE COMPARISONS")
            lines.append("-" * 70)
            for baseline, metrics in self.baseline_comparisons.items():
                lines.append(f"\n  {baseline.replace('_', ' ').title()}:")
                for metric, value in metrics.items():
                    if isinstance(value, bool):
                        lines.append(f"    {metric}: {'✅' if value else '❌'}")
                    elif isinstance(value, (int, float)):
                        lines.append(f"    {metric}: {value:>8.4f}")
        
        lines.append("\n" + "=" * 70)
        return "\n".join(lines)


def calculate_ic_metrics(
    predictions: np.ndarray,
    actuals: np.ndarray,
    periods: Optional[List[int]] = None
) -> ICMetrics:
    """Calculate Information Coefficient metrics.
    
    Args:
        predictions: Array of predicted scores/rankings
        actuals: Array of actual returns
        periods: Optional list of period indices for multi-period IC calculation
    
    Returns:
        ICMetrics with correlation and statistical measures
    """
    # Remove NaN values
    mask = ~(np.isnan(predictions) | np.isnan(actuals))
    predictions = predictions[mask]
    actuals = actuals[mask]
    
    if len(predictions) < 2:
        # Not enough data for correlation
        return ICMetrics(
            ic_pearson=0.0, ic_spearman=0.0, ic_kendall=0.0,
            ic_pearson_pvalue=1.0, ic_spearman_pvalue=1.0, ic_kendall_pvalue=1.0,
            ic_mean=0.0, ic_std=0.0, ic_ir=0.0,
            hit_rate=0.0, sample_size=len(predictions)
        )
    
    # Calculate correlation coefficients
    ic_pearson, p_pearson = stats.pearsonr(predictions, actuals)
    ic_spearman, p_spearman = stats.spearmanr(predictions, actuals)
    ic_kendall, p_kendall = stats.kendalltau(predictions, actuals)
    
    # Calculate IC statistics (if periods provided)
    if periods is not None and len(set(periods)) > 1:
        # Calculate per-period IC
        period_ics = []
        for period in set(periods):
            period_mask = np.array(periods) == period
            if np.sum(period_mask) >= 2:
                period_pred = predictions[period_mask]
                period_actual = actuals[period_mask]
                ic, _ = stats.pearsonr(period_pred, period_actual)
                period_ics.append(ic)
        
        ic_mean = np.mean(period_ics) if period_ics else ic_pearson
        ic_std = np.std(period_ics) if len(period_ics) > 1 else 0.0
        ic_ir = ic_mean / ic_std if ic_std > 0 else 0.0
    else:
        # Single period: use overall IC
        ic_mean = ic_pearson
        ic_std = 0.0
        ic_ir = 0.0
    
    # Calculate hit rate (% correct direction predictions)
    pred_direction = np.sign(predictions)
    actual_direction = np.sign(actuals)
    hit_rate = np.mean(pred_direction == actual_direction)
    
    return ICMetrics(
        ic_pearson=ic_pearson,
        ic_spearman=ic_spearman,
        ic_kendall=ic_kendall,
        ic_pearson_pvalue=p_pearson,
        ic_spearman_pvalue=p_spearman,
        ic_kendall_pvalue=p_kendall,
        ic_mean=ic_mean,
        ic_std=ic_std,
        ic_ir=ic_ir,
        hit_rate=hit_rate,
        sample_size=len(predictions),
    )


def calculate_risk_metrics(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 52,  # Weekly returns by default
) -> RiskMetrics:
    """Calculate risk-adjusted performance metrics.
    
    Args:
        returns: Array of period returns
        risk_free_rate: Risk-free rate for Sharpe/Sortino calculation
        periods_per_year: Number of periods per year for annualization
    
    Returns:
        RiskMetrics with return and risk measures
    """
    # Remove NaN values
    returns = returns[~np.isnan(returns)]
    
    if len(returns) == 0:
        # No valid returns
        return RiskMetrics(
            total_return=0.0, annualized_return=0.0,
            mean_return=0.0, median_return=0.0,
            volatility=0.0, downside_deviation=0.0, max_drawdown=0.0,
            sharpe_ratio=0.0, sortino_ratio=0.0, calmar_ratio=0.0,
            win_rate=0.0, profit_factor=0.0, sample_size=0
        )
    
    # Return metrics
    total_return = np.sum(returns)
    mean_return = np.mean(returns)
    median_return = np.median(returns)
    
    # Annualized return (compound)
    if len(returns) > 0:
        cum_return = np.prod(1 + returns) - 1
        annualized_return = (1 + cum_return) ** (periods_per_year / len(returns)) - 1
    else:
        annualized_return = 0.0
    
    # Risk metrics
    volatility = np.std(returns, ddof=1) if len(returns) > 1 else 0.0
    
    # Downside deviation (only negative returns)
    negative_returns = returns[returns < risk_free_rate]
    downside_deviation = (
        np.std(negative_returns, ddof=1) if len(negative_returns) > 1 else 0.0
    )
    
    # Maximum drawdown
    cumulative = np.cumprod(1 + returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    max_drawdown = np.min(drawdowns) if len(drawdowns) > 0 else 0.0
    
    # Risk-adjusted ratios
    excess_return = mean_return - risk_free_rate
    
    sharpe_ratio = (
        excess_return / volatility * np.sqrt(periods_per_year)
        if volatility > 0 else 0.0
    )
    
    sortino_ratio = (
        excess_return / downside_deviation * np.sqrt(periods_per_year)
        if downside_deviation > 0 else 0.0
    )
    
    calmar_ratio = (
        annualized_return / abs(max_drawdown)
        if max_drawdown < 0 else 0.0
    )
    
    # Win rate and profit factor
    win_rate = np.mean(returns > 0)
    
    positive_returns = returns[returns > 0]
    negative_returns = returns[returns < 0]
    profit_factor = (
        np.sum(positive_returns) / abs(np.sum(negative_returns))
        if len(negative_returns) > 0 and np.sum(negative_returns) != 0
        else 0.0
    )
    
    return RiskMetrics(
        total_return=total_return,
        annualized_return=annualized_return,
        mean_return=mean_return,
        median_return=median_return,
        volatility=volatility,
        downside_deviation=downside_deviation,
        max_drawdown=max_drawdown,
        sharpe_ratio=sharpe_ratio,
        sortino_ratio=sortino_ratio,
        calmar_ratio=calmar_ratio,
        win_rate=win_rate,
        profit_factor=profit_factor,
        sample_size=len(returns),
    )


def calculate_classification_metrics(
    predictions: np.ndarray,
    actuals: np.ndarray,
) -> ClassificationMetrics:
    """Calculate classification-based metrics (ROC/AUC, PR curves).
    
    Treats the prediction as binary classification: predicting whether
    returns will be positive (1) or non-positive (0).
    
    Args:
        predictions: Array of predicted scores/rankings
        actuals: Array of actual returns
    
    Returns:
        ClassificationMetrics with ROC/AUC and PR curve data
    """
    # Remove NaN values
    mask = ~(np.isnan(predictions) | np.isnan(actuals))
    predictions = predictions[mask]
    actuals = actuals[mask]
    
    if len(predictions) < 2:
        # Not enough data for classification metrics
        return ClassificationMetrics(
            roc_auc=0.5,
            roc_curve_fpr=np.array([0.0, 1.0]),
            roc_curve_tpr=np.array([0.0, 1.0]),
            roc_curve_thresholds=np.array([0.0, 0.0]),
            pr_auc=0.0,
            pr_curve_precision=np.array([0.0]),
            pr_curve_recall=np.array([1.0]),
            pr_curve_thresholds=np.array([0.0]),
            baseline_accuracy=0.5,
            sample_size=len(predictions),
        )
    
    # Convert returns to binary labels (positive return = 1, else = 0)
    y_true = (actuals > 0).astype(int)
    
    # Baseline accuracy (majority class)
    baseline_accuracy = max(np.mean(y_true), 1 - np.mean(y_true))
    
    # Check if we have both classes
    if len(np.unique(y_true)) < 2:
        # Only one class present - return default metrics
        return ClassificationMetrics(
            roc_auc=0.5,
            roc_curve_fpr=np.array([0.0, 1.0]),
            roc_curve_tpr=np.array([0.0, 1.0]),
            roc_curve_thresholds=np.array([0.0, 0.0]),
            pr_auc=baseline_accuracy,
            pr_curve_precision=np.array([baseline_accuracy]),
            pr_curve_recall=np.array([1.0]),
            pr_curve_thresholds=np.array([0.0]),
            baseline_accuracy=baseline_accuracy,
            sample_size=len(predictions),
        )
    
    # Calculate ROC curve and AUC
    fpr, tpr, roc_thresholds = roc_curve(y_true, predictions)
    roc_auc = roc_auc_score(y_true, predictions)
    
    # Calculate Precision-Recall curve and AUC
    precision, recall, pr_thresholds = precision_recall_curve(y_true, predictions)
    pr_auc = average_precision_score(y_true, predictions)
    
    return ClassificationMetrics(
        roc_auc=roc_auc,
        roc_curve_fpr=fpr,
        roc_curve_tpr=tpr,
        roc_curve_thresholds=roc_thresholds,
        pr_auc=pr_auc,
        pr_curve_precision=precision,
        pr_curve_recall=recall,
        pr_curve_thresholds=pr_thresholds,
        baseline_accuracy=baseline_accuracy,
        sample_size=len(predictions),
    )


def calculate_extended_metrics(
    snapshots: List[TokenSnapshot],
    predictions: np.ndarray,
    top_k: Optional[int] = None,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 52,
    periods: Optional[List[int]] = None,
    include_classification: bool = True,
) -> ExtendedBacktestMetrics:
    """Calculate comprehensive backtest metrics.
    
    Args:
        snapshots: List of token snapshots
        predictions: Array of predicted scores (same length as snapshots)
        top_k: Optional number of top assets to evaluate (None = all assets)
        risk_free_rate: Risk-free rate for ratio calculations
        periods_per_year: Number of periods per year for annualization
        periods: Optional period indices for multi-period IC
        include_classification: Whether to calculate ROC/AUC and PR metrics
    
    Returns:
        ExtendedBacktestMetrics with IC, risk, and classification metrics
    """
    if len(snapshots) != len(predictions):
        raise ValueError("Snapshots and predictions must have same length")
    
    # Extract actual returns
    actuals = np.array([snap.future_return_7d for snap in snapshots])
    
    # If top_k specified, filter to top predictions
    if top_k is not None and top_k < len(predictions):
        top_indices = np.argsort(predictions)[-top_k:]
        predictions = predictions[top_indices]
        actuals = actuals[top_indices]
        if periods is not None:
            periods = [periods[i] for i in top_indices]
    
    # Calculate IC metrics
    ic_metrics = calculate_ic_metrics(predictions, actuals, periods)
    
    # Calculate risk metrics
    risk_metrics = calculate_risk_metrics(
        actuals,
        risk_free_rate=risk_free_rate,
        periods_per_year=periods_per_year
    )
    
    # Calculate classification metrics (ROC/AUC, PR curves)
    classification_metrics = None
    if include_classification:
        classification_metrics = calculate_classification_metrics(predictions, actuals)
    
    # Metadata
    metadata = {
        'total_snapshots': len(snapshots),
        'evaluated_snapshots': len(predictions),
        'top_k': top_k,
        'risk_free_rate': risk_free_rate,
        'periods_per_year': periods_per_year,
        'include_classification': include_classification,
    }
    
    return ExtendedBacktestMetrics(
        ic_metrics=ic_metrics,
        risk_metrics=risk_metrics,
        classification_metrics=classification_metrics,
        metadata=metadata,
    )


def compare_extended_metrics(
    gem_score_metrics: ExtendedBacktestMetrics,
    baseline_metrics: Dict[str, ExtendedBacktestMetrics]
) -> Dict[str, Dict[str, float]]:
    """Compare extended metrics across strategies.
    
    Args:
        gem_score_metrics: Metrics for GemScore strategy
        baseline_metrics: Dict of baseline strategy metrics
    
    Returns:
        Dictionary with comparative metrics
    """
    comparisons = {}
    
    gem_ic = gem_score_metrics.ic_metrics.ic_pearson
    gem_sharpe = gem_score_metrics.risk_metrics.sharpe_ratio
    gem_sortino = gem_score_metrics.risk_metrics.sortino_ratio
    gem_return = gem_score_metrics.risk_metrics.annualized_return
    
    for name, baseline in baseline_metrics.items():
        base_ic = baseline.ic_metrics.ic_pearson
        base_sharpe = baseline.risk_metrics.sharpe_ratio
        base_sortino = baseline.risk_metrics.sortino_ratio
        base_return = baseline.risk_metrics.annualized_return
        
        comparisons[name] = {
            'ic_improvement': gem_ic - base_ic,
            'sharpe_improvement': gem_sharpe - base_sharpe,
            'sortino_improvement': gem_sortino - base_sortino,
            'return_improvement': gem_return - base_return,
            'ic_better': gem_ic > base_ic,
            'sharpe_better': gem_sharpe > base_sharpe,
            'risk_adjusted_better': (
                gem_sharpe > base_sharpe and gem_sortino > base_sortino
            ),
        }
    
    return comparisons


def format_ic_summary(ic_metrics: ICMetrics) -> str:
    """Format IC metrics as summary string.
    
    Args:
        ic_metrics: ICMetrics to format
    
    Returns:
        Formatted string
    """
    lines = []
    lines.append("Information Coefficient Analysis")
    lines.append("-" * 50)
    lines.append(f"Pearson IC:   {ic_metrics.ic_pearson:>7.4f}  (p={ic_metrics.ic_pearson_pvalue:.4f})")
    lines.append(f"Spearman IC:  {ic_metrics.ic_spearman:>7.4f}  (p={ic_metrics.ic_spearman_pvalue:.4f})")
    lines.append(f"Kendall Tau:  {ic_metrics.ic_kendall:>7.4f}  (p={ic_metrics.ic_kendall_pvalue:.4f})")
    
    if ic_metrics.ic_std > 0:
        lines.append(f"\nIC Statistics:")
        lines.append(f"Mean IC:      {ic_metrics.ic_mean:>7.4f}")
        lines.append(f"Std IC:       {ic_metrics.ic_std:>7.4f}")
        lines.append(f"IC IR:        {ic_metrics.ic_ir:>7.4f}")
    
    lines.append(f"\nHit Rate:     {ic_metrics.hit_rate:>7.2%}")
    lines.append(f"Sample Size:  {ic_metrics.sample_size:>7d}")
    
    # Interpretation guide
    lines.append(f"\nInterpretation:")
    if ic_metrics.ic_pearson > 0.05:
        lines.append("  ✅ Strong predictive power (IC > 0.05)")
    elif ic_metrics.ic_pearson > 0.02:
        lines.append("  ⚠️  Moderate predictive power (IC > 0.02)")
    else:
        lines.append("  ❌ Weak predictive power (IC < 0.02)")
    
    if ic_metrics.ic_pearson_pvalue < 0.05:
        lines.append("  ✅ Statistically significant (p < 0.05)")
    else:
        lines.append("  ⚠️  Not statistically significant (p >= 0.05)")
    
    return "\n".join(lines)
