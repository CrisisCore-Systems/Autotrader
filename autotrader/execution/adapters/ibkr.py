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
import traceback
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
from ibapi.order import Order as IBOrder
from ibapi.common import OrderId
from autotrader.execution.telemetry import TelemetryEngine
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


class CriticalRecoveryAnomaly(RuntimeError):
    """Raised when startup WAL state cannot be reconciled with live broker state."""


def _console_log(level: str, component: str, message: str) -> None:
    print(f"[{str(level).upper()}] [{component}] {message}")


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

    def append_execution_fingerprint(
        self,
        order_id: int,
        exec_id: str,
        price: float,
        shares: float,
    ) -> int:
        with self._lock:
            self.current_sequence += 1
            seq = self.current_sequence
            ts_ms = int(time.time() * 1000)
            line = f"EXEC|{seq}|{ts_ms}|{int(order_id)}|{exec_id}|{float(price)}|{float(shares)}\n"

            fd = os.open(str(self.filepath), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line.encode("utf-8"))
                if hasattr(os, "fdatasync"):
                    os.fdatasync(fd)
                else:
                    os.fsync(fd)
            finally:
                os.close(fd)

            return seq

    def append_execution_shortfall(
        self,
        order_id: int,
        exec_id: str,
        account_id: str,
        symbol: str,
        side: str,
        execution_price: float,
        execution_size: float,
        commission: float,
        benchmark_mid: float,
        execution_mid: float,
        slippage_bps: float,
    ) -> int:
        with self._lock:
            self.current_sequence += 1
            seq = self.current_sequence
            ts_ms = int(time.time() * 1000)
            line = (
                f"SHORTFALL|{seq}|{ts_ms}|{int(order_id)}|{exec_id}|{account_id}|{symbol}|{side}|"
                f"{float(execution_price)}|{float(execution_size)}|{float(commission)}|"
                f"{float(benchmark_mid)}|{float(execution_mid)}|{float(slippage_bps)}\n"
            )

            fd = os.open(str(self.filepath), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line.encode("utf-8"))
                if hasattr(os, "fdatasync"):
                    os.fdatasync(fd)
                else:
                    os.fsync(fd)
            finally:
                os.close(fd)

            return seq

    def rehydrate_and_repair(self) -> Tuple[Dict[int, Dict[str, Any]], Set[str], bool]:
        trackers: Dict[int, Dict[str, Any]] = {}
        seen_execution_fingerprints: Set[str] = set()
        valid_lines: List[bytes] = []
        corrupted_tail = False

        if not self.filepath.exists():
            return trackers, seen_execution_fingerprints, False

        with self.filepath.open("rb") as handle:
            lines = handle.readlines()

        highest_seq = 0
        for idx, raw in enumerate(lines):
            text = raw.decode("utf-8", errors="ignore").strip()
            if not text:
                continue

            try:
                if text.startswith("EXEC|"):
                    parts = text.split("|")
                    if len(parts) != 7:
                        raise ValueError("invalid EXEC WAL row")

                    _, seq, _ts, o_id, exec_id, _price, _shares = parts
                    order_id = int(o_id)
                    fingerprint = f"{order_id}:{exec_id}"
                    seen_execution_fingerprints.add(fingerprint)
                    highest_seq = max(highest_seq, int(seq))
                    valid_lines.append(raw)
                    continue

                if text.startswith("STATE|"):
                    parts = text.split("|")
                    if len(parts) != 7:
                        raise ValueError("invalid STATE WAL row")

                    _, seq, _ts, o_id, status, filled, remaining = parts
                    order_id = int(o_id)
                    trackers[order_id] = {
                        "signal_id": f"ibkr-{order_id}",
                        "status": status,
                        "filled": float(filled),
                        "remaining": float(remaining),
                        "last_seq": int(seq),
                    }
                    highest_seq = max(highest_seq, int(seq))
                    valid_lines.append(raw)
                    continue

                if text.startswith("SHORTFALL|"):
                    parts = text.split("|")
                    if len(parts) != 14:
                        raise ValueError("invalid SHORTFALL WAL row")

                    _, seq, _ts, o_id, _exec_id, _account, _symbol, _side, _px, _qty, _commission, _bench_mid, _exec_mid, _slippage = parts
                    _ = int(o_id)
                    highest_seq = max(highest_seq, int(seq))
                    valid_lines.append(raw)
                    continue

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

        return trackers, seen_execution_fingerprints, corrupted_tail


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
        config: Optional[BrokerConfig] = None,
        default_account_id: Optional[str] = None,
    ):
        EWrapper.__init__(self)
        EClient.__init__(self, wrapper=self)
        
        self.host = host
        self.port = port
        self.client_id = client_id
        self.config = config or BrokerConfig(name="IBKR")
        self._log_dir = "logs"
        self._expected_wal_positions: Dict[str, Dict[str, float]] = {}
        self._expected_active_perm_ids: Set[int] = set()
        self._startup_expected_position_overrides_raw = str(
            os.getenv("IBKR_STARTUP_EXPECT_POSITIONS", "")
        ).strip()
        self._trust_startup_broker_snapshot = str(
            os.getenv("IBKR_TRUST_STARTUP_BROKER_SNAPSHOT", "0")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._startup_expected_position_overrides = self._parse_startup_expected_positions(
            self._startup_expected_position_overrides_raw
        )
        
        # State
        self.connected_flag = False
        self.next_order_id: Optional[int] = None
        self.orders: Dict[str, Order] = {}  # order_id -> Order
        self.ib_to_our_order: Dict[int, str] = {}  # IB order ID -> our order ID
        self.positions_dict: Dict[str, Position] = {}
        self.fill_callbacks: List[Callable] = []
        self.order_update_callbacks: List[Callable] = []
        
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
        self._default_account_id = str(
            default_account_id or os.getenv("IBKR_DEFAULT_ACCOUNT_ID", "U1234567")
        ).strip()
        self._account_states: Dict[str, Dict[str, Any]] = {}
        self._account_state_lock = threading.RLock()
        wal_path = self._project_root / "reports" / "ibkr" / "adapter_state_journal.wal"
        telemetry_path = self._project_root / "reports" / "ibkr" / "execution_performance.jsonl"
        self._last_gasp_path = self._project_root / "reports" / "ibkr" / "crash_diagnostics.json"
        self._last_gasp_lock = threading.Lock()
        self.wal_engine = _AdapterStateWALEngine(wal_path)
        self.telemetry_archiver = _AdapterTelemetryArchiver(telemetry_path)
        self._telemetry_lifecycle: Dict[str, Dict[str, Any]] = {}
        self._telemetry_exported: Set[str] = set()
        self._order_state_snapshots: Dict[int, Dict[str, Any]] = {}
        self._closed_order_ids: Set[int] = set()
        self._seen_execution_fingerprints: Set[str] = set()
        self._rehydration_complete = False

        # Option B scaffolding: reconciliation and drift interlocks.
        self._reconciliation_locks: Set[str] = set()
        self._max_drift_pct = float(os.getenv("IBKR_MAX_POSITION_DRIFT_PCT", "0.01"))
        self._reconciliation_bootstrap_pending = True
        self._reconciliation_circuit_open = False
        self._circuit_breach_symbols: Set[str] = set()
        self._portfolio_value_drift = 0.0
        self._portfolio_value_drift_limit = float(os.getenv("IBKR_MAX_PORTFOLIO_DRIFT_NOTIONAL", "500.0"))
        self._reconciliation_state = "BOOTSTRAP"
        self._reconciliation_events: List[Dict[str, Any]] = []
        self._broker_position_snapshots: Dict[str, Dict[str, float]] = {}
        self._webhook_url = str(os.getenv("TELEMETRY_WEBHOOK_URL", "")).strip()
        self._fired_breach_epochs: Set[str] = set()
        self._webhook_epoch_lock = threading.Lock()
        self._last_telemetry_heartbeat_ms = 0
        self._heartbeat_interval_ms = int(float(os.getenv("IBKR_TELEMETRY_HEARTBEAT_SECONDS", "5")) * 1000)
        self._nbbo_lock = threading.RLock()
        self._nbbo_snapshots: Dict[str, Dict[str, Any]] = {}
        self._nbbo_reqid_to_symbol: Dict[int, str] = {}
        self._nbbo_symbol_to_reqid: Dict[str, int] = {}
        self._next_nbbo_req_id = 100_000
        self._active_order_benchmarks: Dict[int, Dict[str, Any]] = {}
        self._latency_profiling_enabled = str(
            os.getenv("IBKR_LATENCY_PROFILING_ENABLED", "1")
        ).strip().lower() in {"1", "true", "yes", "on"}
        self._global_kill_active = False
        self._startup_attestation_active = False
        self._startup_live_positions: Dict[str, Dict[str, float]] = {}
        self._startup_live_open_order_ids: Set[int] = set()
        self._startup_live_open_perm_ids: Set[int] = set()
        self._startup_positions_end_event = threading.Event()
        self._startup_open_orders_end_event = threading.Event()
        self._startup_attestation_timeout_s = float(os.getenv("IBKR_STARTUP_ATTESTATION_TIMEOUT_SECONDS", "5.0"))
        self.telemetry_gateway = TelemetryEngine(
            host=str(os.getenv("IBKR_TELEMETRY_UDP_HOST", "127.0.0.1")),
            port=int(os.getenv("IBKR_TELEMETRY_UDP_PORT", "9876")),
            queue_maxsize=int(os.getenv("IBKR_TELEMETRY_QUEUE_MAXSIZE", "1000")),
        )
        self._sync_default_account_state()

        # Best-effort WAL recovery to continue sequence after restarts/crashes.
        try:
            self._rehydrated_state, seen_exec_fingerprints, repaired = self.wal_engine.rehydrate_and_repair()
            self._prime_runtime_indexes_from_wal(self._rehydrated_state, seen_exec_fingerprints)
            if repaired:
                _console_log("INFO", "IBKR.Recovery", "WAL tail repaired during startup.")
                self._emit_telemetry_event(
                    event_type="WAL_RECOVERY_ANOMALY",
                    payload={
                        "details": {
                            "reason": "wal_tail_repaired",
                            "wal_path": str(wal_path),
                        }
                    },
                )
                self._dispatch_critical_webhook(
                    alert_type="WAL_RECOVERY_ANOMALY",
                    symbol="GLOBAL",
                    payload={
                        "event_type": "WAL_RECOVERY_ANOMALY",
                        "timestamp_ms": int(time.time() * 1000),
                        "state": self._reconciliation_state,
                        "details": {
                            "reason": "wal_tail_repaired",
                            "wal_path": str(wal_path),
                        },
                    },
                )
        except Exception as exc:
            self._rehydrated_state = {}
            _console_log("WARN", "IBKR.Recovery", f"WAL rehydration failed: {exc}")
            self._write_last_gasp_envelope(exc, context="wal_rehydration")
        finally:
            self._rehydration_complete = True

    def rehydrate_and_repair(self) -> None:
        """Rebuild expected positions and active perm IDs from JSON WAL records."""
        self._expected_wal_positions = {}
        self._expected_active_perm_ids = set()

        wal_file_path = Path(self._log_dir) / "execution_wal.log"
        if not wal_file_path.exists():
            return

        with wal_file_path.open("r", encoding="utf-8") as wal_file:
            for line in wal_file:
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError:
                    continue

                record_type = record.get("type")
                if record_type == "EXEC":
                    self._process_exec_record(record)
                elif record_type == "SHORTFALL":
                    self._process_shortfall_record(record)

    def _process_exec_record(self, record: Dict[str, Any]) -> None:
        """Apply EXEC WAL record to reconstructed position and active perm IDs."""
        account_id = str(record.get("account_id", ""))
        symbol = str(record.get("symbol", ""))
        if not account_id or not symbol:
            return

        quantity = float(record.get("quantity", 0.0))
        perm_id = record.get("perm_id")

        account_positions = self._expected_wal_positions.setdefault(account_id, {})
        account_positions[symbol] = account_positions.get(symbol, 0.0) + quantity

        if perm_id is not None:
            try:
                self._expected_active_perm_ids.add(int(perm_id))
            except (TypeError, ValueError):
                pass

    def _process_shortfall_record(self, record: Dict[str, Any]) -> None:
        """Apply SHORTFALL WAL record to reconstructed position."""
        account_id = str(record.get("account_id", ""))
        symbol = str(record.get("symbol", ""))
        if not account_id or not symbol:
            return

        shortfall = float(record.get("shortfall", 0.0))
        account_positions = self._expected_wal_positions.setdefault(account_id, {})
        account_positions[symbol] = account_positions.get(symbol, 0.0) + shortfall

    def _parse_startup_expected_positions(self, raw: str) -> List[Tuple[Optional[str], str, float]]:
        """
        Parse startup expected position overrides from env.

        Format (comma-delimited):
        - SYMBOL=QTY (applies to all detected live accounts, or default account if none detected)
        - ACCOUNT|SYMBOL=QTY (applies to a specific account)

        Example:
        - USD:AAPL=1
        - DU123456|USD:AAPL=1,DU123456|USD:MSFT=2
        """
        overrides: List[Tuple[Optional[str], str, float]] = []
        if not raw:
            return overrides

        for token in [item.strip() for item in raw.split(",") if item.strip()]:
            if "=" not in token:
                _console_log("WARN", "IBKR.Recovery", f"Ignoring invalid IBKR_STARTUP_EXPECT_POSITIONS token: {token}")
                continue

            lhs, rhs = token.split("=", 1)
            try:
                qty = float(rhs.strip())
            except (TypeError, ValueError):
                _console_log("WARN", "IBKR.Recovery", f"Ignoring startup expected-position token with invalid quantity: {token}")
                continue

            lhs = lhs.strip()
            if "|" in lhs:
                account_raw, symbol_raw = lhs.split("|", 1)
                account_id = self._normalize_account_id(account_raw)
                symbol_key = self._normalize_symbol_key(symbol_raw)
                if symbol_key:
                    overrides.append((account_id, symbol_key, qty))
                continue

            symbol_key = self._normalize_symbol_key(lhs)
            if symbol_key:
                overrides.append((None, symbol_key, qty))

        return overrides

    def _apply_startup_expected_position_overrides(self) -> None:
        if not self._startup_expected_position_overrides:
            return

        live_accounts = set(self._startup_live_positions.keys())
        touched_symbols: Set[str] = set()
        for account_id, symbol_key, qty in self._startup_expected_position_overrides:
            if account_id is None:
                target_accounts = live_accounts if live_accounts else {self._default_account_id}
            else:
                target_accounts = {self._normalize_account_id(account_id)}

            for target_account in target_accounts:
                account_positions = self._expected_wal_positions.setdefault(target_account, {})
                account_positions[symbol_key] = float(qty)
                avg_cost = float(self._broker_position_snapshots.get(symbol_key, {}).get("avg_cost", 0.0))
                self._force_sync_local_ledger(symbol_key, float(qty), avg_cost)
                self._clear_reconciliation_lock_if_safe(symbol_key, "startup expected-position override applied")
                touched_symbols.add(symbol_key)

        if touched_symbols:
            self._refresh_circuit_state_from_snapshots()
            for symbol_key in touched_symbols:
                if self._get_local_position_quantity(symbol_key) == self._get_broker_position_quantity(symbol_key):
                    self._clear_reconciliation_lock_if_safe(symbol_key, "startup override aligned local ledger")
            self._sync_default_account_state()

        _console_log(
            "INFO",
            "IBKR.Recovery",
            (
                "Applied startup expected-position overrides from "
                f"IBKR_STARTUP_EXPECT_POSITIONS ({len(self._startup_expected_position_overrides)} entries)."
            ),
        )

    def _apply_startup_broker_snapshot_baseline(self) -> None:
        if not self._trust_startup_broker_snapshot:
            return

        trusted_expected_positions: Dict[str, Dict[str, float]] = {}
        for account_id, live_positions in self._startup_live_positions.items():
            normalized_account_id = self._normalize_account_id(account_id)
            trusted_expected_positions[normalized_account_id] = {}
            for symbol_key, quantity in live_positions.items():
                normalized_symbol_key = self._normalize_symbol_key(symbol_key)
                if abs(float(quantity)) <= 1e-9:
                    continue
                trusted_expected_positions[normalized_account_id][normalized_symbol_key] = float(quantity)

        self._expected_wal_positions = trusted_expected_positions

        broker_symbols: Set[str] = set()
        for symbol_key, snapshot in self._broker_position_snapshots.items():
            normalized_symbol_key = self._normalize_symbol_key(symbol_key)
            broker_symbols.add(self._normalize_symbol_key(self._symbol_from_key(normalized_symbol_key)))
            broker_qty = float(snapshot.get("quantity", 0.0))
            avg_cost = float(snapshot.get("avg_cost", 0.0))
            self._force_sync_local_ledger(normalized_symbol_key, broker_qty, avg_cost)
            self._clear_reconciliation_lock_if_safe(
                normalized_symbol_key,
                "trusted startup broker snapshot applied",
            )

        for symbol in list(self.positions_dict.keys()):
            if self._normalize_symbol_key(symbol) not in broker_symbols:
                self.positions_dict.pop(symbol, None)

        self._refresh_circuit_state_from_snapshots()
        self._sync_default_account_state()

        _console_log(
            "INFO",
            "IBKR.Recovery",
            "Trust mode active: seeded local baseline from broker snapshot.",
        )

    def _reset_startup_attestation_snapshots(self) -> None:
        self._startup_live_positions = {}
        self._startup_live_open_order_ids = set()
        self._startup_live_open_perm_ids = set()
        self._startup_positions_end_event.clear()
        self._startup_open_orders_end_event.clear()

    def _record_startup_position_snapshot(self, account_id: str, symbol_key: str, quantity: float) -> None:
        act_id = self._normalize_account_id(account_id)
        account_positions = self._startup_live_positions.setdefault(act_id, {})
        account_positions[self._normalize_symbol_key(symbol_key)] = float(quantity)

    def _record_startup_open_order_snapshot(self, order_id: Optional[int], perm_id: Optional[int]) -> None:
        if order_id is not None:
            try:
                self._startup_live_open_order_ids.add(int(order_id))
            except (TypeError, ValueError):
                pass
        if perm_id is not None:
            try:
                self._startup_live_open_perm_ids.add(int(perm_id))
            except (TypeError, ValueError):
                pass

    def _trip_global_kill(self, reason: str, details: Optional[Dict[str, Any]] = None) -> None:
        self._global_kill_active = True
        self._reconciliation_circuit_open = True
        self._reconciliation_state = "BREACHED"
        payload = {
            "event_type": "CRITICAL_RECOVERY_ANOMALY",
            "timestamp_ms": int(time.time() * 1000),
            "state": self._reconciliation_state,
            "details": {
                "reason": str(reason),
                **(details or {}),
            },
        }
        self._record_reconciliation_event(
            symbol="GLOBAL",
            event="critical_recovery_anomaly",
            reason=str(reason),
        )
        self._emit_telemetry_event(
            event_type="CRITICAL_RECOVERY_ANOMALY",
            payload=payload,
        )
        self._dispatch_critical_webhook(
            self._default_account_id,
            "CRITICAL_RECOVERY_ANOMALY",
            "GLOBAL",
            payload,
        )
        self._sync_default_account_state()

    def _validate_startup_recovery_state(self) -> None:
        drift_rows: List[Dict[str, Any]] = []
        live_accounts = set(self._startup_live_positions.keys())
        expected_accounts = set(self._expected_wal_positions.keys())

        for account_id in sorted(live_accounts | expected_accounts):
            expected_positions = self._expected_wal_positions.get(account_id, {})
            live_positions = self._startup_live_positions.get(account_id, {})
            symbols = set(expected_positions.keys()) | set(live_positions.keys())
            for symbol_key in sorted(symbols):
                expected_qty = float(expected_positions.get(symbol_key, 0.0))
                live_qty = float(live_positions.get(symbol_key, 0.0))
                drift_delta = abs(expected_qty - live_qty)
                if drift_delta > 0.0:
                    drift_rows.append(
                        {
                            "account_id": account_id,
                            "symbol": symbol_key,
                            "expected_qty": expected_qty,
                            "live_qty": live_qty,
                            "drift_delta": drift_delta,
                        }
                    )

        known_order_ids = set(int(order_id) for order_id in self._order_state_snapshots.keys())
        ghost_perm_ids = sorted(
            perm_id
            for perm_id in self._startup_live_open_perm_ids
            if int(perm_id) not in self._expected_active_perm_ids
        )
        ghost_order_ids = sorted(
            order_id
            for order_id in self._startup_live_open_order_ids
            if int(order_id) not in known_order_ids
        )

        if drift_rows or ghost_perm_ids or ghost_order_ids:
            details = {
                "position_drift_rows": drift_rows,
                "ghost_perm_ids": ghost_perm_ids,
                "ghost_order_ids": ghost_order_ids,
            }
            self._trip_global_kill("startup_attestation_mismatch", details=details)
            raise CriticalRecoveryAnomaly(
                "Startup broker attestation failed: drift or ghost orders detected"
            )

    async def _run_startup_broker_attestation(self) -> None:
        self._startup_attestation_active = True
        self._reset_startup_attestation_snapshots()

        try:
            self.reqOpenOrders()
            self.reqPositions()

            timeout_s = max(0.1, float(self._startup_attestation_timeout_s))
            started = asyncio.get_running_loop().time()
            while True:
                done = self._startup_positions_end_event.is_set() and self._startup_open_orders_end_event.is_set()
                if done:
                    break
                elapsed = asyncio.get_running_loop().time() - started
                if elapsed >= timeout_s:
                    details = {
                        "positions_stream_done": self._startup_positions_end_event.is_set(),
                        "open_orders_stream_done": self._startup_open_orders_end_event.is_set(),
                        "timeout_seconds": timeout_s,
                    }
                    self._trip_global_kill("startup_attestation_timeout", details=details)
                    raise CriticalRecoveryAnomaly("Startup broker attestation timed out")
                await asyncio.sleep(0.05)

            self._apply_startup_broker_snapshot_baseline()
            self._apply_startup_expected_position_overrides()
            self._validate_startup_recovery_state()
        finally:
            self._startup_attestation_active = False

    def _is_active_open_order_status(self, status: str) -> bool:
        normalized = str(status or "").strip().lower()
        return normalized in {"pendingsubmit", "presubmitted", "submitted", "apipending", "pendingcancel"}
    
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
        _console_log(
            "INFO",
            "IBKR.Connection",
            f"Stabilization verified. Next valid order ID: {orderId}",
        )
    
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

        next_status = self._map_ib_status(status)
        if float(filled) > 0 and float(remaining) > 0:
            next_status = OrderStatus.PARTIAL_FILL

        if not self._should_accept_order_status(
            order_id=int(orderId),
            next_status=next_status,
            filled=float(filled),
            remaining=float(remaining),
        ):
            return

        previous_status = self._status_label(order.status)
        
        # Update status
        order.status = next_status
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
        self._notify_order_update(order)
        
        _console_log(
            "INFO",
            "IBKR.Execution",
            f"Order status update: ID={orderId}, Status={status}, Filled={filled}/{order.quantity}",
        )
    
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
        t0_ns = time.perf_counter_ns()

        # Find our order
        ib_order_id = execution.orderId
        our_order_id = self.ib_to_our_order.get(ib_order_id)
        
        if not our_order_id:
            return
        
        order = self.orders.get(our_order_id)
        if not order:
            return

        execution_fingerprint = self._build_execution_fingerprint(int(ib_order_id), str(execution.execId))
        if not self._should_accept_execution(int(ib_order_id), execution_fingerprint):
            return

        t1_ns = time.perf_counter_ns()

        # Durability fence: persist execution identity before emitting downstream side-effects.
        try:
            self.wal_engine.append_execution_fingerprint(
                order_id=int(ib_order_id),
                exec_id=str(execution.execId),
                price=float(execution.price),
                shares=float(execution.shares),
            )
        except Exception as exc:
            _console_log("WARN", "IBKR.Recovery", f"Execution WAL append failed for order {ib_order_id}: {exc}")
            return

        self._seen_execution_fingerprints.add(execution_fingerprint)

        benchmark = self._active_order_benchmarks.get(int(ib_order_id), {})
        benchmark_mid = benchmark.get("benchmark_mid")
        account_id = self._normalize_account_id(benchmark.get("account_id"))
        symbol_key = str(benchmark.get("symbol_key") or self._normalize_contract_to_key(contract))
        execution_mid = None
        with self._nbbo_lock:
            snapshot = self._nbbo_snapshots.get(symbol_key)
            if snapshot is not None:
                execution_mid = snapshot.get("mid")

        shortfall_mid = benchmark_mid
        if shortfall_mid is None and execution_mid is not None:
            shortfall_mid = float(execution_mid)

        if shortfall_mid is not None:
            slippage_bps = self._calculate_directional_slippage_bps(
                execution_price=float(execution.price),
                benchmark_mid=float(shortfall_mid),
                side=order.side,
            )
            try:
                self.wal_engine.append_execution_shortfall(
                    order_id=int(ib_order_id),
                    exec_id=str(execution.execId),
                    account_id=account_id,
                    symbol=symbol_key,
                    side=order.side.value.upper(),
                    execution_price=float(execution.price),
                    execution_size=float(execution.shares),
                    commission=float(order.commission or 0.0),
                    benchmark_mid=float(shortfall_mid),
                    execution_mid=float(execution_mid if execution_mid is not None else shortfall_mid),
                    slippage_bps=float(slippage_bps),
                )
            except Exception as exc:
                _console_log("WARN", "IBKR.Recovery", f"Shortfall WAL append failed for order {ib_order_id}: {exc}")
                return

        t2_ns = time.perf_counter_ns()

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

        t3_ns = time.perf_counter_ns()
        signal_id = str((order.metadata or {}).get("signal_id", f"ibkr-{ib_order_id}"))
        self._emit_loop_latency_profile(
            phase="exec_details",
            symbol=symbol_key,
            account_id=account_id,
            interlock_duration_ns=(t1_ns - t0_ns),
            wal_durability_duration_ns=(t2_ns - t1_ns),
            wire_serialization_duration_ns=(t3_ns - t2_ns),
            total_loop_transit_ns=(t3_ns - t0_ns),
            order_id=int(ib_order_id),
            signal_id=signal_id,
        )
        
        _console_log(
            "INFO",
            "IBKR.Execution",
            f"Execution fill event: {execution.shares} shares of {contract.symbol} @ {execution.price}",
        )
    
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
        
        _console_log(
            "INFO",
            "IBKR.Execution",
            f"Commission recorded: ${commission:.2f} for execution {exec_id}",
        )
    
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
        if not self._rehydration_complete:
            return

        symbol_key = self._normalize_contract_to_key(contract)
        if self._startup_attestation_active:
            self._record_startup_position_snapshot(account, symbol_key, float(position))
        account_ctx = self._get_account_ctx(account)
        broker_qty = float(position)
        avg_cost = float(avgCost)

        self._broker_position_snapshots[symbol_key] = {
            "quantity": broker_qty,
            "avg_cost": avg_cost,
        }
        account_ctx["broker_position_snapshots"][symbol_key] = {
            "quantity": broker_qty,
            "avg_cost": avg_cost,
        }

        local_qty = self._get_local_position_quantity(symbol_key)
        drift_abs = float(local_qty - broker_qty)
        if abs(broker_qty) > 1e-9:
            drift_pct = abs(drift_abs) / abs(broker_qty)
        else:
            drift_pct = abs(drift_abs)

        has_open_orders = self._count_active_working_orders(symbol_key) > 0

        if drift_pct > self._max_drift_pct:
            self._circuit_breach_symbols.add(symbol_key)
            self._reconciliation_circuit_open = True
            self._reconciliation_state = "BREACHED"
            self._set_reconciliation_lock(symbol_key, "circuit breach")
            self._record_reconciliation_event(
                symbol=symbol_key,
                event="circuit_breach",
                reason=(
                    f"drift {drift_pct:.4f} exceeded threshold {self._max_drift_pct:.4f}; "
                    f"local={local_qty:.8f}, broker={broker_qty:.8f}"
                ),
            )
            self._recalculate_portfolio_value_drift()
            self._emit_circuit_breach_event(
                account,
                trigger_type="SYMBOL_DRIFT",
                symbol=symbol_key,
                drift_pct=drift_pct,
                drift_abs=drift_abs,
            )
            return

        self._circuit_breach_symbols.discard(symbol_key)
        self._reconciliation_circuit_open = len(self._circuit_breach_symbols) > 0
        self._reconciliation_state = "BREACHED" if self._reconciliation_circuit_open else "OPERATIONAL"

        self._recalculate_portfolio_value_drift()
        if self._portfolio_value_drift > self._portfolio_value_drift_limit:
            self._reconciliation_circuit_open = True
            self._reconciliation_state = "BREACHED"
            self._set_reconciliation_lock(symbol_key, "portfolio drift breach")
            self._record_reconciliation_event(
                symbol=symbol_key,
                event="portfolio_breach",
                reason=(
                    f"gross portfolio drift {self._portfolio_value_drift:.4f} exceeded "
                    f"limit {self._portfolio_value_drift_limit:.4f}"
                ),
            )
            self._emit_circuit_breach_event(
                account,
                trigger_type="PORTFOLIO_GROSS_DRIFT",
                symbol="GLOBAL",
                drift_pct=0.0,
                drift_abs=0.0,
            )
            return

        if abs(drift_abs) > 1e-9 and has_open_orders:
            self._set_reconciliation_lock(symbol_key, "in-flight convergence")
            self._record_reconciliation_event(
                symbol=symbol_key,
                event="defer_lock",
                reason=(
                    f"drift detected with open orders; "
                    f"local={local_qty:.8f}, broker={broker_qty:.8f}, drift={drift_abs:.8f}"
                ),
            )
            return

        if abs(drift_abs) > 1e-9 and not has_open_orders:
            self._force_sync_local_ledger(symbol_key, broker_qty, avg_cost)
            self._clear_reconciliation_lock_if_safe(symbol_key, "force sync applied")
            self._record_reconciliation_event(
                symbol=symbol_key,
                event="force_sync",
                reason=(
                    f"local ledger realigned to broker quantity; "
                    f"local={local_qty:.8f}, broker={broker_qty:.8f}"
                ),
            )
            return

        if self._is_reconciliation_locked(symbol_key):
            self._clear_reconciliation_lock_if_safe(symbol_key, "equilibrium reached")
            self._record_reconciliation_event(
                symbol=symbol_key,
                event="equilibrium",
                reason="local and broker position are aligned",
            )

        self._force_sync_local_ledger(symbol_key, broker_qty, avg_cost)
        self._reconciliation_state = "BREACHED" if self._reconciliation_circuit_open else "OPERATIONAL"
        self._sync_default_account_state()
        self._emit_heartbeat_if_due()

    def positionEnd(self):
        """Callback: Position stream complete."""
        if self._startup_attestation_active:
            self._startup_positions_end_event.set()
        self._reconciliation_bootstrap_pending = False
        self._refresh_circuit_state_from_snapshots()
        self._sync_default_account_state()
        self._emit_heartbeat_if_due(force=True)

    def openOrder(self, orderId: OrderId, contract: Contract, order: IBOrder, orderState) -> None:
        """Callback: Open order snapshot row."""
        if not self._startup_attestation_active:
            return
        status = str(getattr(orderState, "status", ""))
        if not self._is_active_open_order_status(status):
            return
        perm_id = getattr(order, "permId", None)
        self._record_startup_open_order_snapshot(int(orderId), perm_id)

    def openOrderEnd(self) -> None:
        """Callback: Open order snapshot complete."""
        if self._startup_attestation_active:
            self._startup_open_orders_end_event.set()

    def operator_clear_circuit(self, reason: str) -> bool:
        """
        Manual override to reset breach trackers and re-arm alerts for a specific account.
        """
        act_id = self._normalize_account_id(reason) if reason and reason.startswith('U') else self._default_account_id

        # Preserve existing reconciliation contract for the default account:
        # clears are rejected while drift remains unresolved.
        if act_id == self._default_account_id:
            for symbol_key, snapshot in self._broker_position_snapshots.items():
                broker_qty = float(snapshot.get("quantity", 0.0))
                local_qty = self._get_local_position_quantity(symbol_key)
                drift_abs = local_qty - broker_qty
                if abs(broker_qty) > 1e-9:
                    drift_pct = abs(drift_abs) / abs(broker_qty)
                else:
                    drift_pct = abs(drift_abs)
                if drift_pct > self._max_drift_pct:
                    return False

        with self._account_state_lock:
            ctx = self._get_account_ctx(act_id)
            ctx["circuit_breaker_open"] = False
            ctx["circuit_breach_symbols"].clear()
            ctx["reconciliation_locks"].clear()
            ctx["fired_breach_epochs"].clear()
            ctx["reconciliation_state"] = "OPERATIONAL"
            ctx["portfolio_value_drift"] = 0.0

            if act_id == self._default_account_id:
                self._reconciliation_circuit_open = False
                self._circuit_breach_symbols.clear()
                self._reconciliation_locks.clear()
                self._fired_breach_epochs.clear()
                self._reconciliation_state = "OPERATIONAL"
                self._portfolio_value_drift = 0.0
            self._global_kill_active = False
        self._record_reconciliation_event(
            symbol="GLOBAL",
            event="circuit_reset",
            reason=f"operator clear accepted for {act_id}",
        )
        self._emit_telemetry_event(
            event_type="CIRCUIT_RESET",
            payload={
                "account_id": act_id,
                "details": {
                    "reason": f"operator clear accepted for {act_id}",
                    "breach_symbols": [],
                }
            },
        )
        return True
    
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
            _console_log("WARN", "IBKR.Connection", f"Infrastructure warning {errorCode}: {errorString}")
            return

        # Hard transport loss - force reconnect state and clear handshake gate
        if errorCode == 1100:
            self._transition_conn_state(ConnState.RECONNECTING)
            self._clear_handshake_event_threadsafe()
            _console_log("WARN", "IBKR.Connection", f"Transport loss {errorCode}: {errorString}")
            return

        # Connectivity restored notice
        if errorCode == 1101:
            _console_log("INFO", "IBKR.Connection", f"Transport restored {errorCode}: {errorString}")
            return

        if errorCode in IBKR_NON_TERMINAL_ORDER_WARNING_CODES:
            _console_log("WARN", "IBKR.Execution", f"Order warning {errorCode}: {errorString}")
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
                    self._notify_order_update(order)
                _console_log("INFO", "IBKR.Execution", f"Cancel notice {errorCode}: {errorString}")
                return
        
            _console_log("WARN", "IBKR.Execution", f"Broker error {errorCode}: {errorString}")
        
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
                self._notify_order_update(order)

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

    def tickPrice(self, reqId: int, tickType: int, price: float, attrib):
        """Callback: L1 market-data price ticks used for NBBO tracking."""
        self._update_nbbo_price(reqId, tickType, price)

    def tickSize(self, reqId: int, tickType: int, size: float):
        """Callback: L1 market-data size ticks used for NBBO tracking."""
        self._update_nbbo_size(reqId, tickType, size)
    
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

                # Rebuild expected startup state from legacy WAL and attest against live broker state.
                self.rehydrate_and_repair()
                await self._run_startup_broker_attestation()
                self._connect_retry_attempt = 0
                return True

            except Exception as e:
                self._connect_retry_attempt += 1
                _console_log("WARN", "IBKR.Connection", f"Connection attempt failed: {e}")

                # Always sever transport before retrying to avoid stale client-id/session collisions.
                try:
                    self.disconnect()
                except Exception as disconnect_exc:
                    _console_log("WARN", "IBKR.Connection", f"Disconnect during retry cleanup failed: {disconnect_exc}")

                # Attestation drift/ghost-order anomalies are terminal until operator intervention.
                if isinstance(e, CriticalRecoveryAnomaly):
                    self._write_last_gasp_envelope(e, context="startup_attestation_failure")
                    break

                if self._connect_retry_attempt >= self._connect_max_retries:
                    self._write_last_gasp_envelope(e, context="connect_retry_exhausted")
                    break

                self._transition_conn_state(ConnState.RECONNECTING)
                backoff_s = self._calculate_backoff_seconds(self._connect_retry_attempt)
                await asyncio.sleep(backoff_s)

        self._transition_conn_state(ConnState.FAILED)
        _console_log("WARN", "IBKR.Connection", "Connection failed after retry budget exhaustion.")
        return False

    def _transition_conn_state(self, new_state: "ConnState") -> None:
        if self._conn_state != new_state:
            _console_log(
                "INFO",
                "IBKR.Connection",
                f"State transition: {self._conn_state.name} -> {new_state.name}",
            )
            self._conn_state = new_state

    def _calculate_backoff_seconds(self, attempt: int) -> float:
        # Full jitter: random(0, min(max_delay, base * 2^attempt))
        upper = min(self._connect_backoff_max, self._connect_backoff_base * (2 ** attempt))
        delay = random.uniform(0.0, upper)
        _console_log("INFO", "IBKR.Connection", f"Reconnect backoff scheduled: {delay:.2f}s")
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

    def _normalize_symbol_key(self, symbol: str) -> str:
        return str(symbol or "").upper().strip()

    def _ensure_nbbo_snapshot(self, symbol_key: str) -> Dict[str, Any]:
        normalized = self._normalize_symbol_key(symbol_key)
        snapshot = self._nbbo_snapshots.get(normalized)
        if snapshot is None:
            snapshot = {
                "symbol": normalized,
                "bid": None,
                "ask": None,
                "bid_size": None,
                "ask_size": None,
                "mid": None,
                "last_update_ms": 0,
            }
            self._nbbo_snapshots[normalized] = snapshot
        return snapshot

    def _refresh_nbbo_mid(self, snapshot: Dict[str, Any]) -> None:
        bid = snapshot.get("bid")
        ask = snapshot.get("ask")
        if bid is not None and ask is not None and bid > 0 and ask > 0:
            snapshot["mid"] = float((bid + ask) / 2.0)

    def _update_nbbo_price(self, req_id: int, tick_type: int, price: float) -> None:
        if tick_type not in {1, 2}:
            return

        symbol_key = self._nbbo_reqid_to_symbol.get(int(req_id))
        if not symbol_key:
            return

        with self._nbbo_lock:
            snapshot = self._ensure_nbbo_snapshot(symbol_key)
            if tick_type == 1:
                snapshot["bid"] = float(price)
            elif tick_type == 2:
                snapshot["ask"] = float(price)
            snapshot["last_update_ms"] = int(time.time() * 1000)
            self._refresh_nbbo_mid(snapshot)

    def _update_nbbo_size(self, req_id: int, tick_type: int, size: float) -> None:
        if tick_type not in {0, 3}:
            return

        symbol_key = self._nbbo_reqid_to_symbol.get(int(req_id))
        if not symbol_key:
            return

        with self._nbbo_lock:
            snapshot = self._ensure_nbbo_snapshot(symbol_key)
            if tick_type == 0:
                snapshot["bid_size"] = float(size)
            elif tick_type == 3:
                snapshot["ask_size"] = float(size)
            snapshot["last_update_ms"] = int(time.time() * 1000)

    def _ensure_nbbo_subscription(self, contract: Contract) -> int:
        """Ensure a symbol has an active L1 quote subscription and return reqId."""
        symbol_key = self._normalize_contract_to_key(contract)

        with self._nbbo_lock:
            existing = self._nbbo_symbol_to_reqid.get(symbol_key)
            if existing is not None:
                return existing

            req_id = int(self._next_nbbo_req_id)
            self._next_nbbo_req_id += 1
            self._nbbo_symbol_to_reqid[symbol_key] = req_id
            self._nbbo_reqid_to_symbol[req_id] = symbol_key
            self._ensure_nbbo_snapshot(symbol_key)

        try:
            self.reqMktData(req_id, contract, "", False, False, [])
        except Exception as exc:
            _console_log("WARN", "IBKR.MarketData", f"NBBO subscription failed for {symbol_key}: {exc}")

        return req_id

    def get_nbbo_snapshot(self, symbol: str, currency: str = "USD") -> Dict[str, Any]:
        """Return the latest NBBO snapshot for symbol/currency."""
        symbol_key = f"{self._normalize_symbol_key(currency)}:{self._normalize_symbol_key(symbol)}"
        with self._nbbo_lock:
            snapshot = self._nbbo_snapshots.get(symbol_key)
            if snapshot is None:
                return {
                    "symbol": symbol_key,
                    "bid": None,
                    "ask": None,
                    "bid_size": None,
                    "ask_size": None,
                    "mid": None,
                    "last_update_ms": 0,
                }
            return dict(snapshot)

    def _capture_order_benchmark(
        self,
        order_id: int,
        account_id: str,
        symbol_key: str,
        side: OrderSide,
    ) -> None:
        with self._nbbo_lock:
            snapshot = self._nbbo_snapshots.get(symbol_key)
            self._active_order_benchmarks[int(order_id)] = {
                "account_id": self._normalize_account_id(account_id),
                "symbol_key": symbol_key,
                "side": side,
                "submission_ts_us": int(time.time() * 1_000_000),
                "benchmark_bid": None if snapshot is None else snapshot.get("bid"),
                "benchmark_ask": None if snapshot is None else snapshot.get("ask"),
                "benchmark_mid": None if snapshot is None else snapshot.get("mid"),
            }

    def _calculate_directional_slippage_bps(
        self,
        *,
        execution_price: float,
        benchmark_mid: float,
        side: OrderSide,
    ) -> float:
        if benchmark_mid <= 0:
            return 0.0
        direction = 1.0 if side == OrderSide.BUY else -1.0
        return ((float(execution_price) - float(benchmark_mid)) / float(benchmark_mid)) * 10000.0 * direction

    def _normalize_account_id(self, account_id: Optional[str]) -> str:
        normalized = str(account_id or "").strip()
        return normalized or self._default_account_id

    def _get_account_ctx(self, account_id: Optional[str] = None) -> Dict[str, Any]:
        act_id = self._normalize_account_id(account_id)
        with self._account_state_lock:
            if act_id not in self._account_states:
                self._account_states[act_id] = {
                    "reconciliation_state": "BOOTSTRAP",
                    "circuit_breaker_open": False,
                    "circuit_breach_symbols": set(),
                    "reconciliation_locks": set(),
                    "broker_position_snapshots": {},
                    "portfolio_value_drift": 0.0,
                    "fired_breach_epochs": set(),
                }
            return self._account_states[act_id]

    def _sync_default_account_state(self) -> None:
        ctx = self._get_account_ctx(self._default_account_id)
        # Keep default namespace aligned with legacy flat attributes for compatibility.
        ctx["reconciliation_state"] = str(self._reconciliation_state)
        ctx["circuit_breaker_open"] = bool(self._reconciliation_circuit_open)
        ctx["circuit_breach_symbols"] = self._circuit_breach_symbols
        ctx["reconciliation_locks"] = self._reconciliation_locks
        ctx["broker_position_snapshots"] = self._broker_position_snapshots
        ctx["portfolio_value_drift"] = float(self._portfolio_value_drift)
        ctx["fired_breach_epochs"] = self._fired_breach_epochs

    def _normalize_contract_to_key(self, contract: Contract) -> str:
        symbol = self._normalize_symbol_key(str(getattr(contract, "symbol", "")))
        currency = self._normalize_symbol_key(str(getattr(contract, "currency", "USD") or "USD"))
        if not symbol:
            return currency
        return f"{currency}:{symbol}"

    def _symbol_from_key(self, symbol_key: str) -> str:
        normalized = self._normalize_symbol_key(symbol_key)
        if ":" in normalized:
            return normalized.split(":", 1)[1]
        return normalized

    def _get_local_position_quantity(self, symbol_key: str) -> float:
        symbol = self._symbol_from_key(symbol_key)
        position = self.positions_dict.get(symbol)
        if not position:
            return 0.0
        return float(position.quantity)

    def _get_broker_position_quantity(self, symbol_key: str) -> float:
        snapshot = self._broker_position_snapshots.get(self._normalize_symbol_key(symbol_key), {})
        return float(snapshot.get("quantity", 0.0))

    def _get_reference_price(self, symbol_key: str) -> float:
        symbol = self._symbol_from_key(symbol_key)
        local = self.positions_dict.get(symbol)
        broker = self._broker_position_snapshots.get(self._normalize_symbol_key(symbol_key), {})

        if local and float(getattr(local, "current_price", 0.0)) > 0:
            return float(local.current_price)
        if broker and float(broker.get("avg_cost", 0.0)) > 0:
            return float(broker.get("avg_cost", 0.0))
        if local and float(getattr(local, "avg_entry_price", 0.0)) > 0:
            return float(local.avg_entry_price)
        return 1.0

    def _recalculate_portfolio_value_drift(self) -> float:
        gross = 0.0
        keys = set(self._broker_position_snapshots.keys())
        for symbol in self.positions_dict.keys():
            keys.add(f"USD:{self._normalize_symbol_key(symbol)}")

        for symbol_key in keys:
            local_qty = self._get_local_position_quantity(symbol_key)
            broker_qty = self._get_broker_position_quantity(symbol_key)
            ref_price = self._get_reference_price(symbol_key)
            gross += abs(local_qty - broker_qty) * abs(ref_price)

        self._portfolio_value_drift = float(gross)
        return self._portfolio_value_drift

    def _refresh_circuit_state_from_snapshots(self) -> None:
        unresolved: Set[str] = set()
        for symbol_key in self._broker_position_snapshots.keys():
            local_qty = self._get_local_position_quantity(symbol_key)
            broker_qty = self._get_broker_position_quantity(symbol_key)
            drift_abs = local_qty - broker_qty
            if abs(broker_qty) > 1e-9:
                drift_pct = abs(drift_abs) / abs(broker_qty)
            else:
                drift_pct = abs(drift_abs)
            if drift_pct > self._max_drift_pct:
                unresolved.add(symbol_key)

        self._circuit_breach_symbols = unresolved
        self._recalculate_portfolio_value_drift()
        portfolio_breach = self._portfolio_value_drift > self._portfolio_value_drift_limit
        self._reconciliation_circuit_open = bool(unresolved) or portfolio_breach

        if self._reconciliation_bootstrap_pending:
            self._reconciliation_state = "BOOTSTRAP"
        elif self._reconciliation_circuit_open:
            self._reconciliation_state = "BREACHED"
        else:
            self._reconciliation_state = "OPERATIONAL"

    def _count_active_working_orders(self, symbol_key: str) -> int:
        return self._count_open_working_orders(self._symbol_from_key(symbol_key))

    def _force_sync_local_ledger(self, symbol_key: str, broker_qty: float, avg_cost: float) -> None:
        symbol = self._symbol_from_key(symbol_key)
        if abs(float(broker_qty)) <= 1e-9:
            self.positions_dict.pop(symbol, None)
            return
        self.positions_dict[symbol] = Position(
            symbol=symbol,
            quantity=float(broker_qty),
            avg_entry_price=float(avg_cost),
            current_price=0.0,
            unrealized_pnl=0.0,
            realized_pnl=0.0,
        )

    def _count_open_working_orders(self, symbol: str) -> int:
        symbol_key = self._normalize_symbol_key(symbol)
        return sum(
            1
            for order in self.orders.values()
            if self._normalize_symbol_key(order.symbol) == symbol_key
            and order.status in (OrderStatus.SUBMITTED, OrderStatus.PARTIAL_FILL)
        )

    def _record_reconciliation_event(self, symbol: str, event: str, reason: str) -> None:
        self._reconciliation_events.append(
            {
                "ts_ms": int(time.time() * 1000),
                "symbol": self._normalize_symbol_key(symbol),
                "event": event,
                "reason": reason,
            }
        )

    def _emit_telemetry_event(self, event_type: str, payload: Optional[Dict[str, Any]] = None) -> None:
        try:
            self.telemetry_gateway.publish(
                event_type=str(event_type),
                state=self._reconciliation_state,
                payload=payload or {},
            )
        except Exception:
            return

    def _emit_loop_latency_profile(
        self,
        *,
        phase: str,
        symbol: str,
        account_id: str,
        interlock_duration_ns: int,
        wal_durability_duration_ns: int,
        wire_serialization_duration_ns: int,
        total_loop_transit_ns: int,
        order_id: Optional[int] = None,
        signal_id: Optional[str] = None,
    ) -> None:
        if not self._latency_profiling_enabled:
            return

        self._emit_telemetry_event(
            event_type="LOOP_LATENCY_PROFILE",
            payload={
                "phase": str(phase),
                "symbol": str(symbol),
                "account_id": self._normalize_account_id(account_id),
                "order_id": None if order_id is None else int(order_id),
                "signal_id": None if signal_id is None else str(signal_id),
                "metrics_ns": {
                    "interlock_duration": max(0, int(interlock_duration_ns)),
                    "wal_durability_duration": max(0, int(wal_durability_duration_ns)),
                    "wire_serialization_duration": max(0, int(wire_serialization_duration_ns)),
                    "total_loop_transit": max(0, int(total_loop_transit_ns)),
                },
            },
        )

    def _emit_heartbeat_if_due(self, force: bool = False) -> None:
        now_ms = int(time.time() * 1000)
        if not force and (now_ms - self._last_telemetry_heartbeat_ms) < self._heartbeat_interval_ms:
            return
        self._last_telemetry_heartbeat_ms = now_ms
        self._emit_telemetry_event(
            event_type="SYSTEM_HEARTBEAT",
            payload={
                "metrics": {
                    "gross_portfolio_drift_notional": float(self._portfolio_value_drift),
                    "active_symbol_locks": int(len(self._reconciliation_locks)),
                    "seen_fingerprints_count": int(len(self._seen_execution_fingerprints)),
                    "telemetry_dropped_events": int(self.telemetry_gateway.dropped_events),
                }
            },
        )

    def _emit_circuit_breach_event(
        self,
        account_id: Optional[str] = None,
        trigger_type: str = "",
        symbol: str = "",
        drift_pct: float = 0.0,
        drift_abs: float = 0.0,
    ) -> None:
        # Backward compatibility: historical call signature omitted account_id:
        # _emit_circuit_breach_event(trigger_type, symbol, drift_pct, drift_abs)
        if not isinstance(symbol, str):
            drift_abs = float(drift_pct)
            drift_pct = float(symbol)
            symbol = str(trigger_type)
            trigger_type = str(account_id)
            account_id = self._default_account_id

        act_id = self._normalize_account_id(account_id)
        ctx = self._get_account_ctx(act_id)
        self._emit_telemetry_event(
            event_type="CIRCUIT_BREACH",
            payload={
                "account_id": act_id,
                "details": {
                    "trigger_type": str(trigger_type),
                    "symbol": self._normalize_symbol_key(symbol),
                    "drift_pct": float(drift_pct),
                    "drift_abs": float(drift_abs),
                    "notional_drift": float(ctx["portfolio_value_drift"]),
                    "notional_limit": float(self._portfolio_value_drift_limit),
                    "breach_symbols": sorted(ctx["circuit_breach_symbols"]),
                }
            },
        )

        self._dispatch_critical_webhook(
            act_id,
            "CIRCUIT_BREACH",
            symbol,
            {
                "event_type": "CIRCUIT_BREACH",
                "timestamp_ms": int(time.time() * 1000),
                "account_id": act_id,
                "state": ctx["reconciliation_state"],
                "details": {
                    "trigger_type": str(trigger_type),
                    "symbol": self._normalize_symbol_key(symbol),
                    "drift_pct": float(drift_pct),
                    "drift_abs": float(drift_abs),
                    "notional_drift": float(ctx["portfolio_value_drift"]),
                    "notional_limit": float(self._portfolio_value_drift_limit),
                    "breach_symbols": sorted(ctx["circuit_breach_symbols"]),
                },
            },
        )

    def _dispatch_critical_webhook(self, account_id: str, alert_type: str, symbol: str, payload: Dict[str, Any]) -> None:
        webhook_url = str(self._webhook_url or "").strip()
        if not webhook_url:
            return

        act_id = self._normalize_account_id(account_id)
        ctx = self._get_account_ctx(act_id)
        symbol_key = self._normalize_symbol_key(symbol)
        epoch_token = f"{str(alert_type)}:{symbol_key}"

        with self._account_state_lock:
            if epoch_token in ctx["fired_breach_epochs"]:
                return
            ctx["fired_breach_epochs"].add(epoch_token)

        self._emit_telemetry_event(
            event_type="WEBHOOK_DISPATCH",
            payload={
                "url": webhook_url,
                "payload": payload,
            },
        )

    def _write_last_gasp_envelope(self, exc: BaseException, context: str) -> None:
        """Persist crash diagnostics synchronously for post-mortem recovery."""
        with self._last_gasp_lock:
            try:
                self._recalculate_portfolio_value_drift()
                envelope = {
                    "event_type": "LAST_GASP_DIAGNOSTIC",
                    "timestamp_ms": int(time.time() * 1000),
                    "context": str(context),
                    "state": str(self._reconciliation_state),
                    "fatal_error": {
                        "type": type(exc).__name__,
                        "message": str(exc),
                        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
                    },
                    "runtime_snapshot": {
                        "gross_portfolio_drift_notional": float(self._portfolio_value_drift),
                        "portfolio_drift_limit": float(self._portfolio_value_drift_limit),
                        "circuit_open": bool(self._reconciliation_circuit_open),
                        "breach_symbols": sorted(self._circuit_breach_symbols),
                        "active_locks": sorted(self._reconciliation_locks),
                        "seen_fingerprints_count": int(len(self._seen_execution_fingerprints)),
                    },
                    "local_positions": {
                        symbol: {
                            "quantity": float(position.quantity),
                            "avg_entry_price": float(position.avg_entry_price),
                            "current_price": float(position.current_price),
                        }
                        for symbol, position in self.positions_dict.items()
                    },
                    "broker_position_snapshots": dict(self._broker_position_snapshots),
                    "recent_reconciliation_events": self._reconciliation_events[-10:],
                }

                payload = json.dumps(envelope, indent=2, sort_keys=True).encode("utf-8")
                self._last_gasp_path.parent.mkdir(parents=True, exist_ok=True)
                fd = os.open(str(self._last_gasp_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
                try:
                    os.write(fd, payload)
                    if hasattr(os, "fdatasync"):
                        os.fdatasync(fd)
                    else:
                        os.fsync(fd)
                finally:
                    os.close(fd)

                self._emit_telemetry_event(
                    event_type="LAST_GASP_WRITTEN",
                    payload={
                        "details": {
                            "context": str(context),
                            "path": str(self._last_gasp_path),
                        }
                    },
                )
            except Exception:
                return

    def _set_reconciliation_lock(self, symbol: str, reason: str) -> None:
        symbol_key = self._symbol_from_key(symbol)
        if symbol_key and symbol_key not in self._reconciliation_locks:
            self._reconciliation_locks.add(symbol_key)
            self._record_reconciliation_event(symbol_key, "lock", reason)

    def _clear_reconciliation_lock_if_safe(self, symbol: str, reason: str) -> None:
        symbol_key = self._symbol_from_key(symbol)
        if not symbol_key:
            return
        if self._count_open_working_orders(symbol_key) > 0:
            return
        if symbol_key in self._reconciliation_locks:
            self._reconciliation_locks.discard(symbol_key)
            self._record_reconciliation_event(symbol_key, "unlock", reason)

    def _is_reconciliation_locked(self, symbol: str) -> bool:
        return self._symbol_from_key(symbol) in self._reconciliation_locks

    def _prime_runtime_indexes_from_wal(
        self,
        trackers: Dict[int, Dict[str, Any]],
        seen_execution_fingerprints: Optional[Set[str]] = None,
    ) -> None:
        self._order_state_snapshots = {
            int(order_id): {
                "signal_id": state.get("signal_id"),
                "status": str(state.get("status", "Pending")),
                "filled": float(state.get("filled", 0.0)),
                "remaining": float(state.get("remaining", 0.0)),
                "last_seq": int(state.get("last_seq", 0)),
            }
            for order_id, state in trackers.items()
        }
        self._closed_order_ids = {
            int(order_id)
            for order_id, state in self._order_state_snapshots.items()
            if self._is_terminal_status_label(str(state.get("status", "")))
        }
        self._telemetry_exported = {str(order_id) for order_id in self._closed_order_ids}
        self._seen_execution_fingerprints = set(seen_execution_fingerprints or set())

    def _status_rank(self, status: OrderStatus) -> int:
        ranking = {
            OrderStatus.PENDING: 0,
            OrderStatus.SUBMITTED: 1,
            OrderStatus.PARTIAL_FILL: 2,
            OrderStatus.FILLED: 3,
            OrderStatus.CANCELLED: 3,
            OrderStatus.REJECTED: 3,
            OrderStatus.EXPIRED: 3,
        }
        return ranking.get(status, -1)

    def _status_rank_from_label(self, label: str) -> int:
        normalized = str(label or "").replace("_", "").replace(" ", "").lower()
        ranking = {
            "pending": 0,
            "submitted": 1,
            "partialfill": 2,
            "filled": 3,
            "cancelled": 3,
            "rejected": 3,
            "expired": 3,
        }
        return ranking.get(normalized, -1)

    def _is_terminal_status(self, status: OrderStatus) -> bool:
        return status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]

    def _is_terminal_status_label(self, label: str) -> bool:
        return self._status_rank_from_label(label) == 3

    def _purge_execution_fingerprints_for_order(self, order_id: int) -> None:
        prefix = f"{int(order_id)}:"
        self._seen_execution_fingerprints = {
            fingerprint
            for fingerprint in self._seen_execution_fingerprints
            if not fingerprint.startswith(prefix)
        }

    def _reset_runtime_indexes_for_submission(self, order: Order) -> None:
        order_id = int(order.order_id)
        signal_id = str((order.metadata or {}).get("signal_id", f"ibkr-{order.order_id}"))
        self._order_state_snapshots[order_id] = {
            "signal_id": signal_id,
            "status": self._status_label(order.status),
            "filled": float(order.filled_quantity),
            "remaining": float(order.remaining_quantity()),
            "last_seq": int(self.wal_engine.current_sequence),
        }
        self._closed_order_ids.discard(order_id)
        self._telemetry_exported.discard(order.order_id)
        self._purge_execution_fingerprints_for_order(order_id)

    def _build_execution_fingerprint(self, order_id: int, exec_id: str) -> str:
        return f"{int(order_id)}:{exec_id}"

    def _should_accept_execution(self, order_id: int, fingerprint: str) -> bool:
        if not self._rehydration_complete:
            return False
        if int(order_id) in self._closed_order_ids:
            return False
        return fingerprint not in self._seen_execution_fingerprints

    def _should_accept_order_status(
        self,
        order_id: int,
        next_status: OrderStatus,
        filled: float,
        remaining: float,
    ) -> bool:
        if not self._rehydration_complete:
            return False

        snapshot = self._order_state_snapshots.get(int(order_id))
        if not snapshot:
            return True

        snapshot_filled = float(snapshot.get("filled", 0.0))
        snapshot_remaining = float(snapshot.get("remaining", 0.0))
        snapshot_rank = self._status_rank_from_label(str(snapshot.get("status", "Pending")))
        next_rank = self._status_rank(next_status)

        if filled < (snapshot_filled - 1e-9):
            return False

        state_advanced = next_rank > snapshot_rank
        filled_advanced = filled > (snapshot_filled + 1e-9)
        remaining_advanced = remaining < (snapshot_remaining - 1e-9)

        if int(order_id) in self._closed_order_ids and not state_advanced and not filled_advanced and not remaining_advanced:
            return False

        if not state_advanced and not filled_advanced and not remaining_advanced:
            return False

        if next_rank < snapshot_rank and not filled_advanced and not remaining_advanced:
            return False

        if remaining > (snapshot_remaining + 1e-9) and not state_advanced and not filled_advanced:
            return False

        return True

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

        order_id = int(order.order_id)
        self._order_state_snapshots[order_id] = {
            "signal_id": signal_id,
            "status": new_label,
            "filled": float(filled),
            "remaining": float(remaining),
            "last_seq": int(self.wal_engine.current_sequence),
        }

        if new_status == OrderStatus.PARTIAL_FILL and not lifecycle.get("ts_first_partial_fill"):
            lifecycle["ts_first_partial_fill"] = int(time.time() * 1000)

        terminal = self._is_terminal_status(new_status)
        if terminal:
            self._closed_order_ids.add(order_id)
        else:
            self._closed_order_ids.discard(order_id)

        if terminal:
            self._clear_reconciliation_lock_if_safe(order.symbol, "all working orders terminal")

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
        self.telemetry_gateway.shutdown()
        _console_log("INFO", "IBKR.Connection", "Disconnected from IBKR.")
    
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
        metadata = order.metadata or {}
        
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

        # Optional concealment controls for hidden/iceberg style routing.
        hidden_flag = metadata.get("is_hidden", getattr(order, "is_hidden", False))
        if bool(hidden_flag):
            ib_order.hidden = True

        display_size = metadata.get("display_size", getattr(order, "display_size", None))
        if display_size is not None:
            display_size_int = int(display_size)
            if display_size_int <= 0:
                raise ValueError("display_size must be a positive integer")
            ib_order.displaySize = display_size_int

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
        t0_ns = time.perf_counter_ns()

        if self._global_kill_active:
            raise RuntimeError("Global kill switch active after recovery anomaly; order submission blocked")

        if self._reconciliation_circuit_open:
            raise RuntimeError("Position drift circuit breaker is active; order submission blocked")

        if self._is_reconciliation_locked(order.symbol):
            raise RuntimeError(f"Reconciliation lock active for {order.symbol}; order submission blocked")

        if not self.connected_flag or self.next_order_id is None:
            raise RuntimeError("Not connected to IBKR")

        t1_ns = time.perf_counter_ns()
        
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
            self._ensure_nbbo_subscription(contract)
            symbol_key = self._normalize_contract_to_key(contract)
            
            # Create IB order
            ib_order = self._create_ib_order(order)
            self._sanitize_ibkr_order(ib_order)
            t2_ns = time.perf_counter_ns()
            
            # Place order
            self.placeOrder(ib_order_id, contract, ib_order)
            t3_ns = time.perf_counter_ns()
            
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
            self._reset_runtime_indexes_for_submission(order)
            self._capture_order_benchmark(
                order_id=int(ib_order_id),
                account_id=str(order.metadata.get("account_id") or order.metadata.get("ibkr_account_id") or self._default_account_id),
                symbol_key=symbol_key,
                side=order.side,
            )
            self._emit_loop_latency_profile(
                phase="submit_order",
                symbol=symbol_key,
                account_id=str(order.metadata.get("account_id") or order.metadata.get("ibkr_account_id") or self._default_account_id),
                interlock_duration_ns=(t1_ns - t0_ns),
                wal_durability_duration_ns=0,
                wire_serialization_duration_ns=(t3_ns - t2_ns),
                total_loop_transit_ns=(t3_ns - t0_ns),
                order_id=int(ib_order_id),
                signal_id=str(order.metadata.get("signal_id", f"ibkr-{ib_order_id}")),
            )
            
            _console_log(
                "INFO",
                "IBKR.Execution",
                f"Order submitted successfully: ID={order.order_id}, Symbol={order.symbol}, Side={order.side.value.upper()}, Quantity={order.quantity}",
            )
            
            return order
        
        except Exception as e:
            _console_log("WARN", "IBKR.Execution", f"Order submission error: {e}")
            order.status = OrderStatus.REJECTED
            self._write_last_gasp_envelope(e, context=f"submit_order:{order.symbol}")
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
                _console_log(
                    "INFO",
                    "IBKR.Execution",
                    f"Order cancelled locally without transmission: ID={order_id}",
                )
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
            
            _console_log("INFO", "IBKR.Execution", f"Order cancelled: ID={order_id}")
            return True
        
        except Exception as e:
            _console_log("WARN", "IBKR.Execution", f"Cancel error: {e}")
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
        
        _console_log("INFO", "IBKR.Execution", f"Order modified: ID={order_id}")
        
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

    def subscribe_order_updates(self, callback: Callable):
        """Subscribe to order lifecycle updates."""
        self.order_update_callbacks.append(callback)

    def _notify_order_update(self, order: Order) -> None:
        for callback in self.order_update_callbacks:
            try:
                callback(order)
            except Exception as exc:
                _console_log("WARN", "IBKR.Callbacks", f"Order update callback failed: {exc}")
