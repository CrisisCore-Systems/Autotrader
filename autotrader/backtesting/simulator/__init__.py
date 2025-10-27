"""
Order execution simulator with realistic assumptions.

This module provides tools for simulating order fills in backtesting with
realistic latency, partial fills, and market microstructure effects.

Key Classes
-----------
OrderSimulator : Main simulator with quote-based and LOB-based fills
LatencyModel : Realistic latency modeling (signal-to-fill)
FillSimulation : Result of order simulation

References
----------
- Almgren & Chriss (2000): "Optimal execution of portfolio transactions"
- Kyle (1985): "Continuous auctions and insider trading"
- Hasbrouck (2007): "Empirical Market Microstructure"
"""

from dataclasses import dataclass, field
from typing import Optional, Literal, Dict, List, Tuple
import pandas as pd
import numpy as np
from decimal import Decimal


@dataclass
class FillSimulation:
    """
    Result of order fill simulation.
    
    Attributes
    ----------
    fill_price : float
        Actual fill price
    fill_quantity : float
        Quantity filled
    remaining_quantity : float
        Unfilled quantity (for partial fills)
    fill_time : pd.Timestamp
        Fill timestamp (includes latency)
    is_filled : bool
        Whether order was filled
    is_partial : bool
        Whether fill was partial
    commission : float
        Transaction commission (calculated by fee model)
    slippage : float
        Slippage cost in dollars
    market_impact : float
        Market impact cost in dollars
    
    Examples
    --------
    >>> fill = FillSimulation(
    ...     fill_price=100.05,
    ...     fill_quantity=100,
    ...     remaining_quantity=0,
    ...     fill_time=pd.Timestamp('2024-01-01 00:00:00.060'),
    ...     is_filled=True,
    ...     is_partial=False,
    ...     commission=0.04,
    ...     slippage=0.50,
    ...     market_impact=0.25
    ... )
    """
    fill_price: float
    fill_quantity: float
    remaining_quantity: float
    fill_time: pd.Timestamp
    is_filled: bool
    is_partial: bool = False
    commission: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    
    def total_cost(self) -> float:
        """Get total execution cost (commission + slippage + impact)."""
        return self.commission + self.slippage + self.market_impact
    
    def effective_price(self) -> float:
        """
        Get effective price including costs.
        
        Effective price = fill price + (total cost / quantity)
        """
        if self.fill_quantity == 0:
            return 0.0
        return self.fill_price + (self.total_cost() / self.fill_quantity)


@dataclass
class LOBSnapshot:
    """
    Limit order book snapshot.
    
    Attributes
    ----------
    bids : List[Tuple[float, float]]
        Bid levels as (price, quantity) tuples
    asks : List[Tuple[float, float]]
        Ask levels as (price, quantity) tuples
    timestamp : pd.Timestamp
        Snapshot timestamp
    """
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]
    timestamp: pd.Timestamp
    
    def get_best_bid(self) -> float:
        """Get best bid price."""
        return self.bids[0][0] if self.bids else 0.0
    
    def get_best_ask(self) -> float:
        """Get best ask price."""
        return self.asks[0][0] if self.asks else 0.0
    
    def get_mid_price(self) -> float:
        """Get mid price."""
        return (self.get_best_bid() + self.get_best_ask()) / 2
    
    def get_spread(self) -> float:
        """Get bid-ask spread."""
        return self.get_best_ask() - self.get_best_bid()
    
    def get_total_bid_depth(self, levels: int = 5) -> float:
        """Get total bid depth (quantity) for top N levels."""
        return sum(qty for _, qty in self.bids[:levels])
    
    def get_total_ask_depth(self, levels: int = 5) -> float:
        """Get total ask depth (quantity) for top N levels."""
        return sum(qty for _, qty in self.asks[:levels])


