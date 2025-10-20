"""Tests for bouncehunter/broker.py module."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from pathlib import Path
import tempfile
import os

from src.bouncehunter.broker import (
    # Enums
    OrderSide,
    OrderType,
    OrderStatus,
    # Data classes
    Position,
    Order,
    Account,
    # Abstract base class
    BrokerAPI,
    # Concrete implementations
    PaperBroker,
    AlpacaBroker,
    QuestradeBroker,
    IBKRBroker,
    # Factory and utilities
    create_broker,
    load_broker_credentials,
)


class TestEnums:
    """Test enum definitions."""

    def test_order_side_enum(self):
        """Test OrderSide enum values."""
        assert OrderSide.BUY.value == "BUY"
        assert OrderSide.SELL.value == "SELL"
        assert len(OrderSide) == 2

    def test_order_type_enum(self):
        """Test OrderType enum values."""
        assert OrderType.MARKET.value == "MARKET"
        assert OrderType.LIMIT.value == "LIMIT"
        assert OrderType.STOP.value == "STOP"
        assert OrderType.STOP_LIMIT.value == "STOP_LIMIT"
        assert len(OrderType) == 4

    def test_order_status_enum(self):
        """Test OrderStatus enum values."""
        assert OrderStatus.PENDING.value == "PENDING"
        assert OrderStatus.SUBMITTED.value == "SUBMITTED"
        assert OrderStatus.FILLED.value == "FILLED"
        assert OrderStatus.PARTIALLY_FILLED.value == "PARTIALLY_FILLED"
        assert OrderStatus.CANCELLED.value == "CANCELLED"
        assert OrderStatus.REJECTED.value == "REJECTED"
        assert len(OrderStatus) == 6


class TestDataClasses:
    """Test data class definitions."""

    def test_position_creation(self):
        """Test Position dataclass creation."""
        pos = Position(
            ticker="AAPL",
            shares=100,
            avg_price=150.0,
            current_price=155.0,
            market_value=15500.0,
            unrealized_pnl=500.0,
            unrealized_pnl_pct=0.0333,
        )
        assert pos.ticker == "AAPL"
        assert pos.shares == 100
        assert pos.avg_price == 150.0
        assert pos.current_price == 155.0
        assert pos.market_value == 15500.0
        assert pos.unrealized_pnl == 500.0
        assert pos.unrealized_pnl_pct == 0.0333

    def test_order_creation(self):
        """Test Order dataclass creation."""
        order = Order(
            order_id="TEST-123",
            ticker="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            limit_price=None,
            stop_price=None,
            status=OrderStatus.SUBMITTED,
            filled_qty=0,
            filled_price=None,
            submitted_at="2024-01-01T10:00:00",
            filled_at=None,
        )
        assert order.order_id == "TEST-123"
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 100
        assert order.status == OrderStatus.SUBMITTED

    def test_account_creation(self):
        """Test Account dataclass creation."""
        positions = [
            Position("AAPL", 100, 150.0, 155.0, 15500.0, 500.0, 0.0333),
            Position("MSFT", 50, 300.0, 310.0, 15500.0, 500.0, 0.0333),
        ]
        account = Account(
            cash=50000.0,
            portfolio_value=100000.0,
            buying_power=75000.0,
            equity=100000.0,
            positions=positions,
        )
        assert account.cash == 50000.0
        assert account.portfolio_value == 100000.0
        assert account.buying_power == 75000.0
        assert account.equity == 100000.0
        assert len(account.positions) == 2


class TestPaperBroker:
    """Test PaperBroker implementation."""

    @pytest.fixture
    def broker(self):
        """Create PaperBroker instance."""
        return PaperBroker(initial_cash=100000.0)

    def test_init(self, broker):
        """Test PaperBroker initialization."""
        assert broker.cash == 100000.0
        assert broker.positions == {}
        assert broker.orders == {}
        assert broker.order_counter == 0

    def test_get_account(self, broker):
        """Test get_account method."""
        account = broker.get_account()
        assert account.cash == 100000.0
        assert account.portfolio_value == 100000.0
        assert account.buying_power == 100000.0
        assert account.equity == 100000.0
        assert account.positions == []

    def test_get_positions_empty(self, broker):
        """Test get_positions with no positions."""
        positions = broker.get_positions()
        assert positions == []

    def test_get_position_none(self, broker):
        """Test get_position for non-existent ticker."""
        position = broker.get_position("AAPL")
        assert position is None

    def test_place_market_order_buy(self, broker):
        """Test placing market buy order."""
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        assert order.order_id == "PAPER-1"
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert order.status == OrderStatus.FILLED
        assert order.filled_price == 100.0  # Default fill price
        assert order.filled_qty == 100

        # Check position was created
        position = broker.get_position("AAPL")
        assert position is not None
        assert position.ticker == "AAPL"
        assert position.shares == 100
        assert position.avg_price == 100.0
        assert position.current_price == 100.0
        assert position.market_value == 10000.0

        # Check cash was reduced
        assert broker.cash == 90000.0

    def test_place_limit_order_buy(self, broker):
        """Test placing limit buy order (stays pending)."""
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=95.0,
        )

        assert order.order_id == "PAPER-1"
        assert order.status == OrderStatus.SUBMITTED
        assert order.limit_price == 95.0
        assert order.filled_price is None  # Not filled yet

    def test_place_order_sell_no_position(self, broker):
        """Test placing sell order with no position (short selling allowed)."""
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.SELL,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        # Should succeed (short selling)
        assert order.status == OrderStatus.FILLED
        assert broker.cash == 100000.0 + 100 * 100.0  # Cash increases from short sale

    def test_place_order_sell_with_position(self, broker):
        """Test placing sell order with existing position."""
        # First buy
        broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        # Then sell
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.SELL,
            quantity=50,
            order_type=OrderType.MARKET,
        )

        assert order.status == OrderStatus.FILLED
        assert broker.cash == 95000.0  # 90000 + 5000 from sale

        # Position should be reduced
        position = broker.get_position("AAPL")
        assert position.shares == 50

    def test_place_bracket_order(self, broker):
        """Test placing bracket order."""
        orders = broker.place_bracket_order(
            ticker="AAPL",
            quantity=100,
            entry_price=100.0,
            stop_price=95.0,
            target_price=110.0,
        )

        assert "entry" in orders
        assert "stop" in orders
        assert "target" in orders

        entry = orders["entry"]
        assert entry.side == OrderSide.BUY
        assert entry.order_type == OrderType.LIMIT
        assert entry.limit_price == 100.0

        stop = orders["stop"]
        assert stop.side == OrderSide.SELL
        assert stop.order_type == OrderType.STOP
        assert stop.stop_price == 95.0

        target = orders["target"]
        assert target.side == OrderSide.SELL
        assert target.order_type == OrderType.LIMIT
        assert target.limit_price == 110.0

    def test_cancel_order(self, broker):
        """Test canceling an order."""
        # Place a limit order (stays pending)
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=95.0,
        )

        # Cancel it
        result = broker.cancel_order(order.order_id)
        assert result is True

        # Check status
        retrieved = broker.get_order(order.order_id)
        assert retrieved.status == OrderStatus.CANCELLED

    def test_cancel_nonexistent_order(self, broker):
        """Test canceling non-existent order."""
        result = broker.cancel_order("NONEXISTENT")
        assert result is False

    def test_get_order(self, broker):
        """Test getting order by ID."""
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        retrieved = broker.get_order(order.order_id)
        assert retrieved.order_id == order.order_id
        assert retrieved.ticker == order.ticker

    def test_close_position(self, broker):
        """Test closing entire position."""
        # Create position
        broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        # Close it
        order = broker.close_position("AAPL")
        assert order.side == OrderSide.SELL
        assert order.quantity == 100
        assert order.status == OrderStatus.FILLED

        # Position should be gone
        position = broker.get_position("AAPL")
        assert position is None

    def test_close_nonexistent_position(self, broker):
        """Test closing non-existent position."""
        with pytest.raises(ValueError, match="No position found for AAPL"):
            broker.close_position("AAPL")

    def test_is_market_open(self, broker):
        """Test market open check."""
        # This is a simplified check - just verify it returns a bool
        result = broker.is_market_open()
        assert isinstance(result, bool)

    def test_position_pnl_calculation(self, broker):
        """Test P&L calculations in positions."""
        # Buy at 100
        broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        position = broker.get_position("AAPL")
        assert position.unrealized_pnl == 0.0  # Bought at current price
        assert position.unrealized_pnl_pct == 0.0

    def test_multiple_positions(self, broker):
        """Test handling multiple positions."""
        # Buy AAPL
        broker.place_order("AAPL", OrderSide.BUY, 100, OrderType.MARKET)
        # Buy MSFT
        broker.place_order("MSFT", OrderSide.BUY, 50, OrderType.MARKET)

        positions = broker.get_positions()
        assert len(positions) == 2

        tickers = {p.ticker for p in positions}
        assert tickers == {"AAPL", "MSFT"}

        account = broker.get_account()
        assert len(account.positions) == 2
        assert account.portfolio_value == 100000.0  # 85k cash + 15k positions


class TestAlpacaBroker:
    """Test AlpacaBroker implementation."""

    @pytest.fixture
    def mock_alpaca_imports(self):
        """Mock Alpaca imports."""
        mock_modules = {
            "alpaca.trading.client": Mock(),
            "alpaca.trading.requests": Mock(),
            "alpaca.trading.enums": Mock(),
        }

        with patch.dict("sys.modules", mock_modules):
            # Set up the mock classes
            mock_client = Mock()
            # Configure mock client methods
            mock_client.get_account.return_value = Mock(
                cash="50000.0",
                portfolio_value="150000.0",
                buying_power="75000.0",
                equity="150000.0"
            )
            mock_client.get_all_positions.return_value = []  # Empty list by default
            mock_client.get_open_position.return_value = None
            mock_client.submit_order.return_value = Mock(
                id="12345",
                symbol="AAPL",
                qty="100",
                limit_price=None,
                status="filled",
                submitted_at=datetime.now()
            )
            mock_client.cancel_order_by_id.return_value = True
            mock_client.get_order_by_id.return_value = Mock(
                id="12345",
                symbol="AAPL",
                side="buy",
                qty="100",
                filled_qty="100",
                filled_avg_price="150.0",
                status="filled",
                submitted_at=datetime.now(),
                filled_at=datetime.now()
            )
            mock_client.get_clock.return_value = Mock(is_open=True)

            mock_modules["alpaca.trading.client"].TradingClient = Mock(return_value=mock_client)

            mock_requests = Mock()
            mock_requests.MarketOrderRequest = Mock()
            mock_requests.LimitOrderRequest = Mock()
            mock_requests.StopLossRequest = Mock()
            mock_requests.TakeProfitRequest = Mock()
            mock_modules["alpaca.trading.requests"] = mock_requests

            mock_enums = Mock()
            mock_enums.OrderSide = Mock()
            mock_enums.TimeInForce = Mock()
            mock_modules["alpaca.trading.enums"] = mock_enums

            yield mock_client

    def test_init_success(self, mock_alpaca_imports):
        """Test AlpacaBroker initialization."""
        mock_client = mock_alpaca_imports
        broker = AlpacaBroker("test_key", "test_secret", paper=True)
        assert broker.client is not None
        assert hasattr(broker, "MarketOrderRequest")

    def test_init_missing_alpaca_py(self):
        """Test AlpacaBroker init when alpaca-py not installed."""
        with patch.dict("sys.modules", {"alpaca": None, "alpaca.trading": None}):
            with pytest.raises(ImportError, match="alpaca-py not installed"):
                AlpacaBroker("test_key", "test_secret")

    def test_get_account(self, mock_alpaca_imports):
        """Test get_account method."""
        mock_client = mock_alpaca_imports

        # Mock account
        mock_account = Mock()
        mock_account.cash = "50000.0"
        mock_account.portfolio_value = "150000.0"
        mock_account.buying_power = "75000.0"
        mock_account.equity = "150000.0"
        mock_client.get_account.return_value = mock_account

        # Ensure get_all_positions returns empty list
        mock_client.get_all_positions.return_value = []

        broker = AlpacaBroker("test_key", "test_secret")
        account = broker.get_account()

        assert account.cash == 50000.0
        assert account.portfolio_value == 150000.0
        assert account.buying_power == 75000.0
        assert account.equity == 150000.0
        assert len(account.positions) == 0  # No positions mocked

    def test_get_positions(self, mock_alpaca_imports):
        """Test get_positions method."""
        mock_client = mock_alpaca_imports

        # Mock positions
        mock_positions = [
            Mock(
                symbol="AAPL",
                qty="100",
                avg_entry_price="150.0",
                current_price="155.0",
                market_value="15500.0",
                unrealized_pl="500.0",
                unrealized_plpc="0.0333",
            )
        ]
        mock_client.get_all_positions.return_value = mock_positions

        broker = AlpacaBroker("test_key", "test_secret")
        positions = broker.get_positions()

        assert len(positions) == 1
        pos = positions[0]
        assert pos.ticker == "AAPL"
        assert pos.shares == 100
        assert pos.avg_price == 150.0
        assert pos.current_price == 155.0

    def test_get_position_exists(self, mock_alpaca_imports):
        """Test get_position for existing position."""
        mock_client = mock_alpaca_imports

        mock_position = Mock()
        mock_position.symbol = "AAPL"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.market_value = "15500.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"
        mock_client.get_open_position.return_value = mock_position

        broker = AlpacaBroker("test_key", "test_secret")
        position = broker.get_position("AAPL")

        assert position is not None
        assert position.ticker == "AAPL"

    def test_get_position_not_exists(self, mock_alpaca_imports):
        """Test get_position for non-existent position."""
        mock_client = mock_alpaca_imports
        mock_client.get_open_position.side_effect = Exception("Not found")

        broker = AlpacaBroker("test_key", "test_secret")
        position = broker.get_position("INVALID")

        assert position is None

    def test_place_market_order(self, mock_alpaca_imports):
        """Test placing market order."""
        mock_client = mock_alpaca_imports

        # Mock order response
        mock_order = Mock()
        mock_order.id = "12345"
        mock_order.symbol = "AAPL"
        mock_order.qty = "100"
        mock_order.limit_price = None
        mock_order.status = "filled"
        mock_order.submitted_at = datetime.now()
        mock_client.submit_order.return_value = mock_order

        broker = AlpacaBroker("test_key", "test_secret")
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        assert order.order_id == "12345"
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        mock_client.submit_order.assert_called_once()

    def test_place_limit_order(self, mock_alpaca_imports):
        """Test placing limit order."""
        mock_client = mock_alpaca_imports

        # Mock order response
        mock_order = Mock()
        mock_order.id = "12345"
        mock_order.symbol = "AAPL"
        mock_order.qty = "100"
        mock_order.limit_price = "150.0"
        mock_order.status = "filled"
        mock_order.submitted_at = datetime.now()
        mock_client.submit_order.return_value = mock_order

        broker = AlpacaBroker("test_key", "test_secret")
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
            limit_price=150.0,
        )

        assert order.limit_price == 150.0
        mock_client.submit_order.assert_called_once()

    def test_place_unsupported_order_type(self, mock_alpaca_imports):
        """Test placing unsupported order type."""
        broker = AlpacaBroker("test_key", "test_secret")
        with pytest.raises(ValueError, match="Order type.*not yet implemented"):
            broker.place_order(
                ticker="AAPL",
                side=OrderSide.BUY,
                quantity=100,
                order_type=OrderType.STOP,
            )

    def test_place_bracket_order(self, mock_alpaca_imports):
        """Test placing bracket order."""
        mock_client = mock_alpaca_imports

        # Mock bracket order response
        mock_order = Mock()
        mock_order.id = "12345"
        mock_order.symbol = "AAPL"
        mock_client.submit_order.return_value = mock_order

        broker = AlpacaBroker("test_key", "test_secret")
        orders = broker.place_bracket_order(
            ticker="AAPL",
            quantity=100,
            entry_price=150.0,
            stop_price=145.0,
            target_price=160.0,
        )

        assert "entry" in orders
        assert orders["stop"] is None  # Alpaca manages internally
        assert orders["target"] is None

    def test_cancel_order_success(self, mock_alpaca_imports):
        """Test canceling order successfully."""
        mock_client = mock_alpaca_imports
        mock_client.cancel_order_by_id.return_value = True

        broker = AlpacaBroker("test_key", "test_secret")
        result = broker.cancel_order("12345")

        assert result is True

    def test_cancel_order_failure(self, mock_alpaca_imports):
        """Test canceling order failure."""
        mock_client = mock_alpaca_imports
        mock_client.cancel_order_by_id.side_effect = Exception("Failed")

        broker = AlpacaBroker("test_key", "test_secret")
        result = broker.cancel_order("12345")

        assert result is False

    def test_get_order(self, mock_alpaca_imports):
        """Test getting order status."""
        mock_client = mock_alpaca_imports

        mock_order = Mock()
        mock_order.id = "12345"
        mock_order.symbol = "AAPL"
        mock_order.side = "buy"
        mock_order.qty = "100"
        mock_order.filled_qty = "100"
        mock_order.filled_avg_price = "150.0"
        mock_order.status = "filled"
        mock_order.submitted_at = datetime.now()
        mock_order.filled_at = datetime.now()
        mock_client.get_order_by_id.return_value = mock_order

        broker = AlpacaBroker("test_key", "test_secret")
        order = broker.get_order("12345")

        assert order.order_id == "12345"
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY

    def test_close_position(self, mock_alpaca_imports):
        """Test closing position."""
        mock_client = mock_alpaca_imports

        broker = AlpacaBroker("test_key", "test_secret")

        # Mock position exists
        mock_position = Mock()
        mock_position.symbol = "AAPL"
        mock_position.qty = "100"
        mock_position.avg_entry_price = "150.0"
        mock_position.current_price = "155.0"
        mock_position.market_value = "15500.0"
        mock_position.unrealized_pl = "500.0"
        mock_position.unrealized_plpc = "0.0333"

        # Mock the get_position call in close_position
        with patch.object(broker, 'get_position', return_value=Position("AAPL", 100, 150.0, 155.0, 15500.0, 500.0, 0.0333)):
            # Mock order response
            mock_order = Mock()
            mock_order.id = "12345"
            mock_order.symbol = "AAPL"
            mock_order.qty = "100"
            mock_order.limit_price = None
            mock_order.status = "filled"
            mock_order.submitted_at = datetime.now()
            mock_client.submit_order.return_value = mock_order

            order = broker.close_position("AAPL")

            assert order.side == OrderSide.SELL
            assert order.order_type == OrderType.MARKET

    def test_is_market_open(self, mock_alpaca_imports):
        """Test market open check."""
        mock_client = mock_alpaca_imports

        mock_clock = Mock()
        mock_clock.is_open = True
        mock_client.get_clock.return_value = mock_clock

        broker = AlpacaBroker("test_key", "test_secret")
        result = broker.is_market_open()

        assert result is True

    def test_map_status(self, mock_alpaca_imports):
        """Test status mapping."""
        broker = AlpacaBroker("test_key", "test_secret")

        assert broker._map_status("filled") == OrderStatus.FILLED
        assert broker._map_status("new") == OrderStatus.SUBMITTED
        assert broker._map_status("canceled") == OrderStatus.CANCELLED
        assert broker._map_status("unknown") == OrderStatus.PENDING


class TestQuestradeBroker:
    """Test QuestradeBroker implementation."""

    @pytest.fixture
    def mock_questrade(self):
        """Mock Questrade client."""
        with patch("questrade_api.Questrade") as mock_qt_class:
            mock_qt = Mock()
            mock_qt_class.return_value = mock_qt

            # Mock accounts
            mock_qt.accounts = {
                "accounts": [{"number": "12345678", "type": "Margin"}]
            }

            # Mock balances
            mock_qt.account_balances.return_value = {
                "perCurrencyBalances": [
                    {
                        "currency": "CAD",
                        "cash": 50000.0,
                        "totalEquity": 150000.0,
                        "buyingPower": 75000.0,
                    }
                ]
            }

            # Mock positions
            mock_qt.account_positions.return_value = {
                "positions": [
                    {
                        "symbol": "AAPL",
                        "openQuantity": 100,
                        "averageEntryPrice": 150.0,
                        "currentPrice": 155.0,
                        "currentMarketValue": 15500.0,
                        "openPnl": 500.0,
                    }
                ]
            }

            # Mock symbol search
            mock_qt.symbols_search.return_value = {
                "symbols": [{"symbolId": 12345}]
            }

            # Mock order placement
            mock_qt.account_order.return_value = {
                "orders": [
                    {
                        "id": "67890",
                        "state": "Accepted",
                        "creationTime": "2024-01-01T10:00:00",
                    }
                ]
            }

            yield mock_qt

    def test_init_success(self, mock_questrade):
        """Test QuestradeBroker initialization."""
        broker = QuestradeBroker("test_token", paper=True)
        assert broker.qt is not None
        assert broker.account_id == "12345678"

    def test_init_missing_questrade_api(self):
        """Test QuestradeBroker init when questrade-api not installed."""
        with patch.dict("sys.modules", {"questrade_api": None}):
            with pytest.raises(ImportError, match="questrade-api not installed"):
                QuestradeBroker("test_token")

    def test_init_no_accounts(self, mock_questrade):
        """Test QuestradeBroker init with no accounts."""
        mock_questrade.accounts = {"accounts": []}
        with pytest.raises(ValueError, match="No Questrade accounts found"):
            QuestradeBroker("test_token")

    def test_get_account(self, mock_questrade):
        """Test get_account method."""
        broker = QuestradeBroker("test_token")
        account = broker.get_account()

        assert account.cash == 50000.0
        assert account.portfolio_value == 150000.0
        assert account.buying_power == 75000.0

    def test_get_positions(self, mock_questrade):
        """Test get_positions method."""
        broker = QuestradeBroker("test_token")
        positions = broker.get_positions()

        assert len(positions) == 1
        pos = positions[0]
        assert pos.ticker == "AAPL"
        assert pos.shares == 100
        assert pos.avg_price == 150.0

    def test_place_order(self, mock_questrade):
        """Test placing order."""
        broker = QuestradeBroker("test_token")
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        assert order.order_id == "67890"
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY

    def test_place_order_symbol_not_found(self, mock_questrade):
        """Test placing order with symbol not found."""
        mock_questrade.symbols_search.return_value = {"symbols": []}
        broker = QuestradeBroker("test_token")

        with pytest.raises(ValueError, match="Symbol AAPL not found"):
            broker.place_order("AAPL", OrderSide.BUY, 100, OrderType.MARKET)

    def test_cancel_order_success(self, mock_questrade):
        """Test canceling order successfully."""
        mock_questrade.account_order_cancel.return_value = {"orderId": 67890}
        broker = QuestradeBroker("test_token")
        result = broker.cancel_order("67890")

        assert result is True

    def test_get_order(self, mock_questrade):
        """Test getting order status."""
        mock_order = {
            "id": "67890",
            "symbol": "AAPL",
            "side": "Buy",
            "totalQuantity": 100,
            "filledQuantity": 100,
            "avgExecPrice": 150.0,
            "state": "Filled",
            "creationTime": "2024-01-01T10:00:00",
        }
        mock_questrade.account_order.return_value = {"orders": [mock_order]}

        broker = QuestradeBroker("test_token")
        order = broker.get_order("67890")

        assert order.order_id == "67890"
        assert order.ticker == "AAPL"
        assert order.side == OrderSide.BUY

    def test_map_status(self, mock_questrade):
        """Test status mapping."""
        broker = QuestradeBroker("test_token")

        assert broker._map_status("Filled") == OrderStatus.FILLED
        assert broker._map_status("Accepted") == OrderStatus.SUBMITTED
        assert broker._map_status("Rejected") == OrderStatus.REJECTED
        assert broker._map_status("unknown") == OrderStatus.PENDING


class TestIBKRBroker:
    """Test IBKRBroker implementation."""

    @pytest.fixture
    def mock_ibkr(self):
        """Mock IBKR client."""
        mock_ib_insync = Mock()
        mock_ib_class = Mock()
        mock_ib_insync.IB = mock_ib_class

        with patch.dict("sys.modules", {"ib_insync": mock_ib_insync}):
            mock_ib = Mock()
            mock_ib_class.return_value = mock_ib
            mock_ib.isConnected.return_value = True

            # Mock account values
            mock_values = [
                Mock(tag="TotalCashValue", value="50000.0"),
                Mock(tag="NetLiquidation", value="150000.0"),
                Mock(tag="BuyingPower", value="75000.0"),
            ]
            mock_ib.accountValues.return_value = mock_values

            # Mock positions
            mock_positions = [
                Mock(
                    contract=Mock(symbol="AAPL"),
                    position=100,
                    avgCost=150.0,
                )
            ]
            mock_ib.positions.return_value = mock_positions

            # Mock ticker data
            mock_ticker = Mock()
            mock_ticker.marketPrice.return_value = 155.0
            mock_ib.reqTickers.return_value = [mock_ticker]

            # Mock order placement
            mock_trade = Mock()
            mock_trade.order.orderId = 12345
            mock_trade.orderStatus.status = "Filled"
            mock_ib.placeOrder.return_value = mock_trade

            yield mock_ib

    def test_init_success(self, mock_ibkr):
        """Test IBKRBroker initialization."""
        broker = IBKRBroker("127.0.0.1", 7497, 1)
        assert broker.ib is not None
        assert hasattr(broker, "Stock")

    def test_init_missing_ib_insync(self):
        """Test IBKRBroker init when ib_insync not installed."""
        with patch.dict("sys.modules", {"ib_insync": None}):
            with pytest.raises(ImportError, match="ib_insync not installed"):
                IBKRBroker()

    def test_get_account(self, mock_ibkr):
        """Test get_account method."""
        broker = IBKRBroker()
        account = broker.get_account()

        assert account.cash == 50000.0
        assert account.portfolio_value == 150000.0
        assert account.buying_power == 75000.0

    def test_get_positions(self, mock_ibkr):
        """Test get_positions method."""
        broker = IBKRBroker()
        positions = broker.get_positions()

        assert len(positions) == 1
        pos = positions[0]
        assert pos.ticker == "AAPL"
        assert pos.shares == 100
        assert pos.avg_price == 150.0

    def test_place_order(self, mock_ibkr):
        """Test placing order."""
        broker = IBKRBroker()
        order = broker.place_order(
            ticker="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )

        assert order.order_id == "12345"
        assert order.status == OrderStatus.FILLED

    def test_place_bracket_order(self, mock_ibkr):
        """Test placing bracket order."""
        broker = IBKRBroker()
        orders = broker.place_bracket_order(
            ticker="AAPL",
            quantity=100,
            entry_price=150.0,
            stop_price=145.0,
            target_price=160.0,
        )

        assert "entry" in orders
        assert "stop" in orders
        assert "target" in orders

    def test_cancel_order(self, mock_ibkr):
        """Test canceling order."""
        mock_trade = Mock()
        mock_trade.order.orderId = 12345
        mock_ibkr.trades.return_value = [mock_trade]

        broker = IBKRBroker()
        result = broker.cancel_order("12345")

        assert result is True

    def test_get_order(self, mock_ibkr):
        """Test getting order status."""
        mock_trade = Mock()
        mock_trade.order.orderId = 12345
        mock_trade.order.totalQuantity = 100
        mock_trade.orderStatus.filled = 100
        mock_trade.orderStatus.avgFillPrice = 150.0
        mock_trade.orderStatus.status = "Filled"
        mock_ibkr.trades.return_value = [mock_trade]

        broker = IBKRBroker()
        order = broker.get_order("12345")

        assert order.order_id == "12345"
        assert order.filled_qty == 100

    def test_close_position(self, mock_ibkr):
        """Test closing position."""
        broker = IBKRBroker()
        order = broker.close_position("AAPL")

        assert order.side == OrderSide.SELL
        assert order.quantity == 100

    def test_is_market_open(self, mock_ibkr):
        """Test market open check."""
        broker = IBKRBroker()
        result = broker.is_market_open()
        assert isinstance(result, bool)

    def test_map_status(self, mock_ibkr):
        """Test status mapping."""
        broker = IBKRBroker()

        assert broker._map_status("Filled") == OrderStatus.FILLED
        assert broker._map_status("Submitted") == OrderStatus.SUBMITTED
        assert broker._map_status("Cancelled") == OrderStatus.CANCELLED


class TestBrokerFactory:
    """Test broker factory and credential loading."""

    def test_create_paper_broker(self):
        """Test creating paper broker."""
        broker = create_broker("paper", initial_cash=50000.0)
        assert isinstance(broker, PaperBroker)
        assert broker.cash == 50000.0

    @patch("src.bouncehunter.broker.load_broker_credentials")
    def test_create_alpaca_broker(self, mock_load_creds):
        """Test creating Alpaca broker."""
        mock_load_creds.return_value = {
            "api_key": "test_key",
            "secret_key": "test_secret",
            "paper": True,
        }

        with patch.dict("sys.modules", {
            "alpaca": Mock(),
            "alpaca.trading": Mock(),
            "alpaca.trading.client": Mock(),
            "alpaca.trading.requests": Mock(),
            "alpaca.trading.enums": Mock()
        }):
            with patch("alpaca.trading.client.TradingClient"):
                broker = create_broker("alpaca")
                assert isinstance(broker, AlpacaBroker)

    @patch("src.bouncehunter.broker.load_broker_credentials")
    def test_create_questrade_broker(self, mock_load_creds):
        """Test creating Questrade broker."""
        mock_load_creds.return_value = {
            "refresh_token": "test_token",
            "paper": True,
        }

        with patch.dict("sys.modules", {"questrade_api": Mock()}):
            with patch("questrade_api.Questrade") as mock_qt:
                mock_qt.return_value.accounts = {"accounts": [{"number": "123"}]}
                broker = create_broker("questrade")
                assert isinstance(broker, QuestradeBroker)

    @patch("src.bouncehunter.broker.load_broker_credentials")
    def test_create_ibkr_broker(self, mock_load_creds):
        """Test creating IBKR broker."""
        mock_load_creds.return_value = {
            "host": "127.0.0.1",
            "port": 7497,
            "client_id": 1,
        }

        with patch.dict("sys.modules", {"ib_insync": Mock()}):
            with patch("ib_insync.IB"):
                broker = create_broker("ibkr")
                assert isinstance(broker, IBKRBroker)

    @patch("src.bouncehunter.broker.load_broker_credentials")
    def test_create_unknown_broker(self, mock_load_creds):
        """Test creating unknown broker type."""
        mock_load_creds.return_value = {}
        with pytest.raises(ValueError, match="Unknown broker type"):
            create_broker("unknown")

    @patch.dict(os.environ, {
        "QUESTRADE_REFRESH_TOKEN": "env_token",
        "QUESTRADE_PAPER": "true",
    })
    def test_load_credentials_from_env_questrade(self):
        """Test loading Questrade credentials from environment."""
        creds = load_broker_credentials("questrade")
        assert creds["refresh_token"] == "env_token"
        assert creds["paper"] is True

    @patch.dict(os.environ, {
        "ALPACA_API_KEY": "env_key",
        "ALPACA_API_SECRET": "env_secret",
        "ALPACA_PAPER": "false",
    })
    def test_load_credentials_from_env_alpaca(self):
        """Test loading Alpaca credentials from environment."""
        creds = load_broker_credentials("alpaca")
        assert creds["api_key"] == "env_key"
        assert creds["secret_key"] == "env_secret"
        assert creds["paper"] is False

    def test_load_credentials_from_file(self):
        """Test loading credentials from YAML file."""
        # Create temporary config file
        config_data = """
