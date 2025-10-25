"""
Portfolio Management Module
============================

Cross-asset portfolio coordination and risk budgeting.

This module implements:
- Concurrency limits (max simultaneous positions)
- Correlation-aware risk budgets
- Cooldown management after losses
- Diversification controls

Key Classes
-----------
ConcurrencyLimit : Limit simultaneous positions
CorrelationManager : Correlation-aware budgets
CooldownManager : Pause after losses
DiversificationManager : Sector/venue limits
PortfolioManager : Main orchestrator

Example
-------
>>> from autotrader.strategy.portfolio import PortfolioManager, PortfolioConfig
>>> 
>>> config = PortfolioConfig(
...     max_concurrent_positions=10,
...     max_correlation=0.7,
...     cooldown_after_loss_count=3
... )
>>> 
>>> portfolio_mgr = PortfolioManager(config)
>>> 
>>> # Check if new position allowed
>>> if portfolio_mgr.can_open_position('BTCUSDT', existing_positions):
...     # Open position
...     portfolio_mgr.add_position('BTCUSDT', size=0.1)
"""

from typing import Optional, Dict, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np
import pandas as pd


class PortfolioStatus(Enum):
    """Status of portfolio manager."""
    ACTIVE = "active"
    COOLDOWN = "cooldown"
    HALTED = "halted"


@dataclass
class PositionInfo:
    """Information about an open position."""
    symbol: str
    size: float
    opened_at: datetime
    sector: Optional[str] = None
    venue: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


class ConcurrencyLimit:
    """
    Limit simultaneous open positions.
    
    Prevents over-diversification and excessive monitoring overhead.
    
    Parameters
    ----------
    max_concurrent : int
        Maximum number of simultaneous positions
    max_per_sector : int
        Maximum positions per sector
    max_per_venue : int
        Maximum positions per venue
    
    Example
    -------
    >>> limit = ConcurrencyLimit(
    ...     max_concurrent=10,
    ...     max_per_sector=5,
    ...     max_per_venue=3
    ... )
    >>> limit.can_open_position(
    ...     sector='crypto',
    ...     venue='binance',
    ...     current_positions=existing_positions
    ... )
    """
    
    def __init__(
        self,
        max_concurrent: int,
        max_per_sector: Optional[int] = None,
        max_per_venue: Optional[int] = None
    ):
        self.max_concurrent = max_concurrent
        self.max_per_sector = max_per_sector or max_concurrent
        self.max_per_venue = max_per_venue or max_concurrent
        
        self.current_positions: Dict[str, PositionInfo] = {}
    
    def can_open_position(
        self,
        sector: Optional[str] = None,
        venue: Optional[str] = None
    ) -> bool:
        """
        Check if new position can be opened.
        
        Parameters
        ----------
        sector : str, optional
            Sector of new position
        venue : str, optional
            Venue of new position
        
        Returns
        -------
        allowed : bool
            True if within limits
        """
        # Check total count
        if len(self.current_positions) >= self.max_concurrent:
            return False
        
        # Check sector
        if sector:
            sector_count = sum(
                1 for p in self.current_positions.values()
                if p.sector == sector
            )
            if sector_count >= self.max_per_sector:
                return False
        
        # Check venue
        if venue:
            venue_count = sum(
                1 for p in self.current_positions.values()
                if p.venue == venue
            )
            if venue_count >= self.max_per_venue:
                return False
        
        return True
    
    def add_position(
        self,
        symbol: str,
        size: float,
        sector: Optional[str] = None,
        venue: Optional[str] = None
    ):
        """Add new position."""
        self.current_positions[symbol] = PositionInfo(
            symbol=symbol,
            size=size,
            opened_at=datetime.now(),
            sector=sector,
            venue=venue
        )
    
    def remove_position(self, symbol: str):
        """Remove closed position."""
        if symbol in self.current_positions:
            del self.current_positions[symbol]


