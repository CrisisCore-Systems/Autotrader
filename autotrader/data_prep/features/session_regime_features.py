"""
Session and regime features for time-of-day and volatility regimes.

Implements temporal and regime features:
- Session proximity: Distance to market open/close
- Day-of-week effects: Monday vs Friday behavior
- Volatility regimes: High/low volatility classification
- Volume regimes: High/low volume classification
- Time-to-event: Minutes until key events

These features capture:
- Intraday patterns (volatility smile, volume U-shape)
- Day-of-week seasonality (weekend effects)
- Regime changes (volatility clustering)
- Event anticipation (pre-close positioning)

References:
- Intraday patterns: Admati & Pfleiderer (1988)
- Volatility regimes: Hamilton (1989) regime switching
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal
from datetime import time


class SessionFeatureExtractor:
    """
    Extract session and regime features.
    
    Features:
    1. time_to_open: Minutes until market open
    2. time_to_close: Minutes until market close
    3. session_progress: Fraction of session elapsed (0-1)
    4. day_of_week: Day indicator (Monday=0, Friday=4)
    5. is_monday: Binary flag for Monday
    6. is_friday: Binary flag for Friday
    7. volatility_regime: High/low volatility indicator
    8. volume_regime: High/low volume indicator
    9. volatility_percentile: Current vol percentile (0-100)
    
    Example:
        extractor = SessionFeatureExtractor(
            market_open=time(9, 30),
            market_close=time(16, 0),
            vol_regime_window=200
        )
        
        features = extractor.extract_all(price_df=df)
    """
    
    def __init__(
        self,
        market_open: time = time(9, 30),
        market_close: time = time(16, 0),
        vol_regime_window: int = 200,
        vol_regime_threshold: float = 0.7,
        volume_regime_window: int = 200,
        volume_regime_threshold: float = 0.7
    ):
        """
        Initialize session feature extractor.
        
        Args:
            market_open: Market open time (default 9:30 AM)
            market_close: Market close time (default 4:00 PM)
            vol_regime_window: Window for volatility regime
            vol_regime_threshold: Percentile threshold for high vol regime
            volume_regime_window: Window for volume regime
            volume_regime_threshold: Percentile threshold for high volume regime
        """
        self.market_open = market_open
        self.market_close = market_close
        self.vol_regime_window = vol_regime_window
        self.vol_regime_threshold = vol_regime_threshold
        self.volume_regime_window = volume_regime_window
        self.volume_regime_threshold = volume_regime_threshold
    
    def extract_all(
        self,
        price_df: pd.DataFrame,
        volume_series: Optional[pd.Series] = None,
        target_index: Optional[pd.Index] = None
    ) -> pd.DataFrame:
        """
        Extract all session and regime features.
        
        Args:
            price_df: Price data with DatetimeIndex
            volume_series: Volume data (optional, for volume regime)
            target_index: Target index to align features to
        
        Returns:
            DataFrame with session and regime features
        """
        if target_index is None:
            target_index = price_df.index
        
        features = pd.DataFrame(index=target_index)
        
        # Time-to-event features
        features['time_to_open'] = self._calculate_time_to_open(target_index)
        features['time_to_close'] = self._calculate_time_to_close(target_index)
        features['session_progress'] = self._calculate_session_progress(target_index)
        
        # Day-of-week features (only if we have a DatetimeIndex)
        if isinstance(target_index, pd.DatetimeIndex):
            features['day_of_week'] = target_index.dayofweek
            features['is_monday'] = (target_index.dayofweek == 0).astype(int)
            features['is_friday'] = (target_index.dayofweek == 4).astype(int)
        else:
            # For non-datetime indices, use default values
            features['day_of_week'] = 2  # Default to Wednesday
            features['is_monday'] = 0
            features['is_friday'] = 0
        
        # Volatility regime
        if 'close' in price_df.columns or len(price_df.columns) > 0:
            price_col = 'close' if 'close' in price_df.columns else price_df.columns[0]
            returns = price_df[price_col].pct_change()
            
            vol_features = self._calculate_volatility_regime(returns)
            features['volatility_regime'] = vol_features['regime']
            features['volatility_percentile'] = vol_features['percentile']
        
        # Volume regime (if available)
        if volume_series is not None:
            volume_features = self._calculate_volume_regime(volume_series)
            features['volume_regime'] = volume_features['regime'].reindex(
                target_index, method='ffill'
            )
            features['volume_percentile'] = volume_features['percentile'].reindex(
                target_index, method='ffill'
            )
        
        return features
    
    def _calculate_time_to_open(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate minutes until market open.
        
        Negative = market is open (minutes since open)
        Positive = market is closed (minutes until open)
        
        Captures pre-market positioning and opening volatility.
        """
        time_to_open = []
        
        for timestamp in index:
            # Handle both DatetimeIndex and integer index
            if isinstance(timestamp, (int, np.integer)):
                # Integer index - use default midnight time
                current_time = pd.Timestamp('00:00:00').time()
            else:
                current_time = timestamp.time()
            
            # Convert times to minutes since midnight
            current_minutes = current_time.hour * 60 + current_time.minute
            open_minutes = self.market_open.hour * 60 + self.market_open.minute
            close_minutes = self.market_close.hour * 60 + self.market_close.minute
            
            if current_minutes < open_minutes:
                # Before open: positive minutes until open
                minutes_to_open = open_minutes - current_minutes
            elif current_minutes < close_minutes:
                # During session: negative minutes (since open)
                minutes_to_open = -(current_minutes - open_minutes)
            else:
                # After close: minutes until next day's open
                minutes_to_open = (24 * 60 - current_minutes) + open_minutes
            
            time_to_open.append(minutes_to_open)
        
        return pd.Series(time_to_open, index=index)
    
    def _calculate_time_to_close(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate minutes until market close.
        
        Positive = market is open (minutes until close)
        Negative = market is closed (minutes since close)
        
        Captures end-of-day positioning and closing volatility.
        """
        time_to_close = []
        
        for timestamp in index:
            # Handle both DatetimeIndex and integer index
            if isinstance(timestamp, (int, np.integer)):
                # Integer index - use default midnight time
                current_time = pd.Timestamp('00:00:00').time()
            else:
                current_time = timestamp.time()
            
            # Convert times to minutes since midnight
            current_minutes = current_time.hour * 60 + current_time.minute
            open_minutes = self.market_open.hour * 60 + self.market_open.minute
            close_minutes = self.market_close.hour * 60 + self.market_close.minute
            
            if current_minutes < open_minutes:
                # Before open: minutes since previous close
                minutes_to_close = -(current_minutes + (24 * 60 - close_minutes))
            elif current_minutes < close_minutes:
                # During session: positive minutes until close
                minutes_to_close = close_minutes - current_minutes
            else:
                # After close: negative minutes (since close)
                minutes_to_close = -(current_minutes - close_minutes)
            
            time_to_close.append(minutes_to_close)
        
        return pd.Series(time_to_close, index=index)
    
    def _calculate_session_progress(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate session progress (0-1).
        
        0 = market open
        1 = market close
        NaN = outside market hours
        
        Captures intraday patterns (volatility smile, volume U-shape).
        """
        session_progress = []
        
        session_length = (
            (self.market_close.hour - self.market_open.hour) * 60 +
            (self.market_close.minute - self.market_open.minute)
        )
        
        for timestamp in index:
            if isinstance(timestamp, (int, np.integer)):
                current_time = pd.Timestamp('00:00:00').time()
            else:
                current_time = timestamp.time()
            
            # Convert to minutes
            current_minutes = current_time.hour * 60 + current_time.minute
            open_minutes = self.market_open.hour * 60 + self.market_open.minute
            close_minutes = self.market_close.hour * 60 + self.market_close.minute
            
            if open_minutes <= current_minutes < close_minutes:
                # During session
                minutes_elapsed = current_minutes - open_minutes
                progress = minutes_elapsed / session_length
            else:
                # Outside session
                progress = np.nan
            
            session_progress.append(progress)
        
        return pd.Series(session_progress, index=index)
    
    def _calculate_volatility_regime(self, returns: pd.Series) -> pd.DataFrame:
        """
        Calculate volatility regime (high/low).
        
        Regime classification:
        - High volatility: vol > 70th percentile
        - Low volatility: vol < 30th percentile
        - Normal: else
        
        Features:
        - regime: 1 (high), 0 (normal), -1 (low)
        - percentile: Current volatility percentile (0-100)
        
        Reference: Hamilton (1989) regime switching models
        """
        # Rolling volatility (standard deviation of returns)
        rolling_vol = returns.rolling(
            window=20,
            min_periods=20
        ).std()
        
        # Regime percentile (relative to historical volatility)
        vol_percentile = rolling_vol.rolling(
            window=self.vol_regime_window,
            min_periods=self.vol_regime_window
        ).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
            raw=False
        )
        
        # Regime classification
        regime = pd.Series(0, index=returns.index)
        regime[vol_percentile > self.vol_regime_threshold * 100] = 1  # High vol
        regime[vol_percentile < (1 - self.vol_regime_threshold) * 100] = -1  # Low vol
        
        return pd.DataFrame({
            'regime': regime,
            'percentile': vol_percentile
        })
    
    def _calculate_volume_regime(self, volume: pd.Series) -> pd.DataFrame:
        """
        Calculate volume regime (high/low).
        
        Regime classification:
        - High volume: vol > 70th percentile
        - Low volume: vol < 30th percentile
        - Normal: else
        
        Features:
        - regime: 1 (high), 0 (normal), -1 (low)
        - percentile: Current volume percentile (0-100)
        """
        # Regime percentile (relative to historical volume)
        volume_percentile = volume.rolling(
            window=self.volume_regime_window,
            min_periods=self.volume_regime_window
        ).apply(
            lambda x: pd.Series(x).rank(pct=True).iloc[-1] * 100,
            raw=False
        )
        
        # Regime classification
        regime = pd.Series(0, index=volume.index)
        regime[volume_percentile > self.volume_regime_threshold * 100] = 1  # High volume
        regime[volume_percentile < (1 - self.volume_regime_threshold) * 100] = -1  # Low volume
        
        return pd.DataFrame({
            'regime': regime,
            'percentile': volume_percentile
        })
    
    def get_feature_names(self) -> list[str]:
        """Get list of feature names produced."""
        base_names = [
            'time_to_open',
            'time_to_close',
            'session_progress',
            'day_of_week',
            'is_monday',
            'is_friday',
            'volatility_regime',
            'volatility_percentile'
        ]
        
        # Optional features (need volume data)
        optional_names = [
            'volume_regime',
            'volume_percentile'
        ]
        
        return base_names + optional_names
