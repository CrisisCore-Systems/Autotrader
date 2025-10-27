"""
Signal Generation Module
========================

Convert model predictions to trading signals with risk-aware filtering.

This module implements:
- Probability thresholding (calibrated probabilities)
- Expected value filtering
- Time stops (maximum holding periods)
- Adverse excursion stops (stop losses)
- Profit-take bands (multi-level exits)

Key Classes
-----------
Signal : Trading signal with direction and confidence
ProbabilityThresholder : Convert probabilities to signals
ExpectedValueFilter : Filter by expected value
TimeStop : Maximum hold time enforcement
AdverseExcursionStop : Stop loss management
ProfitTakeBands : Multi-level profit taking
SignalGenerator : Main signal generation orchestrator

Example
-------
>>> from autotrader.strategy.signals import SignalGenerator, SignalConfig
>>> 
>>> config = SignalConfig(
...     buy_threshold=0.55,
...     sell_threshold=0.45,
...     min_ev=10.0
... )
>>> 
>>> generator = SignalGenerator(config)
>>> signal = generator.generate(
...     prediction=0.62,
...     market_data=market_data,
...     position=current_position
... )
>>> 
>>> if signal.direction == 'long':
...     place_order(signal)
"""

from typing import Optional, List, Tuple, Dict, Literal
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from enum import Enum


class SignalDirection(Enum):
    """Signal direction enum."""
    LONG = 1
    SHORT = -1
    HOLD = 0
    CLOSE = 2


@dataclass
class Signal:
    """
    Trading signal.
    
    Attributes
    ----------
    direction : SignalDirection
        Signal direction (LONG, SHORT, HOLD, CLOSE)
    confidence : float
        Signal confidence (0-1)
    expected_value : float
        Expected value of trade
    metadata : dict
        Additional signal information
    timestamp : datetime
        Signal generation time
    """
    direction: SignalDirection
    confidence: float
    expected_value: float = 0.0
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def is_entry(self) -> bool:
        """Check if signal is entry (long/short)."""
        return self.direction in [SignalDirection.LONG, SignalDirection.SHORT]
    
    @property
    def is_exit(self) -> bool:
        """Check if signal is exit."""
        return self.direction == SignalDirection.CLOSE


@dataclass
class Position:
    """
    Current position state.
    
    Attributes
    ----------
    symbol : str
        Trading symbol
    direction : SignalDirection
        Position direction
    size : float
        Position size
    entry_price : float
        Entry price
    entry_time : datetime
        Entry timestamp
    current_price : float
        Current price
    unrealized_pnl : float
        Unrealized P&L
    max_adverse_excursion : float
        Maximum adverse move
    max_favorable_excursion : float
        Maximum favorable move
    """
    symbol: str
    direction: SignalDirection
    size: float
    entry_price: float
    entry_time: datetime
    current_price: float
    unrealized_pnl: float = 0.0
    max_adverse_excursion: float = 0.0
    max_favorable_excursion: float = 0.0
    
    def update_price(self, price: float):
        """Update position with new price."""
        self.current_price = price
        
        # Update P&L
        if self.direction == SignalDirection.LONG:
            self.unrealized_pnl = (price - self.entry_price) * self.size
            adverse_move = self.entry_price - price
            favorable_move = price - self.entry_price
        else:  # SHORT
            self.unrealized_pnl = (self.entry_price - price) * self.size
            adverse_move = price - self.entry_price
            favorable_move = self.entry_price - price
        
        # Update excursions
        if adverse_move > 0:
            self.max_adverse_excursion = max(
                self.max_adverse_excursion,
                adverse_move / self.entry_price
            )
        
        if favorable_move > 0:
            self.max_favorable_excursion = max(
                self.max_favorable_excursion,
                favorable_move / self.entry_price
            )


