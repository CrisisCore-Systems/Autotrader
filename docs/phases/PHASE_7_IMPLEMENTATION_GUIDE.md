# Phase 7: Backtesting - Implementation Guide

## Overview

This document provides the complete implementation guide for Phase 7. Due to the complexity (~5,000+ lines of code), this guide focuses on:

1. **Architecture Overview**
2. **Key Implementation Patterns**
3. **Critical Code Samples**
4. **Integration with Phases 5-6**
5. **Testing and Validation**

---

## Implementation Status

### ✅ Completed (Specification & Architecture)
- Complete specification document (900+ lines)
- Architecture design
- Module structure
- API design
- Integration patterns

### 🔨 To Implement (~5,000 lines)
1. **Order Simulator** (~800 lines)
   - Quote-based fills
   - LOB simulator
   - Latency modeling
   - Partial fills

2. **Cost Models** (~600 lines)
   - Fee models (maker/taker, tiered)
   - Slippage models (fixed, sqrt, linear, LOB-based)
   - Spread models
   - Overnight costs (funding, borrow)

3. **Backtesting Engine** (~1,200 lines)
   - Event-driven architecture
   - Portfolio tracking
   - Order management
   - Risk management
   - PnL calculation

4. **Walk-Forward Evaluation** (~800 lines)
   - Rolling windows
   - Stability metrics
   - Regime analysis
   - Performance attribution

5. **Reporting System** (~1,000 lines)
   - Tear sheet generation
   - Trade analysis
   - Visualizations
   - HTML/PDF reports

6. **Testing** (~600 lines)
   - Unit tests
   - Integration tests
   - Validation tests

---

## Quick Start Pattern

### Minimal Working Example

```python
# 1. Setup
from autotrader.backtesting import BacktestEngine, OrderSimulator, FeeModel

engine = BacktestEngine(
    initial_capital=100000,
    simulator=OrderSimulator(fill_method='quote_based'),
    fee_model=FeeModel(exchange='binance')
)

# 2. Define Strategy
class SimpleStrategy:
    def generate_signals(self, data):
        # Your logic here
        signals = pd.Series(0, index=data.index)
        signals[data['signal'] > 0.6] = 1  # Buy
        signals[data['signal'] < 0.4] = -1  # Sell
        return signals

strategy = SimpleStrategy()

# 3. Run Backtest
results = engine.run(
    strategy=strategy,
    data=market_data,
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# 4. Analyze Results
print(f"Total Return: {results.total_return:.2%}")
print(f"Sharpe Ratio: {results.sharpe:.2f}")
print(f"Max Drawdown: {results.max_drawdown:.2%}")
```

---

## Core Implementation Patterns

### 1. Order Simulator Pattern

