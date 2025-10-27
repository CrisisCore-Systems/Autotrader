"""
Flow dynamics and order flow toxicity features.

Implements features capturing flow momentum and toxicity:
- Imbalance momentum: Persistence of order flow imbalance
- Pressure decay: How quickly book pressure mean-reverts
- Aggressor streaks: Consecutive trades on same side
- Volume-synchronized bars: Volume-weighted time buckets
- Flow toxicity: VPIN proxy (volume-synchronized probability of informed trading)

These features capture:
- Flow persistence (trending vs mean-reverting)
- Information content of trades (toxic flow)
- Aggressive trading patterns (directional pressure)
- Trade clustering and herding

References:
- VPIN (flow toxicity): Easley et al. (2012)
- Order flow imbalance: Cont et al. (2014)
- Trade aggressiveness: Cartea et al. (2015)
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal


class FlowDynamicsExtractor:
    """
    Extract flow dynamics and toxicity features.
    
    Features:
    1. imbalance_momentum: Rolling correlation of imbalance changes
    2. imbalance_acceleration: Second derivative of imbalance
    3. pressure_decay_rate: Autocorrelation of book pressure
    4. aggressor_streak_buy: Consecutive buy-side aggressive trades
    5. aggressor_streak_sell: Consecutive sell-side aggressive trades
    6. aggressor_dominance: Net aggressor side over window
    7. vpin: Volume-Synchronized Probability of Informed Trading
    8. trade_intensity: Trade arrival rate
    9. volume_clustering: Variance of volume in equal-time buckets
    
    Example:
        extractor = FlowDynamicsExtractor(
            momentum_window=50,
            vpin_buckets=50
        )
        
        features = extractor.extract_all(
            orderbook_df=orderbook,
            trade_df=trades  # Required for most features
        )
    """
    
    def __init__(
        self,
        momentum_window: int = 50,
        decay_window: int = 100,
        vpin_buckets: int = 50,
        intensity_window: int = 20
    ):
        """
        Initialize flow dynamics extractor.
        
        Args:
            momentum_window: Window for imbalance momentum
            decay_window: Window for pressure decay estimation
            vpin_buckets: Number of volume buckets for VPIN
            intensity_window: Window for trade intensity
        """
        self.momentum_window = momentum_window
        self.decay_window = decay_window
        self.vpin_buckets = vpin_buckets
        self.intensity_window = intensity_window
    
    def extract_all(
        self,
        orderbook_df: pd.DataFrame,
        trade_df: Optional[pd.DataFrame] = None,
        target_index: Optional[pd.Index] = None
    ) -> pd.DataFrame:
        """
        Extract all flow dynamics features.
        
        Args:
            orderbook_df: Orderbook snapshots with bid/ask prices and sizes
            trade_df: Trade data (required for most features)
            target_index: Target index to align features to
        
        Returns:
            DataFrame with flow dynamics features
        """
        if target_index is None:
            target_index = orderbook_df.index
        
        features = pd.DataFrame(index=target_index)
        
        # Calculate depth imbalance for momentum features
        if 'bid_size_1' in orderbook_df.columns and 'ask_size_1' in orderbook_df.columns:
            bid_size = orderbook_df['bid_size_1']
            ask_size = orderbook_df['ask_size_1']
            total_size = bid_size + ask_size
            total_size = total_size.replace(0, np.nan)
            depth_imbalance = (bid_size - ask_size) / total_size
        else:
            depth_imbalance = pd.Series(np.nan, index=orderbook_df.index)
        
        # Imbalance momentum (autocorrelation of changes)
        features['imbalance_momentum'] = self._calculate_imbalance_momentum(
            depth_imbalance
        )
        
        # Imbalance acceleration (second derivative)
        features['imbalance_acceleration'] = self._calculate_imbalance_acceleration(
            depth_imbalance
        )
        
        # Pressure decay rate
        features['pressure_decay_rate'] = self._calculate_pressure_decay(
            depth_imbalance
        )
        
        # Trade-based features (if trade data available)
        if trade_df is not None:
            # Aggressor streaks
            streak_features = self._calculate_aggressor_streaks(trade_df)
            features['aggressor_streak_buy'] = streak_features['buy_streak'].reindex(
                target_index, method='ffill'
            )
            features['aggressor_streak_sell'] = streak_features['sell_streak'].reindex(
                target_index, method='ffill'
            )
            features['aggressor_dominance'] = streak_features['dominance'].reindex(
                target_index, method='ffill'
            )
            
            # VPIN (flow toxicity)
            vpin = self._calculate_vpin(trade_df)
            features['vpin'] = vpin.reindex(target_index, method='ffill')
            
            # Trade intensity (arrival rate)
            intensity = self._calculate_trade_intensity(trade_df)
            features['trade_intensity'] = intensity.reindex(target_index, method='ffill')
            
            # Volume clustering
            clustering = self._calculate_volume_clustering(trade_df)
            features['volume_clustering'] = clustering.reindex(target_index, method='ffill')
        
        return features
    
    def _calculate_imbalance_momentum(self, depth_imbalance: pd.Series) -> pd.Series:
        """
        Calculate imbalance momentum (autocorrelation of changes).
        
        Momentum = corr(dImb_t, dImb_{t-1}) over window
        
        Positive momentum = trending (persistent flow)
        Negative momentum = mean-reverting (oscillating flow)
        
        Used to detect regime (directional vs market making).
        """
        # Changes in imbalance
        imbalance_changes = depth_imbalance.diff()
        
        # Rolling autocorrelation
        def calculate_autocorr(changes_window):
            if len(changes_window) < 2:
                return np.nan
            
            # Lag-1 autocorrelation
            changes_t = changes_window[1:].values
            changes_t_minus_1 = changes_window[:-1].values
            
            if len(changes_t) == 0 or np.std(changes_t) == 0:
                return 0
            
            autocorr = np.corrcoef(changes_t, changes_t_minus_1)[0, 1]
            
            return autocorr if not np.isnan(autocorr) else 0
        
        momentum = imbalance_changes.rolling(
            window=self.momentum_window,
            min_periods=self.momentum_window
        ).apply(calculate_autocorr, raw=False)
        
        return momentum
    
    def _calculate_imbalance_acceleration(self, depth_imbalance: pd.Series) -> pd.Series:
        """
        Calculate imbalance acceleration (second derivative).
        
        Acceleration = d²Imb/dt² = d(dImb/dt)/dt
        
        Positive acceleration = increasing buy pressure
        Negative acceleration = increasing sell pressure
        
        Captures turning points in flow direction.
        """
        # First derivative (velocity)
        imbalance_velocity = depth_imbalance.diff()
        
        # Second derivative (acceleration)
        imbalance_acceleration = imbalance_velocity.diff()
        
        # Smooth with rolling mean
        acceleration_smoothed = imbalance_acceleration.rolling(
            window=10,
            min_periods=1
        ).mean()
        
        return acceleration_smoothed
    
    def _calculate_pressure_decay(self, depth_imbalance: pd.Series) -> pd.Series:
        """
        Calculate pressure decay rate.
        
        Decay = exp(-lambda * t) where lambda is decay constant
        Estimated as: -log(autocorr) / lag
        
        High decay = fast mean reversion (market making regime)
        Low decay = slow mean reversion (directional regime)
        """
        # Rolling autocorrelation at lag=1
        def calculate_decay(imb_window):
            if len(imb_window) < 2:
                return np.nan
            
            # Lag-1 autocorrelation
            imb_t = imb_window[1:].values
            imb_t_minus_1 = imb_window[:-1].values
            
            if len(imb_t) == 0 or np.std(imb_t) == 0:
                return 0
            
            autocorr = np.corrcoef(imb_t, imb_t_minus_1)[0, 1]
            
            if autocorr <= 0 or np.isnan(autocorr):
                return 1.0  # Maximum decay
            
            # Decay rate: -log(autocorr)
            decay_rate = -np.log(autocorr)
            
            return decay_rate
        
        decay = depth_imbalance.rolling(
            window=self.decay_window,
            min_periods=self.decay_window
        ).apply(calculate_decay, raw=False)
        
        return decay
    
    def _calculate_aggressor_streaks(
        self,
        trade_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate aggressor side streaks.
        
        Streak = consecutive trades on same side (buy or sell)
        
        Long streaks = directional pressure (informed trading)
        Short streaks = two-sided flow (market making)
        
        Features:
        - buy_streak: Current buy-side streak length
        - sell_streak: Current sell-side streak length
        - dominance: Net aggressor side over window
        """
        if 'side' not in trade_df.columns:
            return pd.DataFrame({
                'buy_streak': np.nan,
                'sell_streak': np.nan,
                'dominance': np.nan
            }, index=trade_df.index)
        
        # Convert side to numeric (-1: sell, +1: buy)
        trade_df = trade_df.copy()
        trade_df['side_numeric'] = trade_df['side'].apply(
            lambda x: 1 if x == 'buy' else -1 if x == 'sell' else 0
        )
        
        # Calculate streaks
        buy_streak = []
        sell_streak = []
        current_buy_streak = 0
        current_sell_streak = 0
        
        for side in trade_df['side_numeric']:
            if side == 1:
                current_buy_streak += 1
                current_sell_streak = 0
            elif side == -1:
                current_sell_streak += 1
                current_buy_streak = 0
            else:
                current_buy_streak = 0
                current_sell_streak = 0
            
            buy_streak.append(current_buy_streak)
            sell_streak.append(current_sell_streak)
        
        # Aggressor dominance (rolling net side)
        dominance = trade_df['side_numeric'].rolling(
            window=self.momentum_window,
            min_periods=1
        ).mean()
        
        return pd.DataFrame({
            'buy_streak': buy_streak,
            'sell_streak': sell_streak,
            'dominance': dominance
        }, index=trade_df.index)
    
    def _calculate_vpin(self, trade_df: pd.DataFrame) -> pd.Series:
        """
        Calculate VPIN (Volume-Synchronized Probability of Informed Trading).
        
        VPIN = sum(|buy_volume - sell_volume|) / total_volume
        
        Calculated over volume buckets (not time buckets).
        Each bucket contains equal volume.
        
        High VPIN = toxic flow (informed trading)
        Low VPIN = benign flow (liquidity provision)
        
        Reference: Easley et al. (2012)
        "Flow Toxicity and Liquidity in a High Frequency World"
        """
        if 'side' not in trade_df.columns or 'size' not in trade_df.columns:
            return pd.Series(np.nan, index=trade_df.index)
        
        trade_df = trade_df.copy()
        
        # Signed volume
        trade_df['signed_volume'] = trade_df.apply(
            lambda row: row['size'] if row['side'] == 'buy' else -row['size'] if row['side'] == 'sell' else 0,
            axis=1
        )
        
        # Calculate total volume to determine bucket size
        total_volume = trade_df['size'].sum()
        bucket_volume = total_volume / self.vpin_buckets
        
        if bucket_volume == 0:
            return pd.Series(np.nan, index=trade_df.index)
        
        # Assign trades to volume buckets
        trade_df['cumulative_volume'] = trade_df['size'].cumsum()
        trade_df['bucket'] = (trade_df['cumulative_volume'] / bucket_volume).astype(int)
        
        # Calculate VPIN per bucket
        vpin_by_bucket = {}
        for bucket_id in range(self.vpin_buckets):
            bucket_trades = trade_df[trade_df['bucket'] == bucket_id]
            
            if len(bucket_trades) == 0:
                continue
            
            buy_volume = bucket_trades[bucket_trades['signed_volume'] > 0]['size'].sum()
            sell_volume = bucket_trades[bucket_trades['signed_volume'] < 0]['size'].sum()
            total_bucket_volume = bucket_trades['size'].sum()
            
            if total_bucket_volume > 0:
                vpin = abs(buy_volume - sell_volume) / total_bucket_volume
                
                # Assign VPIN to all trades in bucket
                for idx in bucket_trades.index:
                    vpin_by_bucket[idx] = vpin
        
        # Create VPIN series
        vpin_series = pd.Series(vpin_by_bucket, name='vpin')
        
        # Forward fill for missing values
        vpin_series = vpin_series.reindex(trade_df.index, method='ffill')
        
        return vpin_series
    
    def _calculate_trade_intensity(self, trade_df: pd.DataFrame) -> pd.Series:
        """
        Calculate trade intensity (arrival rate).
        
        Intensity = # trades / time window
        
        High intensity = high activity (news, volatility)
        Low intensity = low activity (quiet period)
        
        Used to detect regime changes and event detection.
        """
        # Count trades in rolling time window
        # Use resampling to count trades per time unit
        
        # Resample to seconds and count
        trade_counts = trade_df.resample('1s').size()
        
        # Rolling sum over window (in seconds)
        intensity = trade_counts.rolling(
            window=self.intensity_window,
            min_periods=1
        ).sum()
        
        # Align to trade index
        intensity_aligned = intensity.reindex(
            trade_df.index,
            method='ffill'
        )
        
        return intensity_aligned
    
    def _calculate_volume_clustering(self, trade_df: pd.DataFrame) -> pd.Series:
        """
        Calculate volume clustering.
        
        Clustering = variance(volume) / mean(volume)²  (coefficient of variation squared)
        
        High clustering = bursty trading (large trades clustered)
        Low clustering = smooth trading (evenly distributed)
        
        Indicates information-driven trading vs liquidity-driven.
        """
        if 'size' not in trade_df.columns:
            return pd.Series(np.nan, index=trade_df.index)
        
        # Rolling statistics of volume
        volume_mean = trade_df['size'].rolling(
            window=self.momentum_window,
            min_periods=self.momentum_window
        ).mean()
        
        volume_std = trade_df['size'].rolling(
            window=self.momentum_window,
            min_periods=self.momentum_window
        ).std()
        
        # Coefficient of variation squared (avoid division by zero)
        volume_mean_safe = volume_mean.replace(0, np.nan)
        clustering = (volume_std / volume_mean_safe) ** 2
        
        return clustering
    
    def get_feature_names(self) -> list[str]:
        """Get list of feature names produced."""
        base_names = [
            'imbalance_momentum',
            'imbalance_acceleration',
            'pressure_decay_rate'
        ]
        
        # Trade-dependent features
        trade_names = [
            'aggressor_streak_buy',
            'aggressor_streak_sell',
            'aggressor_dominance',
            'vpin',
            'trade_intensity',
            'volume_clustering'
        ]
        
        return base_names + trade_names
