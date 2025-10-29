"""Broker API integration layer for live trading."""

from __future__ import annotations

import io
import logging
import os
from contextlib import redirect_stderr, redirect_stdout
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


class OrderSide(Enum):
    """Order side."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class OrderStatus(Enum):
    """Order status."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


@dataclass
class Position:
    """Current position."""

    ticker: str
    shares: int
    avg_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class Order:
    """Order details."""

    order_id: str
    ticker: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_qty: int = 0
    filled_price: Optional[float] = None
    submitted_at: Optional[str] = None
    filled_at: Optional[str] = None


@dataclass
class Account:
    """Account information."""

    cash: float
    portfolio_value: float
    buying_power: float
    equity: float
    positions: List[Position]


class BrokerAPI(ABC):
    """Abstract base class for broker integrations."""

    @abstractmethod
    def get_account(self) -> Account:
        """Get account information."""
        ...

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get current positions."""
        ...

    @abstractmethod
    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for specific ticker."""
        ...

    @abstractmethod
    def place_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Place an order."""
        ...

    @abstractmethod
    def place_bracket_order(
        self,
        ticker: str,
        quantity: int,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> Dict[str, Order]:
        """Place bracket order (entry + stop + target)."""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        ...

    @abstractmethod
    def get_order(self, order_id: str) -> Order:
        """Get order status."""
        ...

    @abstractmethod
    def close_position(self, ticker: str) -> Order:
        """Close an entire position."""
        ...

    @abstractmethod
    def is_market_open(self) -> bool:
        """Check if market is open."""
        ...


# ==============================================================================
# PAPER BROKER (for testing)
# ==============================================================================


class PaperBroker(BrokerAPI):
    """Paper trading broker (no real money)."""

    def __init__(self, initial_cash: float = 100_000.0):
        self.cash = initial_cash
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0

    def get_account(self) -> Account:
        """Get account information."""
        portfolio_value = self.cash + sum(p.market_value for p in self.positions.values())
        return Account(
            cash=self.cash,
            portfolio_value=portfolio_value,
            buying_power=self.cash,
            equity=portfolio_value,
            positions=list(self.positions.values()),
        )

    def get_positions(self) -> List[Position]:
        """Get current positions."""
        return list(self.positions.values())

    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for specific ticker."""
        return self.positions.get(ticker)

    def place_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Place an order (paper)."""
        self.order_counter += 1
        order_id = f"PAPER-{self.order_counter}"

        order = Order(
            order_id=order_id,
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
            status=OrderStatus.SUBMITTED,
            submitted_at=datetime.now().isoformat(),
        )

        self.orders[order_id] = order

        # Simulate immediate fill for market orders
        if order_type == OrderType.MARKET:
            fill_price = limit_price or 100.0  # Simplified - should fetch real quote
            self._fill_order(order_id, fill_price, quantity)

        return order

    def place_bracket_order(
        self,
        ticker: str,
        quantity: int,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> Dict[str, Order]:
        """Place bracket order (entry + stop + target)."""
        # Entry order
        entry_order = self.place_order(
            ticker=ticker,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=entry_price,
        )

        # Stop loss order (triggered after entry fills)
        stop_order = Order(
            order_id=f"PAPER-{self.order_counter + 1}",
            ticker=ticker,
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=quantity,
            stop_price=stop_price,
            status=OrderStatus.PENDING,
        )
        self.orders[stop_order.order_id] = stop_order

        # Target order (triggered after entry fills)
        target_order = Order(
            order_id=f"PAPER-{self.order_counter + 2}",
            ticker=ticker,
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            limit_price=target_price,
            status=OrderStatus.PENDING,
        )
        self.orders[target_order.order_id] = target_order

        self.order_counter += 2

        return {
            "entry": entry_order,
            "stop": stop_order,
            "target": target_order,
        }

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        if order_id in self.orders:
            self.orders[order_id].status = OrderStatus.CANCELLED
            return True
        return False

    def get_order(self, order_id: str) -> Order:
        """Get order status."""
        return self.orders.get(order_id)

    def close_position(self, ticker: str) -> Order:
        """Close an entire position."""
        position = self.positions.get(ticker)
        if not position:
            raise ValueError(f"No position found for {ticker}")

        return self.place_order(
            ticker=ticker,
            side=OrderSide.SELL,
            quantity=position.shares,
            order_type=OrderType.MARKET,
        )

    def is_market_open(self) -> bool:
        """Check if market is open."""
        now = datetime.now()
        # Simplified: weekdays 9:30 AM - 4:00 PM ET
        return now.weekday() < 5 and 9 <= now.hour < 16

    def _fill_order(self, order_id: str, fill_price: float, fill_qty: int) -> None:
        """Internal: simulate order fill."""
        order = self.orders[order_id]
        order.status = OrderStatus.FILLED
        order.filled_price = fill_price
        order.filled_qty = fill_qty
        order.filled_at = datetime.now().isoformat()

        # Update positions
        if order.side == OrderSide.BUY:
            self.cash -= fill_price * fill_qty
            if order.ticker in self.positions:
                # Add to existing position
                pos = self.positions[order.ticker]
                total_shares = pos.shares + fill_qty
                total_cost = (pos.avg_price * pos.shares) + (fill_price * fill_qty)
                pos.shares = total_shares
                pos.avg_price = total_cost / total_shares
                pos.current_price = fill_price
                pos.market_value = fill_price * total_shares
                pos.unrealized_pnl = (fill_price - pos.avg_price) * total_shares
                pos.unrealized_pnl_pct = pos.unrealized_pnl / (pos.avg_price * total_shares)
            else:
                # New position
                self.positions[order.ticker] = Position(
                    ticker=order.ticker,
                    shares=fill_qty,
                    avg_price=fill_price,
                    current_price=fill_price,
                    market_value=fill_price * fill_qty,
                    unrealized_pnl=0.0,
                    unrealized_pnl_pct=0.0,
                )
        else:  # SELL
            self.cash += fill_price * fill_qty
            if order.ticker in self.positions:
                pos = self.positions[order.ticker]
                pos.shares -= fill_qty
                if pos.shares <= 0:
                    del self.positions[order.ticker]
                else:
                    pos.market_value = pos.current_price * pos.shares
                    pos.unrealized_pnl = (pos.current_price - pos.avg_price) * pos.shares


# ==============================================================================
# ALPACA INTEGRATION
# ==============================================================================


class AlpacaBroker(BrokerAPI):
    """Alpaca API integration."""

    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import (
                MarketOrderRequest,
                LimitOrderRequest,
                StopLossRequest,
                TakeProfitRequest,
            )
            from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce
        except ImportError:
            raise ImportError(
                "alpaca-py not installed. Run: pip install alpaca-py"
            )

        self.client = TradingClient(api_key, secret_key, paper=paper)
        self.MarketOrderRequest = MarketOrderRequest
        self.LimitOrderRequest = LimitOrderRequest
        self.StopLossRequest = StopLossRequest
        self.TakeProfitRequest = TakeProfitRequest
        self.AlpacaSide = AlpacaSide
        self.TimeInForce = TimeInForce

    def get_account(self) -> Account:
        """Get account information."""
        acct = self.client.get_account()
        positions = self.get_positions()

        return Account(
            cash=float(acct.cash),
            portfolio_value=float(acct.portfolio_value),
            buying_power=float(acct.buying_power),
            equity=float(acct.equity),
            positions=positions,
        )

    def get_positions(self) -> List[Position]:
        """Get current positions."""
        positions = self.client.get_all_positions()
        return [
            Position(
                ticker=p.symbol,
                shares=int(p.qty),
                avg_price=float(p.avg_entry_price),
                current_price=float(p.current_price),
                market_value=float(p.market_value),
                unrealized_pnl=float(p.unrealized_pl),
                unrealized_pnl_pct=float(p.unrealized_plpc),
            )
            for p in positions
        ]

    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for specific ticker."""
        try:
            p = self.client.get_open_position(ticker)
            return Position(
                ticker=p.symbol,
                shares=int(p.qty),
                avg_price=float(p.avg_entry_price),
                current_price=float(p.current_price),
                market_value=float(p.market_value),
                unrealized_pnl=float(p.unrealized_pl),
                unrealized_pnl_pct=float(p.unrealized_plpc),
            )
        except Exception:
            return None

    def place_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Place an order."""
        alpaca_side = (
            self.AlpacaSide.BUY if side == OrderSide.BUY else self.AlpacaSide.SELL
        )

        if order_type == OrderType.MARKET:
            request = self.MarketOrderRequest(
                symbol=ticker,
                qty=quantity,
                side=alpaca_side,
                time_in_force=self.TimeInForce.DAY,
            )
        elif order_type == OrderType.LIMIT:
            request = self.LimitOrderRequest(
                symbol=ticker,
                qty=quantity,
                side=alpaca_side,
                limit_price=limit_price,
                time_in_force=self.TimeInForce.DAY,
            )
        else:
            raise ValueError(f"Order type {order_type} not yet implemented")

        alpaca_order = self.client.submit_order(request)

        return Order(
            order_id=str(alpaca_order.id),
            ticker=alpaca_order.symbol,
            side=side,
            order_type=order_type,
            quantity=int(alpaca_order.qty),
            limit_price=float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
            status=self._map_status(alpaca_order.status),
            submitted_at=str(alpaca_order.submitted_at),
        )

    def place_bracket_order(
        self,
        ticker: str,
        quantity: int,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> Dict[str, Order]:
        """Place bracket order (entry + stop + target)."""
        # Alpaca supports bracket orders natively
        request = self.LimitOrderRequest(
            symbol=ticker,
            qty=quantity,
            side=self.AlpacaSide.BUY,
            limit_price=entry_price,
            time_in_force=self.TimeInForce.DAY,
            order_class="bracket",
            take_profit=self.TakeProfitRequest(limit_price=target_price),
            stop_loss=self.StopLossRequest(stop_price=stop_price),
        )

        alpaca_order = self.client.submit_order(request)

        # Main order
        entry_order = Order(
            order_id=str(alpaca_order.id),
            ticker=alpaca_order.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=quantity,
            limit_price=entry_price,
            status=self._map_status(alpaca_order.status),
        )

        # Alpaca returns leg IDs in the response
        return {
            "entry": entry_order,
            "stop": None,  # Alpaca manages internally
            "target": None,  # Alpaca manages internally
        }

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            self.client.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    def get_order(self, order_id: str) -> Order:
        """Get order status."""
        alpaca_order = self.client.get_order_by_id(order_id)

        return Order(
            order_id=str(alpaca_order.id),
            ticker=alpaca_order.symbol,
            side=OrderSide.BUY if alpaca_order.side == "buy" else OrderSide.SELL,
            order_type=OrderType.MARKET,  # Simplified
            quantity=int(alpaca_order.qty),
            filled_qty=int(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0,
            filled_price=(
                float(alpaca_order.filled_avg_price)
                if alpaca_order.filled_avg_price
                else None
            ),
            status=self._map_status(alpaca_order.status),
            submitted_at=str(alpaca_order.submitted_at),
            filled_at=str(alpaca_order.filled_at) if alpaca_order.filled_at else None,
        )

    def close_position(self, ticker: str) -> Order:
        """Close an entire position."""
        position = self.get_position(ticker)
        if not position:
            raise ValueError(f"No position found for {ticker}")

        return self.place_order(
            ticker=ticker,
            side=OrderSide.SELL,
            quantity=position.shares,
            order_type=OrderType.MARKET,
        )

    def is_market_open(self) -> bool:
        """Check if market is open."""
        clock = self.client.get_clock()
        return clock.is_open

    def _map_status(self, alpaca_status: str) -> OrderStatus:
        """Map Alpaca status to our enum."""
        mapping = {
            "new": OrderStatus.SUBMITTED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
            "filled": OrderStatus.FILLED,
            "done_for_day": OrderStatus.CANCELLED,
            "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.CANCELLED,
            "replaced": OrderStatus.CANCELLED,
            "pending_cancel": OrderStatus.CANCELLED,
            "pending_replace": OrderStatus.PENDING,
            "pending_new": OrderStatus.PENDING,
            "accepted": OrderStatus.SUBMITTED,
            "pending_review": OrderStatus.PENDING,
            "rejected": OrderStatus.REJECTED,
            "suspended": OrderStatus.PENDING,
            "stopped": OrderStatus.CANCELLED,
        }
        return mapping.get(alpaca_status.lower(), OrderStatus.PENDING)


# ==============================================================================
# QUESTRADE INTEGRATION (CANADA)
# ==============================================================================


class QuestradeBroker(BrokerAPI):
    """Questrade API integration (Canadian broker)."""

    def __init__(self, refresh_token: str, paper: bool = True):
        try:
            from questrade_api import Questrade
        except ImportError:
            raise ImportError(
                "questrade-api not installed. Run: pip install questrade-api"
            )

        self.qt = Questrade(refresh_token=refresh_token)
        self.paper = paper
        # Get account ID (use first account by default)
        accounts = self.qt.accounts
        if not accounts or not accounts.get("accounts"):
            raise ValueError("No Questrade accounts found")
        self.account_id = accounts["accounts"][0]["number"]

    def get_account(self) -> Account:
        """Get account information."""
        balances = self.qt.account_balances(self.account_id)
        positions = self.get_positions()

        # Extract CAD cash
        cad_balance = next(
            (b for b in balances["perCurrencyBalances"] if b["currency"] == "CAD"),
            {"cash": 0, "totalEquity": 0, "buyingPower": 0}
        )

        return Account(
            cash=float(cad_balance.get("cash", 0)),
            portfolio_value=float(cad_balance.get("totalEquity", 0)),
            buying_power=float(cad_balance.get("buyingPower", 0)),
            equity=float(cad_balance.get("totalEquity", 0)),
            positions=positions,
        )

    def get_positions(self) -> List[Position]:
        """Get current positions."""
        positions_data = self.qt.account_positions(self.account_id)

        positions = []
        for p in positions_data.get("positions", []):
            if p.get("openQuantity", 0) > 0:
                positions.append(
                    Position(
                        ticker=p["symbol"],
                        shares=int(p["openQuantity"]),
                        avg_price=float(p["averageEntryPrice"]),
                        current_price=float(p["currentPrice"]),
                        market_value=float(p["currentMarketValue"]),
                        unrealized_pnl=float(p.get("openPnl", 0)),
                        unrealized_pnl_pct=(
                            float(p.get("openPnl", 0)) / float(p["currentMarketValue"])
                            if p.get("currentMarketValue", 0) > 0 else 0.0
                        ),
                    )
                )
        return positions

    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for specific ticker."""
        positions = self.get_positions()
        return next((p for p in positions if p.ticker == ticker), None)

    def place_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Place an order."""
        # Get symbol ID from ticker
        symbol_info = self.qt.symbols_search(prefix=ticker)
        if not symbol_info.get("symbols"):
            raise ValueError(f"Symbol {ticker} not found")

        symbol_id = symbol_info["symbols"][0]["symbolId"]

        # Map order types
        qt_order_type = "Market" if order_type == OrderType.MARKET else "Limit"
        qt_side = "Buy" if side == OrderSide.BUY else "Sell"

        # Build order request
        order_request = {
            "accountNumber": self.account_id,
            "symbolId": symbol_id,
            "quantity": quantity,
            "orderType": qt_order_type,
            "timeInForce": "Day",
            "action": qt_side,
        }

        if order_type == OrderType.LIMIT and limit_price:
            order_request["limitPrice"] = limit_price

        # Place order
        result = self.qt.account_order(order_request)

        if not result.get("orders"):
            raise ValueError("Order placement failed")

        qt_order = result["orders"][0]

        return Order(
            order_id=str(qt_order["id"]),
            ticker=ticker,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            status=self._map_status(qt_order.get("state", "Pending")),
            submitted_at=qt_order.get("creationTime"),
        )

    def place_bracket_order(
        self,
        ticker: str,
        quantity: int,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> Dict[str, Order]:
        """Place bracket order (Questrade uses separate orders)."""
        # Entry order
        entry_order = self.place_order(
            ticker=ticker,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=entry_price,
        )

        # Note: Questrade doesn't have native bracket orders
        # You would need to manually place stop/target after entry fills
        # For now, return entry order only
        return {
            "entry": entry_order,
            "stop": None,  # Would need to be placed after entry fills
            "target": None,  # Would need to be placed after entry fills
        }

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            result = self.qt.account_order_cancel(order_id)
            return result.get("orderId") == int(order_id)
        except Exception:
            return False

    def get_order(self, order_id: str) -> Order:
        """Get order status."""
        result = self.qt.account_order(order_id)

        if not result.get("orders"):
            raise ValueError(f"Order {order_id} not found")

        qt_order = result["orders"][0]

        return Order(
            order_id=str(qt_order["id"]),
            ticker=qt_order.get("symbol", ""),
            side=OrderSide.BUY if qt_order["side"] == "Buy" else OrderSide.SELL,
            order_type=OrderType.MARKET,  # Simplified
            quantity=int(qt_order["totalQuantity"]),
            filled_qty=int(qt_order.get("filledQuantity", 0)),
            filled_price=(
                float(qt_order.get("avgExecPrice"))
                if qt_order.get("avgExecPrice") else None
            ),
            status=self._map_status(qt_order.get("state", "Pending")),
            submitted_at=qt_order.get("creationTime"),
        )

    def close_position(self, ticker: str) -> Order:
        """Close an entire position."""
        position = self.get_position(ticker)
        if not position:
            raise ValueError(f"No position found for {ticker}")

        return self.place_order(
            ticker=ticker,
            side=OrderSide.SELL,
            quantity=position.shares,
            order_type=OrderType.MARKET,
        )

    def is_market_open(self) -> bool:
        """Check if market is open."""
        # Simplified - Questrade API has time endpoint
        # For now, use same logic as US markets (TSX hours are similar)
        now = datetime.now()
        return now.weekday() < 5 and 9 <= now.hour < 16

    def _map_status(self, qt_status: str) -> OrderStatus:
        """Map Questrade status to our enum."""
        mapping = {
            "Pending": OrderStatus.PENDING,
            "Accepted": OrderStatus.SUBMITTED,
            "Rejected": OrderStatus.REJECTED,
            "PartialFilled": OrderStatus.PARTIALLY_FILLED,
            "Filled": OrderStatus.FILLED,
            "Canceled": OrderStatus.CANCELLED,
            "Expired": OrderStatus.CANCELLED,
        }
        return mapping.get(qt_status, OrderStatus.PENDING)


# ==============================================================================
# INTERACTIVE BROKERS INTEGRATION (GLOBAL/CANADA)
# ==============================================================================


class IBKRBroker(BrokerAPI):
    """Interactive Brokers integration (Canada + Global)."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,
        client_id: int = 7,
        account_id: Optional[str] = None,
        allow_simulation: bool = True,
    ):
        try:
            from ib_insync import IB, Stock, MarketOrder, LimitOrder, StopOrder, Order as IBOrder
        except ImportError:
            raise ImportError(
                "ib_insync not installed. Run: pip install ib_insync"
            )

        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.allow_simulation = allow_simulation

        self.Stock = Stock
        self.MarketOrder = MarketOrder
        self.LimitOrder = LimitOrder
        self.StopOrder = StopOrder
        self.IBOrder = IBOrder

        logger = logging.getLogger(__name__)
        self._ib_original_error_handler = self.ib.wrapper.error

        def _filtered_ib_error(req_id, error_code, error_string, contract):
            message = (error_string or "")
            if (
                error_code == 321
                and "Group name cannot be null" in message
            ) or "request timed out" in message.lower():
                logger.debug(
                    "Suppressed IBKR warning (code=%s, reqId=%s): %s",
                    error_code,
                    req_id,
                    message,
                )
                return

            return self._ib_original_error_handler(
                req_id,
                error_code,
                error_string,
                contract,
            )

        self.ib.wrapper.error = _filtered_ib_error

        self.connected = False
        self.account_id = account_id or "DU0071381"

        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()

        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                self.ib.connect(host, port, clientId=client_id)
                self.connected = True

                accounts = self.ib.managedAccounts()
                if accounts:
                    if account_id and account_id in accounts:
                        self.account_id = account_id
                    else:
                        self.account_id = accounts[0]

                try:
                    self.ib.reqAccountUpdates(True, self.account_id)
                    self.ib.waitOnUpdate(timeout=1)
                finally:
                    try:
                        self.ib.reqAccountUpdates(False, self.account_id)
                    except Exception:
                        pass

                try:
                    self.ib.reqPositions()
                    self.ib.waitOnUpdate(timeout=1)
                finally:
                    try:
                        self.ib.cancelPositions()
                    except Exception:
                        pass
        except Exception as exc:
            self.connected = False
            if not allow_simulation:
                raise ConnectionError(f"Failed to connect to IBKR: {exc}") from exc
        finally:
            self._log_ib_console_output(stdout_buffer.getvalue(), stderr_buffer.getvalue())

    def _log_ib_console_output(self, stdout: str, stderr: str) -> None:
        """Filter noisy IBKR console output and log only actionable warnings."""
        logger = logging.getLogger(__name__)
        suppressed_phrases = (
            "request timed out",
            "Group name cannot be null",
        )

        for stream_output in (stdout, stderr):
            if not stream_output:
                continue

            for line in stream_output.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                lowered = stripped.lower()
                if any(phrase in lowered for phrase in suppressed_phrases):
                    logger.debug("Suppressed IBKR console message: %s", stripped)
                    continue
                logger.warning("IBKR console message: %s", stripped)

    def _scrub_fa_fields(self, order):
        """Force-clear all FA fields from orders (as per user code)."""
        fa_fields = ["faGroup", "faProfile", "faMethod", "faPercentage", "account",
                     "allocationMethod", "group", "profile"]

        for field in fa_fields:
            if hasattr(order, field):
                setattr(order, field, None)

        # Explicitly set account (never None)
        order.account = self.account_id

    def __del__(self):
        """Disconnect on cleanup."""
        if not hasattr(self, "ib") or not self.ib:
            return

        if hasattr(self, "_ib_original_error_handler") and getattr(self.ib, "wrapper", None):
            self.ib.wrapper.error = self._ib_original_error_handler

        if self.ib.isConnected():
            self.ib.disconnect()

    def get_account(self) -> Account:
        """Get account information from IBKR."""
        if not self.connected:
            # Return dummy data when not connected
            return Account(
                cash=100000.0,
                portfolio_value=100000.0,
                buying_power=100000.0,
                equity=100000.0,
                positions=[],
            )

        try:
            summary = self.ib.accountSummary()

            if self.account_id:
                filtered = [
                    item
                    for item in summary
                    if not getattr(item, "account", None)
                    or item.account == self.account_id
                ]
                if filtered:
                    summary = filtered

            def _val(tag: str, default: float = 0.0) -> float:
                for item in summary:
                    if item.tag == tag and (not item.account or item.account == self.account_id):
                        try:
                            return float(item.value)
                        except (TypeError, ValueError):
                            return default
                return default

            positions = self.get_positions()

            net_liquidation = _val("NetLiquidation") or sum(p.market_value for p in positions)
            cash = _val("TotalCashValue")
            buying_power = _val("BuyingPower", default=net_liquidation)

            return Account(
                cash=cash,
                portfolio_value=net_liquidation,
                buying_power=buying_power,
                equity=net_liquidation,
                positions=positions,
            )
        except Exception as exc:
            if self.allow_simulation:
                return Account(
                    cash=100000.0,
                    portfolio_value=100000.0,
                    buying_power=100000.0,
                    equity=100000.0,
                    positions=[],
                )
            raise RuntimeError(f"Failed to retrieve IBKR account summary: {exc}") from exc

    def get_positions(self) -> List[Position]:
        """Get current positions."""
        if not self.connected:
            # Return empty positions when not connected
            return []

        try:
            positions = []
            for pos in self.ib.positions():
                if hasattr(pos, "account") and pos.account and pos.account != self.account_id:
                    continue

                contract = pos.contract
                # Ensure contract details are populated
                if not contract.conId:
                    self.ib.qualifyContracts(contract)

                try:
                    ticker = self.ib.reqTickers(contract)
                    current_price = ticker[0].marketPrice() if ticker else float(pos.avgCost)
                except Exception:
                    current_price = float(pos.avgCost)

                market_value = float(pos.position) * current_price
                unrealized = (current_price - float(pos.avgCost)) * float(pos.position)

                positions.append(
                    Position(
                        ticker=contract.symbol,
                        shares=int(pos.position),
                        avg_price=float(pos.avgCost),
                        current_price=current_price,
                        market_value=market_value,
                        unrealized_pnl=unrealized,
                        unrealized_pnl_pct=(unrealized / market_value) if market_value else 0.0,
                    )
                )

            return positions
        except Exception as exc:
            if self.allow_simulation:
                return []
            raise RuntimeError(f"Failed to retrieve IBKR positions: {exc}") from exc

    def get_position(self, ticker: str) -> Optional[Position]:
        """Get position for specific ticker."""
        positions = self.get_positions()
        return next((p for p in positions if p.ticker == ticker), None)

    def place_order(
        self,
        ticker: str,
        side: OrderSide,
        quantity: int,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Order:
        """Place an order with comprehensive FA scrubbing (user's proven method)."""
        if not self.connected:
            # Simulate order placement when not connected
            import random
            order_id = f"IBKR-{random.randint(1000, 9999)}"
            return Order(
                order_id=order_id,
                ticker=ticker,
                side=side,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                status=OrderStatus.SUBMITTED,
                submitted_at=datetime.now().isoformat(),
            )

        try:
            contract = self.Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)

            action = side.value
            if order_type == OrderType.MARKET:
                ib_order = self.MarketOrder(action, quantity)
            elif order_type == OrderType.LIMIT and limit_price is not None:
                ib_order = self.LimitOrder(action, quantity, limit_price)
            else:
                raise ValueError(f"Order type {order_type} requires additional parameters")

            self._scrub_fa_fields(ib_order)

            trade = self.ib.placeOrder(contract, ib_order)
            self.ib.waitOnUpdate(timeout=5)

            return Order(
                order_id=str(trade.order.orderId),
                ticker=ticker,
                side=side,
                order_type=order_type,
                quantity=quantity,
                limit_price=limit_price,
                status=self._map_status(trade.orderStatus.status),
                submitted_at=datetime.now().isoformat(),
            )
        except Exception as exc:
            if self.allow_simulation:
                import random

                order_id = f"IBKR-{random.randint(1000, 9999)}"
                return Order(
                    order_id=order_id,
                    ticker=ticker,
                    side=side,
                    order_type=order_type,
                    quantity=quantity,
                    limit_price=limit_price,
                    status=OrderStatus.SUBMITTED,
                    submitted_at=datetime.now().isoformat(),
                )
            raise RuntimeError(f"Failed to place IBKR order: {exc}") from exc

    def place_bracket_order(
        self,
        ticker: str,
        quantity: int,
        entry_price: float,
        stop_price: float,
        target_price: float,
    ) -> Dict[str, Order]:
        """Place bracket order with OCO and FA scrubbing (as per user code)."""
        if not self.connected:
            # Simulate bracket order placement when not connected
            import random
            entry_order = Order(
                order_id=f"IBKR-{random.randint(1000, 9999)}",
                ticker=ticker,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                quantity=quantity,
                limit_price=entry_price,
                status=OrderStatus.SUBMITTED,
                submitted_at=datetime.now().isoformat(),
            )
            return {
                "entry": entry_order,
                "stop": None,  # Not implemented in simulation
                "target": None,  # Not implemented in simulation
            }

        try:
            contract = self.Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)

            parent = self.LimitOrder("BUY", quantity, entry_price, transmit=False)
            target = self.LimitOrder("SELL", quantity, target_price, transmit=False)
            stop = self.StopOrder("SELL", quantity, stop_price, transmit=True)

            for o in (parent, target, stop):
                self._scrub_fa_fields(o)

            parent_trade = self.ib.placeOrder(contract, parent)
            self.ib.waitOnUpdate(timeout=2)

            parent_id = parent_trade.order.orderId
            oca_group = f"OCA_{parent_id}"

            target.parentId = parent_id
            target.ocaGroup = oca_group
            target.ocaType = 1  # CANCEL_WITH_BLOCK

            stop.parentId = parent_id
            stop.ocaGroup = oca_group
            stop.ocaType = 1

            target_trade = self.ib.placeOrder(contract, target)
            stop_trade = self.ib.placeOrder(contract, stop)
            self.ib.waitOnUpdate(timeout=2)

            return {
                "entry": Order(
                    order_id=str(parent_id),
                    ticker=ticker,
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=quantity,
                    limit_price=entry_price,
                    status=self._map_status(parent_trade.orderStatus.status),
                    submitted_at=datetime.now().isoformat(),
                ),
                "stop": Order(
                    order_id=str(stop_trade.order.orderId),
                    ticker=ticker,
                    side=OrderSide.SELL,
                    order_type=OrderType.STOP,
                    quantity=quantity,
                    stop_price=stop_price,
                    status=self._map_status(stop_trade.orderStatus.status),
                    submitted_at=datetime.now().isoformat(),
                ),
                "target": Order(
                    order_id=str(target_trade.order.orderId),
                    ticker=ticker,
                    side=OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    quantity=quantity,
                    limit_price=target_price,
                    status=self._map_status(target_trade.orderStatus.status),
                    submitted_at=datetime.now().isoformat(),
                ),
            }
        except Exception as exc:
            if self.allow_simulation:
                import random

                entry_order = Order(
                    order_id=f"IBKR-{random.randint(1000, 9999)}",
                    ticker=ticker,
                    side=OrderSide.BUY,
                    order_type=OrderType.LIMIT,
                    quantity=quantity,
                    limit_price=entry_price,
                    status=OrderStatus.SUBMITTED,
                    submitted_at=datetime.now().isoformat(),
                )
                return {
                    "entry": entry_order,
                    "stop": None,
                    "target": None,
                }
            raise RuntimeError(f"Failed to place IBKR bracket order: {exc}") from exc

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            # Find trade by order ID
            trades = self.ib.trades()
            trade = next((t for t in trades if str(t.order.orderId) == order_id), None)
            if trade:
                self.ib.cancelOrder(trade.order)
                return True
            return False
        except Exception:
            return False

    def get_order(self, order_id: str) -> Order:
        """Get order status."""
        trades = self.ib.trades()
        trade = next((t for t in trades if str(t.order.orderId) == order_id), None)

        if not trade:
            raise ValueError(f"Order {order_id} not found")

        return Order(
            order_id=str(trade.order.orderId),
            ticker=trade.contract.symbol,
            side=OrderSide.BUY if trade.order.action == "BUY" else OrderSide.SELL,
            order_type=OrderType.MARKET,  # Simplified
            quantity=int(trade.order.totalQuantity),
            filled_qty=int(trade.orderStatus.filled),
            filled_price=(
                float(trade.orderStatus.avgFillPrice)
                if trade.orderStatus.avgFillPrice > 0 else None
            ),
            status=self._map_status(trade.orderStatus.status),
        )

    def close_position(self, ticker: str) -> Order:
        """Close an entire position."""
        position = self.get_position(ticker)
        if not position:
            raise ValueError(f"No position found for {ticker}")

        return self.place_order(
            ticker=ticker,
            side=OrderSide.SELL,
            quantity=position.shares,
            order_type=OrderType.MARKET,
        )

    def is_market_open(self) -> bool:
        """Check if market is open."""
        # IBKR provides market data service status
        # Simplified check for now
        now = datetime.now()
        return now.weekday() < 5 and 9 <= now.hour < 16

    def _map_status(self, ib_status: str) -> OrderStatus:
        """Map IBKR status to our enum."""
        mapping = {
            "PendingSubmit": OrderStatus.PENDING,
            "PendingCancel": OrderStatus.PENDING,
            "PreSubmitted": OrderStatus.SUBMITTED,
            "Submitted": OrderStatus.SUBMITTED,
            "ApiPending": OrderStatus.PENDING,
            "ApiCancelled": OrderStatus.CANCELLED,
            "Cancelled": OrderStatus.CANCELLED,
            "Filled": OrderStatus.FILLED,
            "Inactive": OrderStatus.REJECTED,
        }
        return mapping.get(ib_status, OrderStatus.PENDING)


