"""
Risk Controls Module
====================

Enforce trading risk limits and circuit breakers.

This module implements:
- Daily loss limits
- Trade count limits
- Circuit breakers (consecutive losses)
- Drawdown controls
- Inventory and exposure caps

Key Classes
-----------
RiskViolation : Exception for limit breaches
DailyLossLimit : Maximum daily loss
TradeCountLimit : Trade frequency limits
CircuitBreaker : Halt on consecutive losses
DrawdownControl : Scale down in drawdown
InventoryCap : Per-instrument position limits
ExposureLimit : Portfolio exposure limits
RiskManager : Main orchestrator

Example
-------
>>> from autotrader.strategy.risk import RiskManager, RiskConfig
>>> 
>>> config = RiskConfig(
...     max_daily_loss=1000,
...     max_trades_per_day=100,
...     consecutive_loss_limit=5
... )
>>> 
>>> risk_mgr = RiskManager(config)
>>> 
>>> # Check if trade is allowed
>>> if risk_mgr.check_trade_allowed(symbol='BTCUSDT', size=0.1):
...     # Execute trade
...     risk_mgr.record_trade(...)
"""

from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np


class RiskViolation(Exception):
    """Exception raised when risk limit is breached."""
    pass


class LimitStatus(Enum):
    """Status of a risk limit."""
    OK = "ok"
    WARNING = "warning"
    BREACHED = "breached"


@dataclass
class TradeRecord:
    """Record of a completed trade."""
    timestamp: datetime
    symbol: str
    size: float
    pnl: float
    is_win: bool
    metadata: Dict = field(default_factory=dict)


class DailyLossLimit:
    """
    Maximum daily loss limit.
    
    Parameters
    ----------
    max_daily_loss : float
        Maximum loss allowed per day (absolute)
    reset_time : str
        Daily reset time (e.g., '00:00:00')
    warning_threshold : float
        Percentage of limit to trigger warning (0.8 = 80%)
    
    Example
    -------
    >>> limit = DailyLossLimit(max_daily_loss=1000, reset_time='00:00:00')
    >>> limit.check_limit(current_loss=800)  # Returns OK
    >>> limit.check_limit(current_loss=1100)  # Raises RiskViolation
    """
    
    def __init__(
        self,
        max_daily_loss: float,
        reset_time: str = '00:00:00',
        warning_threshold: float = 0.80
    ):
        self.max_daily_loss = max_daily_loss
        self.reset_time = reset_time
        self.warning_threshold = warning_threshold
        
        self.current_loss = 0.0
        self.last_reset = datetime.now()
        self.trades_today: List[TradeRecord] = []
    
    def check_reset(self):
        """Check if daily reset is needed."""
        now = datetime.now()
        
        # Parse reset time
        hour, minute, second = map(int, self.reset_time.split(':'))
        reset_datetime = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
        
        # Reset if past reset time and hasn't been reset today
        if now >= reset_datetime and self.last_reset < reset_datetime:
            self.reset()
    
    def reset(self):
        """Reset daily counters."""
        self.current_loss = 0.0
        self.last_reset = datetime.now()
        self.trades_today = []
    
    def check_limit(self, current_loss: float) -> LimitStatus:
        """
        Check if loss limit is breached.
        
        Parameters
        ----------
        current_loss : float
            Current daily loss (positive = loss)
        
        Returns
        -------
        status : LimitStatus
            OK, WARNING, or BREACHED
        """
        self.check_reset()
        
        if current_loss >= self.max_daily_loss:
            return LimitStatus.BREACHED
        
        if current_loss >= self.max_daily_loss * self.warning_threshold:
            return LimitStatus.WARNING
        
        return LimitStatus.OK
    
    def record_trade(self, trade: TradeRecord):
        """Record a trade for daily tracking."""
        self.check_reset()
        
        self.trades_today.append(trade)
        
        # Update current loss (only count losses)
        if trade.pnl < 0:
            self.current_loss += abs(trade.pnl)


