"""
Multi-symbol portfolio analysis for validation.
Aggregates performance across symbols and asset classes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from baseline_strategies import BaseStrategy, BuyAndHold, Momentum, CrossoverMA


def load_all_symbols(data_dir: Path, symbols: List[str]) -> Dict[str, pd.DataFrame]:
    """Load market data for all symbols."""
    datasets = {}
    for symbol in symbols:
        file_path = data_dir / f"{symbol}_bars_features.parquet"
        if file_path.exists():
            datasets[symbol] = pd.read_parquet(file_path)
            print(f"  Loaded {symbol}: {len(datasets[symbol]):,} bars")
        else:
            print(f"  Warning: {file_path} not found, skipping")
    return datasets


def calculate_strategy_returns(
    strategy: BaseStrategy,
    datasets: Dict[str, pd.DataFrame],
    transaction_cost: float = 0.001
) -> pd.DataFrame:
    """
    Calculate strategy returns for all symbols.
    
    Returns:
        DataFrame with returns for each symbol (index=timestamp, columns=symbols)
    """
    all_returns = {}
    
    for symbol, data in datasets.items():
        signals = strategy.generate_signals(data)
        positions = signals.shift(1).fillna(0)
        position_changes = positions.diff().abs()
        price_returns = data['close'].pct_change()
        strategy_returns = positions * price_returns
        costs = position_changes * transaction_cost
        net_returns = strategy_returns - costs
        
        all_returns[symbol] = net_returns
    
    # Align all returns to common index
    returns_df = pd.DataFrame(all_returns)
    return returns_df.fillna(0)


def calculate_correlation_matrix(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate correlation matrix of returns."""
    return returns_df.corr()