# ==============================================================================
# BROKER FACTORY
# ==============================================================================


def create_broker(broker_type: str, **kwargs) -> BrokerAPI:
    """Factory function to create broker instances.

    Can load credentials from:
    1. Explicit kwargs
    2. Environment variables
    3. configs/broker_credentials.yaml (fallback)
    """
    # Try to load from credentials file if not provided in kwargs
    if not kwargs:
        kwargs = load_broker_credentials(broker_type)
    if broker_type.lower() == "paper":
        return PaperBroker(initial_cash=kwargs.get("initial_cash", 100_000.0))
    elif broker_type.lower() == "alpaca":
        return AlpacaBroker(
            api_key=kwargs["api_key"],
            secret_key=kwargs["secret_key"],
            paper=kwargs.get("paper", True),
        )
    elif broker_type.lower() == "questrade":
        return QuestradeBroker(
            refresh_token=kwargs["refresh_token"],
            paper=kwargs.get("paper", True),
        )
    elif broker_type.lower() == "ibkr":
        return IBKRBroker(
            host=kwargs.get("host", "127.0.0.1"),
            port=kwargs.get("port", 7497),  # 7497 paper, 7496 live
            client_id=kwargs.get("client_id", 7),  # Use 7 as suggested by user
            account_id=kwargs.get("account_id"),
            allow_simulation=kwargs.get("allow_simulation", True),
        )
    else:
        raise ValueError(f"Unknown broker type: {broker_type}")


