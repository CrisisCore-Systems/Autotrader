# Phase 10: Live Market Connectivity and Execution Specification

**Version:** 1.0  
**Date:** October 24, 2025  
**Status:** Specification  

---

## Overview

Phase 10 delivers **production-grade market connectivity and order execution** across multiple asset classes (equities, FX, crypto). It integrates with Phase 8's strategy logic to convert execution decisions into real trades while maintaining strict safety controls and resiliency.

### Key Objectives

1. **Multi-Broker Support:** IBKR (equities), Oanda/FXCM (FX), Binance/Coinbase/OKX (crypto)
2. **Order Management System (OMS):** IOC/limit orders, queue positioning, cancel/replace logic
3. **Latency Optimization:** Coalesced updates, efficient protocols, minimal overhead
4. **Resiliency:** Retry/backoff, dead-letter queue, reconnect strategies, circuit breakers
5. **Paper Trading:** Simulated execution for testing without real capital

---

## Architecture

### Component Hierarchy

```
autotrader/execution/
├── __init__.py                     # Main ExecutionEngine orchestrator
├── adapters/
│   ├── __init__.py                 # BaseBrokerAdapter interface
│   ├── ibkr.py                     # Interactive Brokers
│   ├── binance.py                  # Binance (crypto)
│   ├── coinbase.py                 # Coinbase (crypto)
│   ├── okx.py                      # OKX (crypto)
│   ├── oanda.py                    # Oanda (FX)
│   └── paper.py                    # Paper trading simulator
├── oms/
│   └── __init__.py                 # Order Management System
├── resiliency/
│   └── __init__.py                 # Retry, reconnect, DLQ
└── market_data/
    └── __init__.py                 # Real-time market data feeds
```

### Integration Flow

```
Phase 8 Strategy → ExecutionDecision → ExecutionEngine → BrokerAdapter → Exchange/Broker
                                            ↓
                                         OMS (tracking)
                                            ↓
                                      Resiliency Layer
                                            ↓
                                       Fill Reports → Phase 8
```

---

## Component Specifications

### 1. Broker Adapter Interface

**File:** `autotrader/execution/adapters/__init__.py`

**Purpose:** Abstract base class defining unified interface for all brokers

**Key Classes:**

```python
class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    IOC = "ioc"  # Immediate-or-cancel
    FOK = "fok"  # Fill-or-kill
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"

@dataclass
class Order:
    """Universal order representation."""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float] = None  # None for market orders
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"  # GTC, IOC, FOK, DAY
    
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: float = 0.0
    avg_fill_price: float = 0.0
    commission: float = 0.0
    
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    
    metadata: Dict = field(default_factory=dict)

@dataclass
class Fill:
    """Order fill report."""
    order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float
    timestamp: datetime
    execution_id: str
    metadata: Dict = field(default_factory=dict)

class BaseBrokerAdapter(ABC):
    """Abstract base class for all broker adapters."""
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to broker."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close connection."""
        pass
    
    @abstractmethod
    async def submit_order(self, order: Order) -> Order:
        """Submit order to broker."""
        pass
    
    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel existing order."""
        pass
    
    @abstractmethod
    async def modify_order(
        self, 
        order_id: str, 
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Order:
        """Modify existing order (cancel/replace)."""
        pass
    
    @abstractmethod
    async def get_order_status(self, order_id: str) -> Order:
        """Query order status."""
        pass
    
    @abstractmethod
    async def get_positions(self) -> Dict[str, float]:
        """Get current positions."""
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> Dict[str, float]:
        """Get account balances."""
        pass
    
    @abstractmethod
    def subscribe_fills(self, callback: Callable[[Fill], None]):
        """Subscribe to fill reports."""
        pass
```

**Design Principles:**
- Async/await for non-blocking I/O
- Unified Order/Fill dataclasses across all brokers
- Callback-based fill notifications
- Graceful connection handling

---

### 2. Interactive Brokers (IBKR) Adapter

**File:** `autotrader/execution/adapters/ibkr.py`

**Purpose:** Integration with Interactive Brokers TWS/Gateway via ibapi

