"""
Comparative backtesting framework for validation roadmap.
Compares agentic system against baseline strategies with statistical tests.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List
import warnings

import pandas as pd
import numpy as np
from scipy import stats

# Import baseline strategies
from baseline_strategies import (
    BuyAndHold,
    Momentum,
    MeanReversion,
    CrossoverMA,
    run_baseline_comparison
)


def load_agentic_predictions(predictions_path: Path) -> pd.DataFrame:
    """
    Load predictions from agentic system.
    Expected format: parquet with columns [timestamp, symbol, prediction, confidence]
    """
    if not predictions_path.exists():
        warnings.warn(f"Agentic predictions not found at {predictions_path}. Using random baseline.")
        return None
    
    return pd.read_parquet(predictions_path)


def generate_agentic_signals(data: pd.DataFrame, predictions: pd.DataFrame | None) -> pd.Series:
    """
    Convert agentic predictions to trading signals.
    
    Args:
        data: Market data DataFrame
        predictions: Agentic system predictions (or None for random baseline)
        
    Returns:
        Series of trading signals (-1, 0, 1)
    """
    if predictions is None:
        # Fallback: random signals for testing
        np.random.seed(42)
        return pd.Series(
            np.random.choice([-1, 0, 1], size=len(data), p=[0.2, 0.6, 0.2]),
            index=data.index
        )
    
    # Merge predictions with data
    merged = data.merge(
        predictions[['timestamp', 'prediction']],
        left_on='timestamp',
        right_on='timestamp',
        how='left'
    )
    
    # Convert predictions to signals
    signals = merged['prediction'].fillna(0)
    return signals


def calculate_strategy_stats(returns: pd.Series) -> Dict[str, float]:
    """Calculate detailed statistics for a return series."""
    if len(returns) == 0 or returns.std() == 0:
        return {
            'mean_return': 0.0,
            'std_return': 0.0,
            'skewness': 0.0,
            'kurtosis': 0.0,
            'var_95': 0.0,
            'cvar_95': 0.0,
        }
    
    return {
        'mean_return': returns.mean(),
        'std_return': returns.std(),
        'skewness': returns.skew(),
        'kurtosis': returns.kurtosis(),
        'var_95': returns.quantile(0.05),  # Value at Risk
        'cvar_95': returns[returns <= returns.quantile(0.05)].mean(),  # Conditional VaR
    }


def statistical_comparison(
    agentic_returns: pd.Series,
    baseline_returns: pd.Series,
    strategy_name: str
) -> Dict[str, Any]:
    """
    Perform statistical tests comparing agentic vs baseline strategy.
    
    Tests:
    - T-test for mean return difference
    - F-test for variance ratio
    - Kolmogorov-Smirnov test for distribution similarity
    """
    # T-test for mean difference
    t_stat, t_pval = stats.ttest_ind(agentic_returns, baseline_returns, equal_var=False)
    
    # F-test for variance ratio
    var_ratio = agentic_returns.var() / baseline_returns.var() if baseline_returns.var() > 0 else np.nan
    
    # KS test for distribution
    ks_stat, ks_pval = stats.ks_2samp(agentic_returns, baseline_returns)
    
    # Mean return comparison
    mean_diff = agentic_returns.mean() - baseline_returns.mean()
    mean_diff_pct = (mean_diff / abs(baseline_returns.mean())) * 100 if baseline_returns.mean() != 0 else np.nan
    
    return {
        'comparison': f"Agentic vs {strategy_name}",
        't_statistic': t_stat,
        't_pvalue': t_pval,
        'significant_at_5pct': t_pval < 0.05,
        'mean_return_diff': mean_diff,
        'mean_return_diff_pct': mean_diff_pct,
        'variance_ratio': var_ratio,
        'ks_statistic': ks_stat,
        'ks_pvalue': ks_pval,
        'distributions_different': ks_pval < 0.05,
    }


def run_comparative_backtest(
    data_path: Path,
    predictions_path: Path | None,
    output_dir: Path,
    transaction_cost: float = 0.001
) -> Dict[str, Any]:
    """
    Run full comparative backtest: agentic system vs baseline strategies.
    
    Args:
        data_path: Path to market data parquet
        predictions_path: Path to agentic predictions (None for random baseline)
        output_dir: Directory for output reports
        transaction_cost: Transaction cost per trade
        
    Returns:
        Dict with all results and comparisons
    """
    print(f"📊 Loading market data from {data_path}...")
    data = pd.read_parquet(data_path)
    print(f"   Loaded {len(data):,} bars")
    
    # Load or generate agentic signals
    print(f"\n🤖 Loading agentic predictions...")
    predictions = load_agentic_predictions(predictions_path) if predictions_path else None
    agentic_signals = generate_agentic_signals(data, predictions)
    
    # Calculate agentic system performance
    print(f"\n🔬 Calculating agentic system performance...")
    positions = agentic_signals.shift(1).fillna(0)
    position_changes = positions.diff().abs()
    price_returns = data['close'].pct_change()
    strategy_returns = positions * price_returns
    costs = position_changes * transaction_cost
    agentic_returns = strategy_returns - costs
    
    cumulative_returns = (1 + agentic_returns).cumprod()
    total_return = cumulative_returns.iloc[-1] - 1
    annualized_return = (1 + total_return) ** (252 / (len(data) / 390)) - 1
    volatility = agentic_returns.std() * np.sqrt(252 * 390)
    sharpe_ratio = annualized_return / volatility if volatility > 0 else 0.0
    
    # Downside metrics
    downside_returns = agentic_returns[agentic_returns < 0]
    downside_dev = downside_returns.std() * np.sqrt(252 * 390)
    sortino_ratio = annualized_return / downside_dev if downside_dev > 0 else 0.0
    
    # Max drawdown
    running_max = cumulative_returns.expanding().max()
    drawdown = (cumulative_returns - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # Trade stats
    trades = position_changes[position_changes > 0].count()
    win_rate = (agentic_returns[agentic_returns > 0].count() / len(agentic_returns)) if len(agentic_returns) > 0 else 0.0
    
    agentic_metrics = {
        'strategy': 'Agentic System',
        'total_return': total_return,
        'annualized_return': annualized_return,
        'volatility': volatility,
        'sharpe_ratio': sharpe_ratio,
        'sortino_ratio': sortino_ratio,
        'max_drawdown': max_drawdown,
        'total_trades': int(trades),
        'win_rate': win_rate,
        'final_value': cumulative_returns.iloc[-1],
    }
    
    # Run baseline strategies
    print(f"\n📈 Running baseline strategies...")
    baseline_results = run_baseline_comparison(data, transaction_cost=transaction_cost)
    
    # Combine results
    all_results = pd.concat([
        pd.DataFrame([agentic_metrics]),
        baseline_results
    ], ignore_index=True)
    
    # Statistical comparisons
    print(f"\n📊 Running statistical tests...")
    comparisons = []
    
    for _, baseline_row in baseline_results.iterrows():
        strategy_name = baseline_row['strategy']
        
        # Re-generate baseline signals to get returns
        if strategy_name.startswith('Buy & Hold'):
            strategy = BuyAndHold()
        elif strategy_name.startswith('Momentum'):
            lookback = int(strategy_name.split('(')[1].split(')')[0])
            strategy = Momentum(lookback=lookback)
        elif strategy_name.startswith('Mean Reversion'):
            strategy = MeanReversion()
        elif strategy_name.startswith('MA Crossover'):
            strategy = CrossoverMA()
        else:
            continue
        
        baseline_signals = strategy.generate_signals(data)
        baseline_positions = baseline_signals.shift(1).fillna(0)
        baseline_position_changes = baseline_positions.diff().abs()
        baseline_strategy_returns = baseline_positions * price_returns
        baseline_costs = baseline_position_changes * transaction_cost
        baseline_returns_series = baseline_strategy_returns - baseline_costs
        
        comparison = statistical_comparison(
            agentic_returns,
            baseline_returns_series,
            strategy_name
        )
        comparisons.append(comparison)
    
    statistical_tests = pd.DataFrame(comparisons)
    
    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_results.to_csv(output_dir / 'strategy_comparison.csv', index=False)
    statistical_tests.to_csv(output_dir / 'statistical_tests.csv', index=False)
    
    # Create summary report
    summary = {
        'data_file': str(data_path),
        'num_bars': len(data),
        'transaction_cost': transaction_cost,
        'agentic_performance': agentic_metrics,
        'baseline_count': len(baseline_results),
        'best_baseline': baseline_results.loc[baseline_results['sharpe_ratio'].idxmax()].to_dict(),
        'significant_improvements': int(statistical_tests['significant_at_5pct'].sum()),
        'average_return_improvement_pct': float(statistical_tests['mean_return_diff_pct'].mean()),
    }
    
    with open(output_dir / 'summary.json', 'w') as f:
        json.dump(summary, f, indent=2)
    
    # Print summary
    print(f"\n{'='*70}")
    print(f"COMPARATIVE BACKTEST RESULTS")
    print(f"{'='*70}\n")
    
    print("Performance Comparison:")
    print(all_results[['strategy', 'total_return', 'sharpe_ratio', 'sortino_ratio', 'max_drawdown']].to_string(index=False))
    
    print(f"\n\nStatistical Tests (Agentic vs Baselines):")
    print(statistical_tests[['comparison', 't_pvalue', 'significant_at_5pct', 'mean_return_diff_pct']].to_string(index=False))
    
    print(f"\n\n{'='*70}")
    print(f"Results saved to {output_dir}/")
    print(f"  - strategy_comparison.csv")
    print(f"  - statistical_tests.csv")
    print(f"  - summary.json")
    print(f"{'='*70}\n")
    
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run comparative backtest')
    parser.add_argument('--data', type=Path, required=True,
                       help='Path to market data parquet file')
    parser.add_argument('--predictions', type=Path, default=None,
                       help='Path to agentic predictions parquet (optional)')
    parser.add_argument('--output-dir', type=Path, default=Path('reports/comparative_backtest'),
                       help='Output directory for reports')
    parser.add_argument('--transaction-cost', type=float, default=0.001,
                       help='Transaction cost (default 0.1%)')
    
    args = parser.parse_args()
    
    run_comparative_backtest(
        data_path=args.data,
        predictions_path=args.predictions,
        output_dir=args.output_dir,
        transaction_cost=args.transaction_cost
    )
