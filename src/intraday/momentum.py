"""
Momentum Indicators for Intraday Trading

Calculates technical indicators and momentum features:
- Price momentum (returns at multiple timeframes)
- VWAP deviation
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Volume profile analysis
- Bollinger Bands
- Relative volume

Returns 12-dimensional feature vector.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import List, Optional, Dict
from collections import deque
import logging
import time

from src.intraday.data_pipeline import IntradayDataPipeline, Bar
from src.intraday.utils import (
    safe_zscore,
    validate_features,
    drop_constant_cols,
    safe_corrcoef,
)
from src.common.normalize import safe_zscore as safe_zscore_common, winsorize

logger = logging.getLogger(__name__)


class MomentumFeatures:
    """
    Compute momentum and technical indicator features.
    
    Features (12 dimensions):
    1. returns_1min - 1-minute return
    2. returns_5min - 5-minute return
    3. returns_30min - 30-minute return
    4. vwap_deviation - (price - vwap) / vwap
    5. rsi_14 - RSI with 14-period lookback
    6. macd - MACD line
    7. macd_signal - MACD signal line
    8. macd_hist - MACD histogram
    9. volume_ratio - Current volume / avg volume
    10. volume_poc - Volume Point of Control (price with most volume)
    11. relative_volume - vs 20-day average
    12. bb_position - Position within Bollinger Bands (0-1)
    
    Example:
        >>> pipeline = IntradayDataPipeline(ib, 'SPY')
        >>> pipeline.start()
        >>> features = MomentumFeatures(pipeline)
        >>> feature_vector = features.compute()
        >>> print(feature_vector.shape)  # (12,)
    """
    
    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
        check_stale: bool = False,  # Disable for historical replay
    ):
        """
        Initialize momentum feature engine.
        
        Args:
            pipeline: IntradayDataPipeline instance
            rsi_period: RSI calculation period
            macd_fast: MACD fast EMA period
            macd_slow: MACD slow EMA period
            macd_signal: MACD signal line period
            bb_period: Bollinger Bands period
            bb_std: Bollinger Bands standard deviation multiplier
            check_stale: Enable stale data detection (False for historical mode)
        """
        self.pipeline = pipeline
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.check_stale = check_stale
        
        # State for incremental calculations
        self.volume_history: deque = deque(maxlen=390)  # 1 day of bars
        self._cache: Dict[str, np.ndarray] = {}
        self._last_compute_time: float = 0.0
        self._cache_ttl: float = 60.0  # seconds
        
        logger.info(
            f"Initialized MomentumFeatures "
            f"(rsi={rsi_period}, macd={macd_fast}/{macd_slow}/{macd_signal})"
        )
    
    def compute(self, use_cache: bool = True) -> np.ndarray:
        """
        Compute all momentum features.
        
        Returns:
            12-dimensional numpy array
        """
        current_time = time.time()
        if (
            use_cache
            and "features" in self._cache
            and current_time - self._last_compute_time < self._cache_ttl
        ):
            return self._cache["features"]

        bars = self.pipeline.get_latest_bars(100)

        if len(bars) < 30:
            logger.warning("MomentumFeatures: insufficient bars (%s)", len(bars))
            features = np.zeros(12)
        elif self.check_stale and self._is_stale_data(bars):
            logger.warning("MomentumFeatures: stale data detected")
            features = np.zeros(12)
        else:
            df = self._bars_to_dataframe(bars)
            self._sanity_warn("close", df['close'])
            self._sanity_warn("vwap", df['vwap'])
            self._sanity_warn("volume", df['volume'])

            features = np.array([
                self._returns_1min(df),
                self._returns_5min(df),
                self._returns_30min(df),
                self._vwap_deviation(df),
                self._rsi(df),
                self._macd(df),
                self._macd_signal_line(df),
                self._macd_histogram(df),
                self._volume_ratio(df),
                self._volume_poc(df),
                self._relative_volume(df),
                self._bb_position(df),
            ])
            
            # Validate and clean features
            features = validate_features(features, name="MomentumFeatures")

        self._cache["features"] = features
        self._last_compute_time = current_time
        return features

    def compute_normalized(self, method: str = "minmax") -> np.ndarray:
        """Compute features with robust normalization (winsorize + z-score)."""
        raw = self.compute()
        
        # Apply winsorization to tame outliers
        winsorized = winsorize(raw.reshape(-1, 1), p=0.005).ravel()
        
        # Apply safe z-score normalization
        normalized = safe_zscore_common(winsorized.reshape(-1, 1), axis=0).ravel()
        
        return normalized
    
    def _bars_to_dataframe(self, bars: List[Bar]) -> pd.DataFrame:
        """Convert bars to pandas DataFrame."""
        return pd.DataFrame([
            {
                "close": bar.close,
                "high": bar.high,
                "low": bar.low,
                "volume": bar.volume,
                "vwap": bar.vwap,
            }
            for bar in bars
        ])
    
    # === Feature Calculations ===
    
    def _returns_1min(self, df: pd.DataFrame) -> float:
        """1. 1-minute return."""
        if len(df) < 2:
            return 0.0
        
        return float((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2])
    
    def _returns_5min(self, df: pd.DataFrame) -> float:
        """2. 5-minute return."""
        if len(df) < 6:
            return 0.0
        
        return float((df['close'].iloc[-1] - df['close'].iloc[-6]) / df['close'].iloc[-6])
    
    def _returns_30min(self, df: pd.DataFrame) -> float:
        """3. 30-minute return."""
        if len(df) < 31:
            return 0.0
        
        return float((df['close'].iloc[-1] - df['close'].iloc[-31]) / df['close'].iloc[-31])
    
    def _vwap_deviation(self, df: pd.DataFrame) -> float:
        """
        4. VWAP deviation.
        
        Measures how far current price is from volume-weighted average.
        
        Positive = trading above VWAP (bullish)
        Negative = trading below VWAP (bearish)
        """
        if len(df) < 1:
            return 0.0
        
        current_price = df['close'].iloc[-1]
        vwap = df['vwap'].iloc[-1]
        
        if vwap == 0:
            return 0.0
        
        return float((current_price - vwap) / vwap)
    
    def _rsi(self, df: pd.DataFrame) -> float:
        """5. RSI using Wilder smoothing with fallbacks and NaN protection."""
        if len(df) < self.rsi_period + 1:
            return 50.0

        try:
            import talib
            
            prices = df['close'].values.astype(np.float64)
            
            # Use TA-Lib for RSI (handles warmup internally)
            rsi_series = talib.RSI(prices, timeperiod=self.rsi_period)
            
            # Forward-fill early NaN values with first valid RSI
            first_valid_idx = np.flatnonzero(np.isfinite(rsi_series))
            if len(first_valid_idx) > 0:
                first_val = rsi_series[first_valid_idx[0]]
                rsi_series[:first_valid_idx[0]] = first_val
            
            # Return most recent RSI
            rsi = float(rsi_series[-1])
            
            # Ensure finite output
            if not np.isfinite(rsi):
                return 50.0
            return np.clip(rsi, 0.0, 100.0)
            
        except ImportError:
            # Fallback to manual RSI if TA-Lib not available
            prices = df['close'].values
            deltas = np.diff(prices)
            if len(deltas) < self.rsi_period:
                return 50.0

            gains = np.maximum(deltas, 0)
            losses = np.maximum(-deltas, 0)

            avg_gain = np.mean(gains[:self.rsi_period])
            avg_loss = np.mean(losses[:self.rsi_period])

            for i in range(self.rsi_period, len(gains)):
                avg_gain = ((avg_gain * (self.rsi_period - 1)) + gains[i]) / self.rsi_period
                avg_loss = ((avg_loss * (self.rsi_period - 1)) + losses[i]) / self.rsi_period

            if avg_loss == 0:
                return 100.0 if avg_gain > 0 else 50.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            rsi = float(np.clip(rsi, 0, 100))
            
            if not np.isfinite(rsi):
                return 50.0
            return rsi
        except Exception as exc:
            logger.warning("Momentum RSI calculation failed: %s", exc)
            return 50.0

    def _sanity_warn(self, name: str, series: pd.Series, std_min: float = 1e-6):
        """Log a warning if a series is constant or invalid."""
        try:
            if not np.isfinite(series).all():
                logger.warning(f"Momentum {name} has NaN/inf values")
            elif float(series.std()) <= std_min:
                logger.warning(f"Momentum {name} is nearly constant; std={float(series.std()):.3e}")
        except Exception:
            pass
    
    def _calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()
    
    def _macd(self, df: pd.DataFrame) -> float:
        """
        6. MACD line with NaN protection.
        
        MACD = EMA(12) - EMA(26)
        
        Positive = bullish momentum
        Negative = bearish momentum
        """
        if len(df) < self.macd_slow:
            return 0.0
        
        try:
            import talib
            
            prices = df['close'].values.astype(np.float64)
            macd_line, signal_line, _ = talib.MACD(
                prices,
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            
            # Forward-fill early NaNs
            first_valid = np.flatnonzero(np.isfinite(macd_line))
            if len(first_valid) > 0:
                macd_line[:first_valid[0]] = macd_line[first_valid[0]]
            
            val = float(macd_line[-1])
            return val if np.isfinite(val) else 0.0
            
        except ImportError:
            # Fallback to pandas EMA
            ema_fast = self._calculate_ema(df['close'], self.macd_fast)
            ema_slow = self._calculate_ema(df['close'], self.macd_slow)
            
            macd = ema_fast - ema_slow
            val = float(macd.iloc[-1])
            
            return val if np.isfinite(val) else 0.0
    
    def _macd_signal_line(self, df: pd.DataFrame) -> float:
        """
        7. MACD signal line with NaN protection.
        
        Signal = EMA(MACD, 9)
        
        Used to generate buy/sell signals when MACD crosses signal.
        """
        if len(df) < self.macd_slow + self.macd_signal:
            return 0.0
        
        try:
            import talib
            
            prices = df['close'].values.astype(np.float64)
            _, signal_line, _ = talib.MACD(
                prices,
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            
            # Forward-fill early NaNs
            first_valid = np.flatnonzero(np.isfinite(signal_line))
            if len(first_valid) > 0:
                signal_line[:first_valid[0]] = signal_line[first_valid[0]]
            
            val = float(signal_line[-1])
            return val if np.isfinite(val) else 0.0
            
        except ImportError:
            # Fallback: calculate MACD first, then signal
            ema_fast = self._calculate_ema(df['close'], self.macd_fast)
            ema_slow = self._calculate_ema(df['close'], self.macd_slow)
            macd = ema_fast - ema_slow
            
            # Calculate signal line (EMA of MACD)
            signal = self._calculate_ema(macd, self.macd_signal)
            val = float(signal.iloc[-1])
            
            return val if np.isfinite(val) else 0.0
    
    def _macd_histogram(self, df: pd.DataFrame) -> float:
        """
        8. MACD histogram.
        
        Histogram = MACD - Signal
        
        Measures distance between MACD and signal:
        - Positive = bullish divergence
        - Negative = bearish divergence
        """
        if len(df) < self.macd_slow + self.macd_signal:
            return 0.0
        
        macd = self._macd(df)
        signal = self._macd_signal_line(df)
        
        return float(macd - signal)
    
    def _volume_ratio(self, df: pd.DataFrame) -> float:
        """
        9. Volume ratio.
        
        Current bar volume / average volume over lookback.
        
        >1.0 = Above average volume (increased interest)
        <1.0 = Below average volume
        """
        if len(df) < 20:
            return 1.0
        
        current_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-20:].mean()
        
        if avg_volume == 0:
            return 1.0
        
        return float(current_volume / avg_volume)
    
    def _volume_poc(self, df: pd.DataFrame, bins: int = 20) -> float:
        """10. Volume Point of Control with dynamic binning."""
        if len(df) < 10:
            return 0.0

        try:
            typical_prices = (df['high'] + df['low'] + df['close']) / 3
            volumes = df['volume'].values
            price_range = float(typical_prices.max() - typical_prices.min())
            if price_range == 0:
                return 0.0

            bin_width = price_range / bins
            volume_by_price: Dict[float, float] = {}
            for price, volume in zip(typical_prices, volumes):
                bin_key = round(price / bin_width) * bin_width
                volume_by_price[bin_key] = volume_by_price.get(bin_key, 0.0) + volume

            if not volume_by_price:
                return 0.0

            poc_price = max(volume_by_price, key=volume_by_price.get)
            current_price = df['close'].iloc[-1]
            distance = (current_price - poc_price) / price_range
            return float(np.clip(distance, -1, 1))
        except Exception as exc:
            logger.warning("Momentum POC calculation failed: %s", exc)
            return 0.0
    
    def _relative_volume(self, df: pd.DataFrame) -> float:
        """
        11. Relative volume vs historical average.
        
        Similar to volume_ratio but uses longer lookback (20+ bars).
        
        >1.5 = High volume (potential breakout)
        <0.5 = Low volume (consolidation)
        """
        if len(df) < 50:
            return 1.0
        
        # Use last 10 bars for current volume
        recent_avg_volume = df['volume'].iloc[-10:].mean()
        
        # Use bars 11-50 for historical baseline
        historical_avg_volume = df['volume'].iloc[-50:-10].mean()
        
        if historical_avg_volume == 0:
            return 1.0
        
        return float(recent_avg_volume / historical_avg_volume)
    
    def _bb_position(self, df: pd.DataFrame) -> float:
        """
        12. Bollinger Band position (0-1).
        
        0.0 = At lower band (oversold)
        0.5 = At middle band (neutral)
        1.0 = At upper band (overbought)
        
        Measures where price is within the Bollinger Band range.
        """
        if len(df) < self.bb_period:
            return 0.5  # Neutral
        
        # Calculate Bollinger Bands
        sma = df['close'].rolling(window=self.bb_period).mean()
        std = df['close'].rolling(window=self.bb_period).std()
        
        upper_band = sma + (self.bb_std * std)
        lower_band = sma - (self.bb_std * std)
        
        # Get latest values
        current_price = df['close'].iloc[-1]
        upper = upper_band.iloc[-1]
        lower = lower_band.iloc[-1]
        
        # Calculate position (0-1)
        if upper == lower:
            return 0.5
        
        position = (current_price - lower) / (upper - lower)
        
        # Clamp to 0-1 range
        return float(max(0.0, min(1.0, position)))
    
    # === Utility Methods ===

    def _is_stale_data(self, bars: List[Bar], max_age_minutes: int = 5) -> bool:
        """Detect stale bar streams."""
        latest = bars[-1].timestamp if bars else 0.0
        if latest == 0.0:
            return True
        age_minutes = (time.time() - latest) / 60.0
        return age_minutes > max_age_minutes
    
    def get_feature_names(self) -> List[str]:
        """Get names of all features."""
        return [
            "returns_1min",
            "returns_5min",
            "returns_30min",
            "vwap_deviation",
            "rsi_14",
            "macd",
            "macd_signal",
            "macd_hist",
            "volume_ratio",
            "volume_poc",
            "relative_volume",
            "bb_position",
        ]
    
    def compute_dict(self) -> dict:
        """Compute features as dictionary (for debugging)."""
        features = self.compute()
        names = self.get_feature_names()
        return dict(zip(names, features))
    
    def __repr__(self) -> str:
        return (
            f"MomentumFeatures("
            f"rsi={self.rsi_period}, "
            f"macd={self.macd_fast}/{self.macd_slow}/{self.macd_signal})"
        )

    def _minmax_normalize(self, features: np.ndarray) -> np.ndarray:
        """Clip-normalize features to [0,1] using heuristic ranges."""
        ranges = np.array([
            [-0.05, 0.05],
            [-0.10, 0.10],
            [-0.15, 0.15],
            [-0.05, 0.05],
            [0.0, 100.0],
            [-2.0, 2.0],
            [-2.0, 2.0],
            [-1.0, 1.0],
            [0.0, 5.0],
            [-0.10, 0.10],
            [0.0, 3.0],
            [0.0, 1.0],
        ])

        normalized = np.zeros_like(features)
        for idx, value in enumerate(features):
            min_val, max_val = ranges[idx]
            if max_val == min_val:
                normalized[idx] = 0.0
            else:
                normalized[idx] = (value - min_val) / (max_val - min_val)
            normalized[idx] = float(np.clip(normalized[idx], 0.0, 1.0))
        return normalized


if __name__ == "__main__":
    # Example usage
    import logging
    from ib_insync import IB
    import time
    
    logging.basicConfig(level=logging.INFO)
    
    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    
    # Create pipeline
    from src.intraday.data_pipeline import IntradayDataPipeline
    
    pipeline = IntradayDataPipeline(ib, 'SPY')
    pipeline.start()
    
    # Wait for data (need enough bars for indicators)
    print("Collecting data for 120 seconds...")
    time.sleep(120)
    
    # Compute features
    momentum = MomentumFeatures(pipeline)
    features = momentum.compute()
    feature_dict = momentum.compute_dict()
    
    print("\n📈 Momentum Features:")
    for name, value in feature_dict.items():
        print(f"  {name:20s}: {value:10.6f}")
    
    # Cleanup
    pipeline.stop()
    ib.disconnect()