class TradeCountLimit:
    """
    Trade frequency limits.
    
    Prevent overtrading with per-day, per-hour, and per-minute limits.
    
    Parameters
    ----------
    max_per_day : int
        Maximum trades per day
    max_per_hour : int
        Maximum trades per hour
    max_per_minute : int
        Maximum trades per minute
    
    Example
    -------
    >>> limit = TradeCountLimit(
    ...     max_per_day=100,
    ...     max_per_hour=20,
    ...     max_per_minute=5
    ... )
    >>> limit.check_limit()  # Returns True if allowed
    """
    
    def __init__(
        self,
        max_per_day: int = 1000,
        max_per_hour: int = 100,
        max_per_minute: int = 10
    ):
        self.max_per_day = max_per_day
        self.max_per_hour = max_per_hour
        self.max_per_minute = max_per_minute
        
        self.trades: List[datetime] = []
    
    def check_limit(self) -> bool:
        """
        Check if trade count limits allow new trade.
        
        Returns
        -------
        allowed : bool
            True if trade is allowed
        """
        now = datetime.now()
        
        # Remove old trades
        self._cleanup_old_trades(now)
        
        # Check limits
        day_count = self._count_trades_since(now - timedelta(days=1))
        hour_count = self._count_trades_since(now - timedelta(hours=1))
        minute_count = self._count_trades_since(now - timedelta(minutes=1))
        
        if day_count >= self.max_per_day:
            return False
        if hour_count >= self.max_per_hour:
            return False
        if minute_count >= self.max_per_minute:
            return False
        
        return True
    
    def record_trade(self):
        """Record a new trade."""
        self.trades.append(datetime.now())
    
    def _count_trades_since(self, since: datetime) -> int:
        """Count trades since given time."""
        return sum(1 for t in self.trades if t >= since)
    
    def _cleanup_old_trades(self, now: datetime):
        """Remove trades older than 1 day."""
        cutoff = now - timedelta(days=1)
        self.trades = [t for t in self.trades if t >= cutoff]


class CircuitBreaker:
    """
    Circuit breaker for consecutive losses.
    
    Halt trading after N consecutive losing trades.
    
    Parameters
    ----------
    consecutive_loss_limit : int
        Number of consecutive losses to trigger halt
    cooldown_minutes : int
        Minutes to wait before resuming
    
    Example
    -------
    >>> breaker = CircuitBreaker(
    ...     consecutive_loss_limit=5,
    ...     cooldown_minutes=30
    ... )
    >>> breaker.record_trade(pnl=-100)  # Loss 1
    >>> breaker.record_trade(pnl=-50)   # Loss 2
    >>> breaker.is_halted()  # Returns True after 5 consecutive losses
    """
    
    def __init__(
        self,
        consecutive_loss_limit: int,
        cooldown_minutes: int = 30
    ):
        self.consecutive_loss_limit = consecutive_loss_limit
        self.cooldown_minutes = cooldown_minutes
        
        self.consecutive_losses = 0
        self.halted = False
        self.halt_time: Optional[datetime] = None
    
    def record_trade(self, pnl: float):
        """
        Record trade result.
        
        Parameters
        ----------
        pnl : float
            Trade P&L (negative = loss)
        """
        if pnl < 0:
            self.consecutive_losses += 1
            
            if self.consecutive_losses >= self.consecutive_loss_limit:
                self.halt()
        else:
            # Reset on win
            self.consecutive_losses = 0
            if self.halted:
                self.resume()
    
    def halt(self):
        """Trigger circuit breaker halt."""
        self.halted = True
        self.halt_time = datetime.now()
    
    def resume(self):
        """Resume trading after halt."""
        self.halted = False
        self.halt_time = None
        self.consecutive_losses = 0
    
    def is_halted(self) -> bool:
        """
        Check if circuit breaker is active.
        
        Returns
        -------
        halted : bool
            True if trading is halted
        """
        if not self.halted:
            return False
        
        # Check cooldown
        if self.halt_time:
            elapsed = (datetime.now() - self.halt_time).total_seconds() / 60
            if elapsed >= self.cooldown_minutes:
                self.resume()
                return False
        
        return True


