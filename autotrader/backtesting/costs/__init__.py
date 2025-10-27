"""
Transaction cost models for realistic backtesting.

This module provides comprehensive cost modeling including:
- Transaction fees (maker/taker, tiered)
- Slippage (fixed, square-root, linear models)
- Bid-ask spread costs
- Overnight financing (funding, borrow, swap rates)

Key Classes
-----------
FeeModel : Transaction fee calculation (maker/taker, tiered pricing)
SlippageModel : Market impact and slippage estimation
SpreadModel : Bid-ask spread cost calculation
OvernightCostModel : Overnight financing costs

References
----------
- Almgren & Chriss (2000): "Optimal execution of portfolio transactions"
- Kyle (1985): "Continuous auctions and insider trading"
- Grinold & Kahn (2000): "Active Portfolio Management"
"""

from typing import Dict, Literal, Optional
import numpy as np
import pandas as pd


class FeeModel:
    """
    Transaction fee model with maker/taker and tiered pricing.
    
    Supports multiple exchanges and VIP tiers with realistic fee schedules.
    
    Parameters
    ----------
    exchange : str
        Exchange name ('binance', 'coinbase', 'kraken', 'custom')
    tier : str
        VIP tier level (exchange-specific)
    fee_structure : str
        Fee structure type ('maker_taker', 'fixed', 'percentage')
    custom_fees : dict, optional
        Custom fee schedule (overrides exchange defaults)
    
    Examples
    --------
    >>> fee_model = FeeModel(exchange='binance', tier='vip_0')
    >>> fee = fee_model.calculate_fee(
    ...     quantity=100,
    ...     price=50.0,
    ...     is_maker=True
    ... )
    >>> print(f"Fee: ${fee:.4f}")
    Fee: $1.0000
    
    References
    ----------
    - Exchange fee schedules (Binance, Coinbase, Kraken)
    """
    
    # Binance fee schedule (as of 2024)
    BINANCE_FEES = {
        'vip_0': {'maker': 0.0002, 'taker': 0.0004},  # 2bps / 4bps
        'vip_1': {'maker': 0.00016, 'taker': 0.00038},
        'vip_2': {'maker': 0.00014, 'taker': 0.00036},
        'vip_3': {'maker': 0.00012, 'taker': 0.00034},
        'vip_4': {'maker': 0.00010, 'taker': 0.00032},
        'vip_5': {'maker': 0.00008, 'taker': 0.00030},
    }
    
    # Coinbase Pro fee schedule
    COINBASE_FEES = {
        'tier_0': {'maker': 0.0050, 'taker': 0.0050},  # 50bps flat
        'tier_1': {'maker': 0.0040, 'taker': 0.0060},
        'tier_2': {'maker': 0.0025, 'taker': 0.0040},
        'tier_3': {'maker': 0.0015, 'taker': 0.0025},
    }
    
    # Kraken fee schedule
    KRAKEN_FEES = {
        'tier_0': {'maker': 0.0016, 'taker': 0.0026},
        'tier_1': {'maker': 0.0014, 'taker': 0.0024},
        'tier_2': {'maker': 0.0012, 'taker': 0.0022},
    }
    
    def __init__(
        self,
        exchange: str = 'binance',
        tier: str = 'vip_0',
        fee_structure: Literal['maker_taker', 'fixed', 'percentage'] = 'maker_taker',
        custom_fees: Optional[Dict[str, float]] = None
    ):
        self.exchange = exchange.lower()
        self.tier = tier
        self.fee_structure = fee_structure
        
        # Load fee schedule
        if custom_fees is not None:
            self.fees = custom_fees
        elif self.exchange == 'binance':
            self.fees = self.BINANCE_FEES.get(tier, self.BINANCE_FEES['vip_0'])
        elif self.exchange == 'coinbase':
            self.fees = self.COINBASE_FEES.get(tier, self.COINBASE_FEES['tier_0'])
        elif self.exchange == 'kraken':
            self.fees = self.KRAKEN_FEES.get(tier, self.KRAKEN_FEES['tier_0'])
        else:
            # Default conservative fees
            self.fees = {'maker': 0.001, 'taker': 0.002}
    
    def calculate_fee(
        self,
        quantity: float,
        price: float,
        is_maker: bool = False
    ) -> float:
        """
        Calculate transaction fee.
        
        Parameters
        ----------
        quantity : float
            Order quantity
        price : float
            Fill price
        is_maker : bool
            Whether order provides liquidity (maker) or takes (taker)
        
        Returns
        -------
        fee : float
            Transaction fee in dollars (positive value)
        """
        notional = quantity * price
        
        if self.fee_structure == 'maker_taker':
            fee_rate = self.fees['maker'] if is_maker else self.fees['taker']
        elif self.fee_structure == 'fixed':
            fee_rate = self.fees.get('fixed', 0.001)
        else:  # percentage
            fee_rate = self.fees.get('percentage', 0.001)
        
        return notional * fee_rate
    
    def get_maker_rebate(
        self,
        quantity: float,
        price: float
    ) -> float:
        """
        Get maker rebate (negative fee for providing liquidity).
        
        Some exchanges provide rebates for maker orders.
        """
        # Check if maker fee is negative (rebate)
        if 'maker' in self.fees and self.fees['maker'] < 0:
            notional = quantity * price
            return abs(self.fees['maker']) * notional
        return 0.0
    
    def get_fee_rate(self, is_maker: bool = False) -> float:
        """Get fee rate as decimal (e.g., 0.001 = 10bps)."""
        if self.fee_structure == 'maker_taker':
            return self.fees['maker'] if is_maker else self.fees['taker']
        return self.fees.get('fixed', 0.001)