```python
# simulator/__init__.py
from dataclasses import dataclass
from typing import Optional, Literal
import pandas as pd
import numpy as np

@dataclass
class FillSimulation:
    """Result of fill simulation."""
    fill_price: float
    fill_quantity: float
    fill_time: pd.Timestamp
    is_filled: bool
    commission: float
    slippage: float
    
class LatencyModel:
    """Models realistic latency."""
    
    def __init__(
        self,
        signal_to_order: float = 10.0,  # ms
        network_latency: float = 30.0,   # ms
        exchange_processing: float = 20.0,  # ms
        market_data_delay: float = 5.0   # ms
    ):
        self.signal_to_order = signal_to_order
        self.network_latency = network_latency
        self.exchange_processing = exchange_processing
        self.market_data_delay = market_data_delay
    
    def get_total_latency(self) -> float:
        """Get total one-way latency in ms."""
        return (
            self.signal_to_order +
            self.network_latency +
            self.exchange_processing
        )
    
    def apply_latency(self, timestamp: pd.Timestamp) -> pd.Timestamp:
        """Apply latency to timestamp."""
        latency_ms = self.get_total_latency()
        return timestamp + pd.Timedelta(milliseconds=latency_ms)

class OrderSimulator:
    """
    Simulates order fills with realistic assumptions.
    
    Conservative assumptions:
    - Market orders cross spread (take liquidity)
    - Limit orders require price improvement
    - Latency between signal and fill
    - Partial fills possible
    """
    
    def __init__(
        self,
        fill_method: Literal['quote_based', 'lob_based'] = 'quote_based',
        latency_model: Optional[LatencyModel] = None,
        conservative: bool = True
    ):
        self.fill_method = fill_method
        self.latency_model = latency_model or LatencyModel()
        self.conservative = conservative
    
    def simulate_fill(
        self,
        order_type: Literal['market', 'limit'],
        side: Literal['buy', 'sell'],
        quantity: float,
        price: Optional[float],
        current_bid: float,
        current_ask: float,
        timestamp: pd.Timestamp,
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
            Current bid price
        current_ask : float
            Current ask price
        timestamp : pd.Timestamp
            Order timestamp
        
        Returns
        -------
        FillSimulation
            Fill simulation result
        """
        # Apply latency
        fill_time = self.latency_model.apply_latency(timestamp)
        
        # Simulate fill based on order type
        if order_type == 'market':
            return self._simulate_market_order(
                side, quantity, current_bid, current_ask, fill_time
            )
        else:  # limit
            return self._simulate_limit_order(
                side, quantity, price, current_bid, current_ask, fill_time
            )
    
    def _simulate_market_order(
        self,
        side: str,
        quantity: float,
        bid: float,
        ask: float,
        fill_time: pd.Timestamp
    ) -> FillSimulation:
        """Simulate market order fill."""
        # Conservative: assume crossing spread
        if side == 'buy':
            fill_price = ask  # Take liquidity at ask
            slippage = (ask - (bid + ask) / 2)  # Half-spread slippage
        else:  # sell
            fill_price = bid  # Take liquidity at bid
            slippage = ((bid + ask) / 2 - bid)  # Half-spread slippage
        
        return FillSimulation(
            fill_price=fill_price,
            fill_quantity=quantity,
            fill_time=fill_time,
            is_filled=True,
            commission=0.0,  # Will be calculated by fee model
            slippage=slippage * quantity
        )
    
    def _simulate_limit_order(
        self,
        side: str,
        quantity: float,
        price: float,
        bid: float,
        ask: float,
        fill_time: pd.Timestamp
    ) -> FillSimulation:
        """Simulate limit order fill."""
        # Check if limit order would fill
        if side == 'buy':
            is_filled = bid >= price  # Buy limit fills if bid reaches limit
            fill_price = price if is_filled else None
        else:  # sell
            is_filled = ask <= price  # Sell limit fills if ask reaches limit
            fill_price = price if is_filled else None
        
        if not is_filled:
            return FillSimulation(
                fill_price=0.0,
                fill_quantity=0.0,
                fill_time=fill_time,
                is_filled=False,
                commission=0.0,
                slippage=0.0
            )
        
        return FillSimulation(
            fill_price=fill_price,
            fill_quantity=quantity,
            fill_time=fill_time,
            is_filled=True,
            commission=0.0,
            slippage=0.0  # No slippage for limit orders (provide liquidity)
        )
```

### 2. Cost Models Pattern

