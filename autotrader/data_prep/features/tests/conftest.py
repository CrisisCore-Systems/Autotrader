"""
Shared test fixtures for feature extraction tests.

Provides synthetic bar data for testing all feature extractors.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


@pytest.fixture
def bars_1h_100():
    """
    100 bars of 1-hour OHLCV data with trending price action.
    
    Suitable for testing technical indicators and rolling features.
    """
    np.random.seed(42)
    
    n_bars = 100
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=None)
    
    # Generate trending prices
    drift = 0.001  # Upward trend
    volatility = 0.01
    
    returns = np.random.normal(drift, volatility, n_bars)
    prices = 100.0 * np.exp(np.cumsum(returns))
    
    # Generate OHLC from close prices
    high = prices * (1 + np.abs(np.random.normal(0, 0.005, n_bars)))
    low = prices * (1 - np.abs(np.random.normal(0, 0.005, n_bars)))
    open_prices = np.roll(prices, 1)
    open_prices[0] = prices[0]
    
    # Generate volumes
    volumes = np.random.lognormal(10, 1, n_bars)
    
    # Create timestamps (1-hour bars)
    timestamps = [start_time + timedelta(hours=i) for i in range(n_bars)]
    
    return pd.DataFrame({
        "timestamp_utc": timestamps,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volumes
    })


@pytest.fixture
def bars_1m_1000():
    """
    1,000 bars of 1-minute OHLCV data for performance testing.
    
    Suitable for testing feature extraction speed.
    """
    np.random.seed(123)
    
    n_bars = 1000
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=None)
    
    # Generate mean-reverting prices
    prices = 100.0 + np.cumsum(np.random.normal(0, 0.1, n_bars))
    
    # Generate OHLC
    high = prices * (1 + np.abs(np.random.normal(0, 0.002, n_bars)))
    low = prices * (1 - np.abs(np.random.normal(0, 0.002, n_bars)))
    open_prices = np.roll(prices, 1)
    open_prices[0] = prices[0]
    
    # Generate volumes
    volumes = np.random.lognormal(8, 1, n_bars)
    
    # Create timestamps (1-minute bars)
    timestamps = [start_time + timedelta(minutes=i) for i in range(n_bars)]
    
    return pd.DataFrame({
        "timestamp_utc": timestamps,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volumes
    })


@pytest.fixture
def bars_with_gaps():
    """
    50 bars with missing data (NaN values) for edge case testing.
    
    Suitable for testing NaN handling.
    """
    np.random.seed(456)
    
    n_bars = 50
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=None)
    
    prices = 100.0 + np.cumsum(np.random.normal(0, 0.5, n_bars))
    
    # Introduce NaN values (10% of data)
    nan_indices = np.random.choice(n_bars, size=5, replace=False)
    prices[nan_indices] = np.nan
    
    # Generate OHLC
    high = prices * 1.01
    low = prices * 0.99
    open_prices = prices.copy()
    
    volumes = np.random.lognormal(9, 1, n_bars)
    
    # Create timestamps
    timestamps = [start_time + timedelta(hours=i) for i in range(n_bars)]
    
    return pd.DataFrame({
        "timestamp_utc": timestamps,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volumes
    })


@pytest.fixture
def bars_volatile():
    """
    100 bars with high volatility for stress testing.
    
    Suitable for testing feature stability under extreme conditions.
    """
    np.random.seed(789)
    
    n_bars = 100
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=None)
    
    # High volatility, no drift
    volatility = 0.05
    returns = np.random.normal(0, volatility, n_bars)
    prices = 100.0 * np.exp(np.cumsum(returns))
    
    # Wide OHLC ranges
    high = prices * (1 + np.abs(np.random.normal(0, 0.02, n_bars)))
    low = prices * (1 - np.abs(np.random.normal(0, 0.02, n_bars)))
    open_prices = np.roll(prices, 1)
    open_prices[0] = prices[0]
    
    volumes = np.random.lognormal(10, 2, n_bars)
    
    timestamps = [start_time + timedelta(hours=i) for i in range(n_bars)]
    
    return pd.DataFrame({
        "timestamp_utc": timestamps,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volumes
    })


@pytest.fixture
def bars_flat():
    """
    100 bars with flat prices (no movement) for edge case testing.
    
    Suitable for testing division-by-zero handling.
    """
    n_bars = 100
    start_time = datetime(2024, 1, 1, 9, 30, tzinfo=None)
    
    # Constant price
    prices = np.full(n_bars, 100.0)
    
    # Flat OHLC
    high = prices + 0.01
    low = prices - 0.01
    open_prices = prices.copy()
    
    volumes = np.full(n_bars, 1000.0)
    
    timestamps = [start_time + timedelta(hours=i) for i in range(n_bars)]
    
    return pd.DataFrame({
        "timestamp_utc": timestamps,
        "open": open_prices,
        "high": high,
        "low": low,
        "close": prices,
        "volume": volumes
    })
