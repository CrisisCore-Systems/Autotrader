"""Example: Backtesting microstructure signals with triple-barrier method."""

import asyncio
import time
from pathlib import Path

import numpy as np
import pandas as pd

from src.core.logging_config import get_logger
from src.microstructure.backtester import BacktestConfig, TickBacktester
from src.microstructure.detector import DetectionSignal

logger = get_logger(__name__)


def generate_synthetic_data(
    n_samples: int = 10000,
    base_price: float = 100.0,
    volatility: float = 0.001,
) -> pd.DataFrame:
    """Generate synthetic price data for testing."""
    timestamps = np.arange(n_samples) * 1.0  # 1 second intervals
    
    # Random walk with drift
    returns = np.random.normal(0.0001, volatility, n_samples)
    prices = base_price * np.exp(np.cumsum(returns))
    
    return pd.DataFrame({
        "timestamp": timestamps,
        "price": prices,
    })


def generate_synthetic_signals(
    price_data: pd.DataFrame,
    n_signals: int = 50,
) -> list[DetectionSignal]:
    """Generate synthetic detection signals."""
    signals = []
    
    # Sample random times for signals
    signal_times = np.random.choice(
        price_data["timestamp"].values[100:-100],  # Avoid edges
        size=n_signals,
        replace=False,
    )
    
    for i, timestamp in enumerate(sorted(signal_times)):
        # Create signal with random score
        score = np.random.uniform(0.3, 0.9)
        
        # Randomly assign buy/sell
        signal_type = (
            "buy_imbalance" if np.random.random() > 0.5 
            else "sell_imbalance"
        )
        
        signal = DetectionSignal(
            timestamp=float(timestamp),
            signal_type=signal_type,
            score=score,
            features={},
            cooldown_until=float(timestamp) + 60.0,
            metadata={"signal_id": f"test_signal_{i}"},
        )
        
        signals.append(signal)
    
    return signals


def run_basic_backtest():
    """Run basic backtest example."""
    logger.info("===== Basic Backtest Example =====")
    
    # Generate synthetic data
    logger.info("Generating synthetic price data...")
    price_data = generate_synthetic_data(n_samples=5000)
    
    logger.info(
        "synthetic_data_generated",
        n_samples=len(price_data),
        price_range=(
            price_data["price"].min(),
            price_data["price"].max(),
        ),
    )
    
    # Generate synthetic signals
    logger.info("Generating synthetic signals...")
    signals = generate_synthetic_signals(price_data, n_signals=30)
    
    logger.info(
        "signals_generated",
        n_signals=len(signals),
        buy_signals=sum(1 for s in signals if s.signal_type == "buy_imbalance"),
        sell_signals=sum(1 for s in signals if s.signal_type == "sell_imbalance"),
    )
    
    # Configure backtester
    config = BacktestConfig(
        initial_capital=10000.0,
        profit_target_pct=0.005,  # 0.5%
        stop_loss_pct=0.003,  # 0.3%
        max_holding_seconds=300.0,  # 5 minutes
        fee_rate=0.001,  # 0.1%
        slippage_bps=5.0,
        position_size_pct=0.1,  # 10% per trade
    )
    
    # Run backtest
    logger.info("Running backtest...")
    backtester = TickBacktester(config)
    result = backtester.run(signals, price_data)
    
    # Print results
    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(f"Initial Capital:    ${result.initial_capital:,.2f}")
    print(f"Final Capital:      ${result.final_capital:,.2f}")
    print(f"Total P&L:          ${result.total_pnl:,.2f}")
    print(f"Total Return:       {result.total_return_pct:.2f}%")
    print(f"\nNumber of Trades:   {result.num_trades}")
    print(f"Win Rate:           {result.win_rate * 100:.1f}%")
    print(f"Avg P&L per Trade:  ${result.avg_pnl:.2f}")
    print(f"Sharpe Ratio:       {result.sharpe_ratio:.2f}")
    print(f"Max Drawdown:       {result.max_drawdown:.2f}%")
    
    # Show sample trades
    if result.trades:
        print(f"\n{'=' * 60}")
        print("SAMPLE TRADES (first 5)")
        print("=" * 60)
        
        for i, trade in enumerate(result.trades[:5]):
            signal_id = trade.signal.metadata.get("signal_id", "unknown")
            print(f"\nTrade {i + 1}:")
            print(f"  Signal:      {signal_id}")
            print(f"  Type:        {trade.signal.signal_type}")
            print(f"  Score:       {trade.signal.score:.3f}")
            print(f"  Entry:       ${trade.entry_price:.2f} @ {trade.entry_time:.1f}s")
            print(f"  Exit:        ${trade.exit_price:.2f} @ {trade.exit_time:.1f}s")
            print(f"  Exit Reason: {trade.exit_reason}")
            print(f"  P&L:         ${trade.pnl:.2f} ({trade.pnl_pct:.2f}%)")
            print(f"  Fees:        ${trade.fees:.2f}")
            print(f"  Holding:     {(trade.exit_time - trade.entry_time):.1f}s")
    
    return result