class SlippageModel:
    """
    Market impact and slippage estimation.
    
    Implements multiple slippage models:
    - Fixed: Constant basis points
    - Square-root: Almgren-Chriss square-root model
    - Linear: Linear impact proportional to order size
    - LOB-based: Uses actual limit order book depth
    
    Parameters
    ----------
    model : str
        Slippage model ('fixed', 'sqrt', 'linear', 'lob')
    impact_coefficient : float
        Model-specific impact parameter
    volatility_adjusted : bool
        Adjust slippage for volatility
    min_slippage_bps : float
        Minimum slippage in basis points
    max_slippage_bps : float
        Maximum slippage in basis points (cap)
    
    Examples
    --------
    >>> slippage_model = SlippageModel(model='sqrt', impact_coefficient=0.1)
    >>> slippage_bps = slippage_model.calculate_slippage(
    ...     quantity=1000,
    ...     avg_daily_volume=100000,
    ...     current_volatility=0.02
    ... )
    >>> print(f"Slippage: {slippage_bps:.2f} bps")
    Slippage: 6.32 bps
    
    References
    ----------
    - Almgren & Chriss (2000): Square-root market impact model
    - Kyle (1985): Linear price impact
    - Obizhaeva & Wang (2013): Optimal trading
    """
    
    def __init__(
        self,
        model: Literal['fixed', 'sqrt', 'linear', 'lob'] = 'sqrt',
        impact_coefficient: float = 0.1,
        volatility_adjusted: bool = True,
        min_slippage_bps: float = 0.0,
        max_slippage_bps: float = 100.0
    ):
        self.model = model
        self.impact_coefficient = impact_coefficient
        self.volatility_adjusted = volatility_adjusted
        self.min_slippage_bps = min_slippage_bps
        self.max_slippage_bps = max_slippage_bps
    
    def calculate_slippage(
        self,
        quantity: float,
        avg_daily_volume: float,
        current_volatility: float = 0.02,
        side: Literal['buy', 'sell'] = 'buy',
        lob_depth: Optional[float] = None
    ) -> float:
        """
        Calculate slippage in basis points.
        
        Parameters
        ----------
        quantity : float
            Order quantity
        avg_daily_volume : float
            Average daily volume
        current_volatility : float
            Current realized volatility (daily)
        side : str
            Order side ('buy' or 'sell')
        lob_depth : float, optional
            Available liquidity at best levels (for LOB model)
        
        Returns
        -------
        slippage_bps : float
            Slippage in basis points
        """
        if self.model == 'fixed':
            slippage_bps = self.impact_coefficient
        
        elif self.model == 'sqrt':
            # Almgren-Chriss square-root model
            # Slippage ~ σ × sqrt(Q / V)
            participation_rate = quantity / max(avg_daily_volume, 1.0)
            
            if self.volatility_adjusted:
                slippage_bps = (
                    self.impact_coefficient *
                    current_volatility *
                    np.sqrt(participation_rate) *
                    10000  # Convert to bps
                )
            else:
                slippage_bps = (
                    self.impact_coefficient *
                    np.sqrt(participation_rate) *
                    10000
                )
        
        elif self.model == 'linear':
            # Linear impact: Slippage ~ Q / V
            participation_rate = quantity / max(avg_daily_volume, 1.0)
            slippage_bps = (
                self.impact_coefficient *
                participation_rate *
                10000
            )
        
        elif self.model == 'lob':
            # LOB-based: Use actual depth
            if lob_depth is None or lob_depth == 0:
                # Fallback to sqrt model
                participation_rate = quantity / max(avg_daily_volume, 1.0)
                slippage_bps = (
                    self.impact_coefficient *
                    np.sqrt(participation_rate) *
                    10000
                )
            else:
                # Slippage based on depth exhaustion
                depth_ratio = quantity / lob_depth
                slippage_bps = (
                    self.impact_coefficient *
                    depth_ratio *
                    10000
                )
        
        else:
            slippage_bps = 0.0
        
        # Apply bounds
        slippage_bps = max(self.min_slippage_bps, slippage_bps)
        slippage_bps = min(self.max_slippage_bps, slippage_bps)
        
        return slippage_bps
    
    def calculate_slippage_cost(
        self,
        quantity: float,
        price: float,
        avg_daily_volume: float,
        current_volatility: float = 0.02,
        side: Literal['buy', 'sell'] = 'buy'
    ) -> float:
        """
        Calculate slippage cost in dollars.
        
        Parameters
        ----------
        quantity : float
            Order quantity
        price : float
            Fill price
        avg_daily_volume : float
            Average daily volume
        current_volatility : float
            Current volatility
        side : str
            Order side
        
        Returns
        -------
        slippage_cost : float
            Slippage cost in dollars
        """
        slippage_bps = self.calculate_slippage(
            quantity, avg_daily_volume, current_volatility, side
        )
        
        notional = quantity * price
        return notional * (slippage_bps / 10000)