```python
# costs/__init__.py
from typing import Dict, Literal
import numpy as np

class FeeModel:
    """
    Transaction fee model.
    
    Supports:
    - Maker/taker fees
    - Tiered pricing
    - Multiple exchanges
    """
    
    # Fee schedules (example for Binance)
    BINANCE_FEES = {
        'vip_0': {'maker': 0.0002, 'taker': 0.0004},
        'vip_1': {'maker': 0.00016, 'taker': 0.00038},
        'vip_2': {'maker': 0.00014, 'taker': 0.00036},
    }
    
    def __init__(
        self,
        exchange: str = 'binance',
        tier: str = 'vip_0',
        fee_structure: Literal['maker_taker', 'fixed'] = 'maker_taker'
    ):
        self.exchange = exchange
        self.tier = tier
        self.fee_structure = fee_structure
        
        # Load fee schedule
        if exchange == 'binance':
            self.fees = self.BINANCE_FEES.get(tier, self.BINANCE_FEES['vip_0'])
    
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
            Whether order is maker (provides liquidity)
        
        Returns
        -------
        fee : float
            Transaction fee (positive value)
        """
        notional = quantity * price
        
        if self.fee_structure == 'maker_taker':
            fee_rate = self.fees['maker'] if is_maker else self.fees['taker']
        else:
            fee_rate = self.fees.get('fixed', 0.001)
        
        return notional * fee_rate


class SlippageModel:
    """
    Slippage estimation model.
    
    Models:
    - Fixed: Constant bps
    - Sqrt: Square-root model (Almgren-Chriss)
    - Linear: Linear impact
    """
    
    def __init__(
        self,
        model: Literal['fixed', 'sqrt', 'linear'] = 'sqrt',
        impact_coefficient: float = 0.1,
        volatility_adjusted: bool = True
    ):
        self.model = model
        self.impact_coefficient = impact_coefficient
        self.volatility_adjusted = volatility_adjusted
    
    def calculate_slippage(
        self,
        quantity: float,
        avg_daily_volume: float,
        current_volatility: float = 0.02,
        side: Literal['buy', 'sell'] = 'buy'
    ) -> float:
        """
        Calculate slippage in bps.
        
        Parameters
        ----------
        quantity : float
            Order quantity
        avg_daily_volume : float
            Average daily volume
        current_volatility : float
            Current volatility (daily)
        side : str
            Order side
        
        Returns
        -------
        slippage_bps : float
            Slippage in basis points
        """
        if self.model == 'fixed':
            return self.impact_coefficient  # Fixed bps
        
        elif self.model == 'sqrt':
            # Square-root model: slippage ~ σ × sqrt(Q / V)
            participation_rate = quantity / avg_daily_volume
            slippage_bps = (
                self.impact_coefficient *
                current_volatility *
                np.sqrt(participation_rate) *
                10000  # Convert to bps
            )
            return slippage_bps
        
        elif self.model == 'linear':
            # Linear model: slippage ~ Q / V
            participation_rate = quantity / avg_daily_volume
            slippage_bps = (
                self.impact_coefficient *
                participation_rate *
                10000  # Convert to bps
            )
            return slippage_bps
        
        return 0.0


class SpreadModel:
    """Bid-ask spread cost model."""
    
    def calculate_cost(
        self,
        bid: float,
        ask: float,
        quantity: float
    ) -> float:
        """
        Calculate spread cost.
        
        Assumes crossing half-spread for aggressive orders.
        """
        mid = (bid + ask) / 2
        half_spread = (ask - bid) / 2
        return half_spread * quantity


class OvernightCostModel:
    """
    Overnight financing costs.
    
    - Crypto: Funding rates (8h intervals)
    - Stocks: Borrow costs (for shorts)
    - FX: Swap rates
    """
    
    def __init__(
        self,
        asset_type: Literal['crypto', 'stock', 'forex'] = 'crypto',
        funding_interval: str = '8h'
    ):
        self.asset_type = asset_type
        self.funding_interval = funding_interval
    
    def calculate_cost(
        self,
        position_value: float,
        funding_rate: float,
        hold_time: pd.Timedelta
    ) -> float:
        """Calculate overnight financing cost."""
        if self.asset_type == 'crypto':
            # Funding every 8 hours
            num_funding_periods = hold_time / pd.Timedelta('8h')
            return position_value * funding_rate * num_funding_periods
        elif self.asset_type == 'stock':
            # Daily borrow cost
            num_days = hold_time.days
            return position_value * funding_rate * num_days
        else:
            return 0.0
```

### 3. Backtest Engine Pattern

Due to space constraints, here's the core pattern:

```python
# engine/__init__.py
from dataclasses import dataclass
from typing import Dict, List
import pandas as pd
import numpy as np

@dataclass
class Trade:
    """Represents a completed trade."""
    timestamp: pd.Timestamp
    symbol: str
    side: str  # 'buy' or 'sell'
    quantity: float
    price: float
    commission: float
    slippage: float
    pnl: float = 0.0

class Portfolio:
    """
    Portfolio state tracking.
    
    Tracks:
    - Positions
    - Cash
    - PnL
    - Exposure
    """
    
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, float] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = [initial_capital]
        self.timestamps: List[pd.Timestamp] = []
    
    def execute_trade(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str,
        timestamp: pd.Timestamp,
        commission: float = 0.0,
        slippage: float = 0.0
    ):
        """Execute a trade and update portfolio."""
        # Update position
        if side == 'buy':
            self.positions[symbol] = self.positions.get(symbol, 0.0) + quantity
            cash_change = -(quantity * price + commission + slippage)
        else:  # sell
            self.positions[symbol] = self.positions.get(symbol, 0.0) - quantity
            cash_change = quantity * price - commission - slippage
        
        self.cash += cash_change
        
        # Record trade
        trade = Trade(
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            commission=commission,
            slippage=slippage
        )
        self.trades.append(trade)
    
    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """Get total portfolio value."""
        position_value = sum(
            qty * current_prices.get(symbol, 0.0)
            for symbol, qty in self.positions.items()
        )
        return self.cash + position_value
    
    def get_pnl(self) -> float:
        """Get total PnL."""
        return self.equity_curve[-1] - self.initial_capital


class BacktestEngine:
    """
    Event-driven backtesting engine.
    
    Features:
    - Realistic execution simulation
    - Comprehensive cost modeling
    - Risk management
    - Performance tracking
    """
    
    def __init__(
        self,
        initial_capital: float,
        simulator,
        fee_model,
        slippage_model,
        risk_manager=None
    ):
        self.initial_capital = initial_capital
        self.simulator = simulator
        self.fee_model = fee_model
        self.slippage_model = slippage_model
        self.risk_manager = risk_manager
        
        self.portfolio = Portfolio(initial_capital)
    
    def run(
        self,
        strategy,
        data: pd.DataFrame,
        start_date: str,
        end_date: str
    ):
        """
        Run backtest.
        
        Parameters
        ----------
        strategy : Strategy
            Strategy with generate_signals() method
        data : pd.DataFrame
            Market data with OHLCV + features
        start_date : str
            Backtest start date
        end_date : str
            Backtest end date
        
        Returns
        -------
        results : BacktestResults
            Backtest results
        """
        # Filter data
        mask = (data.index >= start_date) & (data.index <= end_date)
        backtest_data = data[mask]
        
        # Generate signals
        signals = strategy.generate_signals(backtest_data)
        
        # Simulate trading
        for timestamp, signal in signals.items():
            if signal == 0:
                continue  # No trade
            
            # Get current market data
            current_data = backtest_data.loc[timestamp]
            
            # Determine order parameters
            side = 'buy' if signal > 0 else 'sell'
            quantity = abs(signal)  # Signal magnitude = position size
            
            # Simulate fill
            fill = self.simulator.simulate_fill(
                order_type='market',
                side=side,
                quantity=quantity,
                price=None,
                current_bid=current_data['bid'],
                current_ask=current_data['ask'],
                timestamp=timestamp
            )
            
            if not fill.is_filled:
                continue
            
            # Calculate costs
            commission = self.fee_model.calculate_fee(
                quantity, fill.fill_price, is_maker=False
            )
            
            slippage_bps = self.slippage_model.calculate_slippage(
                quantity,
                avg_daily_volume=current_data.get('volume', 1e6),
                current_volatility=current_data.get('volatility', 0.02)
            )
            slippage_amount = quantity * fill.fill_price * slippage_bps / 10000
            
            # Execute trade
            self.portfolio.execute_trade(
                symbol='ASSET',
                quantity=quantity,
                price=fill.fill_price,
                side=side,
                timestamp=fill.fill_time,
                commission=commission,
                slippage=slippage_amount
            )
        
        # Compute results
        returns = pd.Series(self.portfolio.equity_curve).pct_change()
        
        results = BacktestResults(
            total_return=(self.portfolio.equity_curve[-1] / self.initial_capital - 1),
            sharpe=np.sqrt(252) * returns.mean() / returns.std(),
            max_drawdown=self._compute_max_drawdown(self.portfolio.equity_curve),
            num_trades=len(self.portfolio.trades),
            trades=self.portfolio.trades,
            equity_curve=self.portfolio.equity_curve
        )
        
        return results
    
    def _compute_max_drawdown(self, equity_curve: List[float]) -> float:
        """Compute maximum drawdown."""
        equity = np.array(equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdown = (equity - running_max) / running_max
        return np.min(drawdown)


@dataclass
class BacktestResults:
    """Backtest results container."""
    total_return: float
    sharpe: float
    max_drawdown: float
    num_trades: int
    trades: List[Trade]
    equity_curve: List[float]
```

