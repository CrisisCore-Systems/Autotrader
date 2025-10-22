"""
Multi-Asset Trading Support.

Unified infrastructure for trading across multiple asset classes:
- Equities (existing)
- Cryptocurrencies (existing)
- Forex
- Options
- Futures
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Union
from datetime import datetime, date
import numpy as np
import pandas as pd

from src.core.logging_config import get_logger

logger = get_logger(__name__)


class AssetClass(Enum):
    """Asset class enumeration."""
    EQUITY = "equity"
    CRYPTO = "crypto"
    FOREX = "forex"
    OPTION = "option"
    FUTURE = "future"
    BOND = "bond"


class OptionType(Enum):
    """Option type enumeration."""
    CALL = "call"
    PUT = "put"


@dataclass
class Asset:
    """Base asset representation."""
    symbol: str
    asset_class: AssetClass
    exchange: Optional[str] = None
    currency: str = "USD"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'symbol': self.symbol,
            'asset_class': self.asset_class.value,
            'exchange': self.exchange,
            'currency': self.currency,
        }


@dataclass
class ForexPair(Asset):
    """Forex currency pair."""
    base_currency: str = ""
    quote_currency: str = ""
    pip_size: float = 0.0001  # Standard for most pairs
    
    def __post_init__(self):
        self.asset_class = AssetClass.FOREX
        if not self.symbol:
            self.symbol = f"{self.base_currency}/{self.quote_currency}"
    
    @property
    def inverse_symbol(self) -> str:
        """Get inverse pair symbol."""
        return f"{self.quote_currency}/{self.base_currency}"
    
    def calculate_pip_value(self, position_size: float, account_currency: str = "USD") -> float:
        """
        Calculate pip value for position sizing.
        
        Args:
            position_size: Position size in base currency units
            account_currency: Account currency
        
        Returns:
            Value of one pip movement
        """
        # Simplified calculation - would need exchange rates for full implementation
        if self.quote_currency == account_currency:
            return position_size * self.pip_size
        else:
            # Would need to convert via exchange rate
            logger.warning(f"Cross-currency pip calculation not fully implemented")
            return position_size * self.pip_size


@dataclass
class Option(Asset):
    """Options contract."""
    underlying: str = ""
    option_type: Optional[OptionType] = None
    strike: float = 0.0
    expiration: Optional[date] = None
    multiplier: int = 100  # Standard for equity options
    
    def __post_init__(self):
        self.asset_class = AssetClass.OPTION
        if not self.symbol and self.expiration and self.option_type:
            # OCC format: AAPL250117C00150000
            exp_str = self.expiration.strftime("%y%m%d")
            type_char = "C" if self.option_type == OptionType.CALL else "P"
            strike_str = f"{int(self.strike * 1000):08d}"
            self.symbol = f"{self.underlying}{exp_str}{type_char}{strike_str}"
    
    @property
    def is_call(self) -> bool:
        """Check if this is a call option."""
        return self.option_type == OptionType.CALL
    
    @property
    def is_put(self) -> bool:
        """Check if this is a put option."""
        return self.option_type == OptionType.PUT
    
    def intrinsic_value(self, underlying_price: float) -> float:
        """
        Calculate intrinsic value.
        
        Args:
            underlying_price: Current price of underlying asset
        
        Returns:
            Intrinsic value (always >= 0)
        """
        if self.is_call:
            return max(0, underlying_price - self.strike)
        else:
            return max(0, self.strike - underlying_price)
    
    def is_in_the_money(self, underlying_price: float) -> bool:
        """Check if option is in the money."""
        return self.intrinsic_value(underlying_price) > 0
    
    def moneyness(self, underlying_price: float) -> float:
        """
        Calculate moneyness (S/K for calls, K/S for puts).
        
        Returns:
            Moneyness ratio
        """
        if self.is_call:
            return underlying_price / self.strike
        else:
            return self.strike / underlying_price
    
    def days_to_expiration(self, current_date: Optional[date] = None) -> int:
        """Calculate days until expiration."""
        if current_date is None:
            current_date = date.today()
        return (self.expiration - current_date).days


@dataclass
class MarketData:
    """Unified market data structure."""
    asset: Asset
    timestamp: datetime
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None  # For options/futures
    
    @property
    def mid_price(self) -> float:
        """Get mid price between bid and ask."""
        if self.bid is not None and self.ask is not None:
            return (self.bid + self.ask) / 2
        return self.price
    
    @property
    def spread(self) -> Optional[float]:
        """Get bid-ask spread."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None
    
    @property
    def spread_bps(self) -> Optional[float]:
        """Get spread in basis points."""
        if self.spread is not None and self.mid_price > 0:
            return (self.spread / self.mid_price) * 10000
        return None


