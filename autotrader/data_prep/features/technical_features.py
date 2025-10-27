"""
Technical indicator feature extraction.

Implements classic technical analysis indicators for price/volume data:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR (Average True Range)

All indicators use vectorized pandas operations for performance.
"""

import pandas as pd
import numpy as np
from typing import Optional


class TechnicalFeatureExtractor:
    """
    Extract technical analysis features from OHLCV bar data.
    
    Features:
    - RSI (14-period by default)
    - MACD (12/26/9 by default)
    - Bollinger Bands (20/2 by default)
    - ATR (14-period by default)
    
    Total: 7 features
    
    Example:
        extractor = TechnicalFeatureExtractor()
        features = extractor.extract_all(
            bars_df=bars,
            close_col="close",
            high_col="high",
            low_col="low"
        )
    """

    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        atr_period: int = 14
    ):
        """
        Initialize technical feature extractor.

        Args:
            rsi_period: Period for RSI calculation
            macd_fast: Fast EMA period for MACD
            macd_slow: Slow EMA period for MACD
            macd_signal: Signal line period for MACD
            bb_period: Period for Bollinger Bands
            bb_std: Number of standard deviations for Bollinger Bands
            atr_period: Period for ATR calculation
        """
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.atr_period = atr_period

    def extract_all(
        self,
        bars_df: pd.DataFrame,
        close_col: str = "close",
        high_col: str = "high",
        low_col: str = "low",
        volume_col: str = "volume"
    ) -> pd.DataFrame:
        """
        Extract all technical features.

        Args:
            bars_df: DataFrame with OHLCV bar data
            close_col: Name of close price column
            high_col: Name of high price column
            low_col: Name of low price column
            volume_col: Name of volume column

        Returns:
            DataFrame with technical features (same index as input)
        """
        features = pd.DataFrame(index=bars_df.index)

        # RSI (1 feature)
        features["rsi"] = self._calculate_rsi(
            bars_df[close_col]
        )

        # MACD (3 features: line, signal, histogram)
        macd_features = self._calculate_macd(
            bars_df[close_col]
        )
        features["macd_line"] = macd_features["line"]
        features["macd_signal"] = macd_features["signal"]
        features["macd_histogram"] = macd_features["histogram"]

        # Bollinger Bands (2 features: upper/lower relative position)
        bb_features = self._calculate_bollinger_bands(
            bars_df[close_col]
        )
        features["bb_upper_pct"] = bb_features["upper_pct"]
        features["bb_lower_pct"] = bb_features["lower_pct"]

        # ATR (1 feature)
        features["atr"] = self._calculate_atr(
            bars_df[high_col],
            bars_df[low_col],
            bars_df[close_col]
        )

        return features

    def _calculate_rsi(self, close: pd.Series) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).

        RSI = 100 - (100 / (1 + RS))
        where RS = average gain / average loss over period

        Args:
            close: Close prices

        Returns:
            RSI values (0-100 scale)
        """
        # Calculate price changes
        delta = close.diff()

        # Separate gains and losses
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)

        # Calculate exponential moving averages
        avg_gain = gain.ewm(span=self.rsi_period, adjust=False, min_periods=self.rsi_period).mean()
        avg_loss = loss.ewm(span=self.rsi_period, adjust=False, min_periods=self.rsi_period).mean()

        # Calculate RSI
        rs = avg_gain / avg_loss
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # Handle division by zero (all losses → RSI=0)
        rsi = rsi.fillna(0.0)

        return rsi

    def _calculate_macd(self, close: pd.Series) -> dict[str, pd.Series]:
        """
        Calculate MACD (Moving Average Convergence Divergence).

        MACD Line = EMA(fast) - EMA(slow)
        Signal Line = EMA(MACD Line, signal_period)
        Histogram = MACD Line - Signal Line

        Args:
            close: Close prices

        Returns:
            Dictionary with 'line', 'signal', 'histogram'
        """
        # Calculate fast and slow EMAs
        ema_fast = close.ewm(span=self.macd_fast, adjust=False, min_periods=self.macd_fast).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False, min_periods=self.macd_slow).mean()

        # MACD line
        macd_line = ema_fast - ema_slow

        # Signal line
        macd_signal = macd_line.ewm(span=self.macd_signal, adjust=False, min_periods=self.macd_signal).mean()

        # Histogram
        macd_histogram = macd_line - macd_signal

        return {
            "line": macd_line,
            "signal": macd_signal,
            "histogram": macd_histogram
        }

    def _calculate_bollinger_bands(self, close: pd.Series) -> dict[str, pd.Series]:
        """
        Calculate Bollinger Bands.

        Middle Band = SMA(period)
        Upper Band = Middle + (std_dev * num_std)
        Lower Band = Middle - (std_dev * num_std)

        Returns relative position: (close - lower) / (upper - lower)

        Args:
            close: Close prices

        Returns:
            Dictionary with 'upper_pct' (distance to upper band) and
            'lower_pct' (distance to lower band), both in [0, 1] range
        """
        # Calculate middle band (SMA)
        middle = close.rolling(window=self.bb_period, min_periods=self.bb_period).mean()
        std = close.rolling(window=self.bb_period, min_periods=self.bb_period).std()

        # Calculate upper and lower bands
        upper = middle + (std * self.bb_std)
        lower = middle - (std * self.bb_std)

        # Calculate relative position
        band_width = upper - lower
        band_width = band_width.replace(0.0, np.nan)  # Avoid division by zero

        upper_pct = (upper - close) / band_width
        lower_pct = (close - lower) / band_width

        # Clip to [0, 1] range (price can be outside bands)
        upper_pct = upper_pct.clip(0.0, 1.0)
        lower_pct = lower_pct.clip(0.0, 1.0)

        return {
            "upper_pct": upper_pct,
            "lower_pct": lower_pct
        }

    def _calculate_atr(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series
    ) -> pd.Series:
        """
        Calculate ATR (Average True Range).

        True Range = max(high - low, |high - prev_close|, |low - prev_close|)
        ATR = EMA(True Range, period)

        Args:
            high: High prices
            low: Low prices
            close: Close prices

        Returns:
            ATR values
        """
        prev_close = close.shift(1)

        # Calculate true range components
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()

        # True range is the maximum of the three
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # ATR is exponential moving average of true range
        atr = true_range.ewm(span=self.atr_period, adjust=False, min_periods=self.atr_period).mean()

        return atr

    def get_feature_names(self) -> list[str]:
        """
        Get list of feature names produced by this extractor.

        Returns:
            List of 7 feature names
        """
        return [
            "rsi",
            "macd_line",
            "macd_signal",
            "macd_histogram",
            "bb_upper_pct",
            "bb_lower_pct",
            "atr"
        ]