class DrawdownControl:
    """
    Scale position sizes based on drawdown.
    
    Reduce risk during drawdown periods.
    
    Parameters
    ----------
    max_drawdown : float
        Maximum drawdown before halting (e.g., 0.20 = 20%)
    scale_start : float
        Drawdown level to start scaling (e.g., 0.10 = 10%)
    peak_tracking_window : int
        Bars to track peak value
    
    Example
    -------
    >>> control = DrawdownControl(
    ...     max_drawdown=0.20,
    ...     scale_start=0.10
    ... )
    >>> scale_factor = control.get_scale_factor(equity=95000, peak=100000)
    >>> # Returns 0.5 at 10% drawdown, 0.0 at 20% drawdown
    """
    
    def __init__(
        self,
        max_drawdown: float,
        scale_start: float,
        peak_tracking_window: int = 100
    ):
        self.max_drawdown = max_drawdown
        self.scale_start = scale_start
        self.peak_tracking_window = peak_tracking_window
        
        self.peak_equity = 0.0
        self.equity_history: List[float] = []
    
    def update_equity(self, equity: float):
        """Update equity and track peak."""
        self.equity_history.append(equity)
        
        # Trim history
        if len(self.equity_history) > self.peak_tracking_window:
            self.equity_history = self.equity_history[-self.peak_tracking_window:]
        
        # Update peak
        self.peak_equity = max(self.peak_equity, equity)
    
    def get_drawdown(self, equity: float) -> float:
        """
        Calculate current drawdown.
        
        Returns
        -------
        drawdown : float
            Current drawdown (0.10 = 10%)
        """
        if self.peak_equity == 0:
            return 0.0
        
        return (self.peak_equity - equity) / self.peak_equity
    
    def get_scale_factor(self, equity: float) -> float:
        """
        Get position size scale factor based on drawdown.
        
        Linear scaling from 1.0 at scale_start to 0.0 at max_drawdown.
        
        Parameters
        ----------
        equity : float
            Current equity
        
        Returns
        -------
        scale_factor : float
            Multiplier for position sizes (0.0 to 1.0)
        """
        self.update_equity(equity)
        drawdown = self.get_drawdown(equity)
        
        if drawdown >= self.max_drawdown:
            return 0.0
        
        if drawdown <= self.scale_start:
            return 1.0
        
        # Linear scaling between scale_start and max_drawdown
        scale_range = self.max_drawdown - self.scale_start
        scale_factor = 1.0 - (drawdown - self.scale_start) / scale_range
        
        return max(0.0, scale_factor)


class InventoryCap:
    """
    Per-instrument position limits.
    
    Prevent concentration in single instrument.
    
    Parameters
    ----------
    max_position_per_symbol : Dict[str, float]
        Maximum position size per symbol
    default_max : float
        Default maximum for unlisted symbols
    
    Example
    -------
    >>> cap = InventoryCap(
    ...     max_position_per_symbol={'BTCUSDT': 10.0, 'ETHUSDT': 100.0},
    ...     default_max=5.0
    ... )
    >>> cap.check_limit('BTCUSDT', current=8.0, new=3.0)  # False (would exceed 10)
    """
    
    def __init__(
        self,
        max_position_per_symbol: Dict[str, float],
        default_max: float = float('inf')
    ):
        self.max_position_per_symbol = max_position_per_symbol
        self.default_max = default_max
        
        self.current_positions: Dict[str, float] = {}
    
    def get_limit(self, symbol: str) -> float:
        """Get position limit for symbol."""
        return self.max_position_per_symbol.get(symbol, self.default_max)
    
    def check_limit(self, symbol: str, new_size: float) -> bool:
        """
        Check if new position would exceed limit.
        
        Parameters
        ----------
        symbol : str
            Symbol to check
        new_size : float
            Proposed new position size (absolute)
        
        Returns
        -------
        allowed : bool
            True if within limit
        """
        limit = self.get_limit(symbol)
        return abs(new_size) <= limit
    
    def update_position(self, symbol: str, size: float):
        """Update current position for symbol."""
        self.current_positions[symbol] = size