class CorrelationManager:
    """
    Manage correlation-aware risk budgets.
    
    Adjust position sizes based on portfolio correlation.
    
    Parameters
    ----------
    max_correlation : float
        Maximum average correlation (e.g., 0.7)
    lookback : int
        Bars for correlation calculation
    update_frequency : int
        Update correlation every N bars
    
    Example
    -------
    >>> mgr = CorrelationManager(
    ...     max_correlation=0.7,
    ...     lookback=60
    ... )
    >>> scale_factor = mgr.get_correlation_scale_factor(
    ...     new_symbol='BTCUSDT',
    ...     current_positions=['ETHUSDT', 'SOLUSDT'],
    ...     returns_data=returns_df
    ... )
    
    References
    ----------
    - Kritzman et al. (2011): "Portfolio Diversification"
    """
    
    def __init__(
        self,
        max_correlation: float,
        lookback: int = 60,
        update_frequency: int = 10
    ):
        self.max_correlation = max_correlation
        self.lookback = lookback
        self.update_frequency = update_frequency
        
        self.correlation_matrix: Optional[pd.DataFrame] = None
        self.last_update: Optional[datetime] = None
        self.update_counter = 0
    
    def update_correlation_matrix(self, returns: pd.DataFrame):
        """
        Update correlation matrix.
        
        Parameters
        ----------
        returns : pd.DataFrame
            Returns data (columns = symbols)
        """
        if len(returns) < self.lookback:
            return
        
        # Take recent window
        recent_returns = returns.iloc[-self.lookback:]
        
        # Calculate correlation
        self.correlation_matrix = recent_returns.corr()
        self.last_update = datetime.now()
    
    def should_update(self) -> bool:
        """Check if correlation matrix should be updated."""
        self.update_counter += 1
        return self.update_counter % self.update_frequency == 0
    
    def get_average_correlation(
        self,
        symbol: str,
        existing_symbols: List[str]
    ) -> float:
        """
        Get average correlation between symbol and existing positions.
        
        Parameters
        ----------
        symbol : str
            New symbol to check
        existing_symbols : list
            Currently held symbols
        
        Returns
        -------
        avg_correlation : float
            Average correlation (0 to 1)
        """
        if self.correlation_matrix is None:
            return 0.0
        
        if symbol not in self.correlation_matrix.index:
            return 0.0
        
        if not existing_symbols:
            return 0.0
        
        # Filter to existing symbols that are in matrix
        valid_symbols = [
            s for s in existing_symbols
            if s in self.correlation_matrix.columns
        ]
        
        if not valid_symbols:
            return 0.0
        
        # Calculate average correlation
        correlations = [
            abs(self.correlation_matrix.loc[symbol, s])
            for s in valid_symbols
        ]
        
        return np.mean(correlations)
    
    def get_correlation_scale_factor(
        self,
        symbol: str,
        existing_symbols: List[str]
    ) -> float:
        """
        Get position size scale factor based on correlation.
        
        Higher correlation → smaller positions.
        
        Parameters
        ----------
        symbol : str
            New symbol
        existing_symbols : list
            Current positions
        
        Returns
        -------
        scale_factor : float
            Scale factor (0.0 to 1.0)
        """
        avg_corr = self.get_average_correlation(symbol, existing_symbols)
        
        if avg_corr >= self.max_correlation:
            return 0.0
        
        # Linear scaling
        scale_factor = 1.0 - (avg_corr / self.max_correlation)
        
        return scale_factor


class CooldownManager:
    """
    Manage cooldown periods after losses.
    
    Pause trading after consecutive losses to prevent tilt.
    
    Parameters
    ----------
    loss_count_trigger : int
        Number of losses to trigger cooldown
    cooldown_minutes : int
        Initial cooldown duration
    progressive : bool
        Use progressive cooldown (increases with consecutive triggers)
    max_cooldown_minutes : int
        Maximum cooldown duration
    
    Example
    -------
    >>> mgr = CooldownManager(
    ...     loss_count_trigger=3,
    ...     cooldown_minutes=15,
    ...     progressive=True
    ... )
    >>> mgr.record_loss()  # Loss 1
    >>> mgr.record_loss()  # Loss 2
    >>> mgr.record_loss()  # Loss 3 -> cooldown triggered
    >>> mgr.is_in_cooldown()  # True
    """
    
    def __init__(
        self,
        loss_count_trigger: int,
        cooldown_minutes: int,
        progressive: bool = True,
        max_cooldown_minutes: int = 240
    ):
        self.loss_count_trigger = loss_count_trigger
        self.cooldown_minutes = cooldown_minutes
        self.progressive = progressive
        self.max_cooldown_minutes = max_cooldown_minutes
        
        self.consecutive_losses = 0
        self.cooldown_start: Optional[datetime] = None
        self.cooldown_count = 0
    
    def record_loss(self):
        """Record a losing trade."""
        self.consecutive_losses += 1
        
        if self.consecutive_losses >= self.loss_count_trigger:
            self.trigger_cooldown()
    
    def record_win(self):
        """Record a winning trade."""
        self.consecutive_losses = 0
        self.cooldown_count = 0
    
    def trigger_cooldown(self):
        """Start cooldown period."""
        self.cooldown_start = datetime.now()
        self.cooldown_count += 1
        self.consecutive_losses = 0
    
    def get_cooldown_duration(self) -> int:
        """
        Get current cooldown duration.
        
        Returns
        -------
        duration : int
            Cooldown minutes
        """
        if not self.progressive:
            return self.cooldown_minutes
        
        # Progressive: double each time
        duration = self.cooldown_minutes * (2 ** (self.cooldown_count - 1))
        
        return min(duration, self.max_cooldown_minutes)
    
    def is_in_cooldown(self) -> bool:
        """
        Check if currently in cooldown.
        
        Returns
        -------
        in_cooldown : bool
            True if in cooldown period
        """
        if self.cooldown_start is None:
            return False
        
        elapsed = (datetime.now() - self.cooldown_start).total_seconds() / 60
        duration = self.get_cooldown_duration()
        
        if elapsed >= duration:
            self.cooldown_start = None
            return False
        
        return True
    
    def get_remaining_cooldown(self) -> int:
        """Get remaining cooldown minutes."""
        if not self.is_in_cooldown():
            return 0
        
        elapsed = (datetime.now() - self.cooldown_start).total_seconds() / 60
        duration = self.get_cooldown_duration()
        
        return max(0, int(duration - elapsed))


