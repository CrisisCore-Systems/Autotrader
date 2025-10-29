"""Event-driven tick backtester for microstructure signals."""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.core.logging_config import get_logger
from src.microstructure.detector import DetectionSignal

logger = get_logger(__name__)


class ExitReason(Enum):
    """Reasons for exiting a position."""

    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    TIMEOUT = "timeout"
    SIGNAL_REVERSE = "signal_reverse"


@dataclass
class BacktestConfig:
    """Configuration for tick backtester."""

    initial_capital: float = 10000.0
    fee_rate: float = 0.001  # 0.1% per trade
    slippage_bps: float = 5.0  # 5 basis points slippage
    
    # Triple-barrier labeling
    profit_target_pct: float = 0.005  # 0.5% profit target
    stop_loss_pct: float = 0.003  # 0.3% stop loss
    max_holding_seconds: float = 300.0  # 5 minutes max hold
    
    # Position sizing
    position_size_pct: float = 0.1  # 10% of capital per trade


@dataclass
class Trade:
    """Individual backtest trade."""

    entry_time: float
    entry_price: float
    exit_time: float
    exit_price: float
    position_size: float
    pnl: float
    pnl_pct: float
    fees: float
    signal: DetectionSignal
    exit_reason: str  # 'profit_target', 'stop_loss', 'timeout'


@dataclass
class BacktestResult:
    """Backtest results and metrics."""

    trades: List[Trade]
    initial_capital: float
    final_capital: float
    total_pnl: float
    total_return_pct: float
    
    # Performance metrics
    num_trades: int
    win_rate: float
    avg_pnl: float
    sharpe_ratio: float
    max_drawdown: float
    
    # Detection metrics
    precision_at_k: Dict[int, float] = field(default_factory=dict)
    avg_lead_time_seconds: float = 0.0
    
    # Time series metrics
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series())
    returns: pd.Series = field(default_factory=lambda: pd.Series())


