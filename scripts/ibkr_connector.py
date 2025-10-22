"""
IBKR Connection Harness - Production CLI Tool

A tactical IBKR CLI harness for CrisisCore trading systems.
Provides diagnostics, testing, and utility commands for IBKR connections.

Usage:
    python scripts/ibkr_connector.py --ping              # Test connection
    python scripts/ibkr_connector.py --positions         # Show current positions
    python scripts/ibkr_connector.py --account           # Show account summary
    python scripts/ibkr_connector.py --place-test        # Place & cancel test order
    python scripts/ibkr_connector.py --cancel-all        # Cancel all open orders
    python scripts/ibkr_connector.py --quote AAPL        # Get quote for symbol
    python scripts/ibkr_connector.py --orders            # Show open orders

Environment Variables:
    IBKR_HOST       - TWS/Gateway host (default: 127.0.0.1)
    IBKR_PORT       - Port (default: 7497 for TWS paper)
    IBKR_CLIENT_ID  - Client ID (default: 42)
    LOG_LEVEL       - Logging level (default: INFO)

Example:
    # Windows
    $env:IBKR_PORT="7497"; python scripts/ibkr_connector.py --ping
    
    # Linux/Mac
    IBKR_PORT=7497 python scripts/ibkr_connector.py --ping
"""

import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ib_insync import *

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')

# ---- LOGGING SETUP ----
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / f"ibkr_connector_{datetime.now().strftime('%Y%m%d')}.log"