class DiversificationManager:
    """
    Enforce diversification requirements.
    
    Ensure portfolio is sufficiently diversified across sectors and venues.
    
    Parameters
    ----------
    min_sectors : int
        Minimum number of sectors (0 = no minimum)
    min_venues : int
        Minimum number of venues (0 = no minimum)
    max_sector_concentration : float
        Maximum % in single sector (e.g., 0.50 = 50%)
    max_venue_concentration : float
        Maximum % in single venue
    
    Example
    -------
    >>> mgr = DiversificationManager(
    ...     min_sectors=3,
    ...     max_sector_concentration=0.50
    ... )
    >>> mgr.check_diversification(
    ...     positions={'BTC': PositionInfo(...), 'ETH': PositionInfo(...)}
    ... )
    """
    
    def __init__(
        self,
        min_sectors: int = 0,
        min_venues: int = 0,
        max_sector_concentration: float = 1.0,
        max_venue_concentration: float = 1.0
    ):
        self.min_sectors = min_sectors
        self.min_venues = min_venues
        self.max_sector_concentration = max_sector_concentration
        self.max_venue_concentration = max_venue_concentration
    
    def check_diversification(
        self,
        positions: Dict[str, PositionInfo]
    ) -> bool:
        """
        Check if portfolio meets diversification requirements.
        
        Parameters
        ----------
        positions : dict
            Current positions
        
        Returns
        -------
        is_diversified : bool
            True if requirements met
        """
        if not positions:
            return True
        
        # Count sectors and venues
        sectors = set(p.sector for p in positions.values() if p.sector)
        venues = set(p.venue for p in positions.values() if p.venue)
        
        if len(sectors) < self.min_sectors:
            return False
        
        if len(venues) < self.min_venues:
            return False
        
        # Check concentrations
        total_value = sum(abs(p.size) for p in positions.values())
        
        if total_value == 0:
            return True
        
        # Sector concentration
        sector_values = {}
        for p in positions.values():
            if p.sector:
                sector_values[p.sector] = sector_values.get(p.sector, 0) + abs(p.size)
        
        for sector_value in sector_values.values():
            concentration = sector_value / total_value
            if concentration > self.max_sector_concentration:
                return False
        
        # Venue concentration
        venue_values = {}
        for p in positions.values():
            if p.venue:
                venue_values[p.venue] = venue_values.get(p.venue, 0) + abs(p.size)
        
        for venue_value in venue_values.values():
            concentration = venue_value / total_value
            if concentration > self.max_venue_concentration:
                return False
        
        return True


@dataclass
class PortfolioConfig:
    """Configuration for portfolio management."""
    
    # Concurrency limits
    max_concurrent_positions: int = 20
    max_per_sector: Optional[int] = None
    max_per_venue: Optional[int] = None
    
    # Correlation management
    max_correlation: float = 0.70
    correlation_lookback: int = 60
    correlation_update_freq: int = 10
    
    # Cooldown
    cooldown_loss_count: int = 3
    cooldown_minutes: int = 15
    progressive_cooldown: bool = True
    max_cooldown_minutes: int = 240
    
    # Diversification
    min_sectors: int = 0
    min_venues: int = 0
    max_sector_concentration: float = 1.0
    max_venue_concentration: float = 1.0


