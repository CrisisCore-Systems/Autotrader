"""
Baseline trading strategies for comparative validation.
Implements buy-and-hold, momentum, and mean-reversion benchmarks.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd
import numpy as np


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""
    
    def __init__(self, name: str):
        self.name = name
        
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals (-1, 0, 1) for each timestamp.
        
        Args:
            data: DataFrame with OHLCV + features
            
        Returns:
            Series with trading signals: -1 (short), 0 (neutral), 1 (long)
        """
        pass
    
    def calculate_returns(
        self,
        data: pd.DataFrame,
        signals: pd.Series,
        transaction_cost: float = 0.001
    ) -> Dict[str, Any]:
        """
        Calculate strategy returns and performance metrics.
        
        Args:
            data: DataFrame with OHLCV data
            signals: Trading signals from generate_signals()
            transaction_cost: Cost per trade (default 0.1%)
            
        Returns:
            Dict with performance metrics
        """
        # Calculate position changes and apply transaction costs
        positions = signals.shift(1).fillna(0)  # Positions lag signals by 1 bar
        position_changes = positions.diff().abs()
        
        # Calculate raw returns
        price_returns = data['close'].pct_change()
        strategy_returns = positions * price_returns
        
        # Apply transaction costs
        costs = position_changes * transaction_cost
        net_returns = strategy_returns - costs
        
        # Calculate cumulative returns
        cumulative_returns = (1 + net_returns).cumprod()
        
        # Performance metrics
        total_return = cumulative_returns.iloc[-1] - 1
        annualized_return = (1 + total_return) ** (252 / len(data)) - 1
        
        volatility = net_returns.std() * np.sqrt(252 * 390)  # Annualized (1-min bars)
        sharpe_ratio = annualized_return / volatility if volatility > 0 else 0.0
        
        # Downside deviation (only negative returns)
        downside_returns = net_returns[net_returns < 0]
        downside_dev = downside_returns.std() * np.sqrt(252 * 390)
        sortino_ratio = annualized_return / downside_dev if downside_dev > 0 else 0.0
        
        # Max drawdown
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min()
        
        # Trade statistics
        trades = position_changes[position_changes > 0].count()
        win_rate = (net_returns[net_returns > 0].count() / len(net_returns)) if len(net_returns) > 0 else 0.0
        
        return {
            'strategy': self.name,
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


class BuyAndHold(BaseStrategy):
    """Buy-and-hold baseline strategy."""
    
    def __init__(self):
        super().__init__("Buy & Hold")
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Always long (signal = 1)."""
        return pd.Series(1, index=data.index)


class Momentum(BaseStrategy):
    """Momentum strategy based on recent returns."""
    
    def __init__(self, lookback: int = 390):  # 1 day of 1-min bars
        super().__init__(f"Momentum ({lookback})")
        self.lookback = lookback
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Long if recent return > 0, short if < 0.
        Uses rolling lookback window.
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")
            
        # Calculate rolling returns
        rolling_return = data['close'].pct_change(self.lookback)
        
        # Generate signals
        signals = pd.Series(0, index=data.index)
        signals[rolling_return > 0] = 1
        signals[rolling_return < 0] = -1
        
        return signals


class MeanReversion(BaseStrategy):
    """Mean-reversion strategy using Bollinger Bands."""
    
    def __init__(self, lookback: int = 390, num_std: float = 2.0):  # 1 day window
        super().__init__(f"Mean Reversion (BB {num_std}σ)")
        self.lookback = lookback
        self.num_std = num_std
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Long when price < lower band (oversold).
        Short when price > upper band (overbought).
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")
            
        # Calculate Bollinger Bands
        rolling_mean = data['close'].rolling(window=self.lookback).mean()
        rolling_std = data['close'].rolling(window=self.lookback).std()
        
        upper_band = rolling_mean + (self.num_std * rolling_std)
        lower_band = rolling_mean - (self.num_std * rolling_std)
        
        # Generate signals (mean-reversion logic)
        signals = pd.Series(0, index=data.index)
        signals[data['close'] < lower_band] = 1   # Oversold -> Long
        signals[data['close'] > upper_band] = -1  # Overbought -> Short
        
        return signals


class CrossoverMA(BaseStrategy):
    """Moving average crossover strategy."""
    
    def __init__(self, fast: int = 195, slow: int = 780):  # 30min/2hr windows
        super().__init__(f"MA Crossover ({fast}/{slow})")
        self.fast = fast
        self.slow = slow
        
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Long when fast MA > slow MA.
        Short when fast MA < slow MA.
        """
        if 'close' not in data.columns:
            raise ValueError("Data must contain 'close' column")
            
        fast_ma = data['close'].rolling(window=self.fast).mean()
        slow_ma = data['close'].rolling(window=self.slow).mean()
        
        signals = pd.Series(0, index=data.index)
        signals[fast_ma > slow_ma] = 1
        signals[fast_ma < slow_ma] = -1
        
        return signals


def run_baseline_comparison(
    data: pd.DataFrame,
    strategies: list[BaseStrategy] | None = None,
    transaction_cost: float = 0.001
) -> pd.DataFrame:
    """
    Run multiple baseline strategies and return comparison DataFrame.
    
    Args:
        data: Market data with OHLCV
        strategies: List of strategy instances (uses defaults if None)
        transaction_cost: Transaction cost per trade
        
    Returns:
        DataFrame with performance metrics for each strategy
    """
    if strategies is None:
        strategies = [
            BuyAndHold(),
            Momentum(lookback=390),      # 1 day
            Momentum(lookback=1950),     # 5 days
            MeanReversion(lookback=390, num_std=2.0),
            CrossoverMA(fast=195, slow=780),
        ]
    
    results = []
    for strategy in strategies:
        print(f"Running {strategy.name}...")
        signals = strategy.generate_signals(data)
        metrics = strategy.calculate_returns(data, signals, transaction_cost)
        results.append(metrics)
    
    return pd.DataFrame(results)


if __name__ == '__main__':
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser(description='Run baseline strategy comparison')
    parser.add_argument('--data', type=Path, required=True,
                       help='Path to market data parquet file')
    parser.add_argument('--output', type=Path, default='reports/baseline_strategies.csv',
                       help='Output path for results')
    parser.add_argument('--transaction-cost', type=float, default=0.001,
                       help='Transaction cost (default 0.1%)')
    
    args = parser.parse_args()
    
    # Load data
    print(f"📊 Loading data from {args.data}...")
    data = pd.read_parquet(args.data)
    
    # Run comparison
    print(f"\n🔬 Running baseline strategies...")
    results = run_baseline_comparison(data, transaction_cost=args.transaction_cost)
    
    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)
    
    # Print summary
    print(f"\n✅ Results saved to {args.output}\n")
    print(results.to_string(index=False))
    print(f"\nBest Sharpe Ratio: {results.loc[results['sharpe_ratio'].idxmax(), 'strategy']}")
    print(f"Best Return: {results.loc[results['total_return'].idxmax(), 'strategy']}")