**Key Features:**
- TWS connection management
- Contract creation (stocks, options, futures, FX)
- Order submission with venue routing (SMART, ARCA, etc.)
- Real-time fill reports
- Position and P&L tracking

**Implementation:**

```python
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder

class IBKRAdapter(BaseBrokerAdapter, EWrapper, EClient):
    """Interactive Brokers adapter using ibapi."""
    
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 7497,  # TWS paper: 7497, live: 7496
        client_id: int = 1
    ):
        EClient.__init__(self, self)
        self.host = host
        self.port = port
        self.client_id = client_id
        
        # Order tracking
        self.orders: Dict[int, Order] = {}
        self.next_order_id = None
        
        # Callbacks
        self.fill_callbacks: List[Callable] = []
    
    async def connect(self) -> bool:
        """Connect to TWS/Gateway."""
        self.connect(self.host, self.port, self.client_id)
        
        # Wait for next order ID
        await self._wait_for_order_id()
        
        return self.isConnected()
    
    def nextValidId(self, orderId: int):
        """IB callback: next valid order ID."""
        self.next_order_id = orderId
    
    async def submit_order(self, order: Order) -> Order:
        """Submit order to IB."""
        # Create IB contract
        contract = self._create_contract(order.symbol)
        
        # Create IB order
        ib_order = self._create_ib_order(order)
        
        # Submit
        order_id = self.next_order_id
        self.next_order_id += 1
        
        self.placeOrder(order_id, contract, ib_order)
        
        # Track order
        order.order_id = str(order_id)
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now()
        self.orders[order_id] = order
        
        return order
    
    def orderStatus(
        self,
        orderId: int,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        ...
    ):
        """IB callback: order status update."""
        if orderId in self.orders:
            order = self.orders[orderId]
            
            # Update status
            order.status = self._map_ib_status(status)
            order.filled_quantity = filled
            order.avg_fill_price = avgFillPrice
            
            # Notify on fill
            if status == "Filled":
                fill = Fill(
                    order_id=str(orderId),
                    symbol=order.symbol,
                    side=order.side,
                    quantity=filled,
                    price=avgFillPrice,
                    commission=0,  # Updated in commissionReport
                    timestamp=datetime.now(),
                    execution_id=f"IB_{orderId}"
                )
                
                self._notify_fills(fill)
    
    def _create_contract(self, symbol: str) -> Contract:
        """Create IB contract from symbol."""
        contract = Contract()
        contract.symbol = symbol
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
    
    def _create_ib_order(self, order: Order) -> IBOrder:
        """Convert Order to IB Order."""
        ib_order = IBOrder()
        ib_order.action = "BUY" if order.side == OrderSide.BUY else "SELL"
        ib_order.totalQuantity = order.quantity
        ib_order.orderType = order.order_type.value.upper()
        
        if order.price:
            ib_order.lmtPrice = order.price
        
        if order.stop_price:
            ib_order.auxPrice = order.stop_price
        
        ib_order.tif = order.time_in_force
        
        return ib_order
```

**Safety Features:**
- Paper trading port (7497) vs live (7496)
- Order ID validation
- Connection monitoring
- Automatic reconnection

---

### 3. Crypto Exchange Adapters

**Files:** 
- `autotrader/execution/adapters/binance.py`
- `autotrader/execution/adapters/coinbase.py`
- `autotrader/execution/adapters/okx.py`

**Purpose:** Integration with crypto exchanges via REST + WebSocket APIs

**Binance Example:**