class TickBacktester:
    """
    Event-driven tick-by-tick backtester.
    
    Features:
    - Triple-barrier method for labeling
    - Transaction costs (fees + slippage)
    - Purged time-series cross-validation
    - Precision@k and lead-time metrics
    """

    def __init__(self, config: BacktestConfig):
        """Initialize backtester with configuration."""
        self.config = config
        logger.info("backtester_initialized", config=config)
    
    def _apply_slippage(self, price: float, direction: str, entry: bool = True) -> float:
        """Apply slippage to price based on direction.
        
        Args:
            price: Base price
            direction: 'long' or 'short'
            entry: True for entry, False for exit
            
        Returns:
            Price with slippage applied
        """
        slippage_pct = self.config.slippage_bps / 10000.0
        
        if direction == "long":
            return price * (1 + slippage_pct) if entry else price * (1 - slippage_pct)
        else:
            return price * (1 - slippage_pct) if entry else price * (1 + slippage_pct)
    
    def _calculate_pnl(self, position: Dict, exit_price: float) -> Tuple[float, float]:
        """Calculate gross and net PnL for a position.
        
        Args:
            position: Position dictionary
            exit_price: Exit price
            
        Returns:
            Tuple of (gross_pnl, net_pnl)
        """
        if position["direction"] == "long":
            gross_pnl = (
                position["position_value"]
                * (exit_price - position["entry_price"])
                / position["entry_price"]
            )
        else:
            gross_pnl = (
                position["position_value"]
                * (position["entry_price"] - exit_price)
                / position["entry_price"]
            )
        
        exit_fees = position["position_value"] * self.config.fee_rate
        net_pnl = gross_pnl - exit_fees
        
        return gross_pnl, net_pnl
    
    def _check_position_barriers(
        self, 
        position: Dict, 
        price: float, 
        timestamp: float
    ) -> Optional[Tuple[float, ExitReason]]:
        """Check if position hit any barrier (profit target, stop loss, or timeout).
        
        Args:
            position: Position dictionary
            price: Current price
            timestamp: Current timestamp
            
        Returns:
            Tuple of (exit_price, exit_reason) if barrier hit, None otherwise
        """
        direction = position["direction"]
        
        # Check profit target
        if direction == "long" and price >= position["profit_target"]:
            return price, ExitReason.PROFIT_TARGET
        elif direction == "short" and price <= position["profit_target"]:
            return price, ExitReason.PROFIT_TARGET
        
        # Check stop loss
        if direction == "long" and price <= position["stop_loss"]:
            return price, ExitReason.STOP_LOSS
        elif direction == "short" and price >= position["stop_loss"]:
            return price, ExitReason.STOP_LOSS
        
        # Check timeout
        if timestamp >= position["timeout"]:
            return price, ExitReason.TIMEOUT
        
        return None
    
    def _create_trade(
        self,
        position: Dict,
        exit_price: float,
        exit_time: float,
        exit_reason: ExitReason,
        net_pnl: float,
    ) -> Trade:
        """Create a trade record from position.
        
        Args:
            position: Position dictionary
            exit_price: Exit price
            exit_time: Exit timestamp
            exit_reason: Reason for exit
            net_pnl: Net profit/loss
            
        Returns:
            Trade record
        """
        exit_fees = position["position_value"] * self.config.fee_rate
        return_pct = net_pnl / position["position_value"]
        
        return Trade(
            entry_time=position["entry_time"],
            entry_price=position["entry_price"],
            exit_time=exit_time,
            exit_price=exit_price,
            position_size=position["position_value"],
            pnl=net_pnl,
            pnl_pct=return_pct * 100,
            fees=position["entry_fees"] + exit_fees,
            signal=position["signal"],
            exit_reason=exit_reason.value,
        )

    def run(
        self,
        signals: List[DetectionSignal],
        price_data: pd.DataFrame,
    ) -> BacktestResult:
        """
        Run backtest on signals using triple-barrier method.
        
        Args:
            signals: List of detection signals
            price_data: DataFrame with columns ['timestamp', 'price']
            
        Returns:
            BacktestResult with performance metrics
        """
        logger.info(
            "backtest_started",
            num_signals=len(signals),
            data_points=len(price_data),
        )
        
        # Ensure price data is sorted by timestamp
        price_data = price_data.sort_values("timestamp").reset_index(drop=True)
        
        # Create timestamp index for fast lookups
        price_index = pd.Series(
            price_data["price"].values,
            index=price_data["timestamp"].values,
        )
        
        trades: List[Trade] = []
        capital = self.config.initial_capital
        equity_curve = [capital]
        equity_times = [price_data["timestamp"].iloc[0]]
        
        # Track active positions
        active_positions: List[Dict] = []
        
        # Process each signal
        for signal in signals:
            # Skip if we're at max positions
            if len(active_positions) >= 3:  # Max 3 concurrent
                continue
            
            # Skip low-scoring signals
            if signal.score < 0.3:
                continue
            
            # Get entry price with slippage
            try:
                base_price = float(
                    price_index.asof(signal.timestamp)
                )
            except (KeyError, ValueError):
                logger.warning(
                    "signal_skipped_no_price",
                    signal_id=signal.metadata.get("signal_id", "unknown"),
                    timestamp=signal.timestamp,
                )
                continue
            
            # Apply slippage based on direction
            if signal.signal_type == "buy_imbalance":
                direction = "long"
            else:
                direction = "short"
            
            entry_price = self._apply_slippage(base_price, direction, entry=True)
            
            # Calculate position size
            position_value = capital * self.config.position_size_pct
            entry_fees = position_value * self.config.fee_rate
            
            # Create position tracking
            position = {
                "signal": signal,
                "direction": direction,
                "entry_time": signal.timestamp,
                "entry_price": entry_price,
                "position_value": position_value,
                "entry_fees": entry_fees,
                "profit_target": (
                    entry_price * (1 + self.config.profit_target_pct)
                    if direction == "long"
                    else entry_price * (1 - self.config.profit_target_pct)
                ),
                "stop_loss": (
                    entry_price * (1 - self.config.stop_loss_pct)
                    if direction == "long"
                    else entry_price * (1 + self.config.stop_loss_pct)
                ),
                "timeout": signal.timestamp + self.config.max_holding_seconds,
            }
            
            active_positions.append(position)
            capital -= entry_fees
        
        # Simulate tick-by-tick to check barriers
        for idx, row in price_data.iterrows():
            timestamp = row["timestamp"]
            price = row["price"]
            
            # Check each active position for barrier hits
            positions_to_close = []
            
            for pos in active_positions:
                barrier_result = self._check_position_barriers(pos, price, timestamp)
                if barrier_result is not None:
                    exit_price, exit_reason = barrier_result
                    positions_to_close.append((pos, exit_price, exit_reason))
            
            # Close positions that hit barriers
            for pos, exit_price, exit_reason in positions_to_close:
                # Apply slippage on exit
                exit_price = self._apply_slippage(exit_price, pos["direction"], entry=False)
                
                # Calculate PnL
                gross_pnl, net_pnl = self._calculate_pnl(pos, exit_price)
                
                # Update capital
                capital += net_pnl
                
                # Create trade record
                holding_seconds = timestamp - pos["entry_time"]
                trade = self._create_trade(pos, exit_price, timestamp, exit_reason, net_pnl)
                
                trades.append(trade)
                active_positions.remove(pos)
                
                logger.debug(
                    "position_closed",
                    signal_id=pos["signal"].metadata.get("signal_id", "unknown"),
                    exit_reason=exit_reason.value,
                    pnl=net_pnl,
                    holding_seconds=holding_seconds,
                )
            
            # Record equity
            equity_curve.append(capital)
            equity_times.append(timestamp)
        
        # Force close any remaining positions at final price
        final_price = float(price_data["price"].iloc[-1])
        final_time = float(price_data["timestamp"].iloc[-1])
        
        for pos in active_positions:
            exit_price = self._apply_slippage(final_price, pos["direction"], entry=False)
            gross_pnl, net_pnl = self._calculate_pnl(pos, exit_price)
            capital += net_pnl
            
            trade = self._create_trade(pos, exit_price, final_time, ExitReason.TIMEOUT, net_pnl)
            trades.append(trade)
        
        # Calculate metrics
        total_pnl = capital - self.config.initial_capital
        total_return_pct = (total_pnl / self.config.initial_capital) * 100
        
        num_trades = len(trades)
        winning_trades = [t for t in trades if t.pnl > 0]
        win_rate = len(winning_trades) / num_trades if num_trades > 0 else 0.0
        avg_pnl = total_pnl / num_trades if num_trades > 0 else 0.0
        
        # Calculate Sharpe ratio
        if len(trades) > 1:
            returns = np.array([t.pnl_pct for t in trades])
            sharpe_ratio = (
                np.mean(returns) / np.std(returns) * np.sqrt(252)
                if np.std(returns) > 0
                else 0.0
            )
        else:
            sharpe_ratio = 0.0
        
        # Calculate max drawdown
        equity_array = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity_array)
        drawdown = (equity_array - running_max) / running_max
        max_drawdown = float(np.min(drawdown)) * 100  # As percentage
        
        # Create equity curve series
        equity_series = pd.Series(equity_curve, index=equity_times)
        returns_series = equity_series.pct_change().dropna()
        
        logger.info(
            "backtest_completed",
            num_trades=num_trades,
            win_rate=win_rate,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
        )
        
        return BacktestResult(
            trades=trades,
            initial_capital=self.config.initial_capital,
            final_capital=capital,
            total_pnl=total_pnl,
            total_return_pct=total_return_pct,
            num_trades=num_trades,
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            equity_curve=equity_series,
            returns=returns_series,
        )

    def compute_precision_at_k(
        self,
        signals: List[DetectionSignal],
        price_data: pd.DataFrame,
        k_values: List[int] = [1, 5, 10],
    ) -> Dict[int, float]:
        """
        Compute precision@k: % of top-k signals that are profitable.
        
        Args:
            signals: List of detection signals sorted by score
            price_data: Price data for evaluation
            k_values: Values of k to compute
            
        Returns:
            Dict mapping k -> precision
        """
        if not signals:
            return {k: 0.0 for k in k_values}
        
        # Sort signals by score (descending)
        sorted_signals = sorted(
            signals,
            key=lambda s: s.score,
            reverse=True,
        )
        
        # Create price index
        price_index = pd.Series(
            price_data["price"].values,
            index=price_data["timestamp"].values,
        )
        
        # Label each signal as profitable or not
        signal_labels = []
        
        for signal in sorted_signals:
            try:
                entry_price = float(price_index.asof(signal.timestamp))
                
                # Look ahead to find exit price
                future_prices = price_index[
                    price_index.index > signal.timestamp
                ]
                
                if len(future_prices) == 0:
                    continue
                
                # Check next 5 minutes
                timeout = signal.timestamp + self.config.max_holding_seconds
                exit_window = future_prices[
                    future_prices.index <= timeout
                ]
                
                if len(exit_window) == 0:
                    continue
                
                # Determine if profitable based on direction
                if signal.signal_type == "buy_imbalance":
                    # Long position
                    max_price = float(exit_window.max())
                    profit_pct = (max_price - entry_price) / entry_price
                    is_profitable = profit_pct >= self.config.profit_target_pct
                else:
                    # Short position
                    min_price = float(exit_window.min())
                    profit_pct = (entry_price - min_price) / entry_price
                    is_profitable = profit_pct >= self.config.profit_target_pct
                
                signal_labels.append(1 if is_profitable else 0)
                
            except (KeyError, ValueError, IndexError):
                continue
        
        # Calculate precision@k for each k
        precision_dict = {}
        
        for k in k_values:
            if k > len(signal_labels):
                k_actual = len(signal_labels)
            else:
                k_actual = k
            
            if k_actual == 0:
                precision_dict[k] = 0.0
            else:
                top_k_labels = signal_labels[:k_actual]
                precision = sum(top_k_labels) / len(top_k_labels)
                precision_dict[k] = precision
        
        return precision_dict

    def compute_lead_time(
        self,
        signals: List[DetectionSignal],
        price_data: pd.DataFrame,
        move_threshold: float = 0.003,  # 0.3% move
    ) -> float:
        """
        Compute average lead time: time between signal and significant price move.
        
        Args:
            signals: List of detection signals
            price_data: Price data for evaluation
            move_threshold: Threshold for "significant" move (default 0.3%)
        
        Returns:
            Average lead time in seconds
        """
        if not signals:
            return 0.0
        
        # Create price index
        price_index = pd.Series(
            price_data["price"].values,
            index=price_data["timestamp"].values,
        )
        
        lead_times = []
        
        for signal in signals:
            try:
                entry_price = float(price_index.asof(signal.timestamp))
                
                # Look ahead for significant move
                future_prices = price_index[
                    price_index.index > signal.timestamp
                ]
                
                if len(future_prices) == 0:
                    continue
                
                # Find first time price moves beyond threshold
                if signal.signal_type == "buy_imbalance":
                    # Look for upward move
                    target_price = entry_price * (1 + move_threshold)
                    significant_moves = future_prices[
                        future_prices >= target_price
                    ]
                else:
                    # Look for downward move
                    target_price = entry_price * (1 - move_threshold)
                    significant_moves = future_prices[
                        future_prices <= target_price
                    ]
                
                if len(significant_moves) > 0:
                    move_time = significant_moves.index[0]
                    lead_time = move_time - signal.timestamp
                    lead_times.append(lead_time)
                    
            except (KeyError, ValueError, IndexError):
                continue
        
        if not lead_times:
            return 0.0
        
        avg_lead_time = float(np.mean(lead_times))
        
        logger.info(
            "lead_time_computed",
            avg_lead_time_seconds=avg_lead_time,
            num_signals=len(lead_times),
        )
        
        return avg_lead_time

    @staticmethod
    def purged_time_series_cv(
        data: pd.DataFrame,
        n_splits: int = 5,
        embargo_pct: float = 0.01,
        purge_pct: float = 0.01,
    ) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """
        Purged time-series cross-validation with embargo.
        
        Prevents look-ahead bias by:
        1. Purging samples from train set that overlap with test
        2. Adding embargo period between train and test
        
        Args:
            data: Time series data with 'timestamp' column
            n_splits: Number of CV folds
            embargo_pct: Embargo period as % of data (buffer after test)
            purge_pct: Purge period as % of data (remove from train)
            
        Returns:
            List of (train, test) DataFrame splits
        """
        if "timestamp" not in data.columns:
            raise ValueError("Data must have 'timestamp' column")
        
        # Sort by timestamp
        data = data.sort_values("timestamp").reset_index(drop=True)
        
        n_samples = len(data)
        test_size = n_samples // n_splits
        embargo_size = int(n_samples * embargo_pct)
        purge_size = int(n_samples * purge_pct)
        
        splits = []
        
        for i in range(n_splits):
            # Define test set indices
            test_start = i * test_size
            test_end = min((i + 1) * test_size, n_samples)
            
            # Define embargo period (after test)
            embargo_end = min(test_end + embargo_size, n_samples)
            
            # Define purge period (before test)
            purge_start = max(test_start - purge_size, 0)
            
            # Create train set (excluding purge and embargo)
            train_indices = []
            
            # Add all data before purge period
            if purge_start > 0:
                train_indices.extend(range(0, purge_start))
            
            # Add all data after embargo period
            if embargo_end < n_samples:
                train_indices.extend(range(embargo_end, n_samples))
            
            # Create test set
            test_indices = list(range(test_start, test_end))
            
            if len(train_indices) > 0 and len(test_indices) > 0:
                train_df = data.iloc[train_indices].reset_index(drop=True)
                test_df = data.iloc[test_indices].reset_index(drop=True)
                splits.append((train_df, test_df))
                
                logger.debug(
                    "cv_split_created",
                    split=i + 1,
                    train_samples=len(train_df),
                    test_samples=len(test_df),
                    purge_size=purge_size,
                    embargo_size=embargo_size,
                )
        
        logger.info(
            "purged_cv_completed",
            n_splits=len(splits),
            total_samples=n_samples,
        )
        
        return splits