def _load_questrade_from_env() -> Optional[Dict]:
    """Load Questrade credentials from environment variables."""
    refresh_token = os.getenv("QUESTRADE_REFRESH_TOKEN")
    if refresh_token:
        return {
            "refresh_token": refresh_token,
            "paper": os.getenv("QUESTRADE_PAPER", "false").lower() == "true",
        }
    return None


def _load_alpaca_from_env() -> Optional[Dict]:
    """Load Alpaca credentials from environment variables."""
    api_key = os.getenv("ALPACA_API_KEY")
    api_secret = os.getenv("ALPACA_API_SECRET")
    if api_key and api_secret:
        return {
            "api_key": api_key,
            "secret_key": api_secret,
            "paper": os.getenv("ALPACA_PAPER", "true").lower() == "true",
        }
    return None


def _load_ibkr_from_env() -> Optional[Dict]:
    """Load IBKR credentials from environment variables."""
    account_id = os.getenv("IBKR_ACCOUNT_ID")
    if account_id:
        return {
            "host": os.getenv("IBKR_HOST", "127.0.0.1"),
            "port": int(os.getenv("IBKR_PORT", "7497")),
            "client_id": int(os.getenv("IBKR_CLIENT_ID", "1")),
            "account_id": account_id,
        }
    return None


