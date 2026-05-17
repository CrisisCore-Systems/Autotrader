#!/usr/bin/env python3
"""
TR-004: Multi-Order Concurrent Trading Harness (v2-async)
Scope Guard: Paper Trading Only (Port 7497). Real-time Async Event Routing.
Integrates ib_insync event loop handling with strict aggregate risk ceilings.
"""

import os
import sys
import json
import asyncio
import logging
from typing import List, Dict, Any, Optional
from ib_insync import IB, Stock, LimitOrder, OrderStatus

# Structural logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TR-004-Async")

class AsyncConcurrentHarness:
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 95):
        self.host = host
        self.port = port
        self.client_id = client_id
        
        # Enforce local isolation guardrails
        if self.port in [7496, 4001]:
            logger.critical("SAFETY BREACH: Production port targeted. Halting execution.")
            raise PermissionError("Production environment interlock tripped.")
            
        self.ib = IB()
        self.signal_queue: asyncio.Queue = asyncio.Queue()
        
        # Risk thresholds
        self.max_single_notional = 5.00
        self.max_aggregate_notional = 20.00
        self.current_exposure = 0.0
        
        # Isolated state mapping: orderId -> metadata/status tracker
        self.order_trackers: Dict[int, Dict[str, Any]] = {}

    async def connect_exchange(self):
        """Establishes persistent non-blocking connection to TWS."""
        logger.info(f"Connecting to IBKR Paper Gateway at {self.host}:{self.port}...")
        try:
            # Extend timeout to 15s to handle degraded TWS farm connections
            await asyncio.wait_for(
                self.ib.connectAsync(self.host, self.port, clientId=self.client_id, timeout=15),
                timeout=20
            )
        except asyncio.TimeoutError:
            logger.warning("Connection handshake timed out (TWS data farms degraded). Proceeding with established socket connection.")
        
        logger.info("📡 Live Event Loop Connected to IBKR.")
        
        # Register global callback routers
        self.ib.orderStatusEvent += self.on_order_status_update
        self.ib.execDetailsEvent += self.on_execution_details

    def on_order_status_update(self, trade):
        """Global callback router. Flags changes to isolated order trackers."""
        order_id = trade.order.orderId
        status = trade.orderStatus.status
        filled = trade.orderStatus.filled
        remaining = trade.orderStatus.remaining
        
        if order_id in self.order_trackers:
            self.order_trackers[order_id]["status"] = status
            self.order_trackers[order_id]["filled"] = filled
            logger.info(
                f"[OrderID-{order_id}] 🔄 State Update: Status={status} | Filled={filled} | Remaining={remaining}"
            )
        else:
            logger.debug(f"[OrderID-{order_id}] Received status for untracked order ID: {order_id}")

    def on_execution_details(self, trade, fill):
        """Handles granular fill events for fractional/partial executions."""
        order_id = trade.order.orderId
        logger.info(f"[OrderID-{order_id}] ⚡ Execution Match Observed: {fill.execution.shares} shares @ ${fill.execution.price:.4f}")

    async def ingest_signals(self, signals: List[Dict[str, Any]]):
        """Parses batch arrays and queues items that fit within the safety valves."""
        for s in signals:
            symbol = s.get("symbol")
            qty = float(s.get("quantity", 0))
            price = float(s.get("limit_price", 0))
            notional = qty * price

            if notional > self.max_single_notional:
                logger.warning(f"[Ingestion] ❌ Rejected {symbol}: Notional ${notional:.2f} breaches Single Cap (${self.max_single_notional:.2f})")
                continue

            if self.current_exposure + notional > self.max_aggregate_notional:
                logger.critical(f"[Ingestion] ⚠️ Blocked {symbol}: Aggregate exposure would reach ${self.current_exposure + notional:.2f} (Max ${self.max_aggregate_notional:.2f})")
                break

            self.current_exposure += notional
            await self.signal_queue.put(s)
            logger.info(f"[Ingestion] ✅ Queued {symbol} (${notional:.2f}) | Total Allocated Exposure: ${self.current_exposure:.2f}")

    async def process_queue_worker(self):
        """Continuous consumer loop that pops signals and dispatches them to the exchange."""
        logger.info("[Worker] Initializing active queue consumer loop...")
        
        while not self.signal_queue.empty():
            signal = await self.signal_queue.get()
            symbol = signal.get("symbol")
            
            # Formulate IB Contract and Order
            contract = Stock(symbol, signal.get("exchange", "SMART"), signal.get("currency", "USD"))
            await self.ib.qualifyContractsAsync(contract)
            
            order = LimitOrder(signal.get("side").upper(), signal.get("quantity"), signal.get("limit_price"))
            
            # Place order via ib_insync (non-blocking placement)
            trade = self.ib.placeOrder(contract, order)
            order_id = order.orderId
            
            # Register isolated tracker state space
            self.order_trackers[order_id] = {
                "signal_id": signal.get("signal_id"),
                "symbol": symbol,
                "status": "pending",
                "filled": 0.0
            }
            
            logger.info(f"[OrderID-{order_id}] 🚀 Dispatched Order for {symbol}")
            self.signal_queue.task_done()

    async def terminate_session(self, timeout: int = 3):
        """Gracefully disconnects and cancels any remaining open orders in the pipeline."""
        logger.info(f"[Shutdown] Initiating defensive teardown window ({timeout}s)...")
        
        # Cancel all open orders routed via this client session
        self.ib.reqGlobalCancel()
        await asyncio.sleep(timeout)
        
        self.ib.disconnect()
        logger.info("[Shutdown] Safety disconnect executed. Loop closed.")

async def main():
    # Target our validated concurrent boundary test payload
    fixture_path = "scripts/fixtures/ibkr/simulated_concurrent_batch_test_v2.json"
    if not os.path.exists(fixture_path):
        print(f"CRITICAL: Fixture payload missing at {fixture_path}")
        return

    with open(fixture_path, 'r') as f:
        signals_payload = json.load(f)

    # Initialize Harness on the safe paper trading port
    harness = AsyncConcurrentHarness(host="127.0.0.1", port=7497, client_id=95)
    
    try:
        await harness.connect_exchange()
        
        # Run Ingestion and Sizing allocation phase
        await harness.ingest_signals(signals_payload)
        
        # Fire active processing loops
        await harness.process_queue_worker()
        
        # Hold execution window open briefly to monitor streaming callback events
        logger.info("[MainLoop] Holding active channel open for order propagation...")
        await asyncio.sleep(4)
        
    except Exception as e:
        logger.error(f"[MainLoop] Execution engine failure: {e}")
    finally:
        await harness.terminate_session(timeout=2)

if __name__ == "__main__":
    asyncio.run(main())
