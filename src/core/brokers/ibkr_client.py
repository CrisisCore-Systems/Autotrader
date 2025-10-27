"""
Interactive Brokers Client - Canadian Trading Adapter

Drop-in replacement for Alpaca client using ib-insync for Canadian markets.
Provides the same interface as AlpacaClient for seamless integration.

Requirements:
    - ib-insync: pip install ib-insync
    - TWS or IB Gateway running with API enabled
    - Paper trading account configured

Setup:
    1. Install IBKR TWS or IB Gateway
    2. Login to Paper account
    3. Enable API: Global Configuration → API → Settings
       - Enable ActiveX and Socket Clients
       - Add 127.0.0.1 to trusted IPs
       - Socket port: 7497 (TWS paper) or 4002 (Gateway paper)
    4. Set environment variables:
       - IBKR_HOST=127.0.0.1
       - IBKR_PORT=7497
       - IBKR_CLIENT_ID=42
"""

from ib_insync import IB, MarketOrder, LimitOrder, Stock, Contract
import os
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class IBKRPosition:
    """Position information matching expected interface."""
    symbol: str
    qty: float
    avg_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


@dataclass
class IBKROrder:
    """Order information matching expected interface."""
    order_id: int
    symbol: str
    qty: float
    side: str
    order_type: str
    status: str
    filled_qty: float
    filled_avg_price: float
    limit_price: Optional[float] = None
    created_at: Optional[datetime] = None


