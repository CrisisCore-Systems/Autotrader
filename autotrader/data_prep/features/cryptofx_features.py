"""
Crypto and FX-specific features for 24/7 and global markets.

Implements market-specific features:
- Funding rate proximity (crypto): 8-hour funding cycles
- Rollover proximity (FX): 5 PM ET daily rollover
- Weekend effects: Saturday/Sunday behavior
- Overnight flags: Trading outside regular hours
- Holiday effects: Reduced liquidity periods
- Market hour indicators: Asian/European/US sessions

These features capture:
- Funding rate arbitrage opportunities (crypto)
- Rollover costs and positioning (FX)
- Weekend liquidity drain (crypto)
- Cross-timezone momentum (FX)
- Holiday thin markets

References:
- Funding rates: Perpetual futures mechanics
- FX rollover: Tom-next swaps and carry trades
- Weekend effects: Cryptocurrencies trade 24/7 with liquidity patterns
"""

import pandas as pd
import numpy as np
from typing import Optional, Literal
from datetime import time, datetime


class CryptoFXFeatureExtractor:
    """
    Extract crypto and FX-specific features.
    
    Features:
    1. minutes_to_funding: Minutes until next funding (crypto)
    2. funding_cycle: Which funding cycle (0, 1, 2 for 8h cycles)
    3. minutes_to_rollover: Minutes until FX rollover (5 PM ET)
    4. is_weekend: Saturday or Sunday flag
    5. is_overnight: Outside regular trading hours
    6. trading_session: Asian (0), European (1), US (2), Overlap (3)
    7. is_holiday: Major holiday flag
    8. weekend_proximity: Hours from/to weekend
    
    Example:
        # For crypto (24/7 with funding)
        extractor = CryptoFXFeatureExtractor(
            market_type='crypto',
            funding_interval_hours=8
        )
        
        # For FX (24/5 with rollover)
        extractor = CryptoFXFeatureExtractor(
            market_type='fx',
            fx_rollover_time=time(17, 0)  # 5 PM ET
        )
        
        features = extractor.extract_all(df)
    """
    
    def __init__(
        self,
        market_type: Literal['crypto', 'fx'] = 'crypto',
        funding_interval_hours: int = 8,
        fx_rollover_time: time = time(17, 0),  # 5 PM ET
        holidays: Optional[list[datetime]] = None
    ):
        """
        Initialize crypto/FX feature extractor.
        
        Args:
            market_type: 'crypto' or 'fx'
            funding_interval_hours: Funding rate interval (crypto, typically 8h)
            fx_rollover_time: FX rollover time (typically 5 PM ET)
            holidays: List of holiday dates
        """
        self.market_type = market_type
        self.funding_interval_hours = funding_interval_hours
        self.fx_rollover_time = fx_rollover_time
        self.holidays = holidays or []
        
        # Funding times (crypto): typically 00:00, 08:00, 16:00 UTC
        self.funding_times = [
            time(i, 0) for i in range(0, 24, funding_interval_hours)
        ]
    
    def extract_all(
        self,
        df: pd.DataFrame,
        target_index: Optional[pd.Index] = None
    ) -> pd.DataFrame:
        """
        Extract all crypto/FX features.
        
        Args:
            df: Price data with DatetimeIndex
            target_index: Target index to align features to
        
        Returns:
            DataFrame with crypto/FX features
        """
        if target_index is None:
            target_index = df.index
        
        features = pd.DataFrame(index=target_index)
        
        if self.market_type == 'crypto':
            # Crypto-specific features
            features['minutes_to_funding'] = self._calculate_minutes_to_funding(target_index)
            features['funding_cycle'] = self._calculate_funding_cycle(target_index)
            features['is_weekend'] = self._calculate_is_weekend(target_index)
            features['weekend_proximity'] = self._calculate_weekend_proximity(target_index)
        
        elif self.market_type == 'fx':
            # FX-specific features
            features['minutes_to_rollover'] = self._calculate_minutes_to_rollover(target_index)
            features['is_overnight'] = self._calculate_is_overnight(target_index)
            features['trading_session'] = self._calculate_trading_session(target_index)
            features['is_weekend'] = self._calculate_is_weekend(target_index)
            features['weekend_proximity'] = self._calculate_weekend_proximity(target_index)
        
        # Common features
        features['is_holiday'] = self._calculate_is_holiday(target_index)
        
        return features
    
    def _calculate_minutes_to_funding(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate minutes until next funding rate event (crypto).
        
        Funding rates are paid/received at fixed intervals (typically 8h):
        - 00:00 UTC
        - 08:00 UTC
        - 16:00 UTC
        
        Features:
        - Positive: minutes until next funding
        - Range: [0, 480) for 8h intervals
        
        Useful for:
        - Funding rate arbitrage
        - Position timing (enter after funding, exit before)
        - Volatility spikes near funding times
        """
        minutes_to_funding = []
        
        for timestamp in index:
            current_time = timestamp.time()
            current_minutes = current_time.hour * 60 + current_time.minute
            
            # Find next funding time
            min_distance = float('inf')
            for funding_time in self.funding_times:
                funding_minutes = funding_time.hour * 60 + funding_time.minute
                
                if funding_minutes > current_minutes:
                    # Same day
                    distance = funding_minutes - current_minutes
                else:
                    # Next day
                    distance = (24 * 60 - current_minutes) + funding_minutes
                
                min_distance = min(min_distance, distance)
            
            minutes_to_funding.append(min_distance)
        
        return pd.Series(minutes_to_funding, index=index)
    
    def _calculate_funding_cycle(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate which funding cycle (0, 1, 2 for 8h intervals).
        
        Cycles:
        - 0: 00:00-08:00 UTC
        - 1: 08:00-16:00 UTC
        - 2: 16:00-24:00 UTC
        
        Different cycles may have different characteristics
        (e.g., Asian vs US vs European active hours).
        """
        cycles = []
        
        for timestamp in index:
            hour = timestamp.hour
            cycle = hour // self.funding_interval_hours
            cycles.append(cycle)
        
        return pd.Series(cycles, index=index)
    
    def _calculate_minutes_to_rollover(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate minutes until FX rollover (typically 5 PM ET).
        
        FX rollover:
        - Interest paid/charged on overnight positions
        - Occurs at 5 PM ET daily
        - Major volatility event
        
        Features:
        - Positive: minutes until rollover
        - Negative: minutes since rollover
        - Range: (-720, 720] for ±12 hours
        
        Useful for:
        - Carry trade positioning
        - Volatility timing
        - Avoiding rollover costs
        """
        minutes_to_rollover = []
        
        rollover_minutes = self.fx_rollover_time.hour * 60 + self.fx_rollover_time.minute
        
        for timestamp in index:
            current_time = timestamp.time()
            current_minutes = current_time.hour * 60 + current_time.minute
            
            if current_minutes < rollover_minutes:
                # Before rollover today
                minutes = rollover_minutes - current_minutes
            else:
                # After rollover today (next is tomorrow)
                minutes = -(current_minutes - rollover_minutes)
            
            minutes_to_rollover.append(minutes)
        
        return pd.Series(minutes_to_rollover, index=index)
    
    def _calculate_is_overnight(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate if outside regular trading hours (FX).
        
        Regular FX hours: roughly 17:00 ET Sunday - 17:00 ET Friday
        Overnight: Friday 17:00 - Sunday 17:00
        
        Overnight periods have:
        - Lower liquidity
        - Wider spreads
        - Higher gap risk
        """
        is_overnight = []
        
        for timestamp in index:
            day_of_week = timestamp.dayofweek
            current_time = timestamp.time()
            current_minutes = current_time.hour * 60 + current_time.minute
            rollover_minutes = self.fx_rollover_time.hour * 60 + self.fx_rollover_time.minute
            
            # Friday after 5 PM
            friday_closed = (day_of_week == 4 and current_minutes >= rollover_minutes)
            
            # Saturday (all day)
            saturday = (day_of_week == 5)
            
            # Sunday before 5 PM
            sunday_closed = (day_of_week == 6 and current_minutes < rollover_minutes)
            
            overnight = friday_closed or saturday or sunday_closed
            is_overnight.append(int(overnight))
        
        return pd.Series(is_overnight, index=index)
    
    def _calculate_trading_session(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate which FX trading session (Asian/European/US/Overlap).
        
        Sessions (UTC):
        - Asian: 00:00-08:00 (Tokyo)
        - European: 08:00-16:00 (London)
        - US: 13:00-21:00 (New York)
        - Overlap: 13:00-16:00 (London + NY)
        
        Sessions:
        - 0: Asian
        - 1: European
        - 2: US
        - 3: European/US overlap (highest liquidity)
        
        Useful for:
        - Session-specific strategies
        - Liquidity estimation
        - Volatility forecasting
        """
        sessions = []
        
        for timestamp in index:
            hour_utc = timestamp.hour
            
            # Overlap: 13:00-16:00 UTC (London + NY)
            if 13 <= hour_utc < 16:
                session = 3
            # European: 08:00-16:00 UTC
            elif 8 <= hour_utc < 16:
                session = 1
            # US: 13:00-21:00 UTC
            elif 13 <= hour_utc < 21:
                session = 2
            # Asian: else
            else:
                session = 0
            
            sessions.append(session)
        
        return pd.Series(sessions, index=index)
    
    def _calculate_is_weekend(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate weekend flag.
        
        Weekend:
        - Crypto: Saturday + Sunday (lower liquidity)
        - FX: Friday 5 PM - Sunday 5 PM (market closed)
        
        Weekend effects:
        - Lower volume
        - Wider spreads
        - Different participant mix (retail vs institutional)
        """
        is_weekend = (index.dayofweek >= 5).astype(int)
        
        return pd.Series(is_weekend, index=index)
    
    def _calculate_weekend_proximity(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate hours from/to weekend.
        
        Positive: hours until weekend
        Negative: hours into weekend
        
        Captures pre-weekend positioning and post-weekend recovery.
        """
        weekend_proximity = []
        
        for timestamp in index:
            day_of_week = timestamp.dayofweek
            hour = timestamp.hour
            
            if day_of_week < 5:
                # Weekday: hours until Saturday
                hours_until_weekend = (5 - day_of_week) * 24 - hour
                weekend_proximity.append(hours_until_weekend)
            else:
                # Weekend: hours into weekend (negative)
                hours_into_weekend = (day_of_week - 5) * 24 + hour
                weekend_proximity.append(-hours_into_weekend)
        
        return pd.Series(weekend_proximity, index=index)
    
    def _calculate_is_holiday(self, index: pd.DatetimeIndex) -> pd.Series:
        """
        Calculate holiday flag.
        
        Holidays have:
        - Lower liquidity
        - Wider spreads
        - Reduced institutional participation
        
        User provides list of holiday dates.
        """
        is_holiday = index.normalize().isin([h.date() if isinstance(h, datetime) else h for h in self.holidays]).astype(int)
        
        return pd.Series(is_holiday, index=index)
    
    def get_feature_names(self) -> list[str]:
        """Get list of feature names produced."""
        if self.market_type == 'crypto':
            return [
                'minutes_to_funding',
                'funding_cycle',
                'is_weekend',
                'weekend_proximity',
                'is_holiday'
            ]
        elif self.market_type == 'fx':
            return [
                'minutes_to_rollover',
                'is_overnight',
                'trading_session',
                'is_weekend',
                'weekend_proximity',
                'is_holiday'
            ]
        else:
            return ['is_holiday']
