"""
Cost-aware labeling foundation for HFT strategies.

This module provides base classes and cost models for generating labels
that account for transaction costs (fees, spread, slippage).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class CostModel:
    """
    Transaction cost model for realistic label generation.
    
    Attributes:
        maker_fee: Maker fee in basis points (e.g., 0.02 for 0.02%)
        taker_fee: Taker fee in basis points (e.g., 0.04 for 0.04%)
        spread_cost: Fraction of spread as cost (0.5 = half-spread crossing)
        slippage_bps: Slippage in basis points (market impact + adverse selection)
        min_profit_bps: Minimum profit threshold in basis points
    """
    maker_fee: float = 0.02  # 0.02% (2 bps) - typical maker fee
    taker_fee: float = 0.04  # 0.04% (4 bps) - typical taker fee
    spread_cost: float = 0.5  # 50% of spread (half-spread)
    slippage_bps: float = 0.5  # 0.5 bps slippage
    min_profit_bps: float = 1.0  # 1 bp minimum profit after costs
    
    def total_cost_bps(self, is_maker: bool = True) -> float:
        """
        Calculate total transaction cost in basis points.
        
        Args:
            is_maker: True for maker order (limit), False for taker (market)
            
        Returns:
            Total cost in basis points (one-way)
        """
        fee = self.maker_fee if is_maker else self.taker_fee
        # Total cost = fee + slippage + half-spread crossing
        return fee + self.slippage_bps + (self.spread_cost * 2.0)  # 2 bps = typical FX spread
    
    def round_trip_cost_bps(self, is_maker: bool = True) -> float:
        """
        Calculate round-trip transaction cost (entry + exit).
        
        Args:
            is_maker: True for maker orders
            
        Returns:
            Round-trip cost in basis points
        """
        return 2 * self.total_cost_bps(is_maker)
    
    def profitable_threshold_bps(self, is_maker: bool = True) -> float:
        """
        Calculate minimum return required for profitable trade.
        
        Args:
            is_maker: True for maker orders
            
        Returns:
            Minimum profitable return in basis points
        """
        return self.round_trip_cost_bps(is_maker) + self.min_profit_bps


class BaseLabeler(ABC):
    """
    Abstract base class for all labeling methods.
    
    All labelers must implement cost-aware label generation.
    """
    
    def __init__(
        self,
        cost_model: Optional[CostModel] = None,
        horizon_seconds: int = 60,
        name: str = "base"
    ):
        """
        Initialize labeler.
        
        Args:
            cost_model: Transaction cost model (defaults to standard costs)
            horizon_seconds: Forward-looking horizon in seconds
            name: Labeler name for identification
        """
        self.cost_model = cost_model or CostModel()
        self.horizon_seconds = horizon_seconds
        self.name = name
    
    @abstractmethod
    def generate_labels(
        self,
        bars: pd.DataFrame,
        price_col: str = "close",
        timestamp_col: str = "timestamp",
        **kwargs
    ) -> pd.Series:
        """
        Generate labels for bar data.
        
        Args:
            bars: DataFrame with OHLCV data
            price_col: Name of price column to use
            timestamp_col: Name of timestamp column
            **kwargs: Additional labeler-specific parameters
            
        Returns:
            Series with labels (index matches bars)
        """
        raise NotImplementedError("Subclasses must implement generate_labels()")
    
    def _calculate_forward_return_bps(
        self,
        bars: pd.DataFrame,
        price_col: str = "close",
        timestamp_col: str = "timestamp"
    ) -> pd.Series:
        """
        Calculate forward returns over the specified horizon.
        
        Args:
            bars: DataFrame with bar data
            price_col: Price column name
            timestamp_col: Timestamp column name
            
        Returns:
            Series with forward returns in basis points
        """
        if timestamp_col not in bars.columns:
            raise ValueError(f"timestamp_col '{timestamp_col}' not found in bars")
        if price_col not in bars.columns:
            raise ValueError(f"price_col '{price_col}' not found in bars")
        
        # Ensure timestamp is datetime
        bars = bars.copy()
        if not pd.api.types.is_datetime64_any_dtype(bars[timestamp_col]):
            bars[timestamp_col] = pd.to_datetime(bars[timestamp_col])
        
        # Calculate horizon timestamp
        bars["_horizon_time"] = bars[timestamp_col] + pd.Timedelta(seconds=self.horizon_seconds)
        
        # Sort by timestamp
        bars_sorted = bars.sort_values(timestamp_col).reset_index(drop=True)
        
        # Use merge_asof to find the first bar at or after horizon time (vectorized)
        # Left side: current bars with horizon_time
        # Right side: future bars (prices to lookup)
        future_bars = bars_sorted[[timestamp_col, price_col]].copy()
        future_bars = future_bars.rename(columns={
            timestamp_col: "_future_time",
            price_col: "_horizon_price"
        })
        
        # Merge asof: for each horizon_time, find the first future bar >= horizon_time
        merged = pd.merge_asof(
            bars_sorted.sort_values("_horizon_time"),
            future_bars.sort_values("_future_time"),
            left_on="_horizon_time",
            right_on="_future_time",
            direction="forward"  # Find first bar >= horizon_time
        )
        
        # Restore original order
        merged = merged.sort_index()
        
        # Calculate returns in basis points
        current_price = merged[price_col]
        horizon_price = merged["_horizon_price"]
        
        returns_bps = ((horizon_price - current_price) / current_price) * 10_000
        
        return returns_bps
    
    def _calculate_microprice(
        self,
        bars: pd.DataFrame,
        bid_col: str = "bid",
        ask_col: str = "ask",
        bid_vol_col: str = "bid_vol",
        ask_vol_col: str = "ask_vol"
    ) -> pd.Series:
        """
        Calculate microprice (volume-weighted mid price).
        
        Microprice = bid * (ask_vol / (bid_vol + ask_vol)) + ask * (bid_vol / (bid_vol + ask_vol))
        
        This is a better estimate of "fair price" than simple mid-quote.
        
        Args:
            bars: DataFrame with order book data
            bid_col: Bid price column
            ask_col: Ask price column
            bid_vol_col: Bid volume column
            ask_vol_col: Ask volume column
            
        Returns:
            Series with microprice values
        """
        required_cols = [bid_col, ask_col, bid_vol_col, ask_vol_col]
        missing = [col for col in required_cols if col not in bars.columns]
        
        if missing:
            # Fall back to mid-quote if volume data not available
            if bid_col in bars.columns and ask_col in bars.columns:
                return (bars[bid_col] + bars[ask_col]) / 2.0
            else:
                raise ValueError(f"Missing required columns for microprice: {missing}")
        
        bid = bars[bid_col]
        ask = bars[ask_col]
        bid_vol = bars[bid_vol_col]
        ask_vol = bars[ask_vol_col]
        
        total_vol = bid_vol + ask_vol
        
        # Avoid division by zero
        total_vol = total_vol.replace(0, np.nan)
        
        # Microprice weighted by opposite-side volume
        microprice = (bid * ask_vol + ask * bid_vol) / total_vol
        
        # Fill NaN with mid-quote
        mid_quote = (bid + ask) / 2.0
        microprice = microprice.fillna(mid_quote)
        
        return microprice


def estimate_capacity(
    bars: pd.DataFrame,
    volume_col: str = "volume",
    horizon_seconds: int = 60,
    max_participation_rate: float = 0.02  # 2% of volume
) -> float:
    """
    Estimate trading capacity for a given horizon.
    
    Capacity = average volume over horizon * max participation rate
    
    Args:
        bars: DataFrame with volume data
        volume_col: Volume column name
        horizon_seconds: Trading horizon in seconds
        max_participation_rate: Maximum fraction of volume to trade (e.g., 0.02 = 2%)
        
    Returns:
        Estimated capacity in base currency units
    """
    if volume_col not in bars.columns:
        raise ValueError(f"volume_col '{volume_col}' not found in bars")
    
    # Calculate average volume per second
    if "timestamp" in bars.columns:
        # Calculate time span
        bars_sorted = bars.sort_values("timestamp")
        time_span_seconds = (bars_sorted["timestamp"].max() - bars_sorted["timestamp"].min()).total_seconds()
        
        if time_span_seconds > 0:
            total_volume = bars[volume_col].sum()
            volume_per_second = total_volume / time_span_seconds
        else:
            volume_per_second = bars[volume_col].mean()
    else:
        # Fallback: use mean volume per bar
        volume_per_second = bars[volume_col].mean()
    
    # Capacity = volume over horizon * participation rate
    horizon_volume = volume_per_second * horizon_seconds
    capacity = horizon_volume * max_participation_rate
    
    return capacity


def calculate_sharpe_ratio(returns: pd.Series, periods_per_year: int = 252 * 78) -> float:
    """
    Calculate annualized Sharpe ratio.
    
    Args:
        returns: Series of returns (in decimal, e.g., 0.001 for 0.1%)
        periods_per_year: Number of periods per year (e.g., 252*78 for 5-min bars in trading year)
        
    Returns:
        Annualized Sharpe ratio
    """
    if len(returns) == 0 or returns.std() == 0:
        return 0.0
    
    mean_return = returns.mean()
    std_return = returns.std()
    
    sharpe = (mean_return / std_return) * np.sqrt(periods_per_year)
    
    return sharpe


def calculate_information_ratio(
    predictions: pd.Series,
    actuals: pd.Series
) -> float:
    """
    Calculate information ratio (IC-based).
    
    IR = mean(IC) / std(IC) where IC is the correlation between predictions and actuals
    
    Args:
        predictions: Predicted returns or signals
        actuals: Actual returns
        
    Returns:
        Information ratio
    """
    if len(predictions) != len(actuals):
        raise ValueError("predictions and actuals must have same length")
    
    # Remove NaN
    valid_mask = predictions.notna() & actuals.notna()
    predictions = predictions[valid_mask]
    actuals = actuals[valid_mask]
    
    if len(predictions) < 2:
        return 0.0
    
    # Calculate correlation (IC)
    ic = predictions.corr(actuals)
    
    if pd.isna(ic):
        return 0.0
    
    # For single IC value, IR = IC / std(IC) approximates to IC / (1/sqrt(N))
    # This is a simplified version; full rolling IC would be better
    ir = ic * np.sqrt(len(predictions))
    
    return ir