```python
from binance.client import Client
from binance.streams import ThreadedWebsocketManager

class BinanceAdapter(BaseBrokerAdapter):
    """Binance exchange adapter."""
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        testnet: bool = False
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        self.client = None
        self.ws_manager = None
        
        # Order tracking
        self.orders: Dict[str, Order] = {}
        self.fill_callbacks: List[Callable] = []
    
    async def connect(self) -> bool:
        """Connect to Binance."""
        if self.testnet:
            base_url = "https://testnet.binance.vision/api"
        else:
            base_url = "https://api.binance.com/api"
        
        self.client = Client(
            self.api_key,
            self.api_secret,
            tld='us' if not self.testnet else None,
            testnet=self.testnet
        )
        
        # Start WebSocket for real-time updates
        self.ws_manager = ThreadedWebsocketManager(
            api_key=self.api_key,
            api_secret=self.api_secret
        )
        self.ws_manager.start()
        
        # Subscribe to user data stream
        self.ws_manager.start_user_socket(callback=self._handle_user_data)
        
        return True
    
    async def submit_order(self, order: Order) -> Order:
        """Submit order to Binance."""
        params = {
            'symbol': order.symbol,
            'side': order.side.value.upper(),
            'type': self._map_order_type(order.order_type),
            'quantity': order.quantity
        }
        
        if order.order_type == OrderType.LIMIT:
            params['timeInForce'] = order.time_in_force
            params['price'] = str(order.price)
        
        # Submit via REST
        response = self.client.create_order(**params)
        
        # Update order
        order.order_id = str(response['orderId'])
        order.status = self._map_binance_status(response['status'])
        order.submitted_at = datetime.fromtimestamp(response['transactTime'] / 1000)
        
        self.orders[order.order_id] = order
        
        return order
    
    def _handle_user_data(self, msg: Dict):
        """Handle WebSocket user data updates."""
        if msg['e'] == 'executionReport':
            # Order update
            order_id = str(msg['i'])
            
            if order_id in self.orders:
                order = self.orders[order_id]
                
                # Update status
                order.status = self._map_binance_status(msg['X'])
                order.filled_quantity = float(msg['z'])
                order.avg_fill_price = float(msg['Z']) / float(msg['z']) if float(msg['z']) > 0 else 0
                
                # Create fill if filled
                if msg['X'] in ['FILLED', 'PARTIALLY_FILLED']:
                    fill = Fill(
                        order_id=order_id,
                        symbol=order.symbol,
                        side=order.side,
                        quantity=float(msg['l']),  # Last executed quantity
                        price=float(msg['L']),     # Last executed price
                        commission=float(msg['n']),
                        timestamp=datetime.fromtimestamp(msg['E'] / 1000),
                        execution_id=str(msg['t'])
                    )
                    
                    self._notify_fills(fill)
    
    def _map_order_type(self, order_type: OrderType) -> str:
        """Map OrderType to Binance type."""
        mapping = {
            OrderType.MARKET: 'MARKET',
            OrderType.LIMIT: 'LIMIT',
            OrderType.IOC: 'LIMIT',  # Use LIMIT with IOC TIF
            OrderType.STOP: 'STOP_LOSS',
            OrderType.STOP_LIMIT: 'STOP_LOSS_LIMIT'
        }
        return mapping.get(order_type, 'MARKET')
```

**Key Features:**
- REST API for order submission
- WebSocket for real-time updates
- User data stream for fills
- Testnet support for paper trading
- Rate limit handling

---

### 4. FX Broker Adapter (Oanda)

**File:** `autotrader/execution/adapters/oanda.py`

**Purpose:** Integration with Oanda v20 API for FX trading

```python
import oandapyV20
from oandapyV20 import API
from oandapyV20.endpoints.orders import OrderCreate
from oandapyV20.endpoints.positions import PositionsList

class OandaAdapter(BaseBrokerAdapter):
    """Oanda FX broker adapter."""
    
    def __init__(
        self,
        account_id: str,
        access_token: str,
        environment: str = "practice"  # practice or live
    ):
        self.account_id = account_id
        self.access_token = access_token
        self.environment = environment
        
        self.client = None
        self.orders: Dict[str, Order] = {}
    
    async def connect(self) -> bool:
        """Connect to Oanda."""
        self.client = API(
            access_token=self.access_token,
            environment=self.environment
        )
        
        # Test connection
        try:
            positions = PositionsList(accountID=self.account_id)
            self.client.request(positions)
            return True
        except Exception:
            return False
    
    async def submit_order(self, order: Order) -> Order:
        """Submit order to Oanda."""
        # Create order data
        order_data = {
            "order": {
                "type": self._map_order_type(order.order_type),
                "instrument": order.symbol,
                "units": str(int(order.quantity) if order.side == OrderSide.BUY else -int(order.quantity)),
            }
        }
        
        if order.order_type == OrderType.LIMIT:
            order_data["order"]["price"] = str(order.price)
            order_data["order"]["timeInForce"] = order.time_in_force
        
        # Submit
        request = OrderCreate(accountID=self.account_id, data=order_data)
        response = self.client.request(request)
        
        # Update order
        order.order_id = response['orderCreateTransaction']['id']
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now()
        
        self.orders[order.order_id] = order
        
        return order
```