class SpreadModel:
    """
    Bid-ask spread cost model.
    
    Calculates cost of crossing spread for market orders.
    
    Parameters
    ----------
    crossing_assumption : str
        Spread crossing assumption ('full', 'half', 'none')
    spread_estimator : str
        How to estimate spread ('actual', 'roll', 'effective')
    
    Examples
    --------
    >>> spread_model = SpreadModel(crossing_assumption='half')
    >>> cost = spread_model.calculate_cost(
    ...     bid=100.00,
    ...     ask=100.02,
    ...     quantity=100
    ... )
    >>> print(f"Spread cost: ${cost:.2f}")
    Spread cost: $1.00
    """
    
    def __init__(
        self,
        crossing_assumption: Literal['full', 'half', 'none'] = 'half',
        spread_estimator: Literal['actual', 'roll', 'effective'] = 'actual'
    ):
        self.crossing_assumption = crossing_assumption
        self.spread_estimator = spread_estimator
    
    def calculate_cost(
        self,
        bid: float,
        ask: float,
        quantity: float,
        is_aggressive: bool = True
    ) -> float:
        """
        Calculate spread cost.
        
        Parameters
        ----------
        bid : float
            Bid price
        ask : float
            Ask price
        quantity : float
            Order quantity
        is_aggressive : bool
            Whether order takes liquidity (crosses spread)
        
        Returns
        -------
        spread_cost : float
            Spread cost in dollars
        """
        if not is_aggressive:
            return 0.0  # Limit orders don't pay spread
        
        mid = (bid + ask) / 2
        spread = ask - bid
        
        if self.crossing_assumption == 'full':
            # Pessimistic: pay full spread
            cost_per_share = spread
        elif self.crossing_assumption == 'half':
            # Realistic: pay half spread
            cost_per_share = spread / 2
        else:  # none
            cost_per_share = 0.0
        
        return cost_per_share * quantity
    
    def estimate_spread(
        self,
        prices: pd.Series,
        method: str = 'roll'
    ) -> float:
        """
        Estimate bid-ask spread from price series.
        
        Parameters
        ----------
        prices : pd.Series
            Price time series
        method : str
            Estimation method ('roll', 'high_low')
        
        Returns
        -------
        spread : float
            Estimated spread
        
        References
        ----------
        - Roll (1984): "A Simple Implicit Measure of the Effective Bid-Ask Spread"
        """
        if method == 'roll':
            # Roll's estimator: spread = 2 × sqrt(-Cov(ΔP_t, ΔP_{t-1}))
            returns = prices.diff()
            cov = returns.autocorr(lag=1)
            if cov < 0:
                spread = 2 * np.sqrt(-cov * returns.var())
            else:
                spread = 0.0
        
        elif method == 'high_low':
            # High-low spread estimator
            spread = (prices.max() - prices.min()) / prices.mean()
        
        else:
            spread = 0.0
        
        return spread