class ExposureLimit:
    """
    Portfolio-wide exposure limits.
    
    Control gross, net, and sector exposures.
    
    Parameters
    ----------
    max_gross_exposure : float
        Maximum gross exposure (sum of absolute positions)
    max_net_exposure : float
        Maximum net exposure (sum of positions)
    max_sector_exposure : Dict[str, float]
        Maximum exposure per sector
    
    Example
    -------
    >>> limit = ExposureLimit(
    ...     max_gross_exposure=200000,
    ...     max_net_exposure=100000,
    ...     max_sector_exposure={'crypto': 50000, 'stocks': 100000}
    ... )
    >>> limit.check_limit(positions={'BTCUSDT': 10000, 'ETHUSDT': 15000})
    """
    
    def __init__(
        self,
        max_gross_exposure: float,
        max_net_exposure: float,
        max_sector_exposure: Optional[Dict[str, float]] = None
    ):
        self.max_gross_exposure = max_gross_exposure
        self.max_net_exposure = max_net_exposure
        self.max_sector_exposure = max_sector_exposure or {}
        
        # Symbol to sector mapping
        self.symbol_sectors: Dict[str, str] = {}
    
    def set_symbol_sector(self, symbol: str, sector: str):
        """Map symbol to sector."""
        self.symbol_sectors[symbol] = sector
    
    def calculate_exposures(
        self,
        positions: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate various exposures.
        
        Returns
        -------
        exposures : dict
            'gross', 'net', and sector exposures
        """
        gross = sum(abs(v) for v in positions.values())
        net = sum(positions.values())
        
        # Sector exposures
        sector_exp = {}
        for symbol, value in positions.items():
            sector = self.symbol_sectors.get(symbol, 'unknown')
            sector_exp[sector] = sector_exp.get(sector, 0) + abs(value)
        
        return {
            'gross': gross,
            'net': net,
            'sectors': sector_exp
        }
    
    def check_limit(self, positions: Dict[str, float]) -> bool:
        """
        Check if exposures are within limits.
        
        Parameters
        ----------
        positions : dict
            Current positions (symbol -> value)
        
        Returns
        -------
        allowed : bool
            True if within all limits
        """
        exposures = self.calculate_exposures(positions)
        
        # Check gross
        if exposures['gross'] > self.max_gross_exposure:
            return False
        
        # Check net
        if abs(exposures['net']) > self.max_net_exposure:
            return False
        
        # Check sectors
        for sector, exposure in exposures['sectors'].items():
            max_sector = self.max_sector_exposure.get(sector, float('inf'))
            if exposure > max_sector:
                return False
        
        return True


@dataclass
class RiskConfig:
    """Configuration for risk management."""
    
    # Daily loss limit
    max_daily_loss: float = 10000
    daily_loss_warning: float = 0.80
    
    # Trade count limits
    max_trades_per_day: int = 1000
    max_trades_per_hour: int = 100
    max_trades_per_minute: int = 10
    
    # Circuit breaker
    consecutive_loss_limit: int = 5
    cooldown_minutes: int = 30
    
    # Drawdown control
    max_drawdown: float = 0.20
    scale_start_drawdown: float = 0.10
    
    # Inventory limits
    max_position_per_symbol: Dict[str, float] = field(default_factory=dict)
    default_max_position: float = float('inf')
    
    # Exposure limits
    max_gross_exposure: float = float('inf')
    max_net_exposure: float = float('inf')
    max_sector_exposure: Dict[str, float] = field(default_factory=dict)


class RiskManager:
    """
    Main risk management orchestrator.
    
    Coordinates all risk controls and enforces limits.
    
    Parameters
    ----------
    config : RiskConfig
        Risk configuration
    
    Example
    -------
    >>> config = RiskConfig(
    ...     max_daily_loss=1000,
    ...     max_trades_per_day=100,
    ...     consecutive_loss_limit=5
    ... )
    >>> 
    >>> risk_mgr = RiskManager(config)
    >>> 
    >>> # Check if trade allowed
    >>> if risk_mgr.check_trade_allowed('BTCUSDT', 0.1, equity=100000):
    ...     # Execute trade
    ...     trade = TradeRecord(...)
    ...     risk_mgr.record_trade(trade)
    """
    
    def __init__(self, config: RiskConfig):
        self.config = config
        
        # Initialize controls
        self.daily_loss = DailyLossLimit(
            max_daily_loss=config.max_daily_loss,
            warning_threshold=config.daily_loss_warning
        )
        
        self.trade_count = TradeCountLimit(
            max_per_day=config.max_trades_per_day,
            max_per_hour=config.max_trades_per_hour,
            max_per_minute=config.max_trades_per_minute
        )
        
        self.circuit_breaker = CircuitBreaker(
            consecutive_loss_limit=config.consecutive_loss_limit,
            cooldown_minutes=config.cooldown_minutes
        )
        
        self.drawdown_control = DrawdownControl(
            max_drawdown=config.max_drawdown,
            scale_start=config.scale_start_drawdown
        )
        
        self.inventory_cap = InventoryCap(
            max_position_per_symbol=config.max_position_per_symbol,
            default_max=config.default_max_position
        )
        
        self.exposure_limit = ExposureLimit(
            max_gross_exposure=config.max_gross_exposure,
            max_net_exposure=config.max_net_exposure,
            max_sector_exposure=config.max_sector_exposure
        )
    
    def check_trade_allowed(
        self,
        symbol: str,
        size: float,
        equity: float,
        current_positions: Optional[Dict[str, float]] = None
    ) -> bool:
        """
        Check if trade is allowed by all risk controls.
        
        Parameters
        ----------
        symbol : str
            Trading symbol
        size : float
            Proposed position size
        equity : float
            Current equity
        current_positions : dict, optional
            Current positions (for exposure check)
        
        Returns
        -------
        allowed : bool
            True if all checks pass
        """
        # Circuit breaker
        if self.circuit_breaker.is_halted():
            return False
        
        # Trade count
        if not self.trade_count.check_limit():
            return False
        
        # Daily loss (check status)
        loss_status = self.daily_loss.check_limit(self.daily_loss.current_loss)
        if loss_status == LimitStatus.BREACHED:
            return False
        
        # Drawdown scale factor
        scale_factor = self.drawdown_control.get_scale_factor(equity)
        if scale_factor == 0:
            return False
        
        # Inventory cap
        if not self.inventory_cap.check_limit(symbol, size):
            return False
        
        # Exposure limits
        if current_positions is not None:
            test_positions = current_positions.copy()
            test_positions[symbol] = size
            
            if not self.exposure_limit.check_limit(test_positions):
                return False
        
        return True
    
    def record_trade(self, trade: TradeRecord):
        """
        Record completed trade.
        
        Parameters
        ----------
        trade : TradeRecord
            Trade to record
        """
        # Update all trackers
        self.daily_loss.record_trade(trade)
        self.trade_count.record_trade()
        self.circuit_breaker.record_trade(trade.pnl)
        self.inventory_cap.update_position(trade.symbol, trade.size)
    
    def get_position_scale_factor(self, equity: float) -> float:
        """Get drawdown-based position scale factor."""
        return self.drawdown_control.get_scale_factor(equity)


# Export public API
__all__ = [
    'RiskViolation',
    'LimitStatus',
    'TradeRecord',
    'DailyLossLimit',
    'TradeCountLimit',
    'CircuitBreaker',
    'DrawdownControl',
    'InventoryCap',
    'ExposureLimit',
    'RiskConfig',
    'RiskManager',
]