def calculate_portfolio_metrics(
    returns_df: pd.DataFrame,
    weights: Dict[str, float] | None = None
) -> Dict[str, float]:
    """
    Calculate portfolio-level performance metrics.
    
    Args:
        returns_df: DataFrame with returns for each symbol
        weights: Portfolio weights (default: equal weight)
        
    Returns:
        Dict with portfolio metrics
    """
    if weights is None:
        # Equal weight portfolio
        weights = {col: 1.0 / len(returns_df.columns) for col in returns_df.columns}
    
    # Calculate portfolio returns
    portfolio_returns = sum(returns_df[symbol] * weight for symbol, weight in weights.items())
    
    # Metrics
    total_return = (1 + portfolio_returns).prod() - 1
    annualized_return = (1 + total_return) ** (252 / (len(portfolio_returns) / 390)) - 1
    volatility = portfolio_returns.std() * np.sqrt(252 * 390)
    sharpe = annualized_return / volatility if volatility > 0 else 0
    
    # Downside metrics
    downside_returns = portfolio_returns[portfolio_returns < 0]
    downside_dev = downside_returns.std() * np.sqrt(252 * 390) if len(downside_returns) > 0 else 0
    sortino = annualized_return / downside_dev if downside_dev > 0 else 0
    
    # Drawdown
    cumulative = (1 + portfolio_returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = drawdown.min()
    
    return {
        'total_return': float(total_return),
        'annualized_return': float(annualized_return),
        'volatility': float(volatility),
        'sharpe_ratio': float(sharpe),
        'sortino_ratio': float(sortino),
        'max_drawdown': float(max_dd),
    }


def calculate_diversification_benefit(
    returns_df: pd.DataFrame,
    individual_metrics: Dict[str, Dict[str, float]]
) -> float:
    """
    Calculate diversification benefit as portfolio Sharpe vs avg individual Sharpe.
    
    Returns:
        Diversification ratio (portfolio_sharpe / avg_individual_sharpe)
    """
    portfolio_metrics = calculate_portfolio_metrics(returns_df)
    avg_individual_sharpe = np.mean([m['sharpe_ratio'] for m in individual_metrics.values()])
    
    if avg_individual_sharpe > 0:
        return portfolio_metrics['sharpe_ratio'] / avg_individual_sharpe
    return 0.0


def plot_correlation_heatmap(corr_matrix: pd.DataFrame, output_path: Path) -> None:
    """Create correlation matrix heatmap."""
    plt.figure(figsize=(10, 8))
    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt='.2f',
        cmap='coolwarm',
        center=0,
        vmin=-1,
        vmax=1,
        square=True,
        cbar_kws={'label': 'Correlation'}
    )
    plt.title('Strategy Returns Correlation Matrix', fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def run_portfolio_analysis(
    data_dir: Path,
    output_dir: Path,
    symbols: List[str],
    transaction_cost: float = 0.001
) -> Dict[str, Any]:
    """
    Run comprehensive portfolio analysis.
    
    Args:
        data_dir: Directory with parquet files
        output_dir: Output directory
        symbols: List of symbols to analyze
        transaction_cost: Transaction cost
        
    Returns:
        Dict with all analysis results
    """
    print("="*70)
    print("PORTFOLIO ANALYSIS")
    print("="*70)
    
    # Load data
    print(f"\nLoading {len(symbols)} symbols from {data_dir}...")
    datasets = load_all_symbols(data_dir, symbols)
    
    if len(datasets) == 0:
        raise ValueError("No data loaded. Check data directory and symbol names.")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define strategies
    strategies = [
        BuyAndHold(),
        Momentum(lookback=3900),
        CrossoverMA(fast=65, slow=1950),
    ]
    
    results = {
        'symbols': list(datasets.keys()),
        'num_symbols': len(datasets),
        'transaction_cost': transaction_cost,
        'strategies': {}
    }
    
    for strategy in strategies:
        print(f"\n{strategy.name}")
        print("-" * 70)
        
        # Calculate returns for all symbols
        returns_df = calculate_strategy_returns(strategy, datasets, transaction_cost)
        
        # Individual symbol metrics
        individual_metrics = {}
        for symbol in returns_df.columns:
            symbol_returns = returns_df[symbol]
            individual_metrics[symbol] = {
                'sharpe_ratio': float((symbol_returns.mean() * 252 * 390) / (symbol_returns.std() * np.sqrt(252 * 390))) if symbol_returns.std() > 0 else 0,
                'total_return': float((1 + symbol_returns).prod() - 1),
            }
            print(f"  {symbol}: Sharpe={individual_metrics[symbol]['sharpe_ratio']:.4f}, Return={individual_metrics[symbol]['total_return']:.4f}")
        
        # Correlation matrix
        strategy_name_safe = strategy.name.replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')
        corr_matrix = calculate_correlation_matrix(returns_df)
        corr_matrix.to_csv(output_dir / f'{strategy_name_safe}_correlation.csv')
        
        # Plot heatmap
        plot_correlation_heatmap(
            corr_matrix,
            output_dir / f'{strategy_name_safe}_correlation_heatmap.png'
        )
        
        # Portfolio metrics (equal weight)
        portfolio_metrics = calculate_portfolio_metrics(returns_df)
        
        # Diversification benefit
        div_benefit = calculate_diversification_benefit(returns_df, individual_metrics)
        
        print(f"\n  Portfolio (Equal Weight):")
        print(f"    Sharpe: {portfolio_metrics['sharpe_ratio']:.4f}")
        print(f"    Return: {portfolio_metrics['total_return']:.4f}")
        print(f"    Max DD: {portfolio_metrics['max_drawdown']:.2%}")
        print(f"    Diversification Benefit: {div_benefit:.2f}x")
        
        # Store results
        strategy_results = {
            'individual_metrics': individual_metrics,
            'correlation_matrix': corr_matrix.to_dict(),
            'portfolio_metrics': portfolio_metrics,
            'diversification_benefit': float(div_benefit),
            'avg_correlation': float(corr_matrix.values[np.triu_indices_from(corr_matrix.values, k=1)].mean()),
        }
        
        results['strategies'][strategy.name] = strategy_results
    
    # Save comprehensive results
    # Convert to JSON-serializable format
    json_results = {
        'symbols': results['symbols'],
        'num_symbols': results['num_symbols'],
        'transaction_cost': results['transaction_cost'],
        'strategies': {}
    }
    
    for strategy_name, strategy_data in results['strategies'].items():
        json_results['strategies'][strategy_name] = {
            'individual_metrics': strategy_data['individual_metrics'],
            'portfolio_metrics': strategy_data['portfolio_metrics'],
            'diversification_benefit': strategy_data['diversification_benefit'],
            'avg_correlation': strategy_data['avg_correlation'],
        }
    
    with open(output_dir / 'portfolio_analysis_summary.json', 'w') as f:
        json.dump(json_results, f, indent=2)
    
    # Create comparison table
    comparison = []
    for strategy_name, strategy_data in results['strategies'].items():
        comparison.append({
            'Strategy': strategy_name,
            'Portfolio Sharpe': f"{strategy_data['portfolio_metrics']['sharpe_ratio']:.4f}",
            'Portfolio Return': f"{strategy_data['portfolio_metrics']['total_return']:.4f}",
            'Avg Individual Sharpe': f"{np.mean([m['sharpe_ratio'] for m in strategy_data['individual_metrics'].values()]):.4f}",
            'Diversification': f"{strategy_data['diversification_benefit']:.2f}x",
            'Avg Correlation': f"{strategy_data['avg_correlation']:.2f}",
        })
    
    comparison_df = pd.DataFrame(comparison)
    comparison_df.to_csv(output_dir / 'portfolio_comparison.csv', index=False)
    
    # Print summary
    print("\n" + "="*70)
    print("PORTFOLIO COMPARISON")
    print("="*70 + "\n")
    print(comparison_df.to_string(index=False))
    
    print(f"\n{'='*70}")
    print(f"Results saved to {output_dir}/")
    print(f"  - *_correlation.csv (correlation matrices)")
    print(f"  - *_correlation_heatmap.png (visualizations)")
    print(f"  - portfolio_analysis_summary.json (full results)")
    print(f"  - portfolio_comparison.csv (strategy comparison)")
    print("="*70 + "\n")
    
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Multi-symbol portfolio analysis')
    parser.add_argument('--data-dir', type=Path, required=True,
                       help='Directory containing parquet files')
    parser.add_argument('--output-dir', type=Path, default=Path('reports/portfolio_analysis'),
                       help='Output directory')
    parser.add_argument('--symbols', nargs='+', 
                       default=['AAPL', 'MSFT', 'NVDA', 'BTCUSD', 'ETHUSD', 'EURUSD', 'GBPUSD'],
                       help='Symbols to analyze')
    parser.add_argument('--transaction-cost', type=float, default=0.001,
                       help='Transaction cost (default: 0.1%)')
    
    args = parser.parse_args()
    
    run_portfolio_analysis(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        symbols=args.symbols,
        transaction_cost=args.transaction_cost
    )
