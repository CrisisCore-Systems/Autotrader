#!/usr/bin/env python3
"""
TR-004-MOCK: Concurrent Harness Simulation Suite (Level 3 - Self Auditing)
Validates thread-isolated callback demultiplexing with strict assertion guards.
"""

import os
import json
import asyncio
import logging
import sys
from typing import Dict, Any, List

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TR-004-Mock-CI")


class MockTrade:
    def __init__(self, order_id: int, action: str, total_quantity: float, limit_price: float):
        self.order = type('Order', (), {'orderId': order_id, 'action': action})()
        self.orderStatus = type('OrderStatus', (), {'status': 'PendingSubmit', 'filled': 0.0, 'remaining': total_quantity})()


class MockIB:
    def __init__(self):
        self.orderStatusEvent = []
        self.next_order_id = 1001

    async def connectAsync(self, host: str, port: int, clientId: int):
        await asyncio.sleep(0.01)
        logger.info("📡 [MockExchange] Synthetic Connection Established.")

    async def qualifyContractsAsync(self, contract):
        await asyncio.sleep(0.001)

    def placeOrder(self, contract, order) -> MockTrade:
        order.orderId = self.next_order_id
        trade = MockTrade(order.orderId, order.action, order.totalQuantity, order.lmtPrice)
        self.next_order_id += 1
        asyncio.create_task(self._simulate_asynchronous_lifecycle(trade, contract.symbol))
        return trade

    async def _simulate_asynchronous_lifecycle(self, trade: MockTrade, symbol: str):
        order_id = trade.order.orderId
        qty = trade.orderStatus.remaining

        # Timing Profile: (Ack Delay, Partial Delay, Final Delay)
        step_matrix = {
            1001: (0.05, 0.40, 0.80),
            1002: (0.02, 0.10, 0.30),
            1003: (0.08, 0.60, 1.20)
        }

        ack_delay, partial_delay, final_delay = step_matrix.get(order_id, (0.05, 0.30, 0.60))

        await asyncio.sleep(ack_delay)
        trade.orderStatus.status = "Submitted"
        self._trigger_status(trade)

        await asyncio.sleep(partial_delay)
        trade.orderStatus.status = "PartiallyFilled"
        trade.orderStatus.filled = qty * 0.5
        trade.orderStatus.remaining = qty * 0.5
        self._trigger_status(trade)

        await asyncio.sleep(final_delay)
        trade.orderStatus.status = "Filled"
        trade.orderStatus.filled = qty
        trade.orderStatus.remaining = 0.0
        self._trigger_status(trade)

    def _trigger_status(self, trade: MockTrade):
        for callback in self.orderStatusEvent:
            callback(trade)

    def disconnect(self):
        logger.info("⚙️ [MockExchange] Disconnected cleanly.")


