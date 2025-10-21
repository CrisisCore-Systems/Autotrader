"""
Intelligent adjustment logic for exit strategies.

Adapts exit criteria based on:
- Market volatility (VIX levels)
- Time of day (market open/close volatility)
- Market regime (bull/bear/sideways)
- Per-symbol patterns (learned from history)

This module provides the intelligence layer that sits above base exit strategies,
dynamically tuning targets and thresholds for optimal performance.
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, time
from zoneinfo import ZoneInfo
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Eastern Time for market hours
EASTERN = ZoneInfo("America/New_York")


class MarketRegime(Enum):
    """Market regime classification."""
    BULL = "BULL"        # Strong uptrend
    BEAR = "BEAR"        # Strong downtrend
    SIDEWAYS = "SIDEWAYS"  # Range-bound
    UNKNOWN = "UNKNOWN"  # Insufficient data


class VolatilityLevel(Enum):
    """Volatility classification."""
    LOW = "LOW"      # VIX < 15
    NORMAL = "NORMAL"  # VIX 15-20
    HIGH = "HIGH"    # VIX 20-30
    EXTREME = "EXTREME"  # VIX > 30


class TimeOfDayPeriod(Enum):
    """Trading day periods with different characteristics."""
    OPEN = "OPEN"      # 09:30-10:00 - High volatility
    MORNING = "MORNING"    # 10:00-11:30 - Active trading
    MIDDAY = "MIDDAY"     # 11:30-14:00 - Lunch lull
    AFTERNOON = "AFTERNOON"  # 14:00-15:30 - Moderate activity
    CLOSE = "CLOSE"      # 15:30-16:00 - High volatility


class MarketConditions:
    """
    Analyzes current market conditions for intelligent adjustments.
    
    Provides context about volatility, regime, and time of day to inform
    exit strategy adjustments.
    """
    
    def __init__(self, vix_provider: Optional[Any] = None, regime_detector: Optional[Any] = None):
        """
        Initialize market conditions analyzer.
        
        Args:
            vix_provider: Optional provider for VIX data
            regime_detector: Optional detector for market regime
        """
        self.vix_provider = vix_provider
        self.regime_detector = regime_detector
        self._cached_vix: Optional[float] = None
        self._cached_regime: MarketRegime = MarketRegime.UNKNOWN
    
    def get_volatility_level(self, current_vix: Optional[float] = None) -> VolatilityLevel:
        """
        Classify current volatility level.
        
        Args:
            current_vix: Current VIX value, or None to fetch
            
        Returns:
            VolatilityLevel classification
        """
        if current_vix is None:
            if self.vix_provider:
                try:
                    current_vix = self.vix_provider.get_vix()
                    self._cached_vix = current_vix
                except Exception as e:
                    logger.warning(f"Failed to fetch VIX: {e}, using cached value")
                    current_vix = self._cached_vix or 20.0  # Default to NORMAL
            else:
                current_vix = self._cached_vix or 20.0
        
        if current_vix < 15:
            return VolatilityLevel.LOW
        elif current_vix < 20:
            return VolatilityLevel.NORMAL
        elif current_vix < 30:
            return VolatilityLevel.HIGH
        else:
            return VolatilityLevel.EXTREME
    
    def get_time_period(self, current_time: Optional[datetime] = None) -> TimeOfDayPeriod:
        """
        Determine current time period in trading day.
        
        Args:
            current_time: Current time (defaults to now in ET)
            
        Returns:
            TimeOfDayPeriod classification
        """
        if current_time is None:
            current_time = datetime.now(EASTERN)
        
        # Ensure timezone-aware
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=EASTERN)
        
        # Convert to ET if needed
        if current_time.tzinfo != EASTERN:
            current_time = current_time.astimezone(EASTERN)
        
        time_only = current_time.time()
        
        if time(9, 30) <= time_only < time(10, 0):
            return TimeOfDayPeriod.OPEN
        elif time(10, 0) <= time_only < time(11, 30):
            return TimeOfDayPeriod.MORNING
        elif time(11, 30) <= time_only < time(14, 0):
            return TimeOfDayPeriod.MIDDAY
        elif time(14, 0) <= time_only < time(15, 30):
            return TimeOfDayPeriod.AFTERNOON
        elif time(15, 30) <= time_only < time(16, 0):
            return TimeOfDayPeriod.CLOSE
        else:
            # Outside market hours - treat as MIDDAY (most conservative)
            return TimeOfDayPeriod.MIDDAY
    
    def set_market_regime(self, regime: MarketRegime) -> None:
        """
        Set current market regime (typically updated daily).
        
        Args:
            regime: Market regime classification
        """
        self._cached_regime = regime
        logger.info(f"Market regime updated: {regime.value}")
    
    def get_market_regime(self) -> MarketRegime:
        """
        Get current market regime.
        
        Returns:
            MarketRegime classification (BULL, BEAR, SIDEWAYS, or UNKNOWN)
        """
        # Use regime detector if available
        if self.regime_detector:
            try:
                regime = self.regime_detector.detect_regime()
                self._cached_regime = regime
                return regime
            except Exception as e:
                logger.warning(f"Failed to detect regime: {e}, using cached value")
                return self._cached_regime
        
        # Return cached regime if no detector
        return self._cached_regime


class AdjustmentCalculator:
    """
    Calculates adjustments to exit strategy parameters.
    
    Uses market conditions to dynamically tune profit targets, position sizes,
    and other exit criteria for optimal performance.
    """
    
    def __init__(
        self,
        market_conditions: MarketConditions,
        enable_volatility_adjustments: bool = True,
        enable_time_adjustments: bool = True,
        enable_regime_adjustments: bool = True
    ):
        """
        Initialize adjustment calculator.
        
        Args:
            market_conditions: Market conditions analyzer
            enable_volatility_adjustments: Enable VIX-based adjustments
            enable_time_adjustments: Enable time-of-day adjustments
            enable_regime_adjustments: Enable regime-based adjustments
        """
        self.market_conditions = market_conditions
        self.enable_volatility = enable_volatility_adjustments
        self.enable_time = enable_time_adjustments
        self.enable_regime = enable_regime_adjustments
    
    def adjust_tier1_target(
        self,
        base_target: float,
        current_time: Optional[datetime] = None,
        current_vix: Optional[float] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Adjust Tier-1 profit target based on conditions.
        
        Args:
            base_target: Base profit target percentage (e.g., 5.0)
            current_time: Current time for time-of-day adjustments
            current_vix: Current VIX for volatility adjustments
            
        Returns:
            Tuple of (adjusted_target, adjustment_details)
        """
        adjusted_target = base_target
        adjustments = {
            'base_target': base_target,
            'volatility_adjustment': 0.0,
            'time_adjustment': 0.0,
            'regime_adjustment': 0.0,
            'final_target': base_target
        }
        
        # Volatility adjustments
        if self.enable_volatility:
            vol_level = self.market_conditions.get_volatility_level(current_vix)
            
            if vol_level == VolatilityLevel.LOW:
                # Low volatility - increase target to wait for better moves
                vol_adj = 1.0  # +1%
            elif vol_level == VolatilityLevel.NORMAL:
                vol_adj = 0.0
            elif vol_level == VolatilityLevel.HIGH:
                # High volatility - decrease target to lock in gains faster
                vol_adj = -1.0  # -1%
            else:  # EXTREME
                # Extreme volatility - significantly decrease target
                vol_adj = -2.0  # -2%
            
            adjusted_target += vol_adj
            adjustments['volatility_adjustment'] = vol_adj
            adjustments['volatility_level'] = vol_level.value
        
        # Time-of-day adjustments
        if self.enable_time:
            time_period = self.market_conditions.get_time_period(current_time)
            
            if time_period in (TimeOfDayPeriod.OPEN, TimeOfDayPeriod.CLOSE):
                # High volatility periods - tighten target
                time_adj = -0.5  # -0.5%
            elif time_period == TimeOfDayPeriod.MIDDAY:
                # Midday lull - can afford to wait
                time_adj = 0.5  # +0.5%
            else:
                time_adj = 0.0
            
            adjusted_target += time_adj
            adjustments['time_adjustment'] = time_adj
            adjustments['time_period'] = time_period.value
        
        # Market regime adjustments
        if self.enable_regime:
            regime = self.market_conditions.get_market_regime()
            
            if regime == MarketRegime.BULL:
                # Bull market - can hold for higher targets
                regime_adj = 1.0  # +1%
            elif regime == MarketRegime.BEAR:
                # Bear market - take profits quickly
                regime_adj = -1.5  # -1.5%
            elif regime == MarketRegime.SIDEWAYS:
                # Sideways - standard target
                regime_adj = 0.0
            else:  # UNKNOWN
                regime_adj = 0.0
            
            adjusted_target += regime_adj
            adjustments['regime_adjustment'] = regime_adj
            adjustments['market_regime'] = regime.value
        
        # Floor at 2% minimum, cap at 10% maximum
        adjusted_target = max(2.0, min(10.0, adjusted_target))
        adjustments['final_target'] = adjusted_target
        
        return adjusted_target, adjustments
    
    def adjust_tier2_target(
        self,
        base_min: float,
        base_max: float,
        current_time: Optional[datetime] = None,
        current_vix: Optional[float] = None
    ) -> Tuple[Tuple[float, float], Dict[str, Any]]:
        """
        Adjust Tier-2 profit target range based on conditions.
        
        Args:
            base_min: Base minimum profit target (e.g., 8.0)
            base_max: Base maximum profit target (e.g., 10.0)
            current_time: Current time for time-of-day adjustments
            current_vix: Current VIX for volatility adjustments
            
        Returns:
            Tuple of ((adjusted_min, adjusted_max), adjustment_details)
        """
        adjusted_min = base_min
        adjusted_max = base_max
        adjustments = {
            'base_min': base_min,
            'base_max': base_max,
            'volatility_adjustment': 0.0,
            'time_adjustment': 0.0,
            'regime_adjustment': 0.0,
            'final_min': base_min,
            'final_max': base_max
        }
        
        # Volatility adjustments
        if self.enable_volatility:
            vol_level = self.market_conditions.get_volatility_level(current_vix)
            
            if vol_level == VolatilityLevel.LOW:
                # Low volatility - increase range to 9-12%
                vol_adj = 1.0
            elif vol_level == VolatilityLevel.NORMAL:
                vol_adj = 0.0
            elif vol_level == VolatilityLevel.HIGH:
                # High volatility - decrease range to 7-9%
                vol_adj = -1.0
            else:  # EXTREME
                # Extreme volatility - tight range 6-8%
                vol_adj = -2.0
            
            adjusted_min += vol_adj
            adjusted_max += vol_adj
            adjustments['volatility_adjustment'] = vol_adj
            adjustments['volatility_level'] = vol_level.value
        
        # Time-of-day adjustments
        if self.enable_time:
            time_period = self.market_conditions.get_time_period(current_time)
            
            if time_period in (TimeOfDayPeriod.OPEN, TimeOfDayPeriod.CLOSE):
                # High volatility - tighten range
                time_adj = -0.5
            elif time_period == TimeOfDayPeriod.MIDDAY:
                # Midday - can wait for better prices
                time_adj = 0.5
            else:
                time_adj = 0.0
            
            adjusted_min += time_adj
            adjusted_max += time_adj
            adjustments['time_adjustment'] = time_adj
            adjustments['time_period'] = time_period.value
        
        # Market regime adjustments
        if self.enable_regime:
            regime = self.market_conditions.get_market_regime()
            
            if regime == MarketRegime.BULL:
                # Bull market - hold for higher targets (10-13%)
                regime_adj = 2.0
            elif regime == MarketRegime.BEAR:
                # Bear market - exit faster (6-8%)
                regime_adj = -2.0
            elif regime == MarketRegime.SIDEWAYS:
                regime_adj = 0.0
            else:  # UNKNOWN
                regime_adj = 0.0
            
            adjusted_min += regime_adj
            adjusted_max += regime_adj
            adjustments['regime_adjustment'] = regime_adj
            adjustments['market_regime'] = regime.value
        
        # Ensure valid range: min >= 5%, max <= 15%, min < max
        adjusted_min = max(5.0, min(12.0, adjusted_min))
        adjusted_max = max(7.0, min(15.0, adjusted_max))
        
        # Ensure min < max (maintain at least 2% spread)
        if adjusted_max <= adjusted_min:
            adjusted_max = adjusted_min + 2.0
        
        adjustments['final_min'] = adjusted_min
        adjustments['final_max'] = adjusted_max
        
        return (adjusted_min, adjusted_max), adjustments
    
    def adjust_position_size(
        self,
        base_pct: float,
        current_vix: Optional[float] = None
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Adjust position size based on volatility.
        
        Higher volatility → smaller position sizes for risk management.
        
        Args:
            base_pct: Base position percentage (e.g., 50.0 for Tier-1)
            current_vix: Current VIX value
            
        Returns:
            Tuple of (adjusted_pct, adjustment_details)
        """
        adjusted_pct = base_pct
        adjustments = {
            'base_pct': base_pct,
            'volatility_adjustment': 0.0,
            'final_pct': base_pct
        }
        
        if self.enable_volatility:
            vol_level = self.market_conditions.get_volatility_level(current_vix)
            
            if vol_level == VolatilityLevel.LOW:
                # Low vol - can take larger positions
                vol_adj = 5.0  # +5%
            elif vol_level == VolatilityLevel.NORMAL:
                vol_adj = 0.0
            elif vol_level == VolatilityLevel.HIGH:
                # High vol - reduce position size
                vol_adj = -5.0  # -5%
            else:  # EXTREME
                # Extreme vol - significantly reduce
                vol_adj = -10.0  # -10%
            
            adjusted_pct += vol_adj
            adjustments['volatility_adjustment'] = vol_adj
            adjustments['volatility_level'] = vol_level.value
        
        # Floor at 20%, cap at 60%
        adjusted_pct = max(20.0, min(60.0, adjusted_pct))
        adjustments['final_pct'] = adjusted_pct
        
        return adjusted_pct, adjustments


class SymbolLearner:
    """
    Learns per-symbol patterns to optimize exit strategies.
    
    Tracks historical performance and identifies symbol-specific characteristics
    like tendency to run vs fade, average hold time, optimal exit points.
    """
    
    def __init__(self):
        """Initialize symbol learner."""
        self.symbol_stats: Dict[str, Dict[str, Any]] = {}
    
    def record_exit(
        self,
        ticker: str,
        entry_price: float,
        exit_price: float,
        hold_days: int,
        tier: str,
        profit_pct: float
    ) -> None:
        """
        Record an exit for learning.
        
        Args:
            ticker: Symbol ticker
            entry_price: Entry price
            exit_price: Exit price
            hold_days: Days held
            tier: Exit tier ('tier1' or 'tier2')
            profit_pct: Profit percentage achieved
        """
        if ticker not in self.symbol_stats:
            self.symbol_stats[ticker] = {
                'total_exits': 0,
                'tier1_exits': 0,
                'tier2_exits': 0,
                'avg_hold_days': 0.0,
                'avg_profit_pct': 0.0,
                'runner_score': 0.0,  # Tendency to continue higher
                'best_exit_tier': None
            }
        
        stats = self.symbol_stats[ticker]
        n = stats['total_exits']
        
        # Update running averages
        stats['avg_hold_days'] = (stats['avg_hold_days'] * n + hold_days) / (n + 1)
        stats['avg_profit_pct'] = (stats['avg_profit_pct'] * n + profit_pct) / (n + 1)
        stats['total_exits'] += 1
        
        if tier == 'tier1':
            stats['tier1_exits'] += 1
        elif tier == 'tier2':
            stats['tier2_exits'] += 1
        
        # Calculate runner score (higher tier2 exits = more likely to run)
        if stats['total_exits'] >= 5:  # Need minimum sample
            stats['runner_score'] = stats['tier2_exits'] / stats['total_exits']
            
            # Determine best exit tier
            if stats['runner_score'] > 0.6:
                stats['best_exit_tier'] = 'tier2'  # Usually runs
            elif stats['runner_score'] < 0.3:
                stats['best_exit_tier'] = 'tier1'  # Usually fades
            else:
                stats['best_exit_tier'] = 'mixed'
    
    def get_symbol_adjustment(self, ticker: str) -> Dict[str, Any]:
        """
        Get recommended adjustments for a symbol.
        
        Args:
            ticker: Symbol ticker
            
        Returns:
            Dictionary with adjustment recommendations
        """
        if ticker not in self.symbol_stats:
            return {
                'has_data': False,
                'tier1_adjustment': 0.0,
                'tier2_adjustment': 0.0,
                'recommendation': 'Use default strategy'
            }
        
        stats = self.symbol_stats[ticker]
        
        if stats['total_exits'] < 5:
            return {
                'has_data': True,
                'insufficient_sample': True,
                'tier1_adjustment': 0.0,
                'tier2_adjustment': 0.0,
                'recommendation': 'Collecting data, use default strategy'
            }
        
        adjustments = {
            'has_data': True,
            'insufficient_sample': False,
            'total_exits': stats['total_exits'],
            'runner_score': stats['runner_score'],
            'best_exit_tier': stats['best_exit_tier'],
            'tier1_adjustment': 0.0,
            'tier2_adjustment': 0.0
        }
        
        # Adjust based on runner tendency
        if stats['runner_score'] > 0.6:
            # Stock tends to run - increase Tier-1 target, favor Tier-2
            adjustments['tier1_adjustment'] = 1.0  # +1% to Tier-1 target
            adjustments['tier2_adjustment'] = 1.0  # +1% to Tier-2 range
            adjustments['recommendation'] = 'Runner detected - hold for higher targets'
        elif stats['runner_score'] < 0.3:
            # Stock tends to fade - decrease targets, favor Tier-1
            adjustments['tier1_adjustment'] = -0.5  # -0.5% to Tier-1 target
            adjustments['tier2_adjustment'] = -1.0  # -1% to Tier-2 range
            adjustments['recommendation'] = 'Fader detected - take profits earlier'
        else:
            adjustments['recommendation'] = 'Mixed pattern - use default strategy'
        
        return adjustments
    
    def get_stats(self, ticker: Optional[str] = None) -> Dict[str, Any]:
        """
        Get learning statistics.
        
        Args:
            ticker: Optional ticker to get stats for specific symbol
            
        Returns:
            Statistics dictionary
        """
        if ticker:
            return self.symbol_stats.get(ticker, {})
        else:
            return {
                'total_symbols': len(self.symbol_stats),
                'symbols': list(self.symbol_stats.keys()),
                'symbol_stats': self.symbol_stats
            }