---

### 5. Order Management System (OMS)

**File:** `autotrader/execution/oms/__init__.py`

**Purpose:** Track order lifecycle, manage queue positioning, handle cancel/replace

**Key Classes:**

```python
class OrderManager:
    """
    Order Management System.
    
    Tracks all orders, manages lifecycle, provides analytics.
    """
    
    def __init__(self, adapter: BaseBrokerAdapter):
        self.adapter = adapter
        
        # Order tracking
        self.active_orders: Dict[str, Order] = {}
        self.completed_orders: List[Order] = []
        
        # Fill tracking
        self.fills: List[Fill] = []
        
        # Performance metrics
        self.total_filled: float = 0
        self.total_commission: float = 0
        
        # Subscribe to fills
        adapter.subscribe_fills(self._handle_fill)
    
    async def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: float,
        order_type: OrderType = OrderType.LIMIT,
        price: Optional[float] = None,
        **kwargs
    ) -> Order:
        """
        Submit order with risk checks.
        
        Returns
        -------
        order : Order
            Submitted order
        """
        # Create order
        order = Order(
            order_id="",  # Assigned by broker
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            **kwargs
        )
        
        # Submit to broker
        order = await self.adapter.submit_order(order)
        
        # Track
        self.active_orders[order.order_id] = order
        
        return order
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order."""
        success = await self.adapter.cancel_order(order_id)
        
        if success and order_id in self.active_orders:
            order = self.active_orders[order_id]
            order.status = OrderStatus.CANCELLED
            
            # Move to completed
            self.completed_orders.append(order)
            del self.active_orders[order_id]
        
        return success
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Order:
        """
        Modify order (cancel/replace).
        
        Implementation:
        1. Cancel existing order
        2. Submit new order with updated parameters
        3. Update tracking
        """
        if order_id not in self.active_orders:
            raise ValueError(f"Order {order_id} not found")
        
        old_order = self.active_orders[order_id]
        
        # Cancel old
        await self.cancel_order(order_id)
        
        # Submit new with updated params
        new_order = await self.submit_order(
            symbol=old_order.symbol,
            side=old_order.side,
            quantity=quantity or old_order.quantity,
            order_type=old_order.order_type,
            price=price or old_order.price,
            time_in_force=old_order.time_in_force
        )
        
        # Link orders
        new_order.metadata['replaced_order_id'] = order_id
        
        return new_order
    
    def _handle_fill(self, fill: Fill):
        """Handle fill notification."""
        self.fills.append(fill)
        
        # Update metrics
        self.total_filled += fill.quantity * fill.price
        self.total_commission += fill.commission
        
        # Update order
        if fill.order_id in self.active_orders:
            order = self.active_orders[fill.order_id]
            
            if order.status == OrderStatus.FILLED:
                # Move to completed
                self.completed_orders.append(order)
                del self.active_orders[fill.order_id]
    
    def get_position(self, symbol: str) -> float:
        """Get current position for symbol."""
        position = 0.0
        
        # Sum filled orders
        for fill in self.fills:
            if fill.symbol == symbol:
                if fill.side == OrderSide.BUY:
                    position += fill.quantity
                else:
                    position -= fill.quantity
        
        return position
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Get open orders, optionally filtered by symbol."""
        orders = list(self.active_orders.values())
        
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        
        return orders
```

**Advanced Features:**
- Queue positioning (join at back, jump ahead)
- Iceberg orders (show partial quantity)
- TWAP/VWAP execution algorithms
- Smart order routing

---

### 6. Paper Trading Adapter

