"""
Temporal feature extraction.

Implements time-based features for modeling intraday patterns:
- Time-of-day bins (morning/midday/afternoon/close)
- Day-of-week indicators
- Session indicators (pre-market/regular/after-hours)
- Holiday proximity

All features are cyclical-aware for periodic patterns.
"""

import pandas as pd
import numpy as np
from datetime import time
from typing import Optional


class TemporalFeatureExtractor:
    """
    Extract time-based features from timestamped bar data.
    
    Features:
    - hour_sin, hour_cos: Cyclical hour encoding
    - minute_sin, minute_cos: Cyclical minute encoding
    - day_of_week_sin, day_of_week_cos: Cyclical day encoding
    - is_market_open: Regular session indicator (9:30-16:00 ET)
    - is_morning: Morning session (9:30-12:00)
    - is_afternoon: Afternoon session (12:00-16:00)
    - is_close: Last 30 minutes of trading
    
    Total: 11 features
    
    Example:
        extractor = TemporalFeatureExtractor(timezone="America/New_York")
        features = extractor.extract_all(
            bars_df=bars,
            timestamp_col="timestamp_utc"
        )
    """

    def __init__(
        self,
        timezone: str = "America/New_York",
        market_open: time = time(9, 30),
        market_close: time = time(16, 0),
        close_window_minutes: int = 30
    ):
        """
        Initialize temporal feature extractor.

        Args:
            timezone: Timezone for market hours (default: US Eastern)
            market_open: Market open time (default: 9:30 AM)
            market_close: Market close time (default: 4:00 PM)
            close_window_minutes: Minutes before close for 'is_close' flag
        """
        self.timezone = timezone
        self.market_open = market_open
        self.market_close = market_close
        self.close_window_minutes = close_window_minutes

    def extract_all(
        self,
        bars_df: pd.DataFrame,
        timestamp_col: str = "timestamp_utc"
    ) -> pd.DataFrame:
        """
        Extract all temporal features.

        Args:
            bars_df: DataFrame with timestamped bar data
            timestamp_col: Name of timestamp column (must be UTC)

        Returns:
            DataFrame with temporal features (same index as input)
        """
        features = pd.DataFrame(index=bars_df.index)

        # Convert to local timezone
        timestamps = pd.to_datetime(bars_df[timestamp_col])
        if timestamps.dt.tz is None:
            timestamps = timestamps.dt.tz_localize("UTC")
        local_time = timestamps.dt.tz_convert(self.timezone)

        # Cyclical time features
        hour_features = self._encode_cyclical_hour(local_time)
        features["hour_sin"] = hour_features["sin"]
        features["hour_cos"] = hour_features["cos"]

        minute_features = self._encode_cyclical_minute(local_time)
        features["minute_sin"] = minute_features["sin"]
        features["minute_cos"] = minute_features["cos"]

        # Cyclical day-of-week features
        dow_features = self._encode_cyclical_day_of_week(local_time)
        features["day_of_week_sin"] = dow_features["sin"]
        features["day_of_week_cos"] = dow_features["cos"]

        # Session indicators
        features["is_market_open"] = self._is_market_open(local_time)
        features["is_morning"] = self._is_morning_session(local_time)
        features["is_afternoon"] = self._is_afternoon_session(local_time)
        features["is_close"] = self._is_close_window(local_time)

        # Weekend indicator (useful for crypto markets that trade 24/7)
        features["is_weekend"] = local_time.dt.dayofweek.isin([5, 6]).astype(float)

        return features

    def _encode_cyclical_hour(self, timestamps: pd.Series) -> dict[str, pd.Series]:
        """
        Encode hour as cyclical feature using sine/cosine.

        Ensures hour 23 is close to hour 0 in feature space.

        Args:
            timestamps: Localized timestamps

        Returns:
            Dictionary with 'sin' and 'cos' encodings
        """
        hour = timestamps.dt.hour
        hour_rad = 2 * np.pi * hour / 24.0

        return {
            "sin": np.sin(hour_rad),
            "cos": np.cos(hour_rad)
        }

    def _encode_cyclical_minute(self, timestamps: pd.Series) -> dict[str, pd.Series]:
        """
        Encode minute as cyclical feature using sine/cosine.

        Args:
            timestamps: Localized timestamps

        Returns:
            Dictionary with 'sin' and 'cos' encodings
        """
        minute = timestamps.dt.minute
        minute_rad = 2 * np.pi * minute / 60.0

        return {
            "sin": np.sin(minute_rad),
            "cos": np.cos(minute_rad)
        }

    def _encode_cyclical_day_of_week(self, timestamps: pd.Series) -> dict[str, pd.Series]:
        """
        Encode day-of-week as cyclical feature.

        Monday=0, Sunday=6. Ensures Sunday is close to Monday.

        Args:
            timestamps: Localized timestamps

        Returns:
            Dictionary with 'sin' and 'cos' encodings
        """
        day = timestamps.dt.dayofweek
        day_rad = 2 * np.pi * day / 7.0

        return {
            "sin": np.sin(day_rad),
            "cos": np.cos(day_rad)
        }

    def _is_market_open(self, timestamps: pd.Series) -> pd.Series:
        """
        Check if timestamp is during regular market hours.

        Args:
            timestamps: Localized timestamps

        Returns:
            Boolean series (1.0 if market open, 0.0 otherwise)
        """
        time_only = timestamps.dt.time

        is_open = (
            (time_only >= self.market_open) &
            (time_only < self.market_close) &
            (timestamps.dt.dayofweek < 5)  # Monday=0, Friday=4
        )

        return is_open.astype(float)

    def _is_morning_session(self, timestamps: pd.Series) -> pd.Series:
        """
        Check if timestamp is during morning session (open to noon).

        Args:
            timestamps: Localized timestamps

        Returns:
            Boolean series
        """
        time_only = timestamps.dt.time
        noon = time(12, 0)

        is_morning = (
            (time_only >= self.market_open) &
            (time_only < noon) &
            (timestamps.dt.dayofweek < 5)
        )

        return is_morning.astype(float)

    def _is_afternoon_session(self, timestamps: pd.Series) -> pd.Series:
        """
        Check if timestamp is during afternoon session (noon to close).

        Args:
            timestamps: Localized timestamps

        Returns:
            Boolean series
        """
        time_only = timestamps.dt.time
        noon = time(12, 0)

        is_afternoon = (
            (time_only >= noon) &
            (time_only < self.market_close) &
            (timestamps.dt.dayofweek < 5)
        )

        return is_afternoon.astype(float)

    def _is_close_window(self, timestamps: pd.Series) -> pd.Series:
        """
        Check if timestamp is in the closing window (last N minutes).

        Args:
            timestamps: Localized timestamps

        Returns:
            Boolean series
        """
        # Calculate close window start time
        close_minutes = self.market_close.hour * 60 + self.market_close.minute
        window_start_minutes = close_minutes - self.close_window_minutes
        window_start = time(
            hour=window_start_minutes // 60,
            minute=window_start_minutes % 60
        )

        time_only = timestamps.dt.time

        is_close = (
            (time_only >= window_start) &
            (time_only < self.market_close) &
            (timestamps.dt.dayofweek < 5)
        )

        return is_close.astype(float)

    def get_feature_names(self) -> list[str]:
        """
        Get list of feature names produced by this extractor.

        Returns:
            List of 11 feature names
        """
        return [
            "hour_sin",
            "hour_cos",
            "minute_sin",
            "minute_cos",
            "day_of_week_sin",
            "day_of_week_cos",
            "is_market_open",
            "is_morning",
            "is_afternoon",
            "is_close",
            "is_weekend"
        ]
