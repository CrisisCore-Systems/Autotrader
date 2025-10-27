"""
Volume-based feature extraction.

Implements volume-weighted and volume-aware features:
- VWAP (Volume-Weighted Average Price)
- Volume ratios and acceleration
- On-Balance Volume (OBV)
- Volume-price correlation
- Relative volume metrics

These features are critical for HFT/intraday strategies as they capture
liquidity dynamics and informed trading activity.
"""

import pandas as pd
import numpy as np
from typing import Optional


class VolumeFeatureExtractor:
    """
    Extract volume-based features from OHLCV bar data.
    
    Features:
    - vwap: Volume-Weighted Average Price
    - volume_ratio: Current volume / average volume
    - volume_acceleration: Rate of change of volume
    - relative_volume: Volume percentile rank
    - volume_price_corr: Correlation between |returns| and volume
    - obv: On-Balance Volume (cumulative)
    - vw_return: Volume-weighted return
    
    Total: 7 features
    
    Example:
        extractor = VolumeFeatureExtractor(vwap_window=20)
        features = extractor.extract_all(
            bars_df=bars,
            close_col="close",
            volume_col="volume"
        )
    """

    def __init__(
        self,
        vwap_window: int = 20,
        volume_ratio_window: int = 20,
        volume_corr_window: int = 50
    ):
        """
        Initialize volume feature extractor.

        Args:
            vwap_window: Window for VWAP calculation
            volume_ratio_window: Window for average volume
            volume_corr_window: Window for volume-price correlation
        """
        self.vwap_window = vwap_window
        self.volume_ratio_window = volume_ratio_window
        self.volume_corr_window = volume_corr_window

    def extract_all(
        self,
        bars_df: pd.DataFrame,
        close_col: str = "close",
        high_col: str = "high",
        low_col: str = "low",
        volume_col: str = "volume"
    ) -> pd.DataFrame:
        """
        Extract all volume features.

        Args:
            bars_df: DataFrame with OHLCV bar data
            close_col: Name of close price column
            high_col: Name of high price column
            low_col: Name of low price column
            volume_col: Name of volume column

        Returns:
            DataFrame with volume features (same index as input)
        """
        features = pd.DataFrame(index=bars_df.index)

        close = bars_df[close_col]
        high = bars_df[high_col]
        low = bars_df[low_col]
        volume = bars_df[volume_col]

        # Typical price for VWAP
        typical_price = (high + low + close) / 3.0

        # 1. VWAP (Volume-Weighted Average Price)
        features["vwap"] = self._calculate_vwap(typical_price, volume)

        # 2. Volume Ratio (current / average)
        features["volume_ratio"] = self._calculate_volume_ratio(volume)

        # 3. Volume Acceleration (rate of change)
        features["volume_accel"] = self._calculate_volume_acceleration(volume)

        # 4. Relative Volume (percentile rank)
        features["relative_volume"] = self._calculate_relative_volume(volume)

        # 5. Volume-Price Correlation
        features["volume_price_corr"] = self._calculate_volume_price_correlation(
            close, volume
        )

        # 6. On-Balance Volume (OBV)
        features["obv"] = self._calculate_obv(close, volume)

        # 7. Volume-Weighted Return
        features["vw_return"] = self._calculate_volume_weighted_return(
            close, volume
        )

        return features

    def _calculate_vwap(
        self,
        typical_price: pd.Series,
        volume: pd.Series
    ) -> pd.Series:
        """
        Calculate Volume-Weighted Average Price.

        VWAP = Σ(price × volume) / Σ(volume) over window

        Args:
            typical_price: (High + Low + Close) / 3
            volume: Volume

        Returns:
            VWAP values
        """
        pv = typical_price * volume
        
        cumsum_pv = pv.rolling(window=self.vwap_window, min_periods=1).sum()
        cumsum_vol = volume.rolling(window=self.vwap_window, min_periods=1).sum()
        
        # Avoid division by zero
        vwap = cumsum_pv / cumsum_vol.replace(0, np.nan)
        
        return vwap

    def _calculate_volume_ratio(self, volume: pd.Series) -> pd.Series:
        """
        Calculate volume ratio: current volume / rolling average.

        Values > 1.0 indicate above-average volume.

        Args:
            volume: Volume series

        Returns:
            Volume ratio
        """
        avg_volume = volume.rolling(
            window=self.volume_ratio_window,
            min_periods=self.volume_ratio_window
        ).mean()
        
        # Avoid division by zero
        avg_volume = avg_volume.replace(0, np.nan)
        
        return volume / avg_volume

    def _calculate_volume_acceleration(self, volume: pd.Series) -> pd.Series:
        """
        Calculate volume acceleration (rate of change).

        Acceleration = (volume[t] - volume[t-1]) - (volume[t-1] - volume[t-2])
                      = volume[t] - 2*volume[t-1] + volume[t-2]

        Args:
            volume: Volume series

        Returns:
            Volume acceleration
        """
        return volume.diff().diff()

    def _calculate_relative_volume(self, volume: pd.Series) -> pd.Series:
        """
        Calculate relative volume (percentile rank in rolling window).

        Args:
            volume: Volume series

        Returns:
            Relative volume [0, 1]
        """
        def rank_pct(x):
            if len(x) < 2:
                return np.nan
            current = x.iloc[-1]
            rank = (x <= current).sum()
            return rank / len(x)

        return volume.rolling(
            window=self.volume_ratio_window,
            min_periods=self.volume_ratio_window
        ).apply(rank_pct, raw=False)

    def _calculate_volume_price_correlation(
        self,
        close: pd.Series,
        volume: pd.Series
    ) -> pd.Series:
        """
        Calculate rolling correlation between absolute returns and volume.

        Positive correlation: Price moves on high volume (momentum)
        Negative correlation: Price moves on low volume (mean reversion)

        Args:
            close: Close prices
            volume: Volume

        Returns:
            Correlation values [-1, 1]
        """
        abs_returns = np.abs(close.pct_change())
        
        return abs_returns.rolling(
            window=self.volume_corr_window,
            min_periods=self.volume_corr_window
        ).corr(volume)

    def _calculate_obv(self, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Calculate On-Balance Volume (OBV).

        OBV = cumulative volume with sign based on price direction:
        - If close[t] > close[t-1]: OBV += volume[t]
        - If close[t] < close[t-1]: OBV -= volume[t]
        - If close[t] == close[t-1]: OBV unchanged

        Args:
            close: Close prices
            volume: Volume

        Returns:
            OBV values
        """
        price_change = close.diff()
        
        # Sign of price change (-1, 0, or 1)
        sign = np.sign(price_change)
        
        # Signed volume
        signed_volume = sign * volume
        
        # Cumulative sum
        obv = signed_volume.cumsum()
        
        return obv

    def _calculate_volume_weighted_return(
        self,
        close: pd.Series,
        volume: pd.Series
    ) -> pd.Series:
        """
        Calculate volume-weighted return over rolling window.

        Emphasizes returns that occurred on high volume.

        Args:
            close: Close prices
            volume: Volume

        Returns:
            Volume-weighted returns
        """
        returns = close.pct_change()
        
        # Normalize volume to sum to 1 within window
        volume_weights = volume.rolling(
            window=self.volume_ratio_window,
            min_periods=self.volume_ratio_window
        ).apply(lambda x: x.iloc[-1] / x.sum() if x.sum() > 0 else 0, raw=False)
        
        # Weight returns by volume
        vw_returns = returns * volume_weights * self.volume_ratio_window
        
        return vw_returns

    def get_feature_names(self) -> list[str]:
        """
        Get list of feature names produced by this extractor.

        Returns:
            List of 7 feature names
        """
        return [
            "vwap",
            "volume_ratio",
            "volume_accel",
            "relative_volume",
            "volume_price_corr",
            "obv",
            "vw_return"
        ]