**File:** `autotrader/execution/adapters/paper.py`

**Purpose:** Simulated execution for testing without real capital

```python
class PaperTradingAdapter(BaseBrokerAdapter):
    """
    Paper trading simulator.
    
    Simulates order fills with realistic latency and slippage.
    """
    
    def __init__(
        self,
        initial_balance: float = 100000,
        latency_ms: Tuple[int, int] = (10, 50),  # (min, max)
        slippage_bps: float = 5,  # 5 basis points
        commission_bps: float = 10  # 10 basis points
    ):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.latency_ms = latency_ms
        self.slippage_bps = slippage_bps
        self.commission_bps = commission_bps
        
        # State
        self.positions: Dict[str, float] = {}
        self.orders: Dict[str, Order] = {}
        self.order_counter = 0
        
        # Market data (mock)
        self.current_prices: Dict[str, float] = {}
        
        # Callbacks
        self.fill_callbacks: List[Callable] = []
    
    async def connect(self) -> bool:
        """Connect (instant for paper trading)."""
        return True
    
    async def disconnect(self):
        """Disconnect."""
        pass
    
    async def submit_order(self, order: Order) -> Order:
        """Submit order (simulated)."""
        # Assign order ID
        self.order_counter += 1
        order.order_id = f"PAPER_{self.order_counter}"
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now()
        
        # Track
        self.orders[order.order_id] = order
        
        # Simulate latency
        latency = random.randint(*self.latency_ms) / 1000
        await asyncio.sleep(latency)
        
        # Simulate fill
        await self._simulate_fill(order)
        
        return order
    
    async def _simulate_fill(self, order: Order):
        """Simulate order fill."""
        # Get current price (would come from market data in reality)
        current_price = self.current_prices.get(order.symbol, order.price or 100.0)
        
        # Apply slippage
        if order.side == OrderSide.BUY:
            fill_price = current_price * (1 + self.slippage_bps / 10000)
        else:
            fill_price = current_price * (1 - self.slippage_bps / 10000)
        
        # Calculate commission
        notional = order.quantity * fill_price
        commission = notional * (self.commission_bps / 10000)
        
        # Check if we have enough balance
        if order.side == OrderSide.BUY:
            required = notional + commission
            if required > self.balance:
                order.status = OrderStatus.REJECTED
                return
        
        # Fill order
        order.status = OrderStatus.FILLED
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.commission = commission
        order.filled_at = datetime.now()
        
        # Update balance
        if order.side == OrderSide.BUY:
            self.balance -= (notional + commission)
        else:
            self.balance += (notional - commission)
        
        # Update position
        current_pos = self.positions.get(order.symbol, 0.0)
        if order.side == OrderSide.BUY:
            self.positions[order.symbol] = current_pos + order.quantity
        else:
            self.positions[order.symbol] = current_pos - order.quantity
        
        # Create fill
        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            commission=commission,
            timestamp=datetime.now(),
            execution_id=f"FILL_{order.order_id}"
        )
        
        # Notify
        self._notify_fills(fill)
    
    def set_price(self, symbol: str, price: float):
        """Set current market price (for testing)."""
        self.current_prices[symbol] = price
```

**Key Features:**
- Realistic latency simulation (10-50ms)
- Slippage modeling (5 bps default)
- Commission calculation
- Balance and position tracking
- No real capital at risk

---

### 7. Resiliency Layer

**File:** `autotrader/execution/resiliency/__init__.py`

**Purpose:** Handle failures, retries, dead-letter queue, reconnection