def _load_credentials_from_env(broker_type: str) -> Optional[Dict]:
    """Load credentials from environment variables."""
    loaders = {
        "questrade": _load_questrade_from_env,
        "alpaca": _load_alpaca_from_env,
        "ibkr": _load_ibkr_from_env,
    }
    
    loader = loaders.get(broker_type)
    if loader:
        return loader()
    return None


def _extract_broker_credentials(broker_type: str, broker_config: Dict) -> Dict:
    """Extract credentials from broker config based on broker type."""
    if broker_type == "questrade":
        return {
            "refresh_token": broker_config["refresh_token"],
            "paper": broker_config.get("practice_account", False),
        }
    elif broker_type == "alpaca":
        return {
            "api_key": broker_config["api_key"],
            "secret_key": broker_config["api_secret"],
            "paper": broker_config.get("paper_trading", True),
        }
    elif broker_type == "ibkr":
        return {
            "host": broker_config.get("host", "127.0.0.1"),
            "port": broker_config.get("port", 7497),
            "client_id": broker_config.get("client_id", 7),  # Default to 7 as suggested
            "account_id": broker_config.get("account_id"),
            "allow_simulation": broker_config.get("allow_simulation", True),
        }
    elif broker_type == "paper":
        return {
            "initial_cash": broker_config.get("initial_capital", 100_000.0),
        }
    else:
        raise ValueError(f"Unknown broker type: {broker_type}")