class PortfolioManager:
    """
    Main portfolio management orchestrator.
    
    Coordinates concurrency, correlation, cooldown, and diversification.
    
    Parameters
    ----------
    config : PortfolioConfig
        Portfolio configuration
    
    Example
    -------
    >>> config = PortfolioConfig(
    ...     max_concurrent_positions=10,
    ...     max_correlation=0.7,
    ...     cooldown_loss_count=3
    ... )
    >>> 
    >>> portfolio_mgr = PortfolioManager(config)
    >>> 
    >>> # Check if can open position
    >>> can_open = portfolio_mgr.can_open_position(
    ...     symbol='BTCUSDT',
    ...     sector='crypto',
    ...     venue='binance',
    ...     returns_data=returns_df
    ... )
    >>> 
    >>> if can_open:
    ...     portfolio_mgr.add_position('BTCUSDT', size=0.1, sector='crypto')
    """
    
    def __init__(self, config: PortfolioConfig):
        self.config = config
        
        # Initialize managers
        self.concurrency = ConcurrencyLimit(
            max_concurrent=config.max_concurrent_positions,
            max_per_sector=config.max_per_sector,
            max_per_venue=config.max_per_venue
        )
        
        self.correlation = CorrelationManager(
            max_correlation=config.max_correlation,
            lookback=config.correlation_lookback,
            update_frequency=config.correlation_update_freq
        )
        
        self.cooldown = CooldownManager(
            loss_count_trigger=config.cooldown_loss_count,
            cooldown_minutes=config.cooldown_minutes,
            progressive=config.progressive_cooldown,
            max_cooldown_minutes=config.max_cooldown_minutes
        )
        
        self.diversification = DiversificationManager(
            min_sectors=config.min_sectors,
            min_venues=config.min_venues,
            max_sector_concentration=config.max_sector_concentration,
            max_venue_concentration=config.max_venue_concentration
        )
        
        self.status = PortfolioStatus.ACTIVE
    
    def can_open_position(
        self,
        symbol: str,
        sector: Optional[str] = None,
        venue: Optional[str] = None,
        returns_data: Optional[pd.DataFrame] = None
    ) -> bool:
        """
        Check if new position can be opened.
        
        Parameters
        ----------
        symbol : str
            Symbol to trade
        sector : str, optional
            Sector of symbol
        venue : str, optional
            Trading venue
        returns_data : pd.DataFrame, optional
            Returns data for correlation check
        
        Returns
        -------
        allowed : bool
            True if all checks pass
        """
        # Cooldown check
        if self.cooldown.is_in_cooldown():
            return False
        
        # Concurrency check
        if not self.concurrency.can_open_position(sector, venue):
            return False
        
        # Correlation check
        if returns_data is not None:
            if self.correlation.should_update():
                self.correlation.update_correlation_matrix(returns_data)
            
            existing_symbols = list(self.concurrency.current_positions.keys())
            scale_factor = self.correlation.get_correlation_scale_factor(
                symbol,
                existing_symbols
            )
            
            if scale_factor == 0:
                return False
        
        return True
    
    def add_position(
        self,
        symbol: str,
        size: float,
        sector: Optional[str] = None,
        venue: Optional[str] = None
    ):
        """
        Add new position to portfolio.
        
        Parameters
        ----------
        symbol : str
            Symbol
        size : float
            Position size
        sector : str, optional
            Sector
        venue : str, optional
            Venue
        """
        self.concurrency.add_position(symbol, size, sector, venue)
    
    def remove_position(self, symbol: str):
        """Remove position from portfolio."""
        self.concurrency.remove_position(symbol)
    
    def record_trade_result(self, pnl: float):
        """
        Record trade result for cooldown tracking.
        
        Parameters
        ----------
        pnl : float
            Trade P&L (negative = loss)
        """
        if pnl < 0:
            self.cooldown.record_loss()
        else:
            self.cooldown.record_win()
        
        # Update status
        if self.cooldown.is_in_cooldown():
            self.status = PortfolioStatus.COOLDOWN
        else:
            self.status = PortfolioStatus.ACTIVE
    
    def get_correlation_scale_factor(
        self,
        symbol: str
    ) -> float:
        """Get correlation-based position size scale factor."""
        existing_symbols = list(self.concurrency.current_positions.keys())
        return self.correlation.get_correlation_scale_factor(symbol, existing_symbols)
    
    def check_diversification(self) -> bool:
        """Check if portfolio is properly diversified."""
        return self.diversification.check_diversification(
            self.concurrency.current_positions
        )
    
    def get_status_info(self) -> Dict:
        """
        Get current portfolio status.
        
        Returns
        -------
        info : dict
            Status information
        """
        return {
            'status': self.status.value,
            'num_positions': len(self.concurrency.current_positions),
            'max_positions': self.config.max_concurrent_positions,
            'in_cooldown': self.cooldown.is_in_cooldown(),
            'cooldown_remaining': self.cooldown.get_remaining_cooldown(),
            'is_diversified': self.check_diversification()
        }


# Export public API
__all__ = [
    'PortfolioStatus',
    'PositionInfo',
    'ConcurrencyLimit',
    'CorrelationManager',
    'CooldownManager',
    'DiversificationManager',
    'PortfolioConfig',
    'PortfolioManager',
]
