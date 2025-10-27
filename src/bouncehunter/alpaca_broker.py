"""
Alpaca Paper Trading Broker Integration

Handles order execution, position tracking, and portfolio management
for PennyHunter Phase 3 agentic system.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        StopLossRequest,
        TakeProfitRequest,
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestQuoteRequest
except ImportError:
    print("⚠️  alpaca-py not installed. Run: pip install alpaca-py")
    TradingClient = None

logger = logging.getLogger(__name__)


@dataclass
class TradeOrder:
    """Trade order details."""
    ticker: str
    action: str  # 'BUY' or 'SELL'
    entry_price: float
    stop_price: float
    target_price: float
    position_size_pct: float
    confidence: float
    signal_id: str
    regime: str
    agent_votes: Dict[str, bool]


@dataclass
class Position:
    """Current position details."""
    ticker: str
    qty: int
    entry_price: float
    current_price: float
    stop_price: float
    target_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    signal_id: str
    entry_date: datetime


class AlpacaBroker:
    """
    Alpaca Paper Trading Broker.
    
    Handles:
    - Order execution (market orders with stop/target brackets)
    - Position tracking
    - Portfolio management
    - Risk checks
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        paper: bool = True,
        initial_capital: float = 25000,
        max_position_pct: float = 0.10,
        risk_per_trade_pct: float = 0.01,
        max_concurrent: int = 5,
    ):
        """
        Initialize Alpaca broker.
        
        Args:
            api_key: Alpaca API key (or set ALPACA_API_KEY env var)
            api_secret: Alpaca API secret (or set ALPACA_API_SECRET env var)
            paper: Use paper trading (default True)
            initial_capital: Starting capital
            max_position_pct: Max position size (% of capital)
            risk_per_trade_pct: Risk per trade (% of capital)
            max_concurrent: Max concurrent positions
        """
        if TradingClient is None:
            raise ImportError("alpaca-py not installed. Run: pip install alpaca-py")
        
        # Get credentials from env if not provided
        self.api_key = api_key or os.getenv('ALPACA_API_KEY')
        self.api_secret = api_secret or os.getenv('ALPACA_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError(
                "Alpaca credentials not found. Set ALPACA_API_KEY and ALPACA_API_SECRET "
                "environment variables or pass as arguments."
            )
        
        # Initialize clients
        self.paper = paper
        self.trading_client = TradingClient(
            api_key=self.api_key,
            secret_key=self.api_secret,
            paper=paper
        )
        self.data_client = StockHistoricalDataClient(
            api_key=self.api_key,
            secret_key=self.api_secret
        )
        
        # Risk parameters
        self.initial_capital = initial_capital
        self.max_position_pct = max_position_pct
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_concurrent = max_concurrent
        
        logger.info(f"✅ AlpacaBroker initialized ({'PAPER' if paper else 'LIVE'} trading)")
        self._position_metadata: Dict[str, Dict[str, object]] = {}
    
    def get_account(self) -> dict:
        """Get account information."""
        try:
            account = self.trading_client.get_account()
            return {
                'cash': float(account.cash),
                'portfolio_value': float(account.portfolio_value),
                'buying_power': float(account.buying_power),
                'equity': float(account.equity),
                'positions_count': len(self.get_positions()),
            }
        except Exception as e:
            logger.error(f"❌ Failed to get account: {e}")
            return {}
    
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        try:
            alpaca_positions = self.trading_client.get_all_positions()
            positions = []
            
            for pos in alpaca_positions:
                # Get current quote
                current_price = float(pos.current_price)
                entry_price = float(pos.avg_entry_price)
                qty = int(pos.qty)
                
                # Calculate P&L
                unrealized_pnl = float(pos.unrealized_pl)
                unrealized_pnl_pct = float(pos.unrealized_plpc) * 100
                
                meta = self._position_metadata.get(pos.symbol.upper(), {})
                positions.append(Position(
                    ticker=pos.symbol,
                    qty=qty,
                    entry_price=entry_price,
                    current_price=current_price,
                    stop_price=float(meta.get("stop_price", 0.0) or 0.0),
                    target_price=float(meta.get("target_price", 0.0) or 0.0),
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    signal_id=str(meta.get("signal_id", "")),
                    entry_date=meta.get("entry_time", pos.created_at),
                ))
            
            return positions
            
        except Exception as e:
            logger.error(f"❌ Failed to get positions: {e}")
            return []
    
    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for ticker."""
        try:
            request = StockLatestQuoteRequest(symbol_or_symbols=ticker)
            quotes = self.data_client.get_stock_latest_quote(request)
            
            if ticker in quotes:
                quote = quotes[ticker]
                # Use mid-price
                return (quote.ask_price + quote.bid_price) / 2
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get price for {ticker}: {e}")
            return None
    
    def check_risk_limits(self, order: TradeOrder) -> Tuple[bool, str]:
        """
        Check if order passes risk limits.
        
        Returns:
            (allowed, reason)
        """
        account = self.get_account()
        positions = self.get_positions()
        
        # Check max concurrent positions
        if len(positions) >= self.max_concurrent:
            return False, f"Max concurrent positions reached ({self.max_concurrent})"
        
        # Check if already in position
        for pos in positions:
            if pos.ticker == order.ticker:
                return False, f"Already in position for {order.ticker}"
        
        # Check position size
        portfolio_value = account.get('portfolio_value', self.initial_capital)
        max_position_value = portfolio_value * self.max_position_pct
        
        # Calculate position value
        position_value = portfolio_value * order.position_size_pct
        
        if position_value > max_position_value:
            return False, f"Position size ${position_value:.0f} exceeds max ${max_position_value:.0f}"
        
        # Check buying power
        buying_power = account.get('buying_power', portfolio_value)
        if position_value > buying_power:
            return False, f"Insufficient buying power (need ${position_value:.0f}, have ${buying_power:.0f})"
        
        return True, "Risk checks passed"
    
    def calculate_position_size(
        self,
        order: TradeOrder,
        portfolio_value: float
    ) -> int:
        """
        Calculate position size in shares.
        
        Uses position_size_pct from order.
        """
        position_value = portfolio_value * order.position_size_pct
        shares = int(position_value / order.entry_price)
        
        # Ensure at least 1 share
        return max(1, shares)
    
    def execute_trade(self, order: TradeOrder) -> Optional[str]:
        """
        Execute trade with bracket orders (entry + stop + target).
        
        Returns:
            order_id if successful, None otherwise
        """
        # Check risk limits
        allowed, reason = self.check_risk_limits(order)
        if not allowed:
            logger.warning(f"❌ Trade rejected: {reason}")
            return None
        
        # Get current price
        current_price = self.get_current_price(order.ticker)
        if current_price is None:
            logger.error(f"❌ Could not get price for {order.ticker}")
            return None
        
        # Calculate position size
        account = self.get_account()
        portfolio_value = account.get('portfolio_value', self.initial_capital)
        qty = self.calculate_position_size(order, portfolio_value)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 EXECUTING TRADE")
        logger.info(f"{'='*70}")
        logger.info(f"  Ticker:       {order.ticker}")
        logger.info(f"  Action:       {order.action}")
        logger.info(f"  Entry:        ${order.entry_price:.2f} (current: ${current_price:.2f})")
        logger.info(f"  Stop:         ${order.stop_price:.2f} ({((order.stop_price/order.entry_price - 1)*100):.1f}%)")
        logger.info(f"  Target:       ${order.target_price:.2f} ({((order.target_price/order.entry_price - 1)*100):.1f}%)")
        logger.info(f"  Quantity:     {qty} shares")
        logger.info(f"  Position $:   ${qty * order.entry_price:.0f} ({order.position_size_pct*100:.1f}% of portfolio)")
        logger.info(f"  Confidence:   {order.confidence:.1f}/10")
        logger.info(f"  Regime:       {order.regime}")
        logger.info(f"  Signal ID:    {order.signal_id}")
        
        try:
            if order.stop_price <= 0 or order.target_price <= 0:
                logger.error("❌ Stop and target prices must be positive for bracket orders")
                return None

            side = OrderSide.BUY if order.action == 'BUY' else OrderSide.SELL

            # Create market order (entry) with attached bracket legs
            market_order = MarketOrderRequest(
                symbol=order.ticker,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
                order_class=OrderClass.BRACKET,
                take_profit=TakeProfitRequest(limit_price=round(order.target_price, 2)),
                stop_loss=StopLossRequest(stop_price=round(order.stop_price, 2)),
            )
            
            # Submit entry order
            entry_order = self.trading_client.submit_order(market_order)
            order_id = entry_order.id

            ticker_key = order.ticker.upper()
            self._position_metadata[ticker_key] = {
                "stop_price": order.stop_price,
                "target_price": order.target_price,
                "signal_id": order.signal_id,
                "entry_time": datetime.utcnow(),
            }
            
            logger.info(f"✅ Entry order submitted: {order_id}")
            
            # TODO: Submit bracket orders (stop loss + take profit)
            # Note: Alpaca API requires waiting for entry fill before submitting brackets
            # For now, we'll track stop/target manually and submit later
            
            logger.info(f"{'='*70}\n")
            
            return str(order_id)
            
        except Exception as e:
            logger.error(f"❌ Failed to execute trade: {e}")
            import traceback
            traceback.print_exc()
            self._position_metadata.pop(order.ticker.upper(), None)
            return None
    
    def close_position(
        self,
        ticker: str,
        reason: str = "Manual close"
    ) -> bool:
        """Close position for ticker."""
        try:
            # Close position (market order to close entire position)
            self.trading_client.close_position(ticker)
            logger.info(f"✅ Closed position {ticker}: {reason}")
            self._position_metadata.pop(ticker.upper(), None)
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to close {ticker}: {e}")
            return False
    
    def check_stops_and_targets(self) -> List[Dict]:
        """
        Check all positions for stop/target hits.
        
        Returns:
            List of actions to take (close position)
        """
        actions = []
        positions = self.get_positions()
        
        for pos in positions:
            # Get current price
            current_price = self.get_current_price(pos.ticker)
            if current_price is None:
                continue
            
            # Check stop loss
            if pos.stop_price > 0 and current_price <= pos.stop_price:
                actions.append({
                    'ticker': pos.ticker,
                    'action': 'CLOSE',
                    'reason': 'STOP_HIT',
                    'entry': pos.entry_price,
                    'exit': current_price,
                    'pnl_pct': ((current_price / pos.entry_price) - 1) * 100,
                })
            
            # Check target
            elif pos.target_price > 0 and current_price >= pos.target_price:
                actions.append({
                    'ticker': pos.ticker,
                    'action': 'CLOSE',
                    'reason': 'TARGET_HIT',
                    'entry': pos.entry_price,
                    'exit': current_price,
                    'pnl_pct': ((current_price / pos.entry_price) - 1) * 100,
                })
        
        return actions
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get status of order."""
        try:
            order = self.trading_client.get_order_by_id(order_id)
            return {
                'id': order.id,
                'status': order.status,
                'filled_qty': int(order.filled_qty) if order.filled_qty else 0,
                'filled_avg_price': float(order.filled_avg_price) if order.filled_avg_price else 0.0,
            }
        except Exception as e:
            logger.error(f"❌ Failed to get order {order_id}: {e}")
            return None
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel open order."""
        try:
            self.trading_client.cancel_order_by_id(order_id)
            logger.info(f"✅ Cancelled order {order_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to cancel order {order_id}: {e}")
            return False


# Convenience functions

def create_paper_broker(
    initial_capital: float = 25000,
    risk_per_trade: float = 0.01,
) -> AlpacaBroker:
    """Create paper trading broker with sensible defaults."""
    return AlpacaBroker(
        paper=True,
        initial_capital=initial_capital,
        max_position_pct=0.10,  # 10% max position
        risk_per_trade_pct=risk_per_trade,
        max_concurrent=5,
    )


def create_live_broker(
    initial_capital: float = 25000,
    risk_per_trade: float = 0.005,  # 0.5% for live
) -> AlpacaBroker:
    """Create live trading broker (use with caution!)."""
    return AlpacaBroker(
        paper=False,
        initial_capital=initial_capital,
        max_position_pct=0.05,  # 5% max position (more conservative)
        risk_per_trade_pct=risk_per_trade,
        max_concurrent=3,  # Fewer concurrent for live
    )