class LatencyModel:
    """
    Realistic latency modeling for order execution.
    
    Models end-to-end latency from signal generation to order fill:
    1. Signal-to-order: Strategy computation + decision time
    2. Network latency: One-way network delay to exchange
    3. Exchange processing: Order matching and execution
    4. Market data delay: Quote age/staleness
    
    Parameters
    ----------
    signal_to_order : float
        Time from signal to order submission (milliseconds)
    network_latency : float
        One-way network latency (milliseconds)
    exchange_processing : float
        Exchange order processing time (milliseconds)
    market_data_delay : float
        Market data staleness (milliseconds)
    jitter : float
        Random jitter standard deviation (milliseconds)
    
    Examples
    --------
    >>> latency_model = LatencyModel(
    ...     signal_to_order=10.0,
    ...     network_latency=30.0,
    ...     exchange_processing=20.0
    ... )
    >>> latency_model.get_total_latency()
    60.0
    
    References
    ----------
    - Hasbrouck & Saar (2013): "Low-latency trading"
    """
    
    def __init__(
        self,
        signal_to_order: float = 10.0,
        network_latency: float = 30.0,
        exchange_processing: float = 20.0,
        market_data_delay: float = 5.0,
        jitter: float = 5.0
    ):
        self.signal_to_order = signal_to_order
        self.network_latency = network_latency
        self.exchange_processing = exchange_processing
        self.market_data_delay = market_data_delay
        self.jitter = jitter
    
    def get_total_latency(self, include_jitter: bool = False) -> float:
        """
        Get total one-way latency in milliseconds.
        
        Parameters
        ----------
        include_jitter : bool
            Whether to include random jitter
        
        Returns
        -------
        latency_ms : float
            Total latency in milliseconds
        """
        base_latency = (
            self.signal_to_order +
            self.network_latency +
            self.exchange_processing
        )
        
        if include_jitter and self.jitter > 0:
            jitter_component = np.random.normal(0, self.jitter)
            return max(0, base_latency + jitter_component)
        
        return base_latency
    
    def apply_latency(
        self,
        timestamp: pd.Timestamp,
        include_jitter: bool = True
    ) -> pd.Timestamp:
        """
        Apply latency to timestamp.
        
        Parameters
        ----------
        timestamp : pd.Timestamp
            Original signal timestamp
        include_jitter : bool
            Whether to include random jitter
        
        Returns
        -------
        delayed_timestamp : pd.Timestamp
            Timestamp after latency applied
        """
        latency_ms = self.get_total_latency(include_jitter=include_jitter)
        return timestamp + pd.Timedelta(milliseconds=latency_ms)
    
    def get_market_data_staleness(self) -> pd.Timedelta:
        """Get market data staleness as Timedelta."""
        return pd.Timedelta(milliseconds=self.market_data_delay)


