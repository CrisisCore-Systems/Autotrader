"""
Parameter grid search for baseline strategies.
Explores hyperparameter space to find optimal configurations.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List
from itertools import product

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from baseline_strategies import (
    Momentum,
    MeanReversion,
    CrossoverMA,
    BaseStrategy
)


def grid_search_momentum(
    data: pd.DataFrame,
    lookback_periods: List[int],
    transaction_cost: float = 0.001
) -> pd.DataFrame:
    """
    Grid search over momentum strategy lookback periods.
    
    Args:
        data: Market data DataFrame
        lookback_periods: List of lookback windows to test
        transaction_cost: Transaction cost per trade
        
    Returns:
        DataFrame with results for each parameter combination
    """
    print(f"\n🔍 Grid Search: Momentum Strategy")
    print(f"   Testing {len(lookback_periods)} lookback periods...")
    
    results = []
    
    for lookback in lookback_periods:
        strategy = Momentum(lookback=lookback)
        signals = strategy.generate_signals(data)
        metrics = strategy.calculate_returns(data, signals, transaction_cost)
        metrics['lookback'] = lookback
        results.append(metrics)
        print(f"   ✓ lookback={lookback:4d}: Sharpe={metrics['sharpe_ratio']:.4f}, Return={metrics['total_return']:.4f}")
    
    return pd.DataFrame(results)


def grid_search_mean_reversion(
    data: pd.DataFrame,
    lookback_periods: List[int],
    std_thresholds: List[float],
    transaction_cost: float = 0.001
) -> pd.DataFrame:
    """
    Grid search over mean reversion strategy parameters.
    
    Args:
        data: Market data DataFrame
        lookback_periods: List of Bollinger Band lookback windows
        std_thresholds: List of standard deviation thresholds
        transaction_cost: Transaction cost per trade
        
    Returns:
        DataFrame with results for each parameter combination
    """
    print(f"\n🔍 Grid Search: Mean Reversion Strategy")
    print(f"   Testing {len(lookback_periods)} × {len(std_thresholds)} = {len(lookback_periods) * len(std_thresholds)} combinations...")
    
    results = []
    
    for lookback, num_std in product(lookback_periods, std_thresholds):
        strategy = MeanReversion(lookback=lookback, num_std=num_std)
        signals = strategy.generate_signals(data)
        metrics = strategy.calculate_returns(data, signals, transaction_cost)
        metrics['lookback'] = lookback
        metrics['num_std'] = num_std
        results.append(metrics)
        print(f"   ✓ lookback={lookback:4d}, std={num_std:.1f}: Sharpe={metrics['sharpe_ratio']:.4f}")
    
    return pd.DataFrame(results)


def grid_search_ma_crossover(
    data: pd.DataFrame,
    fast_periods: List[int],
    slow_periods: List[int],
    transaction_cost: float = 0.001
) -> pd.DataFrame:
    """
    Grid search over MA crossover strategy parameters.
    
    Args:
        data: Market data DataFrame
        fast_periods: List of fast MA periods
        slow_periods: List of slow MA periods
        transaction_cost: Transaction cost per trade
        
    Returns:
        DataFrame with results for each parameter combination
    """
    print(f"\n🔍 Grid Search: MA Crossover Strategy")
    
    # Filter valid combinations (fast < slow)
    valid_combos = [(f, s) for f, s in product(fast_periods, slow_periods) if f < s]
    print(f"   Testing {len(valid_combos)} valid combinations (fast < slow)...")
    
    results = []
    
    for fast, slow in valid_combos:
        strategy = CrossoverMA(fast=fast, slow=slow)
        signals = strategy.generate_signals(data)
        metrics = strategy.calculate_returns(data, signals, transaction_cost)
        metrics['fast'] = fast
        metrics['slow'] = slow
        results.append(metrics)
        print(f"   ✓ fast={fast:4d}, slow={slow:4d}: Sharpe={metrics['sharpe_ratio']:.4f}")
    
    return pd.DataFrame(results)


def create_heatmap(
    results: pd.DataFrame,
    x_col: str,
    y_col: str,
    metric_col: str,
    title: str,
    output_path: Path
) -> None:
    """
    Create heatmap visualization of parameter search results.
    
    Args:
        results: DataFrame with grid search results
        x_col: Column name for x-axis
        y_col: Column name for y-axis
        metric_col: Column name for metric to visualize
        title: Plot title
        output_path: Path to save figure
    """
    # Pivot data for heatmap
    heatmap_data = results.pivot(index=y_col, columns=x_col, values=metric_col)
    
    # Create figure
    plt.figure(figsize=(12, 8))
    sns.heatmap(
        heatmap_data,
        annot=True,
        fmt='.4f',
        cmap='RdYlGn',
        center=0,
        cbar_kws={'label': metric_col.replace('_', ' ').title()}
    )
    plt.title(title, fontsize=14, fontweight='bold')
    plt.xlabel(x_col.replace('_', ' ').title(), fontsize=12)
    plt.ylabel(y_col.replace('_', ' ').title(), fontsize=12)
    plt.tight_layout()
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"   📊 Heatmap saved: {output_path}")


def find_optimal_parameters(
    results: pd.DataFrame,
    param_cols: List[str],
    metric: str = 'sharpe_ratio'
) -> Dict[str, Any]:
    """
    Find optimal parameter combination based on specified metric.
    
    Args:
        results: DataFrame with grid search results
        param_cols: List of parameter column names
        metric: Metric to optimize (default: sharpe_ratio)
        
    Returns:
        Dict with optimal parameters and performance
    """
    # Find best row
    best_idx = results[metric].idxmax()
    best_row = results.loc[best_idx]
    
    optimal = {
        'metric_optimized': metric,
        'best_value': float(best_row[metric]),
        'parameters': {col: int(best_row[col]) if col in ['lookback', 'fast', 'slow'] else float(best_row[col]) for col in param_cols},
        'performance': {
            'total_return': float(best_row['total_return']),
            'annualized_return': float(best_row['annualized_return']),
            'sharpe_ratio': float(best_row['sharpe_ratio']),
            'sortino_ratio': float(best_row['sortino_ratio']),
            'max_drawdown': float(best_row['max_drawdown']),
            'total_trades': int(best_row['total_trades']),
            'win_rate': float(best_row['win_rate']),
        }
    }
    
    return optimal


def run_full_parameter_search(
    data_path: Path,
    output_dir: Path,
    transaction_cost: float = 0.001
) -> Dict[str, Any]:
    """
    Run complete parameter search across all baseline strategies.
    
    Args:
        data_path: Path to market data parquet
        output_dir: Directory for output files
        transaction_cost: Transaction cost per trade
        
    Returns:
        Dict with all results and optimal parameters
    """
    print(f"{'='*70}")
    print(f"PARAMETER GRID SEARCH")
    print(f"{'='*70}")
    print(f"\n📊 Loading data from {data_path}...")
    
    data = pd.read_parquet(data_path)
    symbol = data_path.stem.replace('_bars_features', '').replace('_bars', '')
    print(f"   Symbol: {symbol}, Bars: {len(data):,}")
    
    output_dir = output_dir / symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_summary = {
        'symbol': symbol,
        'num_bars': len(data),
        'transaction_cost': transaction_cost,
        'strategies': {}
    }
    
    # 1. Momentum grid search
    momentum_lookbacks = [195, 390, 780, 1950, 3900]  # 30min, 1hr, 2hr, 5days, 10days
    momentum_results = grid_search_momentum(data, momentum_lookbacks, transaction_cost)
    momentum_results.to_csv(output_dir / 'momentum_grid_search.csv', index=False)
    
    momentum_optimal = find_optimal_parameters(momentum_results, ['lookback'])
    results_summary['strategies']['momentum'] = momentum_optimal
    
    print(f"\n   🏆 Optimal Momentum: lookback={momentum_optimal['parameters']['lookback']}, "
          f"Sharpe={momentum_optimal['best_value']:.4f}")
    
    # 2. Mean Reversion grid search
    mr_lookbacks = [195, 390, 780, 1950]
    mr_std_thresholds = [1.5, 2.0, 2.5, 3.0]
    mr_results = grid_search_mean_reversion(data, mr_lookbacks, mr_std_thresholds, transaction_cost)
    mr_results.to_csv(output_dir / 'mean_reversion_grid_search.csv', index=False)
    
    # Create heatmap for mean reversion
    create_heatmap(
        mr_results,
        x_col='lookback',
        y_col='num_std',
        metric_col='sharpe_ratio',
        title=f'Mean Reversion: Sharpe Ratio Heatmap ({symbol})',
        output_path=output_dir / 'mean_reversion_heatmap.png'
    )
    
    mr_optimal = find_optimal_parameters(mr_results, ['lookback', 'num_std'])
    results_summary['strategies']['mean_reversion'] = mr_optimal
    
    print(f"\n   🏆 Optimal Mean Reversion: lookback={mr_optimal['parameters']['lookback']}, "
          f"std={mr_optimal['parameters']['num_std']:.1f}, Sharpe={mr_optimal['best_value']:.4f}")
    
    # 3. MA Crossover grid search
    ma_fast_periods = [65, 130, 195, 260, 390]  # 10min, 20min, 30min, 40min, 1hr
    ma_slow_periods = [390, 780, 1170, 1950]     # 1hr, 2hr, 3hr, 5hr
    ma_results = grid_search_ma_crossover(data, ma_fast_periods, ma_slow_periods, transaction_cost)
    ma_results.to_csv(output_dir / 'ma_crossover_grid_search.csv', index=False)
    
    # Create heatmap for MA crossover
    create_heatmap(
        ma_results,
        x_col='fast',
        y_col='slow',
        metric_col='sharpe_ratio',
        title=f'MA Crossover: Sharpe Ratio Heatmap ({symbol})',
        output_path=output_dir / 'ma_crossover_heatmap.png'
    )
    
    ma_optimal = find_optimal_parameters(ma_results, ['fast', 'slow'])
    results_summary['strategies']['ma_crossover'] = ma_optimal
    
    print(f"\n   🏆 Optimal MA Crossover: fast={ma_optimal['parameters']['fast']}, "
          f"slow={ma_optimal['parameters']['slow']}, Sharpe={ma_optimal['best_value']:.4f}")
    
    # Save summary
    with open(output_dir / 'parameter_search_summary.json', 'w') as f:
        json.dump(results_summary, f, indent=2)
    
    # Print summary table
    print(f"\n{'='*70}")
    print(f"OPTIMAL PARAMETERS SUMMARY ({symbol})")
    print(f"{'='*70}\n")
    
    summary_table = []
    for strategy_name, optimal in results_summary['strategies'].items():
        row = {
            'Strategy': strategy_name.replace('_', ' ').title(),
            'Parameters': ', '.join([f"{k}={v}" for k, v in optimal['parameters'].items()]),
            'Sharpe': f"{optimal['performance']['sharpe_ratio']:.4f}",
            'Return': f"{optimal['performance']['total_return']:.4f}",
            'Max DD': f"{optimal['performance']['max_drawdown']:.2%}",
            'Trades': optimal['performance']['total_trades'],
        }
        summary_table.append(row)
    
    summary_df = pd.DataFrame(summary_table)
    print(summary_df.to_string(index=False))
    summary_df.to_csv(output_dir / 'optimal_parameters_summary.csv', index=False)
    
    print(f"\n{'='*70}")
    print(f"Results saved to {output_dir}/")
    print(f"  - *_grid_search.csv (detailed results)")
    print(f"  - *_heatmap.png (visualizations)")
    print(f"  - parameter_search_summary.json (optimal parameters)")
    print(f"  - optimal_parameters_summary.csv (summary table)")
    print(f"{'='*70}\n")
    
    return results_summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Parameter grid search for baseline strategies')
    parser.add_argument('--data', type=Path, required=True,
                       help='Path to market data parquet file')
    parser.add_argument('--output-dir', type=Path, default=Path('reports/parameter_search'),
                       help='Output directory for results')
    parser.add_argument('--transaction-cost', type=float, default=0.001,
                       help='Transaction cost (default 0.1%)')
    
    args = parser.parse_args()
    
    run_full_parameter_search(
        data_path=args.data,
        output_dir=args.output_dir,
        transaction_cost=args.transaction_cost
    )