def run_precision_analysis():
    """Run precision@k analysis."""
    logger.info("===== Precision@K Analysis =====")
    
    # Generate data
    price_data = generate_synthetic_data(n_samples=3000)
    signals = generate_synthetic_signals(price_data, n_signals=50)
    
    # Configure backtester
    config = BacktestConfig()
    backtester = TickBacktester(config)
    
    # Compute precision@k
    logger.info("Computing precision@k...")
    precision_dict = backtester.compute_precision_at_k(
        signals,
        price_data,
        k_values=[1, 5, 10, 20],
    )
    
    print("\n" + "=" * 60)
    print("PRECISION@K RESULTS")
    print("=" * 60)
    print("\nPrecision of top-k signals:")
    for k, precision in precision_dict.items():
        print(f"  Top {k:2d}: {precision * 100:.1f}%")
    
    return precision_dict


def run_lead_time_analysis():
    """Run lead-time analysis."""
    logger.info("===== Lead-Time Analysis =====")
    
    # Generate data
    price_data = generate_synthetic_data(n_samples=3000)
    signals = generate_synthetic_signals(price_data, n_signals=50)
    
    # Configure backtester
    config = BacktestConfig()
    backtester = TickBacktester(config)
    
    # Compute lead time
    logger.info("Computing lead time...")
    avg_lead_time = backtester.compute_lead_time(
        signals,
        price_data,
        move_threshold=0.003,  # 0.3%
    )
    
    print("\n" + "=" * 60)
    print("LEAD-TIME ANALYSIS")
    print("=" * 60)
    print(f"\nAverage Lead Time: {avg_lead_time:.1f} seconds")
    print(f"                   ({avg_lead_time / 60:.1f} minutes)")
    
    return avg_lead_time


def run_cross_validation():
    """Run purged time-series cross-validation."""
    logger.info("===== Cross-Validation Example =====")
    
    # Generate data
    price_data = generate_synthetic_data(n_samples=1000)
    
    # Run purged CV
    logger.info("Running purged time-series CV...")
    splits = TickBacktester.purged_time_series_cv(
        price_data,
        n_splits=5,
        embargo_pct=0.02,  # 2% embargo
        purge_pct=0.01,  # 1% purge
    )
    
    print("\n" + "=" * 60)
    print("CROSS-VALIDATION SPLITS")
    print("=" * 60)
    print(f"\nTotal samples: {len(price_data)}")
    print(f"Number of splits: {len(splits)}")
    
    for i, (train, test) in enumerate(splits):
        print(f"\nSplit {i + 1}:")
        print(f"  Train: {len(train):4d} samples")
        print(f"  Test:  {len(test):4d} samples")
        print(f"  Train time range: {train['timestamp'].min():.1f} - {train['timestamp'].max():.1f}")
        print(f"  Test time range:  {test['timestamp'].min():.1f} - {test['timestamp'].max():.1f}")
    
    return splits


def main():
    """Run all backtest examples."""
    print("\n" + "=" * 70)
    print(" MICROSTRUCTURE BACKTESTING EXAMPLES")
    print("=" * 70)
    
    try:
        # Run basic backtest
        result = run_basic_backtest()
        
        # Run precision analysis
        precision = run_precision_analysis()
        
        # Run lead-time analysis
        lead_time = run_lead_time_analysis()
        
        # Run cross-validation
        splits = run_cross_validation()
        
        print("\n" + "=" * 70)
        print(" ALL EXAMPLES COMPLETED SUCCESSFULLY")
        print("=" * 70)
        
        logger.info(
            "backtest_examples_completed",
            total_trades=result.num_trades,
            final_return_pct=result.total_return_pct,
            avg_lead_time_seconds=lead_time,
        )
        
    except Exception as e:
        logger.error("backtest_examples_failed", error=str(e), exc_info=True)
        raise


if __name__ == "__main__":
    main()