class ProbabilityThresholder:
    """
    Convert calibrated probabilities to trading signals.
    
    Parameters
    ----------
    buy_threshold : float
        Minimum probability to go long (e.g., 0.55)
    sell_threshold : float
        Maximum probability to go short (e.g., 0.45)
    hold_band : float
        Neutral zone width (optional)
    
    Example
    -------
    >>> thresholder = ProbabilityThresholder(
    ...     buy_threshold=0.55,
    ...     sell_threshold=0.45
    ... )
    >>> signal = thresholder.generate(probability=0.62)
    >>> print(signal.direction)  # LONG
    """
    
    def __init__(
        self,
        buy_threshold: float = 0.55,
        sell_threshold: float = 0.45,
        hold_band: Optional[float] = None
    ):
        if buy_threshold <= sell_threshold:
            raise ValueError("buy_threshold must be > sell_threshold")
        
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.hold_band = hold_band or (buy_threshold - sell_threshold)
    
    def generate(self, probability: float) -> Signal:
        """
        Generate signal from probability.
        
        Parameters
        ----------
        probability : float
            Probability of upward move (0-1)
        
        Returns
        -------
        signal : Signal
            Trading signal
        """
        if probability >= self.buy_threshold:
            return Signal(
                direction=SignalDirection.LONG,
                confidence=probability,
                metadata={'threshold': 'buy'}
            )
        elif probability <= self.sell_threshold:
            return Signal(
                direction=SignalDirection.SHORT,
                confidence=1 - probability,
                metadata={'threshold': 'sell'}
            )
        else:
            return Signal(
                direction=SignalDirection.HOLD,
                confidence=0.5,
                metadata={'threshold': 'hold'}
            )