class SimulatedConcurrentHarness:
    def __init__(self):
        self.ib = MockIB()
        self.signal_queue: asyncio.Queue = asyncio.Queue()
        self.max_single_notional = 5.00
        self.max_aggregate_notional = 20.00
        self.current_exposure = 0.0
        self.order_trackers: Dict[int, Dict[str, Any]] = {}

        # Chronological audit journal for automated evaluation
        self.execution_journal: List[str] = []

        self.ib.orderStatusEvent.append(self.on_order_status_update)

    def on_order_status_update(self, trade):
        order_id = trade.order.orderId
        status = trade.orderStatus.status
        filled = trade.orderStatus.filled
        remaining = trade.orderStatus.remaining

        if order_id in self.order_trackers:
            tracker = self.order_trackers[order_id]
            tracker["status"] = status
            tracker["filled"] = filled
            tracker["remaining"] = remaining

            # Log and update the validation journal entry
            journal_entry = f"{order_id}:{status}"
            self.execution_journal.append(journal_entry)

            logger.info(
                f"[OrderID-{order_id}] [CallbackRouter] State Mutated ──> "
                f"Symbol: {tracker['symbol']} | Status: {status:<15} | Filled: {filled} | Remaining: {remaining}"
            )

    async def ingest_signals(self, signals: List[Dict[str, Any]]):
        for s in signals:
            symbol = s.get("symbol")
            qty = float(s.get("quantity", 0))
            price = float(s.get("limit_price", 0))
            notional = qty * price

            if notional > self.max_single_notional:
                logger.warning(f"[Ingestion] ❌ Rejected {symbol}: Notional ${notional:.2f} breaches Single Cap (${self.max_single_notional})")
                continue

            if self.current_exposure + notional > self.max_aggregate_notional:
                logger.critical(f"[Ingestion] ⚠️ Blocked {symbol}: Aggregate exposure would hit ${self.current_exposure + notional:.2f}")
                break

            self.current_exposure += notional
            await self.signal_queue.put(s)
            logger.info(f"[Ingestion] ✅ Queued {symbol} (${notional:.2f})")

    async def process_queue_worker(self):
        while not self.signal_queue.empty():
            signal = await self.signal_queue.get()
            symbol = signal.get("symbol")

            contract = type('Stock', (), {'symbol': symbol})()
            order = type('LimitOrder', (), {
                'action': signal.get("side").upper(),
                'totalQuantity': signal.get("quantity"),
                'lmtPrice': signal.get("limit_price"),
                'orderId': 0
            })()

            trade = self.ib.placeOrder(contract, order)
            order_id = order.orderId

            self.order_trackers[order_id] = {
                "symbol": symbol,
                "status": "PendingSubmit",
                "filled": 0.0,
                "remaining": float(signal.get("quantity", 0))
            }
            self.signal_queue.task_done()

    def verify_execution_contract(self):
        """Runs automated post-flight verification on the step sequences."""
        logger.info("\n=== Running Automated Contract Assertions ===")

        # Isolate indices within the chronological journal
        try:
            idx_1002_filled = self.execution_journal.index("1002:Filled")
            idx_1001_filled = self.execution_journal.index("1001:Filled")

            logger.info(f"Verified: 1002:Filled at index {idx_1002_filled}")
            logger.info(f"Verified: 1001:Filled at index {idx_1001_filled}")

            # Enforce Invariant 1: Out-of-order race settlement validation
            assert idx_1002_filled < idx_1001_filled, "CRITICAL: FIFO ordering detected. Level 2 out-of-order execution test failed."
            logger.info("✅ Invariant 1 Pass: 1002 settled out-of-order before 1001.")

            # Enforce Invariant 2: Integrity of terminal status targets
            for oid in [1001, 1002, 1003]:
                assert self.order_trackers[oid]["status"] == "Filled", f"Order {oid} failed to reach state: Filled"
                assert self.order_trackers[oid]["remaining"] == 0.0, f"Order {oid} failed remaining check: expected 0.0"
            logger.info("✅ Invariant 2 Pass: All concurrent tracking allocations reached terminal state 'Filled'.")

            print("\nTR-004-MOCK: ALL PASS ✅")

        except (ValueError, AssertionError) as e:
            logger.error(f"❌ ARCHITECTURAL CONTRACT VIOLATED: {e}")
            sys.exit(1)


async def main():
    fixture_path = "scripts/fixtures/ibkr/simulated_concurrent_batch_test_v2.json"
    if not os.path.exists(fixture_path):
        sys.exit(f"Missing test payload target at {fixture_path}")

    with open(fixture_path, 'r') as f:
        signals_payload = json.load(f)

    harness = SimulatedConcurrentHarness()

    await harness.ib.connectAsync("127.0.0.1", 7497, clientId=99)
    await harness.ingest_signals(signals_payload)
    await harness.process_queue_worker()

    # Hold the window open to let fractured callbacks resolve completely
    await asyncio.sleep(2.5)

    harness.verify_execution_contract()
    harness.ib.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