---

## Integration with Phases 5-6

```python
# Complete integration example
from autotrader.data_prep.features import FeatureFactory
from autotrader.modeling.baselines import XGBoostModel
from autotrader.backtesting import BacktestEngine, OrderSimulator, FeeModel, SlippageModel

# 1. Extract features (Phase 5)
factory = FeatureFactory.microstructure()
features = factory.extract_all(bars, orderbook, trades)

# 2. Train model (Phase 6)
model = XGBoostModel()
model.fit(X_train, y_train)

# 3. Create strategy
class MLStrategy:
    def __init__(self, model):
        self.model = model
    
    def generate_signals(self, data):
        proba = self.model.predict_proba(data)[:, 1]
        signals = pd.Series(0, index=data.index)
        signals[proba > 0.65] = 1
        signals[proba < 0.35] = -1
        return signals

# 4. Run backtest (Phase 7)
engine = BacktestEngine(
    initial_capital=100000,
    simulator=OrderSimulator(fill_method='quote_based'),
    fee_model=FeeModel(exchange='binance'),
    slippage_model=SlippageModel(model='sqrt')
)

results = engine.run(
    strategy=MLStrategy(model),
    data=features,
    start_date='2024-01-01',
    end_date='2024-12-31'
)

print(f"Sharpe: {results.sharpe:.2f}")
```

---

## Testing Strategy

```python
# tests/test_simulator.py
import pytest
from autotrader.backtesting.simulator import OrderSimulator, LatencyModel

def test_market_order_buy():
    """Test market buy order simulation."""
    simulator = OrderSimulator(fill_method='quote_based')
    
    fill = simulator.simulate_fill(
        order_type='market',
        side='buy',
        quantity=100,
        price=None,
        current_bid=100.00,
        current_ask=100.02,
        timestamp=pd.Timestamp('2024-01-01')
    )
    
    assert fill.is_filled
    assert fill.fill_price == 100.02  # Takes ask
    assert fill.fill_quantity == 100
    assert fill.slippage > 0  # Pays half-spread


def test_latency_model():
    """Test latency application."""
    latency_model = LatencyModel(
        signal_to_order=10,
        network_latency=30,
        exchange_processing=20
    )
    
    timestamp = pd.Timestamp('2024-01-01 00:00:00')
    delayed = latency_model.apply_latency(timestamp)
    
    expected_delay = 10 + 30 + 20  # 60ms
    assert (delayed - timestamp).total_seconds() * 1000 == expected_delay
```

---

## Next Steps

1. **Implement core modules** (following patterns above)
2. **Add comprehensive tests**
3. **Validate against known results**
4. **Run example backtests**
5. **Generate tear sheets**
6. **Document findings**

---

**Status**: Architecture and patterns defined. Ready for implementation (~5,000 lines).