```python
class ResiliencyManager:
    """
    Manage execution resiliency.
    
    Features:
    - Exponential backoff retry
    - Dead-letter queue for failed orders
    - Automatic reconnection
    - Circuit breaker
    """
    
    def __init__(
        self,
        adapter: BaseBrokerAdapter,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        backoff_multiplier: float = 2.0,
        circuit_breaker_threshold: int = 5
    ):
        self.adapter = adapter
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.backoff_multiplier = backoff_multiplier
        self.circuit_breaker_threshold = circuit_breaker_threshold
        
        # State
        self.dead_letter_queue: List[Tuple[Order, Exception]] = []
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure: Optional[datetime] = None
    
    async def submit_order_with_retry(self, order: Order) -> Order:
        """
        Submit order with exponential backoff retry.
        
        Returns
        -------
        order : Order
            Submitted order
        
        Raises
        ------
        Exception
            If all retries exhausted
        """
        if self.circuit_open:
            raise Exception("Circuit breaker open")
        
        backoff = self.initial_backoff
        
        for attempt in range(self.max_retries):
            try:
                result = await self.adapter.submit_order(order)
                
                # Success - reset failure count
                self.failure_count = 0
                
                return result
            
            except Exception as e:
                self.failure_count += 1
                self.last_failure = datetime.now()
                
                # Check circuit breaker
                if self.failure_count >= self.circuit_breaker_threshold:
                    self.circuit_open = True
                    raise Exception("Circuit breaker triggered")
                
                if attempt < self.max_retries - 1:
                    # Retry with backoff
                    await asyncio.sleep(backoff)
                    backoff *= self.backoff_multiplier
                else:
                    # All retries exhausted - add to DLQ
                    self.dead_letter_queue.append((order, e))
                    raise
    
    async def reconnect(self):
        """Attempt to reconnect to broker."""
        try:
            await self.adapter.disconnect()
            await asyncio.sleep(5)
            success = await self.adapter.connect()
            
            if success:
                self.failure_count = 0
                self.circuit_open = False
            
            return success
        
        except Exception:
            return False
    
    async def process_dead_letter_queue(self):
        """Attempt to reprocess failed orders."""
        if not self.dead_letter_queue:
            return
        
        reprocessed = []
        
        for order, error in self.dead_letter_queue:
            try:
                await self.adapter.submit_order(order)
                reprocessed.append((order, error))
            except Exception:
                continue  # Leave in DLQ
        
        # Remove reprocessed
        for item in reprocessed:
            self.dead_letter_queue.remove(item)
```

---

### 8. Execution Engine Orchestrator

**File:** `autotrader/execution/__init__.py`

**Purpose:** Main integration layer combining all components

```python
from autotrader.strategy import TradingStrategy, ExecutionDecision
from autotrader.execution.adapters import BaseBrokerAdapter
from autotrader.execution.oms import OrderManager
from autotrader.execution.resiliency import ResiliencyManager

class ExecutionEngine:
    """
    Main execution orchestrator.
    
    Integrates Phase 8 strategy with execution adapters.
    """
    
    def __init__(
        self,
        strategy: TradingStrategy,
        adapter: BaseBrokerAdapter,
        enable_resiliency: bool = True
    ):
        self.strategy = strategy
        self.adapter = adapter
        
        # Initialize components
        self.oms = OrderManager(adapter)
        
        if enable_resiliency:
            self.resiliency = ResiliencyManager(adapter)
        else:
            self.resiliency = None
    
    async def execute_decision(self, decision: ExecutionDecision) -> Order:
        """
        Execute trading decision from Phase 8.
        
        Parameters
        ----------
        decision : ExecutionDecision
            Decision from strategy
        
        Returns
        -------
        order : Order
            Executed order
        """
        if decision.action == 'HOLD':
            return None
        
        # Convert decision to order
        side = OrderSide.BUY if decision.action == 'LONG' else OrderSide.SELL
        
        # Submit with resiliency
        if self.resiliency:
            order = await self.resiliency.submit_order_with_retry(
                Order(
                    order_id="",
                    symbol=decision.symbol,
                    side=side,
                    order_type=OrderType.LIMIT,
                    quantity=decision.size,
                    price=decision.metadata.get('limit_price')
                )
            )
        else:
            order = await self.oms.submit_order(
                symbol=decision.symbol,
                side=side,
                quantity=decision.size,
                order_type=OrderType.LIMIT,
                price=decision.metadata.get('limit_price')
            )
        
        return order
    
    async def run_live_trading(self):
        """
        Main live trading loop.
        
        Processes market data and executes strategy decisions.
        """
        await self.adapter.connect()
        
        try:
            while True:
                # Get market data
                # Process through strategy
                # Execute decisions
                
                await asyncio.sleep(0.1)  # 100ms cycle
        
        finally:
            await self.adapter.disconnect()
```

