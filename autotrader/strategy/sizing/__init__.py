"""
Position Sizing Module
======================

Determine optimal position sizes based on risk management principles.

This module implements:
- Volatility scaling
- Kelly criterion
- Fixed fractional sizing
- Risk parity
- Maximum position limits

Key Classes
-----------
PositionSize : Position size with metadata
VolatilityScaler : Scale by realized volatility
KellySizer : Kelly criterion optimal sizing
FixedFractionalSizer : Fixed fraction of capital
RiskParitySizer : Equal risk contribution
PositionSizer : Main orchestrator

Example
-------
>>> from autotrader.strategy.sizing import PositionSizer, SizingConfig
>>> 
>>> config = SizingConfig(
...     method='volatility_scaled',
...     target_volatility=0.01,
...     max_position_pct=0.20
... )
>>> 
>>> sizer = PositionSizer(config)
>>> size = sizer.calculate_size(
...     signal=signal,
...     capital=100000,
...     volatility=0.02
... )
"""

from typing import Optional, Dict, Literal
from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class PositionSize:
    """
    Position size result.
    
    Attributes
    ----------
    size : float
        Position size (units or dollars)
    leverage : float
        Leverage used
    risk_amount : float
        Dollar risk of position
    metadata : dict
        Additional information
    """
    size: float
    leverage: float = 1.0
    risk_amount: float = 0.0
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VolatilityScaler:
    """
    Scale position size by realized volatility.
    
    Inverse volatility scaling: higher volatility → smaller positions.
    
    Parameters
    ----------
    target_volatility : float
        Target position volatility (e.g., 0.01 = 1%)
    lookback : int
        Bars for volatility estimation
    method : str
        Volatility estimation method: 'std', 'ewma', 'parkinson'
    min_observations : int
        Minimum bars required
    
    Example
    -------
    >>> scaler = VolatilityScaler(target_volatility=0.01, lookback=20)
    >>> size = scaler.calculate_size(
    ...     base_size=10000,
    ...     returns=returns_series
    ... )
    """
    
    def __init__(
        self,
        target_volatility: float,
        lookback: int = 20,
        method: Literal['std', 'ewma', 'parkinson'] = 'ewma',
        min_observations: int = 10
    ):
        self.target_volatility = target_volatility
        self.lookback = lookback
        self.method = method
        self.min_observations = min_observations
    
    def estimate_volatility(
        self,
        returns: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None
    ) -> float:
        """
        Estimate realized volatility.
        
        Parameters
        ----------
        returns : pd.Series
            Return series
        high : pd.Series, optional
            High prices (for Parkinson)
        low : pd.Series, optional
            Low prices (for Parkinson)
        
        Returns
        -------
        volatility : float
            Annualized volatility
        """
        if len(returns) < self.min_observations:
            return self.target_volatility  # Default
        
        # Take recent window
        recent_returns = returns.iloc[-self.lookback:]
        
        if self.method == 'std':
            # Simple standard deviation
            vol = recent_returns.std()
        
        elif self.method == 'ewma':
            # Exponentially weighted moving average
            vol = recent_returns.ewm(span=self.lookback).std().iloc[-1]
        
        elif self.method == 'parkinson':
            # Parkinson high-low estimator (more efficient)
            if high is None or low is None:
                raise ValueError("Parkinson method requires high and low prices")
            
            recent_high = high.iloc[-self.lookback:]
            recent_low = low.iloc[-self.lookback:]
            
            hl_ratio = np.log(recent_high / recent_low)
            vol = np.sqrt(1 / (4 * len(hl_ratio) * np.log(2)) * (hl_ratio ** 2).sum())
        
        else:
            raise ValueError(f"Unknown method: {self.method}")
        
        # Annualize (assuming daily returns)
        vol_annualized = vol * np.sqrt(252)
        
        return vol_annualized
    
    def calculate_size(
        self,
        base_size: float,
        returns: pd.Series,
        high: Optional[pd.Series] = None,
        low: Optional[pd.Series] = None
    ) -> PositionSize:
        """
        Calculate volatility-scaled position size.
        
        Parameters
        ----------
        base_size : float
            Base position size
        returns : pd.Series
            Historical returns
        high, low : pd.Series, optional
            High/low prices (for Parkinson)
        
        Returns
        -------
        position_size : PositionSize
            Scaled position size
        """
        realized_vol = self.estimate_volatility(returns, high, low)
        
        # Scale factor: target / realized
        scale_factor = self.target_volatility / realized_vol
        
        # Limit extreme scaling
        scale_factor = np.clip(scale_factor, 0.1, 10.0)
        
        scaled_size = base_size * scale_factor
        
        return PositionSize(
            size=scaled_size,
            risk_amount=scaled_size * realized_vol,
            metadata={
                'target_vol': self.target_volatility,
                'realized_vol': realized_vol,
                'scale_factor': scale_factor,
                'method': self.method
            }
        )