class ExpectedValueFilter:
    """
    Filter signals by expected value.
    
    Only allows trades with positive expected value after costs.
    
    Parameters
    ----------
    min_ev : float
        Minimum expected value per trade
    transaction_cost : float
        Total transaction cost (fees + slippage + spread)
    
    Example
    -------
    >>> filter = ExpectedValueFilter(min_ev=10.0, transaction_cost=5.0)
    >>> signal = filter.check(
    ...     win_prob=0.55,
    ...     avg_win=100.0,
    ...     avg_loss=80.0
    ... )
    >>> print(signal)  # True if EV > 15.0
    """
    
    def __init__(
        self,
        min_ev: float,
        transaction_cost: float
    ):
        self.min_ev = min_ev
        self.transaction_cost = transaction_cost
    
    def calculate_ev(
        self,
        win_prob: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate expected value.
        
        EV = P(win) * AvgWin - P(loss) * AvgLoss - Cost
        """
        loss_prob = 1 - win_prob
        ev = win_prob * avg_win - loss_prob * avg_loss - self.transaction_cost
        return ev
    
    def check(
        self,
        win_prob: float,
        avg_win: float,
        avg_loss: float
    ) -> bool:
        """
        Check if trade meets EV threshold.
        
        Returns
        -------
        allowed : bool
            True if EV > min_ev
        """
        ev = self.calculate_ev(win_prob, avg_win, avg_loss)
        return ev >= self.min_ev
    
    def filter_signal(
        self,
        signal: Signal,
        win_prob: float,
        avg_win: float,
        avg_loss: float
    ) -> Signal:
        """
        Filter signal by EV.
        
        Returns HOLD signal if EV too low.
        """
        if not signal.is_entry:
            return signal
        
        ev = self.calculate_ev(win_prob, avg_win, avg_loss)
        
        if ev >= self.min_ev:
            signal.expected_value = ev
            return signal
        else:
            return Signal(
                direction=SignalDirection.HOLD,
                confidence=0.0,
                expected_value=ev,
                metadata={'filtered': 'low_ev', 'ev': ev}
            )


class TimeStop:
    """
    Maximum holding period enforcement.
    
    Close positions after maximum time elapsed.
    
    Parameters
    ----------
    max_hold_bars : int, optional
        Maximum bars to hold
    max_hold_seconds : int, optional
        Maximum seconds to hold
    
    Example
    -------
    >>> stop = TimeStop(max_hold_bars=100, max_hold_seconds=300)
    >>> position = Position(...)
    >>> if stop.should_close(position):
    ...     close_position(position)
    """
    
    def __init__(
        self,
        max_hold_bars: Optional[int] = None,
        max_hold_seconds: Optional[int] = None
    ):
        if max_hold_bars is None and max_hold_seconds is None:
            raise ValueError("Must specify max_hold_bars or max_hold_seconds")
        
        self.max_hold_bars = max_hold_bars
        self.max_hold_seconds = max_hold_seconds
    
    def should_close(
        self,
        position: Position,
        current_bar: Optional[int] = None
    ) -> bool:
        """
        Check if position should close.
        
        Parameters
        ----------
        position : Position
            Current position
        current_bar : int, optional
            Current bar number
        
        Returns
        -------
        should_close : bool
            True if max hold time exceeded
        """
        # Check bar-based stop
        if self.max_hold_bars is not None and current_bar is not None:
            bars_held = current_bar
            if bars_held >= self.max_hold_bars:
                return True
        
        # Check time-based stop
        if self.max_hold_seconds is not None:
            time_held = (datetime.now() - position.entry_time).total_seconds()
            if time_held >= self.max_hold_seconds:
                return True
        
        return False


class AdverseExcursionStop:
    """
    Stop loss based on adverse price movement.
    
    Parameters
    ----------
    max_mae_pct : float
        Maximum adverse excursion as percentage (e.g., 0.02 = 2%)
    max_mae_dollars : float, optional
        Maximum adverse excursion in dollars
    trailing : bool
        Use trailing stop (moves with profit)
    
    Example
    -------
    >>> stop = AdverseExcursionStop(max_mae_pct=0.02, trailing=True)
    >>> position = Position(...)
    >>> position.update_price(new_price)
    >>> if stop.should_close(position):
    ...     close_position(position)
    """
    
    def __init__(
        self,
        max_mae_pct: float,
        max_mae_dollars: Optional[float] = None,
        trailing: bool = False
    ):
        self.max_mae_pct = max_mae_pct
        self.max_mae_dollars = max_mae_dollars
        self.trailing = trailing
        self.trail_high_water = {}
    
    def should_close(self, position: Position) -> Tuple[bool, str]:
        """
        Check if position should close.
        
        Returns
        -------
        should_close : bool
            True if stop loss hit
        reason : str
            Reason for closure
        """
        # Check percentage-based stop
        if position.max_adverse_excursion >= self.max_mae_pct:
            return True, f"mae_pct_{position.max_adverse_excursion:.4f}"
        
        # Check dollar-based stop
        if self.max_mae_dollars is not None:
            if abs(position.unrealized_pnl) >= self.max_mae_dollars:
                if position.unrealized_pnl < 0:  # Loss
                    return True, f"mae_dollars_{abs(position.unrealized_pnl):.2f}"
        
        # Trailing stop logic
        if self.trailing:
            symbol = position.symbol
            
            # Update high water mark
            if symbol not in self.trail_high_water:
                self.trail_high_water[symbol] = position.entry_price
            
            # Check if new high
            if position.direction == SignalDirection.LONG:
                if position.current_price > self.trail_high_water[symbol]:
                    self.trail_high_water[symbol] = position.current_price
                
                # Check trailing stop
                trail_pct = (self.trail_high_water[symbol] - position.current_price) / \
                           self.trail_high_water[symbol]
                
                if trail_pct >= self.max_mae_pct:
                    return True, f"trailing_stop_{trail_pct:.4f}"
            
            else:  # SHORT
                if position.current_price < self.trail_high_water[symbol]:
                    self.trail_high_water[symbol] = position.current_price
                
                trail_pct = (position.current_price - self.trail_high_water[symbol]) / \
                           self.trail_high_water[symbol]
                
                if trail_pct >= self.max_mae_pct:
                    return True, f"trailing_stop_{trail_pct:.4f}"
        
        return False, ""


class ProfitTakeBands:
    """
    Multi-level profit taking.
    
    Parameters
    ----------
    levels : List[Tuple[float, float]]
        List of (profit_pct, close_fraction)
        e.g., [(0.01, 0.5), (0.02, 1.0)]
        = Take 50% at 1% profit, 100% at 2%
    
    Example
    -------
    >>> bands = ProfitTakeBands([
    ...     (0.005, 0.25),  # 25% at 0.5%
    ...     (0.010, 0.50),  # 50% at 1.0%
    ...     (0.020, 1.00),  # All at 2.0%
    ... ])
    >>> 
    >>> position = Position(...)
    >>> close_fraction = bands.get_close_fraction(position)
    >>> if close_fraction > 0:
    ...     close_size = position.size * close_fraction
    """
    
    def __init__(self, levels: List[Tuple[float, float]]):
        # Sort by profit level
        self.levels = sorted(levels, key=lambda x: x[0])
        self.triggered_levels = {}
    
    def get_close_fraction(self, position: Position) -> float:
        """
        Get fraction of position to close.
        
        Returns
        -------
        close_fraction : float
            Fraction to close (0-1)
        """
        symbol = position.symbol
        
        # Initialize tracking
        if symbol not in self.triggered_levels:
            self.triggered_levels[symbol] = -1
        
        # Calculate profit percentage
        profit_pct = position.max_favorable_excursion
        
        # Check each level
        for i, (level_pct, close_frac) in enumerate(self.levels):
            if profit_pct >= level_pct and i > self.triggered_levels[symbol]:
                self.triggered_levels[symbol] = i
                return close_frac
        
        return 0.0
    
    def reset(self, symbol: str):
        """Reset profit levels for symbol."""
        if symbol in self.triggered_levels:
            del self.triggered_levels[symbol]


@dataclass
class SignalConfig:
    """Configuration for signal generation."""
    # Probability thresholding
    buy_threshold: float = 0.55
    sell_threshold: float = 0.45
    
    # Expected value
    min_ev: float = 10.0
    transaction_cost: float = 5.0
    avg_win: float = 100.0
    avg_loss: float = 80.0
    
    # Time stops
    max_hold_bars: Optional[int] = 100
    max_hold_seconds: Optional[int] = 300
    
    # Adverse excursion
    max_mae_pct: float = 0.02
    trailing_stop: bool = True
    
    # Profit taking
    profit_levels: List[Tuple[float, float]] = field(default_factory=lambda: [
        (0.005, 0.25),
        (0.010, 0.50),
        (0.020, 1.00)
    ])


class SignalGenerator:
    """
    Main signal generation orchestrator.
    
    Combines all signal generation components.
    
    Parameters
    ----------
    config : SignalConfig
        Signal generation configuration
    
    Example
    -------
    >>> config = SignalConfig(
    ...     buy_threshold=0.55,
    ...     min_ev=10.0,
    ...     max_mae_pct=0.02
    ... )
    >>> 
    >>> generator = SignalGenerator(config)
    >>> 
    >>> # Generate entry signal
    >>> signal = generator.generate_entry(
    ...     prediction=0.62,
    ...     win_prob=0.55
    ... )
    >>> 
    >>> # Check exit conditions
    >>> should_exit, reason = generator.check_exit(
    ...     position=position,
    ...     current_bar=150
    ... )
    """
    
    def __init__(self, config: SignalConfig):
        self.config = config
        
        # Initialize components
        self.prob_thresholder = ProbabilityThresholder(
            buy_threshold=config.buy_threshold,
            sell_threshold=config.sell_threshold
        )
        
        self.ev_filter = ExpectedValueFilter(
            min_ev=config.min_ev,
            transaction_cost=config.transaction_cost
        )
        
        self.time_stop = TimeStop(
            max_hold_bars=config.max_hold_bars,
            max_hold_seconds=config.max_hold_seconds
        )
        
        self.adverse_stop = AdverseExcursionStop(
            max_mae_pct=config.max_mae_pct,
            trailing=config.trailing_stop
        )
        
        self.profit_bands = ProfitTakeBands(
            levels=config.profit_levels
        )
    
    def generate_entry(
        self,
        prediction: float,
        win_prob: float,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None
    ) -> Signal:
        """
        Generate entry signal.
        
        Parameters
        ----------
        prediction : float
            Model prediction (probability)
        win_prob : float
            Estimated win probability
        avg_win : float, optional
            Average win size
        avg_loss : float, optional
            Average loss size
        
        Returns
        -------
        signal : Signal
            Entry signal (or HOLD if filtered)
        """
        # Generate base signal
        signal = self.prob_thresholder.generate(prediction)
        
        # Filter by expected value
        if signal.is_entry:
            signal = self.ev_filter.filter_signal(
                signal=signal,
                win_prob=win_prob,
                avg_win=avg_win or self.config.avg_win,
                avg_loss=avg_loss or self.config.avg_loss
            )
        
        return signal
    
    def check_exit(
        self,
        position: Position,
        current_bar: Optional[int] = None
    ) -> Tuple[bool, str]:
        """
        Check if position should exit.
        
        Parameters
        ----------
        position : Position
            Current position
        current_bar : int, optional
            Current bar number
        
        Returns
        -------
        should_exit : bool
            True if should exit
        reason : str
            Exit reason
        """
        # Check time stop
        if self.time_stop.should_close(position, current_bar):
            return True, "time_stop"
        
        # Check adverse excursion
        should_close, reason = self.adverse_stop.should_close(position)
        if should_close:
            return True, reason
        
        # Check profit taking
        close_fraction = self.profit_bands.get_close_fraction(position)
        if close_fraction >= 1.0:
            return True, "profit_target_full"
        elif close_fraction > 0:
            return True, f"profit_target_partial_{close_fraction:.2f}"
        
        return False, ""


# Export public API
__all__ = [
    'Signal',
    'SignalDirection',
    'Position',
    'ProbabilityThresholder',
    'ExpectedValueFilter',
    'TimeStop',
    'AdverseExcursionStop',
    'ProfitTakeBands',
    'SignalConfig',
    'SignalGenerator',
]