class IBKRClient:
    """
    Interactive Brokers client adapter for Canadian trading.
    
    Provides drop-in replacement for Alpaca client with the same interface.
    All methods match Alpaca signatures for seamless integration.
    """
    
    def __init__(self,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 client_id: Optional[int] = None,
                 paper: bool = True):
        """Initialize IBKR connection.
        
        Args:
            host: TWS/Gateway host (default: 127.0.0.1)
            port: TWS/Gateway port (default: 7497 for paper TWS)
            client_id: Unique client ID (default: 42)
            paper: Whether using paper trading (default: True)
        """
        self.host = host or os.getenv("IBKR_HOST", "127.0.0.1")
        self.port = int(port or os.getenv("IBKR_PORT", "7497"))
        self.client_id = int(client_id or os.getenv("IBKR_CLIENT_ID", "42"))
        self.paper = paper or os.getenv("USE_PAPER", "1") == "1"
        
        self.ib = IB()
        self._connected = False
        
        logger.info(f"Initializing IBKR client: host={self.host}, port={self.port}, client_id={self.client_id}, paper={self.paper}")
        
        try:
            self.ib.connect(self.host, self.port, clientId=self.client_id)
            self._connected = True
            logger.info("Successfully connected to IBKR")
        except Exception as e:
            logger.error(f"Failed to connect to IBKR: {e}")
            raise ConnectionError(f"IBKR connection failed: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected to IBKR."""
        return self._connected and self.ib.isConnected()
    
    def _ensure_connected(self):
        """Ensure connection is active, reconnect if needed."""
        if not self.is_connected():
            logger.warning("Connection lost, reconnecting...")
            try:
                self.ib.connect(self.host, self.port, clientId=self.client_id)
                self._connected = True
                logger.info("Reconnected to IBKR")
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                raise ConnectionError(f"IBKR reconnection failed: {e}")
    
    # --- Contract creation ---
    
    def _stock(self, symbol: str, exchange: str = "SMART", currency: str = "USD") -> Contract:
        """Create and qualify stock contract.
        
        Args:
            symbol: Stock symbol
            exchange: Exchange (default: SMART for best routing)
            currency: Currency (default: USD, use CAD for Canadian stocks)
            
        Returns:
            Qualified Contract object
        """
        self._ensure_connected()
        
        # Auto-detect Canadian stocks (TSX/TSXV)
        if symbol.endswith(".TO") or symbol.endswith(".V"):
            exchange = "TSE" if symbol.endswith(".TO") else "VENTURE"
            currency = "CAD"
            symbol = symbol.split(".")[0]  # Remove exchange suffix
        
        contract = Stock(symbol, exchange, currency)
        qualified = self.ib.qualifyContracts(contract)
        
        if not qualified:
            raise ValueError(f"Failed to qualify contract for {symbol}")
        
        return qualified[0]
    
    # --- Market data ---
    
    def get_last_price(self, symbol: str) -> float:
        """Get last traded price for symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Last price (or close if no recent trades)
        """
        try:
            contract = self._stock(symbol)
            ticker = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(0.6)  # Allow time for tick data
            
            # Try last, then close, then bid/ask midpoint
            price = ticker.last or ticker.close or ((ticker.bid + ticker.ask) / 2 if ticker.bid and ticker.ask else 0.0)
            
            self.ib.cancelMktData(contract)
            return float(price)
        
        except Exception as e:
            logger.error(f"Failed to get last price for {symbol}: {e}")
            return 0.0
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get detailed quote for symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dict with bid, ask, last, volume, etc.
        """
        try:
            contract = self._stock(symbol)
            ticker = self.ib.reqMktData(contract, "", False, False)
            self.ib.sleep(0.6)
            
            quote = {
                "symbol": symbol,
                "bid": float(ticker.bid or 0),
                "ask": float(ticker.ask or 0),
                "last": float(ticker.last or ticker.close or 0),
                "close": float(ticker.close or 0),
                "volume": int(ticker.volume or 0),
                "bid_size": int(ticker.bidSize or 0),
                "ask_size": int(ticker.askSize or 0),
                "timestamp": datetime.now()
            }
            
            self.ib.cancelMktData(contract)
            return quote
        
        except Exception as e:
            logger.error(f"Failed to get quote for {symbol}: {e}")
            return {
                "symbol": symbol,
                "bid": 0.0,
                "ask": 0.0,
                "last": 0.0,
                "volume": 0,
                "timestamp": datetime.now()
            }
    
    def get_bars(self, symbol: str, timeframe: str = "1Min", limit: int = 100) -> List[Dict]:
        """Get historical bars (not used in current implementation but kept for compatibility).
        
        Args:
            symbol: Stock symbol
            timeframe: Bar timeframe (1Min, 5Min, etc.)
            limit: Number of bars to fetch
            
        Returns:
            List of bar dictionaries
        """
        try:
            contract = self._stock(symbol)
            
            # Convert timeframe to IBKR format
            duration = f"{limit} S"  # seconds for minute bars
            bar_size = timeframe.replace("Min", " min").replace("Hour", " hour")
            
            bars = self.ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='TRADES',
                useRTH=False
            )
            
            return [
                {
                    "timestamp": bar.date,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume
                }
                for bar in bars
            ]
        
        except Exception as e:
            logger.error(f"Failed to get bars for {symbol}: {e}")
            return []
    
    # --- Order management ---
    
    def place_market_order(self, symbol: str, qty: float, side: str = "buy") -> Dict[str, Any]:
        """Place market order.
        
        Args:
            symbol: Stock symbol
            qty: Quantity (positive for buy/sell)
            side: "buy" or "sell"
            
        Returns:
            Dict with order_id and status
        """
        try:
            contract = self._stock(symbol)
            action = "BUY" if side.lower().startswith("b") else "SELL"
            order = MarketOrder(action, abs(qty))
            
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(0.2)
            
            logger.info(f"Placed market order: {action} {qty} {symbol}, order_id={trade.order.orderId}")
            
            return {
                "order_id": trade.order.orderId,
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "order_type": "market",
                "status": trade.orderStatus.status if trade.orderStatus else "Submitted",
                "filled_qty": trade.orderStatus.filled if trade.orderStatus else 0,
                "filled_avg_price": trade.orderStatus.avgFillPrice if trade.orderStatus else 0
            }
        
        except Exception as e:
            logger.error(f"Failed to place market order for {symbol}: {e}")
            raise
    
    def place_limit_order(self, symbol: str, qty: float, limit_price: float, side: str = "buy") -> Dict[str, Any]:
        """Place limit order.
        
        Args:
            symbol: Stock symbol
            qty: Quantity (positive for buy/sell)
            limit_price: Limit price
            side: "buy" or "sell"
            
        Returns:
            Dict with order_id, status, and limit price
        """
        try:
            contract = self._stock(symbol)
            action = "BUY" if side.lower().startswith("b") else "SELL"
            order = LimitOrder(action, abs(qty), limit_price)
            
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(0.2)
            
            logger.info(f"Placed limit order: {action} {qty} {symbol} @ {limit_price}, order_id={trade.order.orderId}")
            
            return {
                "order_id": trade.order.orderId,
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "order_type": "limit",
                "limit_price": limit_price,
                "status": trade.orderStatus.status if trade.orderStatus else "Submitted",
                "filled_qty": trade.orderStatus.filled if trade.orderStatus else 0,
                "filled_avg_price": trade.orderStatus.avgFillPrice if trade.orderStatus else 0
            }
        
        except Exception as e:
            logger.error(f"Failed to place limit order for {symbol}: {e}")
            raise
    
    def cancel_order(self, order_id: int) -> bool:
        """Cancel order by ID.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            True if successful
        """
        try:
            order = [o for o in self.ib.openOrders() if o.orderId == order_id]
            if order:
                self.ib.cancelOrder(order[0])
                logger.info(f"Cancelled order {order_id}")
                return True
            else:
                logger.warning(f"Order {order_id} not found in open orders")
                return False
        
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
    
    def get_order(self, order_id: int) -> Optional[IBKROrder]:
        """Get order details by ID.
        
        Args:
            order_id: Order ID
            
        Returns:
            IBKROrder object or None if not found
        """
        try:
            trades = self.ib.trades()
            for trade in trades:
                if trade.order.orderId == order_id:
                    return IBKROrder(
                        order_id=trade.order.orderId,
                        symbol=trade.contract.symbol,
                        qty=trade.order.totalQuantity,
                        side="buy" if trade.order.action == "BUY" else "sell",
                        order_type=trade.order.orderType.lower(),
                        status=trade.orderStatus.status if trade.orderStatus else "Unknown",
                        filled_qty=trade.orderStatus.filled if trade.orderStatus else 0,
                        filled_avg_price=trade.orderStatus.avgFillPrice if trade.orderStatus else 0,
                        limit_price=trade.order.lmtPrice if hasattr(trade.order, 'lmtPrice') else None
                    )
            
            logger.warning(f"Order {order_id} not found")
            return None
        
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None
    
    # --- Positions & account ---
    
    def get_positions(self) -> List[IBKRPosition]:
        """Get all current positions.
        
        Returns:
            List of IBKRPosition objects
        """
        try:
            positions = self.ib.positions()
            result = []
            
            for pos in positions:
                # Get current market price for unrealized P&L
                try:
                    ticker = self.ib.reqMktData(pos.contract, "", False, False)
                    self.ib.sleep(0.3)
                    current_price = float(ticker.last or ticker.close or 0)
                    self.ib.cancelMktData(pos.contract)
                except Exception:
                    current_price = 0.0
                
                avg_cost = float(pos.avgCost or 0)
                qty = float(pos.position)
                market_value = current_price * qty
                unrealized_pnl = market_value - (avg_cost * qty)
                unrealized_pnl_pct = (unrealized_pnl / (avg_cost * qty) * 100) if avg_cost > 0 else 0
                
                result.append(IBKRPosition(
                    symbol=pos.contract.symbol,
                    qty=qty,
                    avg_price=avg_cost,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct
                ))
            
            return result
        
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def get_position(self, symbol: str) -> Optional[IBKRPosition]:
        """Get position for specific symbol.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            IBKRPosition or None if no position
        """
        positions = self.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    
    def get_account(self) -> Dict[str, Any]:
        """Get account information.
        
        Returns:
            Dict with account values
        """
        try:
            account_values = self.ib.accountValues()
            
            # Extract key values
            values = {}
            for av in account_values:
                values[av.tag] = float(av.value) if av.value else 0.0
            
            return {
                "equity": values.get("EquityWithLoanValue", 0.0),
                "cash": values.get("CashBalance", 0.0),
                "buying_power": values.get("BuyingPower", 0.0),
                "portfolio_value": values.get("NetLiquidation", 0.0),
                "currency": "CAD" if self.paper else "USD",
                "paper": self.paper
            }
        
        except Exception as e:
            logger.error(f"Failed to get account info: {e}")
            return {
                "equity": 0.0,
                "cash": 0.0,
                "buying_power": 0.0,
                "portfolio_value": 0.0
            }
    
    # --- Cleanup ---
    
    def close(self):
        """Disconnect from IBKR."""
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
                self._connected = False
                logger.info("Disconnected from IBKR")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    def __del__(self):
        """Ensure cleanup on object destruction."""
        self.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