class KellySizer:
    """
    Kelly criterion position sizing.
    
    Optimal sizing based on win rate and payoff ratio.
    
    Parameters
    ----------
    fraction : float
        Kelly fraction (e.g., 0.25 = quarter-Kelly)
    win_rate : float
        Historical win rate
    avg_win : float
        Average win size
    avg_loss : float
        Average loss size
    min_size : float
        Minimum position size
    max_size : float
        Maximum position size
    
    Example
    -------
    >>> sizer = KellySizer(
    ...     fraction=0.25,
    ...     win_rate=0.55,
    ...     avg_win=100,
    ...     avg_loss=80
    ... )
    >>> size = sizer.calculate_size(capital=100000)
    
    References
    ----------
    - Kelly (1956): "A New Interpretation of Information Rate"
    - Thorp (2006): "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market"
    """
    
    def __init__(
        self,
        fraction: float = 0.25,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        min_size: float = 0.0,
        max_size: float = float('inf')
    ):
        if fraction <= 0 or fraction > 1:
            raise ValueError("Kelly fraction must be in (0, 1]")
        
        self.fraction = fraction
        self.win_rate = win_rate
        self.avg_win = avg_win
        self.avg_loss = avg_loss
        self.min_size = min_size
        self.max_size = max_size
    
    def calculate_kelly_fraction(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate optimal Kelly fraction.
        
        Formula: f* = (p*b - q) / b
        where:
          p = win rate
          q = loss rate = 1 - p
          b = avg_win / avg_loss (payoff ratio)
        
        Returns
        -------
        kelly_fraction : float
            Optimal fraction of capital to risk
        """
        if win_rate <= 0 or win_rate >= 1:
            return 0.0
        
        loss_rate = 1 - win_rate
        payoff_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        # Kelly formula
        kelly_f = (win_rate * payoff_ratio - loss_rate) / payoff_ratio
        
        # Kelly can be negative (don't trade) or > 1 (highly leveraged)
        kelly_f = max(0.0, kelly_f)
        kelly_f = min(1.0, kelly_f)  # Cap at 100%
        
        return kelly_f
    
    def calculate_size(
        self,
        capital: float,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None
    ) -> PositionSize:
        """
        Calculate Kelly-optimal position size.
        
        Parameters
        ----------
        capital : float
            Available capital
        win_rate : float, optional
            Win rate (uses default if not provided)
        avg_win : float, optional
            Average win (uses default if not provided)
        avg_loss : float, optional
            Average loss (uses default if not provided)
        
        Returns
        -------
        position_size : PositionSize
            Kelly-optimal size
        """
        # Use provided or default values
        wr = win_rate if win_rate is not None else self.win_rate
        aw = avg_win if avg_win is not None else self.avg_win
        al = avg_loss if avg_loss is not None else self.avg_loss
        
        if wr is None or aw is None or al is None:
            raise ValueError("Must provide win_rate, avg_win, avg_loss")
        
        # Calculate full Kelly
        kelly_f = self.calculate_kelly_fraction(wr, aw, al)
        
        # Apply fraction (e.g., quarter-Kelly)
        adjusted_f = kelly_f * self.fraction
        
        # Calculate size
        size = capital * adjusted_f
        
        # Apply limits
        size = np.clip(size, self.min_size, self.max_size)
        
        return PositionSize(
            size=size,
            leverage=adjusted_f,
            risk_amount=size * (al / aw) if aw > 0 else 0,
            metadata={
                'kelly_fraction': kelly_f,
                'adjusted_fraction': adjusted_f,
                'win_rate': wr,
                'payoff_ratio': aw / al if al > 0 else 0
            }
        )


class FixedFractionalSizer:
    """
    Fixed fraction of capital per trade.
    
    Simple and robust position sizing method.
    
    Parameters
    ----------
    fraction : float
        Fraction of capital per trade (e.g., 0.02 = 2%)
    max_position : float
        Maximum position size (absolute)
    
    Example
    -------
    >>> sizer = FixedFractionalSizer(fraction=0.02, max_position=10000)
    >>> size = sizer.calculate_size(capital=100000)
    >>> print(size.size)  # 2000
    """
    
    def __init__(
        self,
        fraction: float,
        max_position: float = float('inf')
    ):
        if fraction <= 0 or fraction > 1:
            raise ValueError("Fraction must be in (0, 1]")
        
        self.fraction = fraction
        self.max_position = max_position
    
    def calculate_size(self, capital: float) -> PositionSize:
        """
        Calculate fixed fractional size.
        
        Parameters
        ----------
        capital : float
            Available capital
        
        Returns
        -------
        position_size : PositionSize
            Fixed fractional size
        """
        size = capital * self.fraction
        size = min(size, self.max_position)
        
        return PositionSize(
            size=size,
            leverage=self.fraction,
            risk_amount=size,  # Assume full size at risk
            metadata={'fraction': self.fraction}
        )


class RiskParitySizer:
    """
    Risk parity position sizing.
    
    Equal risk contribution across assets.
    
    Parameters
    ----------
    total_risk_budget : float
        Total portfolio risk budget (e.g., 0.10 = 10%)
    volatilities : Dict[str, float]
        Asset volatilities
    
    Example
    -------
    >>> sizer = RiskParitySizer(
    ...     total_risk_budget=0.10,
    ...     volatilities={'BTC': 0.50, 'ETH': 0.60, 'SOL': 0.80}
    ... )
    >>> sizes = sizer.calculate_sizes(capital=100000)
    
    References
    ----------
    - Qian (2005): "Risk Parity Portfolios"
    """
    
    def __init__(
        self,
        total_risk_budget: float,
        volatilities: Dict[str, float]
    ):
        self.total_risk_budget = total_risk_budget
        self.volatilities = volatilities
    
    def calculate_sizes(
        self,
        capital: float
    ) -> Dict[str, PositionSize]:
        """
        Calculate risk parity sizes for all assets.
        
        Formula: weight_i = (1/vol_i) / Σ(1/vol_j)
        
        Parameters
        ----------
        capital : float
            Total capital
        
        Returns
        -------
        sizes : Dict[str, PositionSize]
            Position sizes per asset
        """
        # Calculate inverse volatility weights
        inv_vols = {k: 1 / v for k, v in self.volatilities.items()}
        total_inv_vol = sum(inv_vols.values())
        
        weights = {k: v / total_inv_vol for k, v in inv_vols.items()}
        
        # Scale by risk budget
        sizes = {}
        for symbol, weight in weights.items():
            size = capital * weight * (self.total_risk_budget / self.volatilities[symbol])
            
            sizes[symbol] = PositionSize(
                size=size,
                risk_amount=size * self.volatilities[symbol],
                metadata={
                    'weight': weight,
                    'volatility': self.volatilities[symbol],
                    'risk_contribution': weight * self.volatilities[symbol]
                }
            )
        
        return sizes


@dataclass
class SizingConfig:
    """Configuration for position sizing."""
    method: Literal['volatility_scaled', 'kelly', 'fixed_fractional', 'risk_parity'] = 'volatility_scaled'
    
    # Volatility scaling
    target_volatility: float = 0.01
    lookback: int = 20
    vol_method: str = 'ewma'
    
    # Kelly criterion
    kelly_fraction: float = 0.25
    win_rate: Optional[float] = None
    avg_win: Optional[float] = None
    avg_loss: Optional[float] = None
    
    # Fixed fractional
    fraction: float = 0.02
    
    # Risk parity
    total_risk_budget: float = 0.10
    
    # Common limits
    max_position: float = float('inf')
    max_position_pct: float = 0.20
    min_position: float = 0.0


class PositionSizer:
    """
    Main position sizing orchestrator.
    
    Coordinates different sizing methods and enforces limits.
    
    Parameters
    ----------
    config : SizingConfig
        Sizing configuration
    
    Example
    -------
    >>> config = SizingConfig(
    ...     method='volatility_scaled',
    ...     target_volatility=0.01,
    ...     max_position_pct=0.20
    ... )
    >>> 
    >>> sizer = PositionSizer(config)
    >>> 
    >>> size = sizer.calculate_size(
    ...     capital=100000,
    ...     volatility=0.02,
    ...     returns=returns_series
    ... )
    """
    
    def __init__(self, config: SizingConfig):
        self.config = config
        
        # Initialize sizers based on method
        if config.method == 'volatility_scaled':
            self.sizer = VolatilityScaler(
                target_volatility=config.target_volatility,
                lookback=config.lookback,
                method=config.vol_method
            )
        
        elif config.method == 'kelly':
            self.sizer = KellySizer(
                fraction=config.kelly_fraction,
                win_rate=config.win_rate,
                avg_win=config.avg_win,
                avg_loss=config.avg_loss,
                max_size=config.max_position
            )
        
        elif config.method == 'fixed_fractional':
            self.sizer = FixedFractionalSizer(
                fraction=config.fraction,
                max_position=config.max_position
            )
        
        else:
            raise ValueError(f"Unknown method: {config.method}")
    
    def calculate_size(
        self,
        capital: float,
        volatility: Optional[float] = None,
        returns: Optional[pd.Series] = None,
        win_rate: Optional[float] = None,
        avg_win: Optional[float] = None,
        avg_loss: Optional[float] = None,
        **kwargs
    ) -> PositionSize:
        """
        Calculate position size.
        
        Parameters
        ----------
        capital : float
            Available capital
        volatility : float, optional
            Current volatility (for volatility scaling)
        returns : pd.Series, optional
            Return series (for volatility scaling)
        win_rate : float, optional
            Win rate (for Kelly)
        avg_win : float, optional
            Average win (for Kelly)
        avg_loss : float, optional
            Average loss (for Kelly)
        **kwargs
            Additional method-specific parameters
        
        Returns
        -------
        position_size : PositionSize
            Calculated position size
        """
        # Calculate base size
        if self.config.method == 'volatility_scaled':
            if returns is None:
                raise ValueError("Volatility scaling requires returns series")
            
            base_size = capital * self.config.max_position_pct
            position_size = self.sizer.calculate_size(
                base_size=base_size,
                returns=returns,
                **kwargs
            )
        
        elif self.config.method == 'kelly':
            position_size = self.sizer.calculate_size(
                capital=capital,
                win_rate=win_rate,
                avg_win=avg_win,
                avg_loss=avg_loss
            )
        
        elif self.config.method == 'fixed_fractional':
            position_size = self.sizer.calculate_size(capital)
        
        # Apply global limits
        position_size.size = np.clip(
            position_size.size,
            self.config.min_position,
            capital * self.config.max_position_pct
        )
        
        return position_size


# Export public API
__all__ = [
    'PositionSize',
    'VolatilityScaler',
    'KellySizer',
    'FixedFractionalSizer',
    'RiskParitySizer',
    'SizingConfig',
    'PositionSizer',
]