def load_broker_credentials(broker_type: str) -> Dict:
    """Load broker credentials from YAML file or environment variables.

    Priority:
    1. Environment variables (production)
    2. configs/broker_credentials.yaml (development)

    Args:
        broker_type: Type of broker ('questrade', 'ibkr', 'alpaca', 'paper')

    Returns:
        Dictionary of credentials for the broker

    Raises:
        FileNotFoundError: If credentials file not found
        KeyError: If broker not configured in credentials file
    """
    broker_type = broker_type.lower()

    # Try environment variables first (production)
    env_creds = _load_credentials_from_env(broker_type)
    if env_creds:
        return env_creds

    # Fall back to credentials file (development)
    creds_path = Path("configs/broker_credentials.yaml")
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Credentials file not found: {creds_path}\n"
            f"Create it from template or set environment variables.\n"
            f"See QUESTRADE_SETUP.md for instructions."
        )

    try:
        import yaml
        with open(creds_path) as f:
            all_creds = yaml.safe_load(f)
    except ImportError:
        raise ImportError("pyyaml is required. Install with: pip install pyyaml")

    if broker_type not in all_creds:
        raise KeyError(
            f"Broker '{broker_type}' not found in {creds_path}\n"
            f"Available brokers: {list(all_creds.keys())}"
        )

    broker_config = all_creds[broker_type]

    if not broker_config.get("enabled", False):
        raise ValueError(
            f"Broker '{broker_type}' is disabled in {creds_path}\n"
            f"Set 'enabled: true' to use this broker."
        )

    return _extract_broker_credentials(broker_type, broker_config)