questrade:
  enabled: true
  refresh_token: file_token
  practice_account: false
alpaca:
  enabled: true
  api_key: file_key
  api_secret: file_secret
  paper_trading: false
paper:
  initial_capital: 75000.0
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_data)
            config_path = f.name

        try:
            with patch("src.bouncehunter.broker.Path") as mock_path:
                mock_path.return_value.exists.return_value = True
                mock_path.return_value.__str__ = lambda x: config_path

                with patch("builtins.open", create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = config_data

                    with patch("yaml.safe_load") as mock_yaml:
                        mock_yaml.return_value = {
                            "questrade": {
                                "enabled": True,
                                "refresh_token": "file_token",
                                "practice_account": False,
                            }
                        }

                        creds = load_broker_credentials("questrade")
                        assert creds["refresh_token"] == "file_token"
                        assert creds["paper"] is False

        finally:
            os.unlink(config_path)

    def test_load_credentials_file_not_found(self):
        """Test loading credentials when file not found."""
        with patch("src.bouncehunter.broker.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            with pytest.raises(FileNotFoundError, match="Credentials file not found"):
                load_broker_credentials("questrade")

    def test_load_credentials_broker_not_configured(self):
        """Test loading credentials for unconfigured broker."""
        config_data = """
alpaca:
  enabled: true
  api_key: key
  api_secret: secret
"""

        with patch("src.bouncehunter.broker.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = config_data

                with patch("yaml.safe_load") as mock_yaml:
                    mock_yaml.return_value = {
                        "alpaca": {"enabled": True, "api_key": "key", "api_secret": "secret"}
                    }

                    with pytest.raises(KeyError, match="Broker 'questrade' not found"):
                        load_broker_credentials("questrade")

    def test_load_credentials_broker_disabled(self):
        """Test loading credentials for disabled broker."""
        config_data = """
questrade:
  enabled: false
  refresh_token: token
"""

        with patch("src.bouncehunter.broker.Path") as mock_path:
            mock_path.return_value.exists.return_value = True

            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = config_data

                with patch("yaml.safe_load") as mock_yaml:
                    mock_yaml.return_value = {
                        "questrade": {"enabled": False, "refresh_token": "token"}
                    }

                    with pytest.raises(ValueError, match="Broker 'questrade' is disabled"):
                        load_broker_credentials("questrade")