class OrderSimulator:
    """
    Simulates realistic order fills for backtesting.
    
    Features:
    - Quote-based fills: Simple bid/ask-based simulation
    - LOB-based fills: Depth-aware simulation with market impact
    - Latency modeling: Realistic delays from signal to fill
    - Partial fills: Support for partial execution
    - Conservative assumptions: Crosses spread, takes liquidity
    
    Parameters
    ----------
    fill_method : str
        Fill simulation method ('quote_based' or 'lob_based')
    latency_model : LatencyModel, optional
        Latency model to use
    conservative : bool
        Use conservative assumptions (cross spread, pay impact)
    allow_partial_fills : bool
        Allow partial fills based on liquidity
    min_fill_ratio : float
        Minimum fill ratio for partial fills (0.0-1.0)
    
    Examples
    --------
    >>> simulator = OrderSimulator(fill_method='quote_based')
    >>> fill = simulator.simulate_fill(
    ...     order_type='market',
    ...     side='buy',
    ...     quantity=100,
    ...     price=None,
    ...     current_bid=100.00,
    ...     current_ask=100.02,
    ...     timestamp=pd.Timestamp('2024-01-01')
    ... )
    >>> print(f"Filled at {fill.fill_price}")
    Filled at 100.02
    
    References
    ----------
    - Almgren & Chriss (2000): Optimal execution models
    - Kyle (1985): Market microstructure theory
    """
    
    def __init__(
        self,
        fill_method: Literal['quote_based', 'lob_based'] = 'quote_based',
        latency_model: Optional[LatencyModel] = None,
        conservative: bool = True,
        allow_partial_fills: bool = False,
        min_fill_ratio: float = 0.5
    ):
        self.fill_method = fill_method
        self.latency_model = latency_model or LatencyModel()
        self.conservative = conservative
        self.allow_partial_fills = allow_partial_fills
        self.min_fill_ratio = min_fill_ratio
        
        # Track order history for analysis
        self.fill_history: List[FillSimulation] = []
    
    def simulate_fill(
        self,
        order_type: Literal['market', 'limit'],
        side: Literal['buy', 'sell'],
        quantity: float,
        price: Optional[float],
        current_bid: float,
        current_ask: float,
        timestamp: pd.Timestamp,
        lob_snapshot: Optional[LOBSnapshot] = None,
        avg_daily_volume: Optional[float] = None,
        **kwargs
    ) -> FillSimulation:
        """
        Simulate order fill.
        
        Parameters
        ----------
        order_type : str
            'market' or 'limit'
        side : str
            'buy' or 'sell'
        quantity : float
            Order quantity
        price : float, optional
            Limit price (for limit orders)
        current_bid : float
            Current best bid price
        current_ask : float
            Current best ask price
        timestamp : pd.Timestamp
            Order timestamp
        lob_snapshot : LOBSnapshot, optional
            Full LOB snapshot (for lob_based method)
        avg_daily_volume : float, optional
            Average daily volume (for market impact)
        
        Returns
        -------
        fill : FillSimulation
            Fill simulation result
        """
        # Apply latency
        fill_time = self.latency_model.apply_latency(timestamp)
        
        # Simulate fill based on method and order type
        if self.fill_method == 'quote_based':
            if order_type == 'market':
                fill = self._simulate_market_order_quote(
                    side, quantity, current_bid, current_ask, fill_time,
                    avg_daily_volume
                )
            else:  # limit
                fill = self._simulate_limit_order_quote(
                    side, quantity, price, current_bid, current_ask, fill_time
                )
        
        else:  # lob_based
            if lob_snapshot is None:
                raise ValueError("lob_snapshot required for lob_based simulation")
            
            if order_type == 'market':
                fill = self._simulate_market_order_lob(
                    side, quantity, lob_snapshot, fill_time, avg_daily_volume
                )
            else:  # limit
                fill = self._simulate_limit_order_lob(
                    side, quantity, price, lob_snapshot, fill_time
                )
        
        # Record fill
        self.fill_history.append(fill)
        
        return fill
    
    def _simulate_market_order_quote(
        self,
        side: str,
        quantity: float,
        bid: float,
        ask: float,
        fill_time: pd.Timestamp,
        avg_daily_volume: Optional[float] = None
    ) -> FillSimulation:
        """
        Simulate market order with quote-based method.
        
        Conservative assumptions:
        - Buy market orders take ask (cross spread)
        - Sell market orders take bid
        - Pay half-spread as slippage
        - Additional market impact if order is large
        """
        mid = (bid + ask) / 2
        half_spread = (ask - bid) / 2
        
        if side == 'buy':
            fill_price = ask  # Take liquidity at ask
            slippage = half_spread * quantity  # Pay half spread
        else:  # sell
            fill_price = bid  # Take liquidity at bid
            slippage = half_spread * quantity
        
        # Estimate market impact
        market_impact = 0.0
        if avg_daily_volume is not None and avg_daily_volume > 0:
            participation_rate = quantity / avg_daily_volume
            # Simple square-root impact model
            impact_bps = 10 * np.sqrt(participation_rate)  # 10bps per sqrt(participation)
            market_impact = fill_price * quantity * (impact_bps / 10000)
            
            # Adjust fill price for impact
            if side == 'buy':
                fill_price += (market_impact / quantity)
            else:
                fill_price -= (market_impact / quantity)
        
        return FillSimulation(
            fill_price=fill_price,
            fill_quantity=quantity,
            remaining_quantity=0.0,
            fill_time=fill_time,
            is_filled=True,
            is_partial=False,
            commission=0.0,  # Calculated by fee model
            slippage=slippage,
            market_impact=market_impact
        )
    
    def _simulate_limit_order_quote(
        self,
        side: str,
        quantity: float,
        price: float,
        bid: float,
        ask: float,
        fill_time: pd.Timestamp
    ) -> FillSimulation:
        """
        Simulate limit order with quote-based method.
        
        Fill logic:
        - Buy limit fills if bid >= limit price (aggressive fill)
        - Sell limit fills if ask <= limit price
        - Conservative: requires price improvement for fill
        """
        # Check if limit order would fill
        if side == 'buy':
            # Buy limit needs bid to reach limit (someone willing to sell at/below limit)
            would_fill = bid >= price
            fill_price = price if would_fill else 0.0
        else:  # sell
            # Sell limit needs ask to reach limit (someone willing to buy at/above limit)
            would_fill = ask <= price
            fill_price = price if would_fill else 0.0
        
        if not would_fill:
            return FillSimulation(
                fill_price=0.0,
                fill_quantity=0.0,
                remaining_quantity=quantity,
                fill_time=fill_time,
                is_filled=False,
                is_partial=False,
                commission=0.0,
                slippage=0.0,
                market_impact=0.0
            )
        
        # Limit orders provide liquidity (no slippage, may get rebate)
        return FillSimulation(
            fill_price=fill_price,
            fill_quantity=quantity,
            remaining_quantity=0.0,
            fill_time=fill_time,
            is_filled=True,
            is_partial=False,
            commission=0.0,
            slippage=0.0,  # Providing liquidity
            market_impact=0.0
        )
    
    def _simulate_market_order_lob(
        self,
        side: str,
        quantity: float,
        lob: LOBSnapshot,
        fill_time: pd.Timestamp,
        avg_daily_volume: Optional[float] = None
    ) -> FillSimulation:
        """
        Simulate market order with LOB-based method.
        
        Walks through LOB levels, consuming liquidity at each level
        until order is filled or partial fill occurs.
        """
        remaining_qty = quantity
        total_cost = 0.0
        levels_consumed = []
        
        # Get relevant side of book
        book_levels = lob.asks if side == 'buy' else lob.bids
        
        # Walk through book levels
        for level_price, level_qty in book_levels:
            if remaining_qty <= 0:
                break
            
            # Fill at this level
            fill_qty = min(remaining_qty, level_qty)
            total_cost += fill_qty * level_price
            remaining_qty -= fill_qty
            levels_consumed.append((level_price, fill_qty))
            
            # Check if partial fill should occur
            if self.allow_partial_fills:
                filled_ratio = (quantity - remaining_qty) / quantity
                if filled_ratio < self.min_fill_ratio:
                    # Not enough liquidity for minimum fill
                    continue
        
        # Calculate average fill price
        filled_qty = quantity - remaining_qty
        if filled_qty == 0:
            return FillSimulation(
                fill_price=0.0,
                fill_quantity=0.0,
                remaining_quantity=quantity,
                fill_time=fill_time,
                is_filled=False,
                is_partial=False,
                commission=0.0,
                slippage=0.0,
                market_impact=0.0
            )
        
        avg_fill_price = total_cost / filled_qty
        
        # Calculate slippage (difference from mid)
        mid_price = lob.get_mid_price()
        if side == 'buy':
            slippage_per_share = avg_fill_price - mid_price
        else:
            slippage_per_share = mid_price - avg_fill_price
        slippage = slippage_per_share * filled_qty
        
        # Estimate market impact
        market_impact = 0.0
        if avg_daily_volume is not None and avg_daily_volume > 0:
            participation_rate = filled_qty / avg_daily_volume
            impact_bps = 10 * np.sqrt(participation_rate)
            market_impact = avg_fill_price * filled_qty * (impact_bps / 10000)
        
        is_partial = remaining_qty > 0
        
        return FillSimulation(
            fill_price=avg_fill_price,
            fill_quantity=filled_qty,
            remaining_quantity=remaining_qty,
            fill_time=fill_time,
            is_filled=True,
            is_partial=is_partial,
            commission=0.0,
            slippage=slippage,
            market_impact=market_impact
        )
    
    def _simulate_limit_order_lob(
        self,
        side: str,
        quantity: float,
        price: float,
        lob: LOBSnapshot,
        fill_time: pd.Timestamp
    ) -> FillSimulation:
        """
        Simulate limit order with LOB-based method.
        
        Checks if limit price would be filled given current LOB state.
        """
        best_bid = lob.get_best_bid()
        best_ask = lob.get_best_ask()
        
        # Same logic as quote-based for limit orders
        if side == 'buy':
            would_fill = best_bid >= price
        else:
            would_fill = best_ask <= price
        
        if not would_fill:
            return FillSimulation(
                fill_price=0.0,
                fill_quantity=0.0,
                remaining_quantity=quantity,
                fill_time=fill_time,
                is_filled=False,
                is_partial=False,
                commission=0.0,
                slippage=0.0,
                market_impact=0.0
            )
        
        return FillSimulation(
            fill_price=price,
            fill_quantity=quantity,
            remaining_quantity=0.0,
            fill_time=fill_time,
            is_filled=True,
            is_partial=False,
            commission=0.0,
            slippage=0.0,
            market_impact=0.0
        )
    
    def get_fill_statistics(self) -> Dict[str, float]:
        """
        Get statistics on fill history.
        
        Returns
        -------
        stats : dict
            Fill statistics including:
            - total_fills: Number of fills
            - fill_rate: Percentage of orders filled
            - partial_fill_rate: Percentage of partial fills
            - avg_slippage: Average slippage per fill
            - avg_impact: Average market impact per fill
        """
        if not self.fill_history:
            return {
                'total_fills': 0,
                'fill_rate': 0.0,
                'partial_fill_rate': 0.0,
                'avg_slippage': 0.0,
                'avg_impact': 0.0
            }
        
        filled = [f for f in self.fill_history if f.is_filled]
        partial = [f for f in self.fill_history if f.is_partial]
        
        total_slippage = sum(f.slippage for f in filled)
        total_impact = sum(f.market_impact for f in filled)
        
        return {
            'total_fills': len(filled),
            'fill_rate': len(filled) / len(self.fill_history),
            'partial_fill_rate': len(partial) / len(filled) if filled else 0.0,
            'avg_slippage': total_slippage / len(filled) if filled else 0.0,
            'avg_impact': total_impact / len(filled) if filled else 0.0
        }
    
    def reset_history(self):
        """Reset fill history."""
        self.fill_history = []


# Export public API
__all__ = [
    'OrderSimulator',
    'LatencyModel',
    'FillSimulation',
    'LOBSnapshot',
]
