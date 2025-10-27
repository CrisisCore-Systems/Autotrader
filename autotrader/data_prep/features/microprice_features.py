"""
Microprice and high-frequency volatility features.

Implements microstructure-level price and volatility measures:
- Microprice: Volume-weighted mid-price (more accurate than simple mid)
- Realized volatility: Sum of squared returns over high-frequency intervals
- Realized variance: Unbiased variance estimator
- Jump detection: Lee-Mykland (2008) test statistic for price jumps
- Intraday patterns: Volatility regimes and clustering

These features capture high-frequency dynamics critical for:
- Market making (microprice is better price for execution)
- Risk management (realized vol more accurate than EWMA)
- Event detection (jumps signal news arrival)
- Regime switching (vol clustering for position sizing)

References:
- Microprice: Stoikov (2018), Cartea et al. (2015)
- Realized volatility: Andersen et al. (2001)
- Jump detection: Lee & Mykland (2008)
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal


class MicropriceFeatureExtractor:
    """
    Extract microprice and high-frequency volatility features.
    
    Features:
    1. microprice: Volume-weighted mid-price (better than simple mid)
    2. microprice_spread: Distance from microprice to mid (liquidity signal)
    3. realized_vol: sqrt(sum of squared returns) over window
    4. realized_var: Unbiased variance estimator
    5. jump_stat: Lee-Mykland jump test statistic
    6. jump_flag: Binary indicator for significant jumps
    7. vol_ratio: Current vol / recent average vol (regime detector)
    8. returns_skew: Rolling skewness of returns (crash risk)
    9. returns_kurt: Rolling kurtosis (tail risk)
    
    Example:
        extractor = MicropriceFeatureExtractor(
            realized_vol_window=50,
            jump_window=100
        )
        
        features = extractor.extract_all(
            bars_df=bars,
            orderbook_df=orderbook  # For microprice calculation
        )
    """
    
    def __init__(
        self,
        realized_vol_window: int = 50,
        jump_window: int = 100,
        jump_threshold: float = 4.0,  # 4-sigma for jump detection
        vol_ratio_window: int = 200,
        moment_window: int = 100
    ):
        """
        Initialize microprice feature extractor.
        
        Args:
            realized_vol_window: Window for realized volatility (bars)
            jump_window: Window for jump test statistic
            jump_threshold: Threshold for jump detection (sigma)
            vol_ratio_window: Window for volatility regime detection
            moment_window: Window for skewness/kurtosis
        """
        self.realized_vol_window = realized_vol_window
        self.jump_window = jump_window
        self.jump_threshold = jump_threshold
        self.vol_ratio_window = vol_ratio_window
        self.moment_window = moment_window
    
    def extract_all(
        self,
        bars_df: pd.DataFrame,
        orderbook_df: Optional[pd.DataFrame] = None,
        close_col: str = "close",
        high_col: str = "high",
        low_col: str = "low",
        volume_col: str = "volume"
    ) -> pd.DataFrame:
        """
        Extract all microprice and volatility features.
        
        Args:
            bars_df: OHLCV bar data
            orderbook_df: Orderbook snapshots (optional, for microprice)
            close_col: Close price column
            high_col: High price column
            low_col: Low price column
            volume_col: Volume column
        
        Returns:
            DataFrame with microprice/volatility features
        """
        features = pd.DataFrame(index=bars_df.index)
        
        close = bars_df[close_col]
        high = bars_df[high_col]
        low = bars_df[low_col]
        volume = bars_df[volume_col]
        
        # Calculate log returns
        log_returns = np.log(close / close.shift(1))
        
        # Microprice (if orderbook available)
        if orderbook_df is not None:
            features['microprice'] = self._calculate_microprice(orderbook_df, bars_df.index)
            features['microprice_spread'] = self._calculate_microprice_spread(
                features['microprice'], close
            )
        
        # Realized volatility and variance
        features['realized_vol'] = self._calculate_realized_volatility(log_returns)
        features['realized_var'] = self._calculate_realized_variance(log_returns)
        
        # Jump detection (Lee-Mykland 2008)
        features['jump_stat'] = self._calculate_jump_statistic(log_returns)
        features['jump_flag'] = (features['jump_stat'].abs() > self.jump_threshold).astype(int)
        
        # Volatility regime
        features['vol_ratio'] = self._calculate_volatility_ratio(features['realized_vol'])
        
        # Higher moments (skewness, kurtosis)
        features['returns_skew'] = self._calculate_rolling_skewness(log_returns)
        features['returns_kurt'] = self._calculate_rolling_kurtosis(log_returns)
        
        return features
    
    def _calculate_microprice(
        self,
        orderbook_df: pd.DataFrame,
        target_index: pd.Index
    ) -> pd.Series:
        """
        Calculate volume-weighted microprice.
        
        Microprice = (bid * ask_size + ask * bid_size) / (bid_size + ask_size)
        
        This is more accurate than simple mid = (bid + ask) / 2 because it
        weights by liquidity at each level.
        
        Args:
            orderbook_df: Orderbook with bid/ask prices and sizes
            target_index: Target index to align to
        
        Returns:
            Microprice series aligned to target_index
        """
        if 'bid_price_1' not in orderbook_df.columns:
            # Fallback: use close price
            return pd.Series(np.nan, index=target_index)
        
        bid = orderbook_df['bid_price_1']
        ask = orderbook_df['ask_price_1']
        bid_size = orderbook_df['bid_size_1']
        ask_size = orderbook_df['ask_size_1']
        
        # Volume-weighted microprice
        microprice = (bid * ask_size + ask * bid_size) / (bid_size + ask_size)
        
        # Align to target index (forward fill from orderbook to bars)
        microprice = microprice.reindex(target_index, method='ffill')
        
        return microprice
    
    def _calculate_microprice_spread(
        self,
        microprice: pd.Series,
        mid: pd.Series
    ) -> pd.Series:
        """
        Calculate spread between microprice and simple mid.
        
        Positive = microprice > mid (more ask pressure)
        Negative = microprice < mid (more bid pressure)
        
        This is a liquidity signal: larger spread = more imbalance.
        """
        return (microprice - mid) / mid
    
    def _calculate_realized_volatility(self, returns: pd.Series) -> pd.Series:
        """
        Calculate realized volatility.
        
        RV = sqrt(sum(r_t^2)) over window
        
        More accurate than EWMA for high-frequency data because it uses
        all squared returns, not exponentially weighted.
        """
        squared_returns = returns ** 2
        
        # Sum of squared returns over window
        sum_sq_returns = squared_returns.rolling(
            window=self.realized_vol_window,
            min_periods=self.realized_vol_window
        ).sum()
        
        # Annualization factor (assuming intraday bars)
        # For 1-min bars: sqrt(525600) for annual vol
        # For simplicity, return per-bar vol (user can annualize)
        realized_vol = np.sqrt(sum_sq_returns)
        
        return realized_vol
    
    def _calculate_realized_variance(self, returns: pd.Series) -> pd.Series:
        """
        Calculate realized variance (unbiased).
        
        RVar = sum(r_t^2) / (n - 1)
        
        Unbiased estimator for variance (Bessel's correction).
        """
        squared_returns = returns ** 2
        
        realized_var = squared_returns.rolling(
            window=self.realized_vol_window,
            min_periods=self.realized_vol_window
        ).mean()
        
        # Bessel correction
        realized_var = realized_var * self.realized_vol_window / (self.realized_vol_window - 1)
        
        return realized_var
    
    def _calculate_jump_statistic(self, returns: pd.Series) -> pd.Series:
        """
        Calculate Lee-Mykland (2008) jump test statistic.
        
        L_t = |r_t| / sqrt(BV_t)
        
        where BV_t is bipower variation (robust volatility estimator).
        
        L_t > threshold indicates a significant jump (news arrival).
        
        Reference: Lee, S. S., & Mykland, P. A. (2008).
        "Jumps in financial markets: A new nonparametric test and jump dynamics."
        Review of Financial Studies, 21(6), 2535-2563.
        """
        # Bipower variation (robust to jumps)
        abs_returns = returns.abs()
        abs_returns_lagged = abs_returns.shift(1)
        
        # BV = (π/2) * sum(|r_t| * |r_{t-1}|)
        bv = (np.pi / 2) * (abs_returns * abs_returns_lagged).rolling(
            window=self.jump_window,
            min_periods=self.jump_window
        ).sum()
        
        # Jump statistic
        jump_stat = abs_returns / np.sqrt(bv)
        
        return jump_stat
    
    def _calculate_volatility_ratio(self, realized_vol: pd.Series) -> pd.Series:
        """
        Calculate volatility ratio (regime detector).
        
        vol_ratio = current_vol / average_vol
        
        > 1: High volatility regime
        < 1: Low volatility regime
        
        Useful for position sizing and strategy selection.
        """
        avg_vol = realized_vol.rolling(
            window=self.vol_ratio_window,
            min_periods=self.vol_ratio_window
        ).mean()
        
        return realized_vol / avg_vol
    
    def _calculate_rolling_skewness(self, returns: pd.Series) -> pd.Series:
        """
        Calculate rolling skewness of returns.
        
        Negative skew = crash risk (left tail)
        Positive skew = rally potential (right tail)
        
        Used for tail risk management.
        """
        return returns.rolling(
            window=self.moment_window,
            min_periods=self.moment_window
        ).skew()
    
    def _calculate_rolling_kurtosis(self, returns: pd.Series) -> pd.Series:
        """
        Calculate rolling kurtosis of returns.
        
        High kurtosis = fat tails (more extreme moves)
        
        Used for risk management and option pricing.
        """
        return returns.rolling(
            window=self.moment_window,
            min_periods=self.moment_window
        ).kurt()
    
    def get_feature_names(self) -> list[str]:
        """Get list of feature names produced."""
        base_names = [
            'realized_vol',
            'realized_var',
            'jump_stat',
            'jump_flag',
            'vol_ratio',
            'returns_skew',
            'returns_kurt'
        ]
        
        # Microprice features optional (need orderbook)
        optional_names = [
            'microprice',
            'microprice_spread'
        ]
        
        return base_names + optional_names