@dataclass
class Greeks:
    """Option Greeks for risk management."""
    delta: float  # Price sensitivity
    gamma: float  # Delta sensitivity
    theta: float  # Time decay
    vega: float   # Volatility sensitivity
    rho: float    # Interest rate sensitivity
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'delta': self.delta,
            'gamma': self.gamma,
            'theta': self.theta,
            'vega': self.vega,
            'rho': self.rho,
        }


class BlackScholesCalculator:
    """
    Black-Scholes option pricing and Greeks calculation.
    
    Simplified implementation for basic option valuation.
    """
    
    @staticmethod
    def calculate_d1_d2(
        S: float,  # Spot price
        K: float,  # Strike price
        T: float,  # Time to maturity (years)
        r: float,  # Risk-free rate
        sigma: float,  # Volatility
    ) -> Tuple[float, float]:
        """Calculate d1 and d2 parameters."""
        if T <= 0:
            return 0.0, 0.0
        
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        return d1, d2
    
    @staticmethod
    def calculate_option_price(
        option_type: OptionType,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> float:
        """
        Calculate option price using Black-Scholes.
        
        Args:
            option_type: Call or Put
            S: Spot price
            K: Strike price
            T: Time to maturity (years)
            r: Risk-free rate
            sigma: Volatility (annualized)
        
        Returns:
            Option price
        """
        if T <= 0:
            # At expiration, return intrinsic value
            if option_type == OptionType.CALL:
                return max(0, S - K)
            else:
                return max(0, K - S)
        
        from scipy.stats import norm
        
        d1, d2 = BlackScholesCalculator.calculate_d1_d2(S, K, T, r, sigma)
        
        if option_type == OptionType.CALL:
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        return price
    
    @staticmethod
    def calculate_greeks(
        option_type: OptionType,
        S: float,
        K: float,
        T: float,
        r: float,
        sigma: float,
    ) -> Greeks:
        """
        Calculate option Greeks.
        
        Returns:
            Greeks object with all sensitivities
        """
        if T <= 0:
            return Greeks(delta=0, gamma=0, theta=0, vega=0, rho=0)
        
        from scipy.stats import norm
        
        d1, d2 = BlackScholesCalculator.calculate_d1_d2(S, K, T, r, sigma)
        
        # Delta
        if option_type == OptionType.CALL:
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        
        # Gamma (same for calls and puts)
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        
        # Theta
        theta_common = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        if option_type == OptionType.CALL:
            theta = theta_common - r * K * np.exp(-r * T) * norm.cdf(d2)
        else:
            theta = theta_common + r * K * np.exp(-r * T) * norm.cdf(-d2)
        
        # Theta is typically expressed per day
        theta = theta / 365
        
        # Vega (same for calls and puts)
        vega = S * norm.pdf(d1) * np.sqrt(T)
        
        # Vega is typically expressed per 1% change in volatility
        vega = vega / 100
        
        # Rho
        if option_type == OptionType.CALL:
            rho = K * T * np.exp(-r * T) * norm.cdf(d2)
        else:
            rho = -K * T * np.exp(-r * T) * norm.cdf(-d2)
        
        # Rho is typically expressed per 1% change in interest rate
        rho = rho / 100
        
        return Greeks(
            delta=delta,
            gamma=gamma,
            theta=theta,
            vega=vega,
            rho=rho,
        )


class ImpliedVolatilityCalculator:
    """Calculate implied volatility from option prices."""
    
    @staticmethod
    def calculate_iv(
        option_type: OptionType,
        option_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        initial_guess: float = 0.3,
        tolerance: float = 0.0001,
        max_iterations: int = 100,
    ) -> Optional[float]:
        """
        Calculate implied volatility using Newton-Raphson method.
        
        Args:
            option_type: Call or Put
            option_price: Market price of option
            S: Spot price
            K: Strike price
            T: Time to maturity (years)
            r: Risk-free rate
            initial_guess: Starting volatility guess
            tolerance: Convergence tolerance
            max_iterations: Maximum iterations
        
        Returns:
            Implied volatility or None if convergence fails
        """
        if T <= 0:
            return None
        
        sigma = initial_guess
        
        for i in range(max_iterations):
            # Calculate price and vega at current sigma
            price = BlackScholesCalculator.calculate_option_price(
                option_type, S, K, T, r, sigma
            )
            
            greeks = BlackScholesCalculator.calculate_greeks(
                option_type, S, K, T, r, sigma
            )
            
            vega = greeks.vega * 100  # Convert back from per 1%
            
            # Check for convergence
            diff = option_price - price
            if abs(diff) < tolerance:
                return sigma
            
            # Newton-Raphson update
            if vega > 0:
                sigma = sigma + diff / vega
            else:
                logger.warning("Vega is zero, cannot converge")
                return None
            
            # Ensure sigma stays positive
            sigma = max(0.001, sigma)
        
        logger.warning(f"IV calculation did not converge after {max_iterations} iterations")
        return None


class CorrelationAnalyzer:
    """Analyze correlations across multiple asset classes."""
    
    @staticmethod
    def calculate_cross_asset_correlation(
        returns_dict: Dict[str, pd.Series],
        window: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix across assets.
        
        Args:
            returns_dict: Dict mapping asset symbols to return series
            window: Rolling window (None for full period)
        
        Returns:
            Correlation matrix
        """
        # Combine into DataFrame
        returns_df = pd.DataFrame(returns_dict)
        
        if window is not None:
            # Rolling correlation
            correlation = returns_df.rolling(window=window).corr()
        else:
            # Full period correlation
            correlation = returns_df.corr()
        
        return correlation
    
    @staticmethod
    def detect_correlation_regime(
        correlation_matrix: pd.DataFrame,
        threshold: float = 0.7,
    ) -> str:
        """
        Detect correlation regime (crisis vs normal).
        
        High average correlation suggests crisis/stress.
        
        Args:
            correlation_matrix: Correlation matrix
            threshold: Threshold for high correlation
        
        Returns:
            Regime classification
        """
        # Calculate average absolute correlation (excluding diagonal)
        mask = ~np.eye(correlation_matrix.shape[0], dtype=bool)
        avg_corr = np.abs(correlation_matrix.values[mask]).mean()
        
        if avg_corr >= threshold:
            return "CRISIS"
        elif avg_corr >= 0.5:
            return "ELEVATED"
        else:
            return "NORMAL"


class AssetUniverseManager:
    """Manage multi-asset universe and filtering."""
    
    def __init__(self):
        self.assets: Dict[str, Asset] = {}
        self.asset_classes: Dict[AssetClass, List[str]] = {
            ac: [] for ac in AssetClass
        }
    
    def add_asset(self, asset: Asset):
        """Add asset to universe."""
        self.assets[asset.symbol] = asset
        self.asset_classes[asset.asset_class].append(asset.symbol)
        logger.debug(f"Added {asset.asset_class.value} asset: {asset.symbol}")
    
    def get_assets_by_class(self, asset_class: AssetClass) -> List[Asset]:
        """Get all assets of a specific class."""
        symbols = self.asset_classes.get(asset_class, [])
        return [self.assets[s] for s in symbols if s in self.assets]
    
    def get_asset(self, symbol: str) -> Optional[Asset]:
        """Get asset by symbol."""
        return self.assets.get(symbol)
    
    def filter_assets(
        self,
        asset_classes: Optional[List[AssetClass]] = None,
        min_liquidity: Optional[float] = None,
        currencies: Optional[List[str]] = None,
    ) -> List[Asset]:
        """
        Filter assets by criteria.
        
        Args:
            asset_classes: List of allowed asset classes
            min_liquidity: Minimum liquidity threshold
            currencies: List of allowed currencies
        
        Returns:
            Filtered list of assets
        """
        filtered = list(self.assets.values())
        
        if asset_classes:
            filtered = [a for a in filtered if a.asset_class in asset_classes]
        
        if currencies:
            filtered = [a for a in filtered if a.currency in currencies]
        
        # Additional filters would go here (liquidity, etc.)
        
        return filtered
    
    def get_summary(self) -> Dict[str, int]:
        """Get summary of universe by asset class."""
        return {
            ac.value: len(symbols)
            for ac, symbols in self.asset_classes.items()
            if symbols
        }
