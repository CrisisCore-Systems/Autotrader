"""
Event-driven backtesting engine with realistic execution.

This module provides the core backtesting framework including:
- Event-driven architecture
- Portfolio state tracking
- Order management
- Risk management
- PnL calculation

Key Classes
-----------
BacktestEngine : Main backtesting engine
Portfolio : Portfolio state and tracking
Trade : Individual trade record
Position : Position tracking
RiskManager : Risk constraints and monitoring

References
----------
- Pardo (2008): "The Evaluation and Optimization of Trading Strategies"
- Chan (2009): "Quantitative Trading"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Literal
from enum import Enum
import pandas as pd
import numpy as np
from datetime import datetime


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = 'pending'
    FILLED = 'filled'
    PARTIAL = 'partial'
    CANCELLED = 'cancelled'
    REJECTED = 'rejected'


@dataclass
class Trade:
    """
    Represents a completed trade.
    
    Attributes
    ----------
    trade_id : int
        Unique trade identifier
    timestamp : pd.Timestamp
        Trade execution timestamp
    symbol : str
        Instrument symbol
    side : str
        Trade side ('buy' or 'sell')
    quantity : float
        Quantity traded
    price : float
        Execution price
    commission : float
        Transaction commission
    slippage : float
        Slippage cost
    market_impact : float
        Market impact cost
    pnl : float
        Realized PnL (for closing trades)
    """
    trade_id: int
    timestamp: pd.Timestamp
    symbol: str
    side: str
    quantity: float
    price: float
    commission: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    pnl: float = 0.0
    
    def total_cost(self) -> float:
        """Get total execution cost."""
        return self.commission + self.slippage + self.market_impact
    
    def net_proceeds(self) -> float:
        """Get net proceeds/cost."""
        notional = self.quantity * self.price
        if self.side == 'sell':
            return notional - self.total_cost()
        else:  # buy
            return -(notional + self.total_cost())


@dataclass
class Position:
    """
    Represents a position in an instrument.
    
    Attributes
    ----------
    symbol : str
        Instrument symbol
    quantity : float
        Current quantity (positive=long, negative=short)
    avg_price : float
        Average entry price
    market_value : float
        Current market value
    unrealized_pnl : float
        Unrealized PnL
    realized_pnl : float
        Realized PnL from closed trades
    """
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0
    
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0
    
    def is_flat(self) -> bool:
        """Check if position is flat."""
        return self.quantity == 0
    
    def update_market_value(self, current_price: float):
        """Update market value and unrealized PnL."""
        self.market_value = self.quantity * current_price
        if self.quantity != 0:
            self.unrealized_pnl = (current_price - self.avg_price) * self.quantity


class Portfolio:
    """
    Portfolio state tracking and management.
    
    Tracks:
    - Positions in multiple instruments
    - Cash balance
    - Equity (cash + positions)
    - Trade history
    - Performance metrics
    
    Parameters
    ----------
    initial_capital : float
        Starting capital
    currency : str
        Base currency
    
    Examples
    --------
    >>> portfolio = Portfolio(initial_capital=100000)
    >>> portfolio.execute_trade(
    ...     symbol='BTCUSDT',
    ...     quantity=1.0,
    ...     price=50000,
    ...     side='buy',
    ...     timestamp=pd.Timestamp('2024-01-01')
    ... )
    """
    
    def __init__(
        self,
        initial_capital: float,
        currency: str = 'USD'
    ):
        self.initial_capital = initial_capital
        self.currency = currency
        self.cash = initial_capital
        
        # Position tracking
        self.positions: Dict[str, Position] = {}
        
        # Trade history
        self.trades: List[Trade] = []
        self.trade_counter = 0
        
        # Equity curve
        self.equity_curve: List[float] = [initial_capital]
        self.timestamps: List[pd.Timestamp] = []
        
        # Performance tracking
        self.total_commissions = 0.0
        self.total_slippage = 0.0
        self.total_market_impact = 0.0
    
    def execute_trade(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str,
        timestamp: pd.Timestamp,
        commission: float = 0.0,
        slippage: float = 0.0,
        market_impact: float = 0.0
    ) -> Trade:
        """
        Execute a trade and update portfolio state.
        
        Parameters
        ----------
        symbol : str
            Instrument symbol
        quantity : float
            Trade quantity (positive)
        price : float
            Execution price
        side : str
            Trade side ('buy' or 'sell')
        timestamp : pd.Timestamp
            Trade timestamp
        commission : float
            Transaction commission
        slippage : float
            Slippage cost
        market_impact : float
            Market impact cost
        
        Returns
        -------
        trade : Trade
            Executed trade object
        """
        # Calculate realized PnL for closing trades
        pnl = 0.0
        if symbol in self.positions:
            position = self.positions[symbol]
            if (side == 'sell' and position.is_long()) or \
               (side == 'buy' and position.is_short()):
                # Closing trade
                close_qty = min(abs(quantity), abs(position.quantity))
                pnl = (price - position.avg_price) * close_qty * np.sign(position.quantity)
                pnl -= (commission + slippage + market_impact)
        
        # Create trade record
        trade = Trade(
            trade_id=self.trade_counter,
            timestamp=timestamp,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            commission=commission,
            slippage=slippage,
            market_impact=market_impact,
            pnl=pnl
        )
        self.trade_counter += 1
        
        # Update position
        self._update_position(symbol, quantity, price, side, pnl)
        
        # Update cash
        self.cash += trade.net_proceeds()
        
        # Track costs
        self.total_commissions += commission
        self.total_slippage += slippage
        self.total_market_impact += market_impact
        
        # Record trade
        self.trades.append(trade)
        
        return trade
    
    def _update_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        side: str,
        realized_pnl: float
    ):
        """Update position state after trade."""
        if symbol not in self.positions:
            self.positions[symbol] = Position(symbol=symbol)
        
        position = self.positions[symbol]
        
        # Determine quantity change
        qty_change = quantity if side == 'buy' else -quantity
        old_qty = position.quantity
        new_qty = old_qty + qty_change
        
        # Update average price
        if np.sign(old_qty) == np.sign(qty_change) or old_qty == 0:
            # Adding to position
            if new_qty != 0:
                position.avg_price = (
                    (old_qty * position.avg_price + qty_change * price) / new_qty
                )
        elif abs(new_qty) < abs(old_qty):
            # Reducing position, keep same avg price
            pass
        else:
            # Flipping position
            position.avg_price = price
        
        position.quantity = new_qty
        position.realized_pnl += realized_pnl
        
        # Remove position if closed
        if abs(new_qty) < 1e-8:
            del self.positions[symbol]
    
    def update_market_prices(
        self,
        prices: Dict[str, float],
        timestamp: pd.Timestamp
    ):
        """
        Update portfolio value with current market prices.
        
        Parameters
        ----------
        prices : dict
            Current prices for each symbol
        timestamp : pd.Timestamp
            Current timestamp
        """
        # Update position market values
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_market_value(prices[symbol])
        
        # Calculate total equity
        position_value = sum(p.market_value for p in self.positions.values())
        equity = self.cash + position_value
        
        # Record
        self.equity_curve.append(equity)
        self.timestamps.append(timestamp)
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """Get current position for symbol."""
        return self.positions.get(symbol)
    
    def get_total_value(self, current_prices: Dict[str, float]) -> float:
        """Get total portfolio value."""
        position_value = sum(
            qty * current_prices.get(symbol, 0.0)
            for symbol, qty in self.get_positions().items()
        )
        return self.cash + position_value
    
    def get_positions(self) -> Dict[str, float]:
        """Get all positions as {symbol: quantity} dict."""
        return {
            symbol: position.quantity
            for symbol, position in self.positions.items()
        }
    
    def get_total_pnl(self) -> float:
        """Get total PnL (realized + unrealized)."""
        realized = sum(p.realized_pnl for p in self.positions.values())
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return (self.equity_curve[-1] - self.initial_capital) if self.equity_curve else 0.0
    
    def get_realized_pnl(self) -> float:
        """Get total realized PnL."""
        return sum(p.realized_pnl for p in self.positions.values())
    
    def get_unrealized_pnl(self) -> float:
        """Get total unrealized PnL."""
        return sum(p.unrealized_pnl for p in self.positions.values())
    
    def get_equity_series(self) -> pd.Series:
        """Get equity curve as time series."""
        if not self.timestamps:
            return pd.Series([self.initial_capital])
        return pd.Series(self.equity_curve, index=self.timestamps)
    
    def get_returns(self) -> pd.Series:
        """Get return series."""
        equity = self.get_equity_series()
        return equity.pct_change().fillna(0)


class RiskManager:
    """
    Risk management and position limits.
    
    Enforces:
    - Position size limits
    - Leverage limits
    - Maximum drawdown limits
    - Daily loss limits
    
    Parameters
    ----------
    max_position_size : float, optional
        Maximum position size (fraction of portfolio)
    max_leverage : float, optional
        Maximum leverage
    max_drawdown : float, optional
        Maximum drawdown before stopping (fraction)
    max_daily_loss : float, optional
        Maximum daily loss (fraction of portfolio)
    
    Examples
    --------
    >>> risk_mgr = RiskManager(
    ...     max_position_size=0.2,
    ...     max_leverage=2.0,
    ...     max_drawdown=0.1
    ... )
    >>> is_valid = risk_mgr.check_order(
    ...     portfolio_value=100000,
    ...     order_size=15000,
    ...     current_positions={}
    ... )
    """
    
    def __init__(
        self,
        max_position_size: Optional[float] = None,
        max_leverage: Optional[float] = None,
        max_drawdown: Optional[float] = None,
        max_daily_loss: Optional[float] = None
    ):
        self.max_position_size = max_position_size
        self.max_leverage = max_leverage
        self.max_drawdown = max_drawdown
        self.max_daily_loss = max_daily_loss
        
        # State tracking
        self.peak_equity = 0.0
        self.daily_start_equity = 0.0
        self.is_risk_breached = False
    
    def check_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
        portfolio_value: float,
        current_positions: Dict[str, float]
    ) -> bool:
        """
        Check if order violates risk constraints.
        
        Returns
        -------
        is_valid : bool
            True if order passes all risk checks
        """
        if self.is_risk_breached:
            return False
        
        # Check position size limit
        if self.max_position_size is not None:
            order_value = quantity * price
            max_value = portfolio_value * self.max_position_size
            if order_value > max_value:
                return False
        
        # Check leverage limit
        if self.max_leverage is not None:
            total_position_value = sum(
                abs(qty * price)  # Simplified: should use actual prices
                for qty in current_positions.values()
            )
            total_position_value += (quantity * price)
            leverage = total_position_value / portfolio_value
            if leverage > self.max_leverage:
                return False
        
        return True
    
    def update(
        self,
        current_equity: float,
        is_new_day: bool = False
    ):
        """
        Update risk state.
        
        Parameters
        ----------
        current_equity : float
            Current portfolio equity
        is_new_day : bool
            Whether this is start of new trading day
        """
        # Update peak
        if current_equity > self.peak_equity:
            self.peak_equity = current_equity
        
        # Check drawdown limit
        if self.max_drawdown is not None and self.peak_equity > 0:
            drawdown = (self.peak_equity - current_equity) / self.peak_equity
            if drawdown > self.max_drawdown:
                self.is_risk_breached = True
        
        # Reset daily tracking
        if is_new_day:
            self.daily_start_equity = current_equity
        
        # Check daily loss limit
        if self.max_daily_loss is not None and self.daily_start_equity > 0:
            daily_loss = (self.daily_start_equity - current_equity) / self.daily_start_equity
            if daily_loss > self.max_daily_loss:
                self.is_risk_breached = True


@dataclass
class BacktestResults:
    """
    Backtest results container.
    
    Attributes
    ----------
    start_date : pd.Timestamp
        Backtest start date
    end_date : pd.Timestamp
        Backtest end date
    initial_capital : float
        Starting capital
    final_capital : float
        Ending capital
    total_return : float
        Total return (fraction)
    num_trades : int
        Number of trades
    trades : List[Trade]
        List of all trades
    equity_curve : pd.Series
        Equity time series
    """
    start_date: pd.Timestamp
    end_date: pd.Timestamp
    initial_capital: float
    final_capital: float
    total_return: float
    sharpe: float
    max_drawdown: float
    num_trades: int
    win_rate: float
    trades: List[Trade]
    equity_curve: pd.Series
    
    def to_dict(self) -> Dict:
        """Convert results to dictionary."""
        return {
            'start_date': self.start_date,
            'end_date': self.end_date,
            'initial_capital': self.initial_capital,
            'final_capital': self.final_capital,
            'total_return': self.total_return,
            'sharpe': self.sharpe,
            'max_drawdown': self.max_drawdown,
            'num_trades': self.num_trades,
            'win_rate': self.win_rate
        }


class BacktestEngine:
    """
    Event-driven backtesting engine with realistic execution.
    
    Features:
    - Realistic order simulation
    - Comprehensive cost modeling
    - Portfolio tracking
    - Risk management
    - Performance analytics
    
    Parameters
    ----------
    initial_capital : float
        Starting capital
    simulator : OrderSimulator
        Order fill simulator
    fee_model : FeeModel
        Transaction fee model
    slippage_model : SlippageModel, optional
        Slippage model
    risk_manager : RiskManager, optional
        Risk management
    
    Examples
    --------
    >>> from autotrader.backtesting import BacktestEngine, OrderSimulator, FeeModel
    >>> engine = BacktestEngine(
    ...     initial_capital=100000,
    ...     simulator=OrderSimulator(fill_method='quote_based'),
    ...     fee_model=FeeModel(exchange='binance')
    ... )
    """
    
    def __init__(
        self,
        initial_capital: float,
        simulator,
        fee_model,
        slippage_model=None,
        risk_manager: Optional[RiskManager] = None
    ):
        self.initial_capital = initial_capital
        self.simulator = simulator
        self.fee_model = fee_model
        self.slippage_model = slippage_model
        self.risk_manager = risk_manager
        
        # Initialize portfolio
        self.portfolio = Portfolio(initial_capital)
        
        # Market data cache
        self.current_prices: Dict[str, float] = {}
    
    def run(
        self,
        strategy,
        data: pd.DataFrame,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbol: str = 'ASSET'
    ) -> BacktestResults:
        """
        Run backtest.
        
        Parameters
        ----------
        strategy : Strategy
            Strategy with generate_signals() method
        data : pd.DataFrame
            Market data with OHLCV + features
            Must have columns: bid, ask, close, volume
        start_date : str, optional
            Backtest start date
        end_date : str, optional
            Backtest end date
        symbol : str
            Instrument symbol
        
        Returns
        -------
        results : BacktestResults
            Backtest results
        """
        # Filter data
        backtest_data = data.copy()
        if start_date:
            backtest_data = backtest_data[backtest_data.index >= start_date]
        if end_date:
            backtest_data = backtest_data[backtest_data.index <= end_date]
        
        if len(backtest_data) == 0:
            raise ValueError("No data in backtest period")
        
        # Generate signals
        signals = strategy.generate_signals(backtest_data)
        
        # Event-driven simulation
        for timestamp in backtest_data.index:
            current_bar = backtest_data.loc[timestamp]
            
            # Update market prices
            current_price = current_bar.get('close', current_bar.get('price', 0))
            self.current_prices[symbol] = current_price
            
            # Update portfolio value
            self.portfolio.update_market_prices(self.current_prices, timestamp)
            
            # Check for signal
            if timestamp not in signals.index:
                continue
            
            signal = signals.loc[timestamp]
            if signal == 0 or pd.isna(signal):
                continue
            
            # Determine order parameters
            side = 'buy' if signal > 0 else 'sell'
            quantity = abs(signal)
            
            # Risk check
            if self.risk_manager:
                portfolio_value = self.portfolio.get_total_value(self.current_prices)
                is_valid = self.risk_manager.check_order(
                    symbol, quantity, current_price,
                    portfolio_value,
                    self.portfolio.get_positions()
                )
                if not is_valid:
                    continue
            
            # Simulate fill
            fill = self.simulator.simulate_fill(
                order_type='market',
                side=side,
                quantity=quantity,
                price=None,
                current_bid=current_bar.get('bid', current_price * 0.9995),
                current_ask=current_bar.get('ask', current_price * 1.0005),
                timestamp=timestamp,
                avg_daily_volume=current_bar.get('volume', 1e6)
            )
            
            if not fill.is_filled:
                continue
            
            # Calculate costs
            commission = self.fee_model.calculate_fee(
                quantity, fill.fill_price, is_maker=False
            )
            
            # Execute trade
            self.portfolio.execute_trade(
                symbol=symbol,
                quantity=quantity,
                price=fill.fill_price,
                side=side,
                timestamp=fill.fill_time,
                commission=commission,
                slippage=fill.slippage,
                market_impact=fill.market_impact
            )
            
            # Update risk manager
            if self.risk_manager:
                self.risk_manager.update(
                    self.portfolio.get_total_value(self.current_prices)
                )
        
        # Final portfolio update
        final_timestamp = backtest_data.index[-1]
        self.portfolio.update_market_prices(self.current_prices, final_timestamp)
        
        # Compute results
        equity_series = self.portfolio.get_equity_series()
        returns = equity_series.pct_change().fillna(0)
        
        results = BacktestResults(
            start_date=backtest_data.index[0],
            end_date=backtest_data.index[-1],
            initial_capital=self.initial_capital,
            final_capital=equity_series.iloc[-1],
            total_return=(equity_series.iloc[-1] / self.initial_capital - 1),
            sharpe=self._compute_sharpe(returns),
            max_drawdown=self._compute_max_drawdown(equity_series),
            num_trades=len(self.portfolio.trades),
            win_rate=self._compute_win_rate(self.portfolio.trades),
            trades=self.portfolio.trades,
            equity_curve=equity_series
        )
        
        return results
    
    def _compute_sharpe(self, returns: pd.Series) -> float:
        """Compute annualized Sharpe ratio."""
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        
        # Assume daily returns
        return np.sqrt(252) * returns.mean() / returns.std()
    
    def _compute_max_drawdown(self, equity: pd.Series) -> float:
        """Compute maximum drawdown."""
        if len(equity) < 2:
            return 0.0
        
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max
        return abs(drawdown.min())
    
    def _compute_win_rate(self, trades: List[Trade]) -> float:
        """Compute win rate."""
        if not trades:
            return 0.0
        
        winning_trades = sum(1 for t in trades if t.pnl > 0)
        return winning_trades / len(trades)


# Export public API
__all__ = [
    'BacktestEngine',
    'Portfolio',
    'Trade',
    'Position',
    'RiskManager',
    'BacktestResults',
    'OrderStatus',
]
