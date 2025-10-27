"""
Walk-forward validation with rolling window backtests.
Tests strategy performance on out-of-sample data.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from datetime import timedelta

import pandas as pd
import numpy as np

from baseline_strategies import BaseStrategy, BuyAndHold, Momentum, MeanReversion, CrossoverMA


def split_train_test(
    data: pd.DataFrame,
    train_days: int,
    test_days: int,
    step_days: int = None
) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
    """
    Create rolling window train/test splits.
    
    Args:
        data: Full dataset with timestamp index
        train_days: Training period in days
        test_days: Testing period in days  
        step_days: Step size for rolling (default: test_days)
        
    Returns:
        List of (train_df, test_df) tuples
    """
    if step_days is None:
        step_days = test_days
    
    # Convert days to number of bars (assuming 1-minute bars, 390 bars/day)
    bars_per_day = 390
    train_bars = train_days * bars_per_day
    test_bars = test_days * bars_per_day
    step_bars = step_days * bars_per_day
    
    splits = []
    start_idx = 0
    
    while start_idx + train_bars + test_bars <= len(data):
        train_end = start_idx + train_bars
        test_end = train_end + test_bars
        
        train_df = data.iloc[start_idx:train_end].copy()
        test_df = data.iloc[train_end:test_end].copy()
        
        splits.append((train_df, test_df))
        start_idx += step_bars
    
    return splits


def walk_forward_backtest(
    strategy: BaseStrategy,
    data: pd.DataFrame,
    train_days: int = 120,
    test_days: int = 30,
    step_days: int = 30,
    transaction_cost: float = 0.001
) -> Dict[str, Any]:
    """
    Run walk-forward validation for a strategy.
    
    Args:
        strategy: Strategy instance to test
        data: Full market data
        train_days: Training period in days
        test_days: Testing period in days
        step_days: Step size for rolling window
        transaction_cost: Transaction cost per trade
        
    Returns:
        Dict with walk-forward results
    """
    print(f"\n  Running walk-forward: {strategy.name}")
    print(f"    Train: {train_days} days, Test: {test_days} days, Step: {step_days} days")
    
    splits = split_train_test(data, train_days, test_days, step_days)
    print(f"    Generated {len(splits)} train/test splits")
    
    results = []
    
    for i, (train_df, test_df) in enumerate(splits):
        # Generate signals on test data
        test_signals = strategy.generate_signals(test_df)
        
        # Calculate out-of-sample performance
        positions = test_signals.shift(1).fillna(0)
        position_changes = positions.diff().abs()
        price_returns = test_df['close'].pct_change()
        strategy_returns = positions * price_returns
        costs = position_changes * transaction_cost
        net_returns = strategy_returns - costs
        
        # Metrics
        total_return = (1 + net_returns).prod() - 1
        volatility = net_returns.std() * np.sqrt(252 * 390) if net_returns.std() > 0 else 0
        sharpe = (net_returns.mean() * 252 * 390) / volatility if volatility > 0 else 0
        
        cumulative = (1 + net_returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_dd = drawdown.min()
        
        results.append({
            'split': i + 1,
            'train_start': train_df['timestamp'].iloc[0],
            'train_end': train_df['timestamp'].iloc[-1],
            'test_start': test_df['timestamp'].iloc[0],
            'test_end': test_df['timestamp'].iloc[-1],
            'test_bars': len(test_df),
            'total_return': float(total_return),
            'volatility': float(volatility),
            'sharpe_ratio': float(sharpe),
            'max_drawdown': float(max_dd),
            'trades': int(position_changes[position_changes > 0].count()),
        })
        
        print(f"    Split {i+1}/{len(splits)}: Sharpe={sharpe:.4f}, Return={total_return:.4f}")
    
    # Aggregate statistics
    results_df = pd.DataFrame(results)
    
    summary = {
        'strategy': strategy.name,
        'num_splits': len(splits),
        'train_days': train_days,
        'test_days': test_days,
        'step_days': step_days,
        'avg_sharpe': float(results_df['sharpe_ratio'].mean()),
        'std_sharpe': float(results_df['sharpe_ratio'].std()),
        'avg_return': float(results_df['total_return'].mean()),
        'std_return': float(results_df['total_return'].std()),
        'avg_max_dd': float(results_df['max_drawdown'].mean()),
        'consistency': float((results_df['sharpe_ratio'] > 0).mean()),  # % of positive Sharpe
        'degradation': float(results_df['sharpe_ratio'].iloc[-1] - results_df['sharpe_ratio'].iloc[0]),
        'splits': results
    }
    
    print(f"    Summary: Avg Sharpe={summary['avg_sharpe']:.4f}, Consistency={summary['consistency']:.2%}")
    
    return summary


def run_walk_forward_analysis(
    data_path: Path,
    output_dir: Path,
    train_days: int = 120,
    test_days: int = 30,
    step_days: int = 30,
    transaction_cost: float = 0.001
) -> Dict[str, Any]:
    """
    Run walk-forward analysis for all baseline strategies.
    
    Args:
        data_path: Path to market data
        output_dir: Output directory
        train_days: Training period
        test_days: Testing period
        step_days: Step size
        transaction_cost: Transaction cost
        
    Returns:
        Dict with all results
    """
    print("="*70)
    print("WALK-FORWARD VALIDATION")
    print("="*70)
    
    # Load data
    print(f"\nLoading data from {data_path}...")
    data = pd.read_parquet(data_path)
    symbol = data_path.stem.replace('_bars_features', '').replace('_bars', '')
    print(f"  Symbol: {symbol}, Bars: {len(data):,}")
    
    # Ensure timestamp column
    if 'timestamp' not in data.columns:
        data['timestamp'] = pd.date_range(start='2024-01-01', periods=len(data), freq='1min')
    
    output_dir = output_dir / symbol
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define strategies to test
    strategies = [
        BuyAndHold(),
        Momentum(lookback=390),
        Momentum(lookback=3900),  # Best from parameter search
        MeanReversion(lookback=780, num_std=3.0),  # Best from parameter search
        CrossoverMA(fast=65, slow=1950),  # Best from parameter search
    ]
    
    all_results = {
        'symbol': symbol,
        'num_bars': len(data),
        'train_days': train_days,
        'test_days': test_days,
        'step_days': step_days,
        'transaction_cost': transaction_cost,
        'strategies': {}
    }
    
    # Run walk-forward for each strategy
    for strategy in strategies:
        result = walk_forward_backtest(
            strategy, data, train_days, test_days, step_days, transaction_cost
        )
        all_results['strategies'][strategy.name] = result
        
        # Save individual strategy results
        strategy_name_safe = strategy.name.replace(' ', '_').replace('(', '').replace(')', '').replace(',', '').replace('/', '_')
        splits_df = pd.DataFrame(result['splits'])
        splits_df.to_csv(output_dir / f'{strategy_name_safe}_walk_forward.csv', index=False)
    
    # Save summary
    with open(output_dir / 'walk_forward_summary.json', 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    # Create comparison table
    comparison = []
    for name, result in all_results['strategies'].items():
        comparison.append({
            'Strategy': name,
            'Avg Sharpe': f"{result['avg_sharpe']:.4f}",
            'Std Sharpe': f"{result['std_sharpe']:.4f}",
            'Avg Return': f"{result['avg_return']:.4f}",
            'Consistency': f"{result['consistency']:.1%}",
            'Degradation': f"{result['degradation']:.4f}",
        })
    
    comparison_df = pd.DataFrame(comparison)
    comparison_df.to_csv(output_dir / 'walk_forward_comparison.csv', index=False)
    
    # Print summary
    print("\n" + "="*70)
    print(f"WALK-FORWARD RESULTS ({symbol})")
    print("="*70 + "\n")
    print(comparison_df.to_string(index=False))
    
    print(f"\n{'='*70}")
    print(f"Results saved to {output_dir}/")
    print(f"  - *_walk_forward.csv (split-by-split results)")
    print(f"  - walk_forward_summary.json (full results)")
    print(f"  - walk_forward_comparison.csv (strategy comparison)")
    print("="*70 + "\n")
    
    return all_results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Walk-forward validation')
    parser.add_argument('--data', type=Path, required=True,
                       help='Path to market data parquet')
    parser.add_argument('--output-dir', type=Path, default=Path('reports/walk_forward'),
                       help='Output directory')
    parser.add_argument('--train-days', type=int, default=120,
                       help='Training period in days (default: 120)')
    parser.add_argument('--test-days', type=int, default=30,
                       help='Testing period in days (default: 30)')
    parser.add_argument('--step-days', type=int, default=30,
                       help='Step size in days (default: 30)')
    parser.add_argument('--transaction-cost', type=float, default=0.001,
                       help='Transaction cost (default: 0.1%)')
    
    args = parser.parse_args()
    
    run_walk_forward_analysis(
        data_path=args.data,
        output_dir=args.output_dir,
        train_days=args.train_days,
        test_days=args.test_days,
        step_days=args.step_days,
        transaction_cost=args.transaction_cost
    )