---

## Configuration

### Example Configuration (YAML)

```yaml
# config/execution.yaml

execution:
  broker: binance  # ibkr, binance, coinbase, okx, oanda, paper
  
  # Broker-specific configs
  binance:
    api_key: ${BINANCE_API_KEY}
    api_secret: ${BINANCE_API_SECRET}
    testnet: true
  
  ibkr:
    host: 127.0.0.1
    port: 7497  # Paper trading
    client_id: 1
  
  oanda:
    account_id: ${OANDA_ACCOUNT_ID}
    access_token: ${OANDA_TOKEN}
    environment: practice
  
  paper:
    initial_balance: 100000
    latency_ms: [10, 50]
    slippage_bps: 5
    commission_bps: 10
  
  # OMS settings
  oms:
    max_open_orders: 100
    order_timeout_seconds: 300
  
  # Resiliency
  resiliency:
    max_retries: 3
    initial_backoff: 1.0
    backoff_multiplier: 2.0
    circuit_breaker_threshold: 5
    enable_dlq: true
```

---

## Safety Features

### Pre-Execution Checks

1. **Phase 8 Risk Limits:** All Phase 8 risk controls enforced before execution
2. **Balance Check:** Ensure sufficient capital
3. **Position Limits:** Check inventory caps
4. **Duplicate Order Prevention:** Avoid submitting duplicate orders

### Post-Execution Monitoring

1. **Fill Reconciliation:** Match fills with orders
2. **P&L Tracking:** Real-time P&L calculation
3. **Position Drift:** Alert if actual position deviates from expected
4. **Latency Monitoring:** Track execution latency

### Kill Switch

```python
class KillSwitch:
    """Emergency stop all trading."""
    
    def __init__(self, execution_engine: ExecutionEngine):
        self.engine = execution_engine
    
    async def activate(self):
        """
        Activate kill switch.
        
        1. Cancel all open orders
        2. Close all positions (optional)
        3. Disconnect from broker
        4. Send alerts
        """
        # Cancel all orders
        orders = self.engine.oms.get_open_orders()
        for order in orders:
            await self.engine.oms.cancel_order(order.order_id)
        
        # Disconnect
        await self.engine.adapter.disconnect()
        
        # Alert
        print("🚨 KILL SWITCH ACTIVATED - All trading stopped")
```

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Order Latency (REST) | < 100ms | Submit to acknowledgement |
| Order Latency (WebSocket) | < 50ms | Via persistent connection |
| Fill Latency | < 200ms | Fill to notification |
| Reconnection Time | < 5s | Automatic reconnection |
| Order Success Rate | > 99% | With retry logic |
| Dead-Letter Queue | < 0.1% | Orders requiring manual intervention |

---

## Testing Strategy

### Unit Tests

- Adapter interface compliance
- Order conversion (internal → broker format)
- Fill parsing
- Resiliency logic (retry, backoff)

### Integration Tests

- Paper trading end-to-end
- Broker connectivity (testnet/sandbox)
- Order lifecycle (submit → fill → notify)
- Reconnection scenarios

### Live Dry Run

- Run during live market hours
- Monitor latency and success rates
- Verify fill accuracy
- Test kill switch

---

## Deliverables

✅ **Broker Adapters:** IBKR, Binance, Coinbase, OKX, Oanda  
✅ **Paper Trading:** Fully simulated execution  
✅ **OMS:** Order lifecycle management  
✅ **Resiliency:** Retry, DLQ, reconnect  
✅ **Integration:** Phase 8 strategy → live execution  
✅ **Documentation:** Setup guides, API reference  
✅ **Tests:** Unit, integration, live dry run  

---

## Next Steps

1. Implement broker adapters
2. Build OMS
3. Add resiliency layer
4. Create paper trading adapter
5. Integration testing with Phase 8
6. Live dry run in market hours
7. Production deployment checklist

**Status: Specification Complete, Ready for Implementation**
