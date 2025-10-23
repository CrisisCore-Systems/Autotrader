"""
Interactive Brokers Paper Trading Integration (Canada Compatible)

Handles order execution, position tracking, and portfolio management
for PennyHunter Phase 3 agentic system using Interactive Brokers.

Interactive Brokers is available globally including Canada.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os
import asyncio

try:
    from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder, util
    from ib_insync import Contract, Order, Trade
except ImportError:
    print("⚠️  ib_insync not installed. Run: pip install ib_insync")
    IB = None

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


class IBBroker:
    """
    Interactive Brokers Paper Trading Broker.

    Handles:
    - Order execution (market orders with stop/target brackets)
    - Position tracking
    - Portfolio management
    - Risk checks

    Compatible with Canadian residents via IB Canada.
    """

    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 7497,  # Paper trading port (7496 for live)
        client_id: int = 1,
        paper: bool = True,
        initial_capital: float = 25000,
        max_position_pct: float = 0.10,
        risk_per_trade_pct: float = 0.01,
        max_concurrent: int = 5,
    ):
        """
        Initialize Interactive Brokers connection.

        Args:
            host: TWS/Gateway host (default localhost)
            port: TWS/Gateway port (7497 for paper, 7496 for live)
            client_id: Client ID for connection
            paper: Using paper trading (default True)
            initial_capital: Starting capital
            max_position_pct: Max position size (% of capital)
            risk_per_trade_pct: Risk per trade (% of capital)
            max_concurrent: Max concurrent positions
        """
        if IB is None:
            raise ImportError("ib_insync not installed. Run: pip install ib_insync")

        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.paper = paper

        # Risk parameters
        self.initial_capital = initial_capital
        self.max_position_pct = max_position_pct
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_concurrent = max_concurrent

        # Connection state
        self.connected = False
        self._position_metadata: Dict[str, Dict[str, object]] = {}

        logger.info(f"✅ IBBroker initialized ({'PAPER' if paper else 'LIVE'} trading)")
        logger.info(f"   Host: {host}:{port}")

    def connect(self):
        """Connect to TWS/Gateway."""
        if self.connected:
            logger.info("Already connected to IB")
            return True

        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self.connected = True
            logger.info(f"✅ Connected to Interactive Brokers")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to IB: {e}")
            logger.error(f"   Make sure TWS or IB Gateway is running")
            logger.error(f"   Paper Trading Port: 7497, Live Port: 7496")
            return False

    def disconnect(self):
        """Disconnect from TWS/Gateway."""
        if self.connected:
            self.ib.disconnect()
            self.connected = False
            logger.info("Disconnected from IB")

    def get_account(self) -> dict:
        """Get account information."""
        if not self.connected:
            logger.error("Not connected to IB")
            return {}

        try:
            account_values = self.ib.accountValues()

            # Extract key values
            account_data = {item.tag: float(item.value) for item in account_values if item.value}

            cash = account_data.get('TotalCashValue', 0)
            net_liquidation = account_data.get('NetLiquidation', 0)
            buying_power = account_data.get('BuyingPower', 0)

            return {
                'cash': cash,
                'portfolio_value': net_liquidation,
                'buying_power': buying_power,
                'equity': net_liquidation,
                'positions_count': len(self.get_positions()),
            }
        except Exception as e:
            logger.error(f"❌ Failed to get account: {e}")
            return {}

    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        if not self.connected:
            logger.error("Not connected to IB")
            return []

        try:
            ib_positions = self.ib.positions()
            positions = []

            for pos in ib_positions:
                contract = pos.contract
                if contract.secType != 'STK':  # Only stocks
                    continue

                ticker = contract.symbol
                qty = int(pos.position)
                entry_price = pos.avgCost / abs(qty) if qty != 0 else 0

                # Get current price
                current_price = self.get_current_price(ticker)
                if current_price is None:
                    continue

                # Calculate P&L
                unrealized_pnl = (current_price - entry_price) * qty
                unrealized_pnl_pct = ((current_price / entry_price) - 1) * 100 if entry_price > 0 else 0

                meta = self._position_metadata.get(ticker.upper(), {})
                positions.append(Position(
                    ticker=ticker,
                    qty=qty,
                    entry_price=entry_price,
                    current_price=current_price,
                    stop_price=float(meta.get("stop_price", 0.0) or 0.0),
                    target_price=float(meta.get("target_price", 0.0) or 0.0),
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    signal_id=str(meta.get("signal_id", "")),
                    entry_date=meta.get("entry_time", datetime.now()),
                ))

            return positions

        except Exception as e:
            logger.error(f"❌ Failed to get positions: {e}")
            return []

    def get_current_price(self, ticker: str) -> Optional[float]:
        """Get current price for ticker."""
        if not self.connected:
            return None

        try:
            contract = Stock(ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Request market data
            ticker_obj = self.ib.reqMktData(contract, '', False, False)
            self.ib.sleep(2)  # Wait for data

            # Get last price
            if ticker_obj.last > 0:
                price = ticker_obj.last
            elif ticker_obj.close > 0:
                price = ticker_obj.close
            else:
                price = None

            # Cancel market data
            self.ib.cancelMktData(contract)

            return price

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
        if not self.connected:
            logger.error("Not connected to IB")
            return None

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
            # Create contract
            contract = Stock(order.ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Create market order
            action = 'BUY' if order.action == 'BUY' else 'SELL'
            market_order = MarketOrder(action, qty)

            ticker_key = order.ticker.upper()
            self._position_metadata[ticker_key] = {
                "stop_price": order.stop_price,
                "target_price": order.target_price,
                "signal_id": order.signal_id,
                "entry_time": datetime.utcnow(),
            }

            # Place order
            trade = self.ib.placeOrder(contract, market_order)
            order_id = str(trade.order.orderId)

            logger.info(f"✅ Entry order submitted: {order_id}")

            # Wait for fill
            self.ib.sleep(2)

            # TODO: Submit bracket orders (stop loss + take profit)
            # Note: IB requires waiting for entry fill before submitting brackets

            logger.info(f"{'='*70}\n")

            return order_id

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
        if not self.connected:
            logger.error("Not connected to IB")
            return False

        try:
            # Find position
            positions = self.get_positions()
            position = None
            for pos in positions:
                if pos.ticker == ticker:
                    position = pos
                    break

            if position is None:
                logger.warning(f"No position found for {ticker}")
                return False

            # Create contract
            contract = Stock(ticker, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)

            # Create closing order (opposite action)
            action = 'SELL' if position.qty > 0 else 'BUY'
            qty = abs(position.qty)
            market_order = MarketOrder(action, qty)

            # Place order
            trade = self.ib.placeOrder(contract, market_order)

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

    def get_order_status(self, order_id: int) -> Optional[Dict]:
        """Get status of order."""
        if not self.connected:
            return None

        try:
            trades = self.ib.trades()
            for trade in trades:
                if trade.order.orderId == order_id:
                    return {
                        'id': trade.order.orderId,
                        'status': trade.orderStatus.status,
                        'filled_qty': trade.orderStatus.filled,
                        'filled_avg_price': trade.orderStatus.avgFillPrice,
                    }
            return None
        except Exception as e:
            logger.error(f"❌ Failed to get order {order_id}: {e}")
            return None

    def cancel_order(self, order_id: int) -> bool:
        """Cancel open order."""
        if not self.connected:
            return False

        try:
            trades = self.ib.trades()
            for trade in trades:
                if trade.order.orderId == order_id:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"✅ Cancelled order {order_id}")
                    return True

            logger.warning(f"Order {order_id} not found")
            return False

        except Exception as e:
            logger.error(f"❌ Failed to cancel order {order_id}: {e}")
            return False


# Convenience functions

def create_paper_broker(
    initial_capital: float = 25000,
    risk_per_trade: float = 0.01,
) -> IBBroker:
    """Create paper trading broker with sensible defaults."""
    broker = IBBroker(
        host='127.0.0.1',
        port=7497,  # Paper trading port
        paper=True,
        initial_capital=initial_capital,
        max_position_pct=0.10,  # 10% max position
        risk_per_trade_pct=risk_per_trade,
        max_concurrent=5,
    )
    broker.connect()
    return broker


def create_live_broker(
    initial_capital: float = 25000,
    risk_per_trade: float = 0.005,  # 0.5% for live
) -> IBBroker:
    """Create live trading broker (use with caution!)."""
    broker = IBBroker(
        host='127.0.0.1',
        port=7496,  # Live trading port
        paper=False,
        initial_capital=initial_capital,
        max_position_pct=0.05,  # 5% max position (more conservative)
        risk_per_trade_pct=risk_per_trade,
        max_concurrent=3,  # Fewer concurrent for live
    )
    broker.connect()
    return broker