# Use UTF-8 encoding for log file to handle Unicode characters
logging.basicConfig(
    level=getattr(logging, os.getenv('LOG_LEVEL', 'INFO')),
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ---- CONFIG ----
HOST = os.getenv('IBKR_HOST', '127.0.0.1')
PORT = int(os.getenv('IBKR_PORT', '7497'))
CLIENT_ID = int(os.getenv('IBKR_CLIENT_ID', '42'))

# ---- IBKR CLIENT WRAPPER ----
class IBKRHarness:
    """IBKR connection harness with utility methods"""
    
    def __init__(self, host: str = HOST, port: int = PORT, client_id: int = CLIENT_ID):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()
        self._connected = False
        
        # Start event loop
        try:
            util.startLoop()
        except RuntimeError:
            pass
    
    def connect(self, timeout: int = 10) -> bool:
        """Connect to IBKR"""
        try:
            logger.info(f"Connecting to {self.host}:{self.port} (client_id={self.client_id})...")
            self.ib.connect(self.host, self.port, self.client_id, readonly=False, timeout=timeout)
            self._connected = True
            logger.info(f"[OK] Connected (server version: {self.ib.client.serverVersion()})")
            return True
        except Exception as e:
            logger.error(f"[X] Connection failed: {e}")
            self._troubleshoot()
            return False
    
    def disconnect(self):
        """Disconnect from IBKR"""
        if self._connected:
            self.ib.disconnect()
            self._connected = False
            logger.info("Disconnected")
    
    def _troubleshoot(self):
        """Print troubleshooting tips"""
        print("\n" + "=" * 80)
        print("TROUBLESHOOTING")
        print("=" * 80)
        print("1. Is TWS/Gateway running and logged in?")
        print("2. Is API enabled? (File → Global Configuration → API → Settings)")
        print("3. Is 'Enable ActiveX and Socket Clients' checked?")
        print("4. Is '127.0.0.1' in 'Trusted IPs'?")
        print(f"5. Is port {self.port} correct?")
        print("   - TWS Paper: 7497")
        print("   - TWS Live: 7496")
        print("   - Gateway Paper: 4002")
        print("   - Gateway Live: 4001")
        print("6. Did you restart TWS after changing settings?")
        print("7. Firewall blocking javaw.exe/TWS.exe?")
        print("=" * 80)
    
    def ping(self) -> bool:
        """Test connection"""
        if not self._connected:
            return False
        
        try:
            accounts = self.ib.managedAccounts()
            server_time = self.ib.reqCurrentTime()
            print(f"[OK] Connection OK")
            print(f"  Accounts: {', '.join(accounts)}")
            print(f"  Server time: {server_time}")
            return True
        except Exception as e:
            logger.error(f"[X] Ping failed: {e}")
            return False
    
    def get_account(self) -> Optional[str]:
        """Get account summary"""
        if not self._connected:
            return None
        
        try:
            accounts = self.ib.managedAccounts()
            if not accounts:
                logger.error("No accounts found")
                return None
            
            acct = accounts[0]
            summary = self.ib.accountSummary()
            
            print("=" * 80)
            print(f"ACCOUNT: {acct}")
            print("=" * 80)
            
            key_tags = ['NetLiquidation', 'TotalCashValue', 'BuyingPower', 
                       'GrossPositionValue', 'UnrealizedPnL', 'RealizedPnL']
            
            for item in summary:
                if item.tag in key_tags:
                    print(f"  {item.tag:20s}: {item.value:>15s} {item.currency}")
            
            print("=" * 80)
            return acct
            
        except Exception as e:
            logger.error(f"[X] Account fetch failed: {e}")
            return None
    
    def get_positions(self) -> List:
        """Get current positions"""
        if not self._connected:
            return []
        
        try:
            positions = self.ib.positions()
            
            print("=" * 80)
            print(f"POSITIONS ({len(positions)} total)")
            print("=" * 80)
            
            if not positions:
                print("  No positions")
            else:
                print(f"{'Symbol':<10s} {'Qty':>8s} {'Avg Cost':>12s} {'Mkt Price':>12s} {'P&L':>12s}")
                print("-" * 80)
                
                for pos in positions:
                    symbol = pos.contract.symbol
                    qty = pos.position
                    avg_cost = pos.avgCost
                    
                    # Get current market price
                    ticker = self.ib.reqMktData(pos.contract, '', snapshot=True)
                    self.ib.sleep(1)
                    mkt_price = ticker.last or ticker.close or avg_cost
                    
                    pnl = (mkt_price - avg_cost) * qty
                    
                    print(f"{symbol:<10s} {qty:>8.0f} {avg_cost:>12.2f} {mkt_price:>12.2f} {pnl:>12.2f}")
            
            print("=" * 80)
            return positions
            
        except Exception as e:
            logger.error(f"[X] Positions fetch failed: {e}")
            return []
    
    def get_orders(self) -> List:
        """Get open orders"""
        if not self._connected:
            return []
        
        try:
            trades = self.ib.openTrades()
            
            print("=" * 80)
            print(f"OPEN ORDERS ({len(trades)} total)")
            print("=" * 80)
            
            if not trades:
                print("  No open orders")
            else:
                print(f"{'ID':<8s} {'Symbol':<10s} {'Side':<6s} {'Qty':>8s} {'Type':<8s} {'Status':<12s}")
                print("-" * 80)
                
                for trade in trades:
                    order_id = trade.order.orderId
                    symbol = trade.contract.symbol
                    side = trade.order.action
                    qty = trade.order.totalQuantity
                    order_type = trade.order.orderType
                    status = trade.orderStatus.status
                    
                    print(f"{order_id:<8d} {symbol:<10s} {side:<6s} {qty:>8.0f} {order_type:<8s} {status:<12s}")
            
            print("=" * 80)
            return trades
            
        except Exception as e:
            logger.error(f"[X] Orders fetch failed: {e}")
            return []
    
    def get_quote(self, symbol: str, exchange: str = 'SMART', currency: str = 'USD') -> Optional[float]:
        """Get quote for symbol"""
        if not self._connected:
            return None
        
        try:
            # Detect Canadian stocks
            if symbol.endswith('.TO'):
                symbol = symbol[:-3]
                exchange = 'TSE'
                currency = 'CAD'
            elif symbol.endswith('.V'):
                symbol = symbol[:-2]
                exchange = 'VENTURE'
                currency = 'CAD'
            
            contract = Stock(symbol, exchange, currency)
            self.ib.qualifyContracts(contract)
            
            ticker = self.ib.reqMktData(contract, '', snapshot=True)
            self.ib.sleep(2)
            
            last = ticker.last or ticker.close or 0
            bid = ticker.bid or 0
            ask = ticker.ask or 0
            volume = ticker.volume or 0
            
            print("=" * 80)
            print(f"QUOTE: {symbol} ({exchange})")
            print("=" * 80)
            print(f"  Last:   ${last:.2f}")
            print(f"  Bid:    ${bid:.2f}")
            print(f"  Ask:    ${ask:.2f}")
            print(f"  Volume: {volume:,.0f}")
            print("=" * 80)
            
            self.ib.cancelMktData(contract)
            return last
            
        except Exception as e:
            logger.error(f"[X] Quote fetch failed: {e}")
            return None
    
    def place_test_order(self, symbol: str = 'AAPL') -> bool:
        """Place and immediately cancel a test order"""
        if not self._connected:
            return False
        
        try:
            # Get current price
            contract = Stock(symbol, 'SMART', 'USD')
            self.ib.qualifyContracts(contract)
            
            ticker = self.ib.reqMktData(contract, '', snapshot=True)
            self.ib.sleep(2)
            last = ticker.last or ticker.close or 150.0
            
            # Place limit order 50% below market (won't fill)
            limit_price = round(last * 0.5, 2)
            order = LimitOrder('BUY', 1, limit_price)
            
            logger.info(f"Placing test order: BUY 1 {symbol} @ ${limit_price:.2f} limit")
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(2)
            
            print(f"[OK] Order placed: {trade.orderStatus.status} (ID: {trade.order.orderId})")
            print(f"  Check TWS Mosaic - order should appear!")
            
            # Cancel immediately
            logger.info(f"Canceling test order {trade.order.orderId}")
            self.ib.cancelOrder(order)
            self.ib.sleep(2)
            
            print(f"[OK] Order canceled: {trade.orderStatus.status}")
            print(f"  Order should disappear from TWS Mosaic")
            
            return True
            
        except Exception as e:
            logger.error(f"[X] Test order failed: {e}")
            return False
    
    def cancel_all_orders(self) -> int:
        """Cancel all open orders"""
        if not self._connected:
            return 0
        
        try:
            trades = self.ib.openTrades()
            count = len(trades)
            
            if count == 0:
                print("No open orders to cancel")
                return 0
            
            logger.info(f"Canceling {count} open orders...")
            
            for trade in trades:
                try:
                    self.ib.cancelOrder(trade.order)
                    logger.info(f"  Canceled order {trade.order.orderId} ({trade.contract.symbol})")
                except Exception as e:
                    logger.error(f"  Failed to cancel order {trade.order.orderId}: {e}")
            
            self.ib.sleep(2)
            print(f"[OK] Canceled {count} orders")
            return count
            
        except Exception as e:
            logger.error(f"[X] Cancel all failed: {e}")
            return 0

# ---- CLI ----
def main():
    parser = argparse.ArgumentParser(
        description='IBKR Connection Harness - Production CLI Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('--ping', action='store_true', help='Test connection')
    parser.add_argument('--account', action='store_true', help='Show account summary')
    parser.add_argument('--positions', action='store_true', help='Show current positions')
    parser.add_argument('--orders', action='store_true', help='Show open orders')
    parser.add_argument('--quote', metavar='SYMBOL', help='Get quote for symbol')
    parser.add_argument('--place-test', action='store_true', help='Place & cancel test order')
    parser.add_argument('--cancel-all', action='store_true', help='Cancel all open orders')
    
    args = parser.parse_args()
    
    # Require at least one action
    if not any([args.ping, args.account, args.positions, args.orders, args.quote, 
                args.place_test, args.cancel_all]):
        parser.print_help()
        sys.exit(1)
    
    # Banner
    print("\n" + "=" * 80)
    print("IBKR CONNECTION HARNESS")
    print("=" * 80)
    print(f"Host: {HOST}:{PORT} (client_id={CLIENT_ID})")
    print(f"Log: {LOG_FILE}")
    print("=" * 80 + "\n")
    
    # Create harness
    harness = IBKRHarness(HOST, PORT, CLIENT_ID)
    
    # Connect
    if not harness.connect():
        sys.exit(1)
    
    try:
        # Execute commands
        success = True
        
        if args.ping:
            success = harness.ping() and success
        
        if args.account:
            success = (harness.get_account() is not None) and success
        
        if args.positions:
            harness.get_positions()
        
        if args.orders:
            harness.get_orders()
        
        if args.quote:
            success = (harness.get_quote(args.quote) is not None) and success
        
        if args.place_test:
            success = harness.place_test_order() and success
        
        if args.cancel_all:
            harness.cancel_all_orders()
        
        sys.exit(0 if success else 1)
        
    finally:
        harness.disconnect()

if __name__ == '__main__':
    main()
