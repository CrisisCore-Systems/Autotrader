"""
Interactive Brokers Adapter
===========================

IBKR integration for equities, options, futures, and forex.

Features:
- TWS/Gateway connection
- Contract creation (STK/OPT/FUT/FX)
- Order routing
- Position tracking
- Real-time fills via callbacks

Dependencies:
    pip install ibapi

Example
-------
>>> from autotrader.execution.adapters.ibkr import IBKRAdapter
>>> 
>>> adapter = IBKRAdapter(
...     host='127.0.0.1',
...     port=7497,  # Paper trading
...     client_id=1
... )
>>> 
>>> await adapter.connect()
>>> order = await adapter.submit_order(order)
"""

from typing import Optional, Dict, List, Callable, Tuple, Set, Any
from datetime import datetime
import asyncio
import threading
import random
from enum import Enum, auto
from pathlib import Path
import time
import os
import json
import hmac
import hashlib
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder
from ibapi.common import OrderId
from autotrader.execution.adapters import (
    BaseBrokerAdapter,
    Order,
    Fill,
    Position,
    OrderType,
    OrderSide,
    OrderStatus,
    BrokerConfig
)


class ConnState(Enum):
    DISCONNECTED = auto()
    CONNECTING = auto()
    HANDSHAKE_SYNC = auto()
    CONNECTED = auto()
    RECONNECTING = auto()
    FAILED = auto()


IBKR_INFO_ONLY_CODES = {2104, 2106, 2158}
IBKR_INFRA_FAULT_CODES = {2103, 2105, 2107}
IBKR_NON_TERMINAL_ORDER_WARNING_CODES = {399}
IBKR_CANCEL_NOTICE_CODES = {202}


class _AdapterStateWALEngine:
    """Lightweight append-only WAL with checksum validation and tail repair."""

    def __init__(self, filepath: Path, secret_key: str = "adapter_secure_salt"):
        self.filepath = filepath
        self.secret_key = secret_key.encode("utf-8")
        self.current_sequence = 0
        self._lock = threading.Lock()
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def _calculate_checksum(self, payload: Dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True)
        return hmac.new(self.secret_key, serialized.encode("utf-8"), hashlib.sha256).hexdigest()

    def append_state_transition(
        self,
        order_id: int,
        signal_id: str,
        prev_status: str,
        new_status: str,
        filled: float,
        remaining: float,
    ) -> None:
        with self._lock:
            self.current_sequence += 1
            record = {
                "seq": self.current_sequence,
                "order_id": int(order_id),
                "signal_id": signal_id,
                "prev_status": prev_status,
                "new_status": new_status,
                "filled": float(filled),
                "remaining": float(remaining),
                "ts_ms": int(time.time() * 1000),
            }
            record["checksum"] = self._calculate_checksum(record)
            line = json.dumps(record) + "\n"

            fd = os.open(str(self.filepath), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line.encode("utf-8"))
                if hasattr(os, "fdatasync"):
                    os.fdatasync(fd)
                else:
                    os.fsync(fd)
            finally:
                os.close(fd)

    def rehydrate_and_repair(self) -> Tuple[Dict[int, Dict[str, Any]], bool]:
        trackers: Dict[int, Dict[str, Any]] = {}
        valid_lines: List[bytes] = []
        corrupted_tail = False

        if not self.filepath.exists():
            return trackers, False

        with self.filepath.open("rb") as handle:
            lines = handle.readlines()

        highest_seq = 0
        for idx, raw in enumerate(lines):
            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                continue

            try:
                record = json.loads(text)
                supplied = record.pop("checksum", None)
                expected = self._calculate_checksum(record)
                if supplied != expected:
                    raise ValueError("checksum mismatch")

                order_id = int(record["order_id"])
                trackers[order_id] = {
                    "signal_id": record["signal_id"],
                    "status": record["new_status"],
                    "filled": float(record["filled"]),
                    "remaining": float(record["remaining"]),
                    "last_seq": int(record["seq"]),
                }
                highest_seq = max(highest_seq, int(record["seq"]))
                valid_lines.append(raw)
            except Exception:
                if idx == len(lines) - 1:
                    corrupted_tail = True
                else:
                    raise SystemError("Mid-WAL corruption detected")

        self.current_sequence = highest_seq

        if corrupted_tail:
            with self.filepath.open("wb") as handle:
                for valid in valid_lines:
                    handle.write(valid)

        return trackers, corrupted_tail


