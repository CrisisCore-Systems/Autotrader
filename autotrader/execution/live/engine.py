"""
Phase 5 live execution orchestrator.

Coordinates the OMS, reconciliation loop, and live market-data adapter while
preserving graceful shutdown semantics for production and staging runners.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from inspect import isawaitable
from typing import Any, AsyncIterable, Callable, Dict, List, Optional

from autotrader.execution.adapters import BaseBrokerAdapter
from autotrader.schemas.market_data import AssetClass, OHLCV

from .market_data import LiveMarketDataAdapter
from .oms import LiveOMS
from .reconciler import LiveReconciler


@dataclass
class LiveExecutionEngineConfig:
    """Configuration for the live execution orchestrator."""

    symbols: List[str] = field(default_factory=list)
    venue: str = "LIVE"
    asset_class: AssetClass = AssetClass.CRYPTO
    bar_interval_minutes: int = 15
    rest_fallback_seconds: int = 5
    reconciler_interval_seconds: float = 1.0
    heartbeat_timeout_seconds: float = 30.0
    drift_tolerance_qty: float = 0.0
    max_open_orders: int = 100
    order_timeout_seconds: float = 300.0
    max_completed_bars: int = 5_000
    shutdown_timeout_seconds: float = 10.0
    install_signal_handlers: bool = True


@dataclass
class LiveExecutionEngineStatus:
    """Snapshot of the orchestrator state."""

    running: bool
    stopping: bool
    stop_reason: Optional[str]
    started_at: Optional[datetime]
    stopped_at: Optional[datetime]
    kill_switch_engaged: bool
    heartbeat_age_seconds: Optional[float]
    last_audit_at: Optional[datetime]
    last_heartbeat_at: Optional[datetime]
    symbols: List[str] = field(default_factory=list)
    active_orders: int = 0
    completed_bars: Dict[str, int] = field(default_factory=dict)


class LiveExecutionEngine:
    """Coordinate live OMS, reconciler, and market-data loops."""

    def __init__(
        self,
        broker_adapter: BaseBrokerAdapter,
        config: Optional[LiveExecutionEngineConfig] = None,
        local_snapshot_provider: Optional[Callable[[], Any]] = None,
        exchange_snapshot_provider: Optional[Callable[[], Any]] = None,
        transport_stream_provider: Optional[Callable[[List[str]], AsyncIterable[Dict[str, Any]]]] = None,
        rest_snapshot_provider: Optional[Callable[[List[str]], Any]] = None,
        strategy_bar_callback: Optional[Callable[[OHLCV, "LiveExecutionEngine"], Any]] = None,
        shutdown_callback: Optional[Callable[[LiveExecutionEngineStatus], Any]] = None,
    ):
        self.config = config or LiveExecutionEngineConfig()
        self.broker_adapter = broker_adapter
        self.strategy_bar_callback = strategy_bar_callback
        self.shutdown_callback = shutdown_callback

        self.oms = LiveOMS(
            adapter=broker_adapter,
            max_open_orders=self.config.max_open_orders,
            order_timeout_seconds=self.config.order_timeout_seconds,
            state_snapshot_provider=local_snapshot_provider,
            exchange_snapshot_provider=exchange_snapshot_provider,
            drift_tolerance_qty=self.config.drift_tolerance_qty,
        )

        self.reconciler = LiveReconciler(
            oms=self.oms,
            local_snapshot_provider=self.oms.snapshot_state,
            exchange_snapshot_provider=exchange_snapshot_provider or self.oms.snapshot_state,
            interval_seconds=self.config.reconciler_interval_seconds,
            tolerance_qty=self.config.drift_tolerance_qty,
            heartbeat_timeout_seconds=self.config.heartbeat_timeout_seconds,
        )

        self.market_data = LiveMarketDataAdapter(
            symbols=self.config.symbols,
            reconciler=self.reconciler,
            bar_interval_minutes=self.config.bar_interval_minutes,
            rest_fallback_seconds=self.config.rest_fallback_seconds,
            venue=self.config.venue,
            asset_class=self.config.asset_class,
            transport_stream_provider=transport_stream_provider,
            rest_snapshot_provider=rest_snapshot_provider,
            on_completed_bar=self._handle_completed_bar,
            max_completed_bars=self.config.max_completed_bars,
        )

        self._running = False
        self._stopping = False
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None
        self._stop_reason: Optional[str] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = asyncio.Event()
        self._signal_handlers_installed = False
        self._signal_handler_tokens: Dict[Any, Any] = {}

    @property
    def running(self) -> bool:
        return self._running

    @property
    def stopping(self) -> bool:
        return self._stopping

    async def start(self) -> None:
        """Boot the live stack in dependency order."""
        if self._running:
            return

        self._running = True
        self._stopping = False
        self._stop_reason = None
        self._stopped_at = None
        self._started_at = datetime.now(timezone.utc)
        self._loop = asyncio.get_running_loop()
        self._stop_event = asyncio.Event()

        if self.config.install_signal_handlers:
            self._install_signal_handlers()

        await self.reconciler.start()
        await self.market_data.start()

    async def run(self) -> None:
        """Run until a stop request or termination signal is received."""
        await self.start()
        try:
            await self._stop_event.wait()
        finally:
            await self.stop()

    async def stop(self, reason: Optional[str] = None) -> None:
        """Gracefully stop the live stack without engaging the emergency kill switch."""
        if not self._running and not self._stopping:
            return

        self._stopping = True
        if reason and self._stop_reason is None:
            self._stop_reason = reason

        self._remove_signal_handlers()

        with suppress(Exception):
            await self.market_data.stop()

        with suppress(Exception):
            await self.reconciler.stop()

        self._running = False
        self._stopping = False
        self._stopped_at = datetime.now(timezone.utc)
        self._loop = None

        if self.shutdown_callback is not None:
            status = self.snapshot_status()
            result = self.shutdown_callback(status)
            if isawaitable(result):
                await result

    def request_stop(self, reason: str) -> None:
        """Request a clean shutdown from a signal handler or control path."""
        if self._stop_reason is None:
            self._stop_reason = reason
        self._stop_event.set()

    async def submit_order(self, *args: Any, **kwargs: Any):
        return await self.oms.submit_order(*args, **kwargs)

    async def cancel_order(self, order_id: str) -> bool:
        return await self.oms.cancel_order(order_id)

    async def get_order_status(self, order_id: str):
        return await self.oms.get_order_status(order_id)

    def snapshot_status(self) -> LiveExecutionEngineStatus:
        """Capture a typed status snapshot for diagnostics and shutdown hooks."""
        completed_bars = {
            symbol: len(bar_history)
            for symbol, bar_history in self.market_data.completed_bars.items()
        }

        active_orders = len(self.oms.active_orders)
        return LiveExecutionEngineStatus(
            running=self._running,
            stopping=self._stopping,
            stop_reason=self._stop_reason,
            started_at=self._started_at,
            stopped_at=self._stopped_at,
            kill_switch_engaged=self.oms.kill_switch_engaged,
            heartbeat_age_seconds=self.reconciler.heartbeat_age_seconds(),
            last_audit_at=self.reconciler.last_audit_at,
            last_heartbeat_at=self.reconciler.last_heartbeat_at,
            symbols=list(self.market_data.symbols),
            active_orders=active_orders,
            completed_bars=completed_bars,
        )

    def get_status(self) -> Dict[str, Any]:
        """Return a JSON-friendly status payload."""
        status = self.snapshot_status()
        payload = asdict(status)
        payload["started_at"] = status.started_at.isoformat() if status.started_at else None
        payload["stopped_at"] = status.stopped_at.isoformat() if status.stopped_at else None
        payload["last_audit_at"] = status.last_audit_at.isoformat() if status.last_audit_at else None
        payload["last_heartbeat_at"] = status.last_heartbeat_at.isoformat() if status.last_heartbeat_at else None
        return payload

    async def _handle_completed_bar(self, bar: OHLCV) -> None:
        """Invoke the strategy callback for each completed bar."""
        if self.strategy_bar_callback is None:
            return

        result = self.strategy_bar_callback(bar, self)
        if isawaitable(result):
            await result

    def _install_signal_handlers(self) -> None:
        if self._signal_handlers_installed:
            return

        loop = self._loop
        if loop is None:
            return

        def schedule_stop(signal_name: str) -> None:
            self.request_stop(signal_name)

        for signal_name in ("SIGINT", "SIGTERM"):
            signal_obj = getattr(signal, signal_name, None)
            if signal_obj is None:
                continue

            try:
                loop.add_signal_handler(signal_obj, schedule_stop, signal_name)
                self._signal_handler_tokens[signal_obj] = ("asyncio", schedule_stop)
            except (NotImplementedError, RuntimeError, ValueError):
                try:
                    previous_handler = signal.getsignal(signal_obj)

                    def _handler(_signum, _frame, *, _name=signal_name) -> None:
                        schedule_stop(_name)

                    signal.signal(signal_obj, _handler)
                    self._signal_handler_tokens[signal_obj] = ("signal", previous_handler)
                except Exception:
                    continue

        self._signal_handlers_installed = True

    def _remove_signal_handlers(self) -> None:
        if not self._signal_handlers_installed:
            return

        for signal_obj, token in list(self._signal_handler_tokens.items()):
            mode = token[0] if isinstance(token, tuple) and token else None
            if mode == "asyncio":
                with suppress(Exception):
                    if self._loop is not None:
                        self._loop.remove_signal_handler(signal_obj)
            elif mode == "signal":
                previous_handler = token[1]
                with suppress(Exception):
                    signal.signal(signal_obj, previous_handler)

        self._signal_handler_tokens.clear()
        self._signal_handlers_installed = False


__all__ = [
    "LiveExecutionEngineConfig",
    "LiveExecutionEngineStatus",
    "LiveExecutionEngine",
]