class OvernightCostModel:
    """
    Overnight financing cost model.
    
    Models costs of holding positions overnight:
    - Crypto: Funding rates (typically 8-hour intervals)
    - Stocks: Borrow costs for shorts
    - Forex: Swap rates (rollover)
    
    Parameters
    ----------
    asset_type : str
        Asset class ('crypto', 'stock', 'forex')
    funding_interval : str
        Funding interval for crypto ('8h', '1h', '4h')
    default_rate : float
        Default funding/borrow rate (annualized)
    
    Examples
    --------
    >>> cost_model = OvernightCostModel(asset_type='crypto')
    >>> cost = cost_model.calculate_cost(
    ...     position_value=10000,
    ...     funding_rate=0.0001,
    ...     hold_time=pd.Timedelta('16h')
    ... )
    >>> print(f"Funding cost: ${cost:.2f}")
    Funding cost: $2.00
    
    References
    ----------
    - Binance funding rate mechanism
    - Interactive Brokers borrow rates
    """
    
    def __init__(
        self,
        asset_type: Literal['crypto', 'stock', 'forex'] = 'crypto',
        funding_interval: str = '8h',
        default_rate: float = 0.0001
    ):
        self.asset_type = asset_type
        self.funding_interval = funding_interval
        self.default_rate = default_rate
        
        # Parse funding interval
        if asset_type == 'crypto':
            self.interval_hours = pd.Timedelta(funding_interval).total_seconds() / 3600
        else:
            self.interval_hours = 24.0  # Daily for stocks/forex
    
    def calculate_cost(
        self,
        position_value: float,
        funding_rate: Optional[float] = None,
        hold_time: pd.Timedelta = pd.Timedelta('1d'),
        is_long: bool = True
    ) -> float:
        """
        Calculate overnight financing cost.
        
        Parameters
        ----------
        position_value : float
            Position value (notional)
        funding_rate : float, optional
            Current funding rate (if None, uses default)
        hold_time : pd.Timedelta
            Holding period
        is_long : bool
            Whether position is long (short pays different rate)
        
        Returns
        -------
        cost : float
            Financing cost in dollars (positive = cost, negative = earned)
        """
        if funding_rate is None:
            funding_rate = self.default_rate
        
        if self.asset_type == 'crypto':
            # Crypto funding: periodic payments
            hold_hours = hold_time.total_seconds() / 3600
            num_funding_periods = hold_hours / self.interval_hours
            
            # Long pays positive funding, receives negative funding
            cost = position_value * funding_rate * num_funding_periods
            if not is_long:
                cost = -cost  # Short has opposite sign
        
        elif self.asset_type == 'stock':
            # Stock borrow cost: annualized rate, compounded daily
            hold_days = hold_time.days + (hold_time.seconds / 86400)
            
            if is_long:
                cost = 0.0  # No borrow cost for longs
            else:
                # Short pays borrow rate
                daily_rate = funding_rate / 365
                cost = position_value * daily_rate * hold_days
        
        elif self.asset_type == 'forex':
            # FX swap/rollover
            hold_days = hold_time.days + (hold_time.seconds / 86400)
            cost = position_value * funding_rate * hold_days / 365
        
        else:
            cost = 0.0
        
        return cost
    
    def get_funding_times(
        self,
        start_time: pd.Timestamp,
        end_time: pd.Timestamp
    ) -> pd.DatetimeIndex:
        """
        Get funding timestamps between start and end times.
        
        Useful for crypto funding schedule (e.g., 00:00, 08:00, 16:00 UTC).
        """
        if self.asset_type != 'crypto':
            return pd.DatetimeIndex([])
        
        # Generate funding times
        freq = self.funding_interval
        funding_times = pd.date_range(
            start=start_time.floor(freq),
            end=end_time,
            freq=freq
        )
        
        # Filter to times within period
        funding_times = funding_times[
            (funding_times >= start_time) & (funding_times <= end_time)
        ]
        
        return funding_times