class _AdapterTelemetryArchiver:
    """Append-only telemetry exporter with raw timestamps + derived latencies."""

    def __init__(self, export_path: Path):
        self.export_path = export_path
        self._lock = threading.Lock()
        self.export_path.parent.mkdir(parents=True, exist_ok=True)

    def compile_and_export(
        self,
        lifecycle_history: Dict[str, Any],
        terminal_status: str,
        failure_reason: Optional[str] = None,
    ) -> None:
        ts_ingested = lifecycle_history.get("ts_ingested", 0)
        ts_dispatched = lifecycle_history.get("ts_dispatched", 0)
        ts_first_partial = lifecycle_history.get("ts_first_partial_fill", 0)
        ts_final = lifecycle_history.get("ts_final_settlement", 0)

        latency_ingest_to_dispatch = max(0, ts_dispatched - ts_ingested) if ts_dispatched and ts_ingested else 0
        if ts_first_partial and ts_dispatched:
            latency_dispatch_to_first_partial = max(0, ts_first_partial - ts_dispatched)
            latency_first_partial_to_final = max(0, ts_final - ts_first_partial) if ts_final else 0
        else:
            latency_dispatch_to_first_partial = 0
            latency_first_partial_to_final = 0
        latency_end_to_end = max(0, ts_final - ts_ingested) if ts_final and ts_ingested else 0

        total_qty = float(lifecycle_history.get("total_quantity", 0.0))
        filled_qty = float(lifecycle_history.get("filled_quantity", 0.0))
        avg_price = float(lifecycle_history.get("avg_fill_price", 0.0))
        total_notional = round(filled_qty * avg_price, 4)
        completion_ratio = round(filled_qty / total_qty, 4) if total_qty > 0 else 0.0

        record = {
            "identity": {
                "order_id": lifecycle_history.get("order_id"),
                "signal_id": lifecycle_history.get("signal_id"),
                "symbol": lifecycle_history.get("symbol"),
                "side": lifecycle_history.get("side"),
            },
            "pricing_metrics": {
                "total_quantity": total_qty,
                "avg_fill_price": avg_price,
                "total_notional": total_notional,
            },
            "lifecycle_timestamps": {
                "ts_ingested": ts_ingested,
                "ts_dispatched": ts_dispatched,
                "ts_first_partial_fill": ts_first_partial,
                "ts_final_settlement": ts_final,
            },
            "derived_latencies_ms": {
                "latency_ingest_to_dispatch": latency_ingest_to_dispatch,
                "latency_dispatch_to_first_partial": latency_dispatch_to_first_partial,
                "latency_first_partial_to_final": latency_first_partial_to_final,
                "latency_end_to_end": latency_end_to_end,
            },
            "terminal_summary": {
                "terminal_status": terminal_status,
                "completion_ratio": completion_ratio,
                "failure_reason": failure_reason or "N/A",
            },
            "audit_metadata": {
                "exported_at": int(time.time() * 1000),
                "source_module": "IBKR-ADAPTER",
                "schema_version": "1.0.0",
            },
        }

        line = json.dumps(record) + "\n"
        with self._lock:
            with self.export_path.open("a", encoding="utf-8") as handle:
                handle.write(line)