class TotalCostModel:
    """
    Comprehensive cost model combining all cost components.
    
    Aggregates:
    - Transaction fees
    - Slippage
    - Spread crossing
    - Overnight financing
    
    Parameters
    ----------
    fee_model : FeeModel
        Fee model instance
    slippage_model : SlippageModel
        Slippage model instance
    spread_model : SpreadModel
        Spread model instance
    overnight_model : OvernightCostModel, optional
        Overnight cost model instance
    
    Examples
    --------
    >>> total_cost = TotalCostModel(
    ...     fee_model=FeeModel(exchange='binance'),
    ...     slippage_model=SlippageModel(model='sqrt'),
    ...     spread_model=SpreadModel()
    ... )
    >>> cost = total_cost.calculate_total_cost(
    ...     quantity=100,
    ...     price=50.0,
    ...     is_maker=False,
    ...     avg_daily_volume=10000,
    ...     current_bid=49.99,
    ...     current_ask=50.01
    ... )
    """
    
    def __init__(
        self,
        fee_model: FeeModel,
        slippage_model: SlippageModel,
        spread_model: SpreadModel,
        overnight_model: Optional[OvernightCostModel] = None
    ):
        self.fee_model = fee_model
        self.slippage_model = slippage_model
        self.spread_model = spread_model
        self.overnight_model = overnight_model
    
    def calculate_total_cost(
        self,
        quantity: float,
        price: float,
        is_maker: bool,
        avg_daily_volume: float,
        current_bid: float,
        current_ask: float,
        current_volatility: float = 0.02,
        hold_time: Optional[pd.Timedelta] = None,
        funding_rate: Optional[float] = None
    ) -> Dict[str, float]:
        """
        Calculate total execution cost breakdown.
        
        Returns
        -------
        costs : dict
            Cost breakdown with keys:
            - fee: Transaction fee
            - slippage: Slippage cost
            - spread: Spread cost
            - overnight: Overnight cost (if hold_time provided)
            - total: Sum of all costs
        """
        # Calculate individual costs
        fee = self.fee_model.calculate_fee(quantity, price, is_maker)
        
        slippage = self.slippage_model.calculate_slippage_cost(
            quantity, price, avg_daily_volume, current_volatility
        )
        
        spread_cost = self.spread_model.calculate_cost(
            current_bid, current_ask, quantity, is_aggressive=not is_maker
        )
        
        overnight_cost = 0.0
        if self.overnight_model and hold_time:
            position_value = quantity * price
            overnight_cost = self.overnight_model.calculate_cost(
                position_value, funding_rate, hold_time
            )
        
        return {
            'fee': fee,
            'slippage': slippage,
            'spread': spread_cost,
            'overnight': overnight_cost,
            'total': fee + slippage + spread_cost + overnight_cost
        }


# Export public API
__all__ = [
    'FeeModel',
    'SlippageModel',
    'SpreadModel',
    'OvernightCostModel',
    'TotalCostModel',
]