class IBKRAdapter(EWrapper, EClient, BaseBrokerAdapter):
    """
    Interactive Brokers adapter.
    
    Implements both EWrapper (callbacks) and EClient (requests).
    
    Parameters
    ----------
    host : str
        TWS/Gateway host (default '127.0.0.1')
    port : int
        TWS/Gateway port (7497 for paper, 7496 for live)
    client_id : int
        Client ID (1-32)
    config : BrokerConfig, optional
        Configuration
    
    Example
    -------
    >>> adapter = IBKRAdapter(
    ...     host='127.0.0.1',
    ...     port=7497,
    ...     client_id=1
    ... )
    >>> 
    >>> await adapter.connect()
    >>> 
    >>> # Create order
    >>> order = Order(
    ...     order_id="",
    ...     symbol="AAPL",
    ...     side=OrderSide.BUY,
    ...     order_type=OrderType.LIMIT,
    ...     quantity=100,
    ...     price=150.0
    ... )
    >>> 
    >>> order = await adapter.submit_order(order)
    """
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 7497,
        client_id: int = 1,
        config: Optional[BrokerConfig] = None
    ):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        
        self.host = host
        self.port = port
        self.client_id = client_id
        self.config = config or BrokerConfig(name="IBKR")
        
        # State
        self.connected_flag = False
        self.next_order_id: Optional[int] = None
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.ib_to_our_order: Dict[int, str] = {}  # IB order ID -> our order ID
        self.positions_dict: Dict[str, Position] = {}
        self.fill_callbacks: List[Callable] = []
        
        # Threading
        self.thread: Optional[threading.Thread] = None
        self.connection_event = asyncio.Event()
        self.account_summary_event = asyncio.Event()
        self.account_summary: Dict[str, float] = {}

        # Resilience / handshake gate state (Phase 3 integration)
        self._connect_loop: Optional[asyncio.AbstractEventLoop] = None
        self._handshake_complete_event = asyncio.Event()
        self._active_faults: Set[int] = set()
        self._conn_state = ConnState.DISCONNECTED
        self._connect_retry_attempt = 0
        self._connect_max_retries = 5
        self._connect_backoff_base = 1.0
        self._connect_backoff_max = 30.0
        self._handshake_min_observation_seconds = 0.35

        # Vector B/C runtime middleware
        self._project_root = Path(__file__).resolve().parents[3]
        wal_path = self._project_root / "reports" / "ibkr" / "adapter_state_journal.wal"
        telemetry_path = self._project_root / "reports" / "ibkr" / "execution_performance.jsonl"
        self.wal_engine = _AdapterStateWALEngine(wal_path)
        self.telemetry_archiver = _AdapterTelemetryArchiver(telemetry_path)
        self._telemetry_lifecycle: Dict[str, Dict[str, Any]] = {}
        self._telemetry_exported: Set[str] = set()

        # Best-effort WAL recovery to continue sequence after restarts/crashes.
        try:
            self._rehydrated_state, repaired = self.wal_engine.rehydrate_and_repair()
            if repaired:
                print("🛡️ IBKR adapter WAL tail repaired during startup")
        except Exception as exc:
            self._rehydrated_state = {}
            print(f"⚠️ IBKR adapter WAL rehydration failed: {exc}")
    
    # EWrapper callbacks
    
    def nextValidId(self, orderId: OrderId):
        """
        Callback: Next valid order ID.
        
        Called after connection is established.
        
        Parameters
        ----------
        orderId : int
            Next valid order ID
        """
        self.next_order_id = orderId
        self.connected_flag = True
        self.connection_event.set()
        print(f"✅ Connected to IBKR - next order ID: {orderId}")
    
    def orderStatus(
        self,
        orderId: OrderId,
        status: str,
        filled: float,
        remaining: float,
        avgFillPrice: float,
        permId: int,
        parentId: int,
        lastFillPrice: float,
        clientId: int,
        whyHeld: str,
        mktCapPrice: float
    ):
        """
        Callback: Order status update.
        
        Parameters
        ----------
        orderId : int
            IB order ID
        status : str
            Order status (Submitted, Filled, Cancelled, etc.)
        filled : float
            Filled quantity
        remaining : float
            Remaining quantity
        avgFillPrice : float
            Average fill price
        """
        # Find our order
        our_order_id = self.ib_to_our_order.get(orderId)
        if not our_order_id:
            return
        
        order = self.orders.get(our_order_id)
        if not order:
            return

        previous_status = self._status_label(order.status)
        
        # Update status
        order.status = self._map_ib_status(status)
        if float(filled) > 0 and float(remaining) > 0:
            order.status = OrderStatus.PARTIAL_FILL
        order.filled_quantity = filled
        order.avg_fill_price = avgFillPrice
        
        # Update timestamps
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
            order.filled_at = datetime.now()

        self._record_runtime_transition(
            order=order,
            previous_status=previous_status,
            new_status=order.status,
            filled=float(filled),
            remaining=float(remaining),
        )
        
        print(f"📊 Order {orderId} status: {status} - filled: {filled}/{order.quantity}")
    
    def execDetails(self, reqId: int, contract: Contract, execution):
        """
        Callback: Execution details (fill).
        
        Parameters
        ----------
        reqId : int
            Request ID
        contract : Contract
            Contract
        execution : Execution
            Execution details
        """
        # Find our order
        ib_order_id = execution.orderId
        our_order_id = self.ib_to_our_order.get(ib_order_id)
        
        if not our_order_id:
            return
        
        order = self.orders.get(our_order_id)
        if not order:
            return

        self._mark_first_partial_if_needed(order, float(execution.shares))
        
        # Create Fill
        fill = Fill(
            order_id=our_order_id,
            symbol=contract.symbol,
            side=OrderSide.BUY if execution.side == 'BOT' else OrderSide.SELL,
            quantity=execution.shares,
            price=execution.price,
            commission=0.0,  # Will be updated in commissionReport
            timestamp=datetime.strptime(execution.time, '%Y%m%d  %H:%M:%S'),
            execution_id=execution.execId,
            metadata={
                'ib_order_id': ib_order_id,
                'ib_exec_id': execution.execId,
                'exchange': execution.exchange
            }
        )
        
        # Notify callbacks
        self._notify_fills(fill)
        
        print(f"✅ Fill: {contract.symbol} {execution.shares} @ {execution.price}")
    
    def commissionReport(self, commissionReport):
        """
        Callback: Commission report.
        
        Parameters
        ----------
        commissionReport : CommissionReport
            Commission details
        """
        # Find the latest fill for this execution
        exec_id = commissionReport.execId
        commission = commissionReport.commission
        
        # Update order commission
        for order in self.orders.values():
            if order.commission is None:
                order.commission = 0.0
            order.commission += commission
        
        print(f"💰 Commission: ${commission:.2f} for execution {exec_id}")
    
    def position(self, account: str, contract: Contract, position: float, avgCost: float):
        """
        Callback: Position update.
        
        Parameters
        ----------
        account : str
            Account ID
        contract : Contract
            Contract
        position : float
            Position size (positive=long, negative=short)
        avgCost : float
            Average cost
        """
        if position != 0:
            self.positions_dict[contract.symbol] = Position(
                symbol=contract.symbol,
                quantity=position,
                avg_entry_price=avgCost,
                current_price=0.0,  # Would need market data
                unrealized_pnl=0.0,  # Would need market data
                realized_pnl=0.0
            )
    
    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = ""):
        """
        Callback: Error.
        
        Parameters
        ----------
        reqId : int
            Request ID
        errorCode : int
            Error code
        errorString : str
            Error message
        """
        # Informational-only messages
        if errorCode in IBKR_INFO_ONLY_CODES:
            return

        # Farm degradation signals: keep transport up but block handshake clearance
        if errorCode in IBKR_INFRA_FAULT_CODES:
            self._active_faults.add(errorCode)
            print(f"⚠️ IBKR infra warning {errorCode}: {errorString}")
            return

        # Hard transport loss - force reconnect state and clear handshake gate
        if errorCode == 1100:
            self._transition_conn_state(ConnState.RECONNECTING)
            self._clear_handshake_event_threadsafe()
            print(f"🚨 IBKR transport loss {errorCode}: {errorString}")
            return

        # Connectivity restored notice
        if errorCode == 1101:
            print(f"♻️ IBKR transport restored {errorCode}: {errorString}")
            return

        if errorCode in IBKR_NON_TERMINAL_ORDER_WARNING_CODES:
            print(f"⚠️ IBKR order warning {errorCode}: {errorString}")
            return

        if errorCode in IBKR_CANCEL_NOTICE_CODES and reqId in self.ib_to_our_order:
            our_order_id = self.ib_to_our_order[reqId]
            order = self.orders.get(our_order_id)
            if order:
                if order.status != OrderStatus.CANCELLED:
                    previous_status = self._status_label(order.status)
                    order.status = OrderStatus.CANCELLED
                    order.filled_at = datetime.now()
                    self._record_runtime_transition(
                        order=order,
                        previous_status=previous_status,
                        new_status=OrderStatus.CANCELLED,
                        filled=float(order.filled_quantity),
                        remaining=float(max(0.0, order.remaining_quantity())),
                        failure_reason=f"IBKR cancel notice {errorCode}: {errorString}",
                    )
                print(f"ℹ️ IBKR cancel notice {errorCode}: {errorString}")
                return
        
        print(f"⚠️ IBKR Error {errorCode}: {errorString}")
        
        # Check if this is an order error
        if reqId in self.ib_to_our_order:
            our_order_id = self.ib_to_our_order[reqId]
            order = self.orders.get(our_order_id)
            if order:
                previous_status = self._status_label(order.status)
                order.status = OrderStatus.REJECTED
                order.filled_at = datetime.now()
                self._record_runtime_transition(
                    order=order,
                    previous_status=previous_status,
                    new_status=OrderStatus.REJECTED,
                    filled=float(order.filled_quantity),
                    remaining=float(max(0.0, order.remaining_quantity())),
                    failure_reason=f"IBKR error {errorCode}: {errorString}",
                )

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str):
        """Callback: Account summary value."""
        try:
            if tag in {"NetLiquidation", "TotalCashValue", "AvailableFunds"}:
                key = currency.upper()
                self.account_summary[key] = float(value)
        except Exception:
            return

    def accountSummaryEnd(self, reqId: int):
        """Callback: Account summary stream complete."""
        self.account_summary_event.set()
    
    def _map_ib_status(self, ib_status: str) -> OrderStatus:
        """
        Map IB order status to OrderStatus enum.
        
        IB statuses:
        - PendingSubmit: About to submit
        - PendingCancel: About to cancel
        - PreSubmitted: Submitted to IB system
        - Submitted: Submitted to exchange
        - Cancelled: Cancelled
        - Filled: Fully filled
        - Inactive: Order inactive
        
        Parameters
        ----------
        ib_status : str
            IB status
        
        Returns
        -------
        status : OrderStatus
        """
        mapping = {
            'PendingSubmit': OrderStatus.PENDING,
            'PendingCancel': OrderStatus.SUBMITTED,
            'PreSubmitted': OrderStatus.SUBMITTED,
            'Submitted': OrderStatus.SUBMITTED,
            'Cancelled': OrderStatus.CANCELLED,
            'Filled': OrderStatus.FILLED,
            'Inactive': OrderStatus.CANCELLED
        }
        
        return mapping.get(ib_status, OrderStatus.PENDING)
    
    # BaseBrokerAdapter implementation
    
    async def connect(self) -> bool:
        """
        Connect to TWS/Gateway.
        
        Returns
        -------
        success : bool
            True if connected
        """
        self._connect_loop = asyncio.get_running_loop()
        self._connect_retry_attempt = 0

        while self._connect_retry_attempt < self._connect_max_retries:
            self._transition_conn_state(ConnState.CONNECTING)
            self.connection_event.clear()
            self._handshake_complete_event.clear()
            self._active_faults.clear()

            try:
                # Start connection
                EClient.connect(self, self.host, self.port, self.client_id)

                # Start thread to run message loop
                if self.thread is None or not self.thread.is_alive():
                    self.thread = threading.Thread(target=EClient.run, args=(self,), daemon=True)
                    self.thread.start()

                # Wait for transport readiness (nextValidId callback)
                await asyncio.wait_for(self.connection_event.wait(), timeout=10.0)

                # Handshake sync gate
                self._transition_conn_state(ConnState.HANDSHAKE_SYNC)
                gate_ok = await self._wait_for_handshake_gate(timeout=2.0)
                if not gate_ok:
                    raise ConnectionError("Handshake gate failed due to active infrastructure faults")

                self._transition_conn_state(ConnState.CONNECTED)
                self._connect_retry_attempt = 0

                # Request positions
                self.reqPositions()
                return True

            except Exception as e:
                self._connect_retry_attempt += 1
                print(f"⚠️ IBKR connection attempt failed: {e}")

                if self._connect_retry_attempt >= self._connect_max_retries:
                    break

                self._transition_conn_state(ConnState.RECONNECTING)
                backoff_s = self._calculate_backoff_seconds(self._connect_retry_attempt)
                await asyncio.sleep(backoff_s)

        self._transition_conn_state(ConnState.FAILED)
        print("❌ IBKR connection failed after retry budget exhaustion")
        return False

    def _transition_conn_state(self, new_state: "ConnState") -> None:
        if self._conn_state != new_state:
            print(f"🔄 IBKR connection state: {self._conn_state.name} -> {new_state.name}")
            self._conn_state = new_state

    def _calculate_backoff_seconds(self, attempt: int) -> float:
        # Full jitter: random(0, min(max_delay, base * 2^attempt))
        upper = min(self._connect_backoff_max, self._connect_backoff_base * (2 ** attempt))
        delay = random.uniform(0.0, upper)
        print(f"⏳ IBKR reconnect backoff: {delay:.2f}s")
        return delay

    async def _wait_for_handshake_gate(self, timeout: float) -> bool:
        start = asyncio.get_running_loop().time()
        while (asyncio.get_running_loop().time() - start) < timeout:
            elapsed = asyncio.get_running_loop().time() - start
            if self._conn_state == ConnState.RECONNECTING:
                return False

            if (
                elapsed >= self._handshake_min_observation_seconds
                and len(self._active_faults) == 0
                and self._conn_state == ConnState.HANDSHAKE_SYNC
            ):
                self._handshake_complete_event.set()

            if self._handshake_complete_event.is_set():
                return True

            await asyncio.sleep(0.1)

        return False

    def _clear_handshake_event_threadsafe(self) -> None:
        if self._connect_loop and self._connect_loop.is_running():
            self._connect_loop.call_soon_threadsafe(self._handshake_complete_event.clear)
        else:
            self._handshake_complete_event.clear()

    def _status_label(self, status: OrderStatus) -> str:
        return status.name.title().replace("_", "")

    def _mark_first_partial_if_needed(self, order: Order, exec_shares: float) -> None:
        lifecycle = self._telemetry_lifecycle.get(order.order_id)
        if not lifecycle:
            return
        if lifecycle.get("ts_first_partial_fill"):
            return
        if exec_shares <= 0:
            return
        if float(order.filled_quantity) < float(order.quantity):
            lifecycle["ts_first_partial_fill"] = int(time.time() * 1000)

    def _record_runtime_transition(
        self,
        order: Order,
        previous_status: str,
        new_status: OrderStatus,
        filled: float,
        remaining: float,
        failure_reason: Optional[str] = None,
    ) -> None:
        signal_id = str((order.metadata or {}).get("signal_id", f"ibkr-{order.order_id}"))
        new_label = self._status_label(new_status)

        # Vector B: WAL mutation logging
        self.wal_engine.append_state_transition(
            order_id=int(order.order_id),
            signal_id=signal_id,
            prev_status=previous_status,
            new_status=new_label,
            filled=float(filled),
            remaining=float(remaining),
        )

        # Keep lifecycle history up to date for telemetry export.
        lifecycle = self._telemetry_lifecycle.setdefault(
            order.order_id,
            {
                "order_id": int(order.order_id),
                "signal_id": signal_id,
                "symbol": order.symbol,
                "side": order.side.value.upper(),
                "total_quantity": float(order.quantity),
                "filled_quantity": float(filled),
                "avg_fill_price": float(order.avg_fill_price),
                "ts_ingested": int((order.metadata or {}).get("ts_ingested", int(time.time() * 1000))),
                "ts_dispatched": int((order.submitted_at.timestamp() * 1000) if order.submitted_at else int(time.time() * 1000)),
                "ts_first_partial_fill": None,
                "ts_final_settlement": None,
            },
        )
        lifecycle["filled_quantity"] = float(filled)
        lifecycle["avg_fill_price"] = float(order.avg_fill_price)

        if new_status == OrderStatus.PARTIAL_FILL and not lifecycle.get("ts_first_partial_fill"):
            lifecycle["ts_first_partial_fill"] = int(time.time() * 1000)

        terminal = new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
        if terminal and order.order_id not in self._telemetry_exported:
            lifecycle["ts_final_settlement"] = int(time.time() * 1000)
            self.telemetry_archiver.compile_and_export(
                lifecycle_history=lifecycle,
                terminal_status=new_label,
                failure_reason=failure_reason,
            )
            self._telemetry_exported.add(order.order_id)
    
    def disconnect(self):
        """Disconnect from TWS/Gateway.

        This is intentionally synchronous because ibapi internally calls
        self.disconnect() from synchronous paths.
        """
        EClient.disconnect(self)
        self.connected_flag = False
        print("✅ Disconnected from IBKR")
    
    def _create_contract(
        self,
        symbol: str,
        sec_type: str = 'STK',
        exchange: str = 'SMART',
        currency: str = 'USD'
    ) -> Contract:
        """
        Create IB Contract.
        
        Parameters
        ----------
        symbol : str
            Symbol
        sec_type : str
            Security type (STK/OPT/FUT/FX)
        exchange : str
            Exchange (SMART for stocks)
        currency : str
            Currency
        
        Returns
        -------
        contract : Contract
        """
        normalized = str(symbol).upper().replace("-", "/")
        base_symbol = normalized
        base_currency = currency
        if "/" in normalized:
            base_symbol, base_currency = normalized.split("/", 1)

        contract = Contract()
        contract.symbol = base_symbol
        contract.secType = sec_type
        contract.exchange = exchange
        contract.currency = base_currency
        
        return contract

    def _resolve_contract_params(self, order: Order) -> Tuple[str, str, str, str]:
        """Resolve IBKR contract parameters from order metadata or defaults."""
        metadata = order.metadata or {}
        symbol = str(metadata.get("ibkr_symbol") or order.symbol)
        sec_type = str(metadata.get("ibkr_sec_type") or "STK").upper()
        exchange = str(metadata.get("ibkr_exchange") or "SMART").upper()
        currency = str(metadata.get("ibkr_currency") or "USD").upper()
        return symbol, sec_type, exchange, currency

    def _validate_order_quantity_for_contract(self, order: Order, sec_type: str) -> None:
        """Reject quantities that are invalid for the resolved IBKR contract type."""
        quantity = float(order.quantity)
        if sec_type == "STK" and abs(quantity - round(quantity)) > 1e-9:
            raise ValueError(
                f"IBKR {sec_type} orders require whole-share quantity; got {quantity}."
            )
    
    def _create_ib_order(self, order: Order) -> IBOrder:
        """
        Convert Order to IB Order.
        
        Parameters
        ----------
        order : Order
            Our order
        
        Returns
        -------
        ib_order : IBOrder
            IB order
        """
        ib_order = IBOrder()
        
        # Action
        ib_order.action = 'BUY' if order.side == OrderSide.BUY else 'SELL'
        
        # Quantity
        ib_order.totalQuantity = order.quantity
        
        # Order type
        if order.order_type == OrderType.MARKET:
            ib_order.orderType = 'MKT'
        elif order.order_type == OrderType.LIMIT:
            ib_order.orderType = 'LMT'
            ib_order.lmtPrice = order.price
        elif order.order_type == OrderType.STOP:
            ib_order.orderType = 'STP'
            ib_order.auxPrice = order.stop_price
        elif order.order_type == OrderType.STOP_LIMIT:
            ib_order.orderType = 'STP LMT'
            ib_order.lmtPrice = order.price
            ib_order.auxPrice = order.stop_price
        elif order.order_type == OrderType.IOC:
            ib_order.orderType = 'LMT'
            ib_order.lmtPrice = order.price
            ib_order.tif = 'IOC'
        elif order.order_type == OrderType.FOK:
            ib_order.orderType = 'LMT'
            ib_order.lmtPrice = order.price
            ib_order.tif = 'FOK'

        tif_value = str(order.time_in_force or "").upper()
        if tif_value in {"DAY", "GTC", "IOC", "FOK"}:
            ib_order.tif = tif_value

        # Safety control: non-transmitting order path for dry-run style probes.
        ib_order.transmit = bool(order.metadata.get("ibkr_transmit", True))
        
        return ib_order

    def _sanitize_ibkr_order(self, order: IBOrder) -> None:
        """Clear deprecated IBKR fields that can trigger warnings on newer APIs."""
        for attr in ("eTradeOnly", "firmQuoteOnly"):
            if hasattr(order, attr):
                setattr(order, attr, "")

    def _cancel_order_compat(self, order_id: int) -> None:
        """Call cancelOrder with API-version-compatible signatures."""
        try:
            self.cancelOrder(order_id)
            return
        except TypeError as first_error:
            try:
                self.cancelOrder(order_id, "")
                return
            except TypeError:
                raise first_error
    
    async def submit_order(self, order: Order) -> Order:
        """
        Submit order to IBKR.
        
        Parameters
        ----------
        order : Order
            Order to submit
        
        Returns
        -------
        order : Order
            Order with IB order ID
        """
        if not self.connected_flag or self.next_order_id is None:
            raise RuntimeError("Not connected to IBKR")
        
        try:
            # Get next order ID
            ib_order_id = self.next_order_id
            self.next_order_id += 1
            
            # Create contract
            symbol, sec_type, exchange, currency = self._resolve_contract_params(order)
            self._validate_order_quantity_for_contract(order, sec_type)
            contract = self._create_contract(
                symbol=symbol,
                sec_type=sec_type,
                exchange=exchange,
                currency=currency,
            )
            
            # Create IB order
            ib_order = self._create_ib_order(order)
            self._sanitize_ibkr_order(ib_order)
            
            # Place order
            self.placeOrder(ib_order_id, contract, ib_order)
            
            # Update our order
            order.order_id = str(ib_order_id)
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now()

            now_ms = int(time.time() * 1000)
            ts_ingested = int(order.metadata.get("ts_ingested", now_ms))
            self._telemetry_lifecycle[order.order_id] = {
                "order_id": int(order.order_id),
                "signal_id": str(order.metadata.get("signal_id", f"ibkr-{order.order_id}")),
                "symbol": order.symbol,
                "side": order.side.value.upper(),
                "total_quantity": float(order.quantity),
                "filled_quantity": float(order.filled_quantity),
                "avg_fill_price": float(order.avg_fill_price),
                "ts_ingested": ts_ingested,
                "ts_dispatched": now_ms,
                "ts_first_partial_fill": None,
                "ts_final_settlement": None,
            }
            
            # Store mapping
            self.orders[order.order_id] = order
            self.ib_to_our_order[ib_order_id] = order.order_id
            
            print(f"✅ Order submitted: {order.order_id} - {order.symbol} {order.side.value} {order.quantity}")
            
            return order
        
        except Exception as e:
            print(f"❌ Order submission error: {e}")
            order.status = OrderStatus.REJECTED
            raise
    
    async def cancel_order(self, order_id: str) -> bool:
        """
        Cancel order.
        
        Parameters
        ----------
        order_id : str
            Order ID
        
        Returns
        -------
        success : bool
        """
        try:
            ib_order_id = int(order_id)
            
            order = self.orders.get(order_id)
            if order and not bool((order.metadata or {}).get("ibkr_transmit", True)):
                previous_status = self._status_label(order.status)
                order.status = OrderStatus.CANCELLED
                order.filled_at = datetime.now()
                self._record_runtime_transition(
                    order=order,
                    previous_status=previous_status,
                    new_status=OrderStatus.CANCELLED,
                    filled=float(order.filled_quantity),
                    remaining=float(max(0.0, order.remaining_quantity())),
                    failure_reason="Local cancel issued for non-transmitting order",
                )
                print(f"✅ Order cancelled locally (non-transmitting): {order_id}")
                return True

            self._cancel_order_compat(ib_order_id)

            if order:
                previous_status = self._status_label(order.status)
                order.status = OrderStatus.CANCELLED
                order.filled_at = datetime.now()
                self._record_runtime_transition(
                    order=order,
                    previous_status=previous_status,
                    new_status=OrderStatus.CANCELLED,
                    filled=float(order.filled_quantity),
                    remaining=float(max(0.0, order.remaining_quantity())),
                    failure_reason="Local cancel request submitted to IBKR",
                )
            
            print(f"✅ Order cancelled: {order_id}")
            return True
        
        except Exception as e:
            print(f"❌ Cancel error: {e}")
            return False
    
    async def modify_order(
        self,
        order_id: str,
        quantity: Optional[float] = None,
        price: Optional[float] = None
    ) -> Order:
        """
        Modify order.
        
        IBKR supports order modification.
        
        Parameters
        ----------
        order_id : str
            Order ID
        quantity : float, optional
            New quantity
        price : float, optional
            New price
        
        Returns
        -------
        order : Order
            Modified order
        """
        # Get original order
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        # Update order
        if quantity is not None:
            order.quantity = quantity
        if price is not None:
            order.price = price
        
        # Create contract
        symbol, sec_type, exchange, currency = self._resolve_contract_params(order)
        self._validate_order_quantity_for_contract(order, sec_type)
        contract = self._create_contract(
            symbol=symbol,
            sec_type=sec_type,
            exchange=exchange,
            currency=currency,
        )
        
        # Create IB order with updated params
        ib_order = self._create_ib_order(order)
        self._sanitize_ibkr_order(ib_order)
        
        # Place modified order (same order ID)
        ib_order_id = int(order_id)
        self.placeOrder(ib_order_id, contract, ib_order)
        
        print(f"✅ Order modified: {order_id}")
        
        return order
    
    async def get_order_status(self, order_id: str) -> Order:
        """
        Get order status.
        
        Parameters
        ----------
        order_id : str
            Order ID
        
        Returns
        -------
        order : Order
        """
        order = self.orders.get(order_id)
        if not order:
            raise ValueError(f"Order not found: {order_id}")
        
        # Request order status (will trigger orderStatus callback)
        self.reqOpenOrders()
        
        # Wait briefly for callback
        await asyncio.sleep(0.5)
        
        return order
    
    async def get_positions(self) -> List[Position]:
        """
        Get current positions.
        
        Returns
        -------
        positions : list of Position
        """
        # Request positions (will trigger position callback)
        self.reqPositions()
        
        # Wait briefly for callbacks
        await asyncio.sleep(0.5)
        
        return list(self.positions_dict.values())
    
    async def get_account_balance(self) -> Dict:
        """
        Get account balance.
        
        Returns
        -------
        balance : dict
        """
        if not self.connected_flag:
            return {}

        req_id = 9001
        self.account_summary_event.clear()
        self.account_summary = {}

        self.reqAccountSummary(req_id, "All", "NetLiquidation,TotalCashValue,AvailableFunds")

        try:
            await asyncio.wait_for(self.account_summary_event.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        finally:
            self.cancelAccountSummary(req_id)

        return dict(self.account_summary)
    
    def subscribe_fills(self, callback: Callable):
        """
        Subscribe to fill notifications.
        
        Parameters
        ----------
        callback : callable
            Function(fill) called on each fill
        """
        self.fill_callbacks.append(callback)
