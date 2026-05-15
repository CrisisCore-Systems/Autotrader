"""
Live reconciliation loop.

Runs at fixed cadence, compares local engine state with exchange state,
and triggers the live OMS kill switch on divergence.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Callable, Dict, List, Optional

from .contracts import PortfolioStateSnapshot, StateDivergence, StateDivergenceException
from .oms import LiveOMS


class LiveReconciler:
    """1Hz reconciliation task for live execution state."""

    def __init__(
        self,
        oms: LiveOMS,
        local_snapshot_provider: Callable[[], PortfolioStateSnapshot],
        exchange_snapshot_provider: Callable[[], PortfolioStateSnapshot],
        interval_seconds: float = 1.0,
        tolerance_qty: float = 0.0,
        heartbeat_timeout_seconds: float = 30.0,
    ):
        self.oms = oms
        self.local_snapshot_provider = local_snapshot_provider
        self.exchange_snapshot_provider = exchange_snapshot_provider
        self.interval_seconds = float(interval_seconds)
        self.tolerance_qty = float(tolerance_qty)
        self.heartbeat_timeout_seconds = float(heartbeat_timeout_seconds)
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._last_heartbeat_at: Optional[datetime] = None
        self._last_audit_at: Optional[datetime] = None
        self._last_divergences: List[StateDivergence] = []
        self._heartbeat_lock = Lock()

    @property
    def running(self) -> bool:
        return self._running

    @property
    def last_audit_at(self) -> Optional[datetime]:
        return self._last_audit_at

    @property
    def last_heartbeat_at(self) -> Optional[datetime]:
        with self._heartbeat_lock:
            return self._last_heartbeat_at

    @property
    def last_divergences(self) -> List[StateDivergence]:
        return list(self._last_divergences)

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        self._running = False
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None

    async def run(self) -> None:
        while self._running:
            await self.audit_cycle()
            await asyncio.sleep(self.interval_seconds)

    def mark_heartbeat(self) -> None:
        """Record a successful market-data heartbeat from the live feed."""
        with self._heartbeat_lock:
            self._last_heartbeat_at = datetime.now(timezone.utc)

    def heartbeat_age_seconds(self) -> Optional[float]:
        with self._heartbeat_lock:
            last = self._last_heartbeat_at
        if last is None:
            return None
        return (datetime.now(timezone.utc) - last).total_seconds()

    def heartbeat_stale(self) -> bool:
        age = self.heartbeat_age_seconds()
        return bool(age is not None and age > self.heartbeat_timeout_seconds)

    async def audit_cycle(self) -> bool:
        now = datetime.now(timezone.utc)

        if self.heartbeat_stale():
            exception = StateDivergenceException(
                f"Heartbeat stale for {self.heartbeat_age_seconds():.2f}s",
                divergences=[],
            )
            await self.oms.emergency_kill(
                reason=str(exception),
                metadata={
                    "heartbeat_age_seconds": self.heartbeat_age_seconds(),
                    "heartbeat_timeout_seconds": self.heartbeat_timeout_seconds,
                },
            )
            self._last_audit_at = now
            raise exception

        if self.oms.kill_switch_engaged:
            self._last_audit_at = now
            return False

        local = self.local_snapshot_provider()
        exchange = self.exchange_snapshot_provider()
        divergences = self._compare_snapshots(local, exchange)
        self._last_audit_at = now

        if divergences:
            self._last_divergences = divergences
            exception = StateDivergenceException(
                "Live portfolio state diverged from exchange state",
                divergences=divergences,
            )
            await self.oms.emergency_kill(
                reason=str(exception),
                metadata={"divergences": [asdict(item) for item in divergences]},
            )
            raise exception

        return True

    async def audit_balances(self, local_portfolio_state: Dict[str, Any] | PortfolioStateSnapshot) -> bool:
        """Compare a provided local state object to the current exchange snapshot."""
        if isinstance(local_portfolio_state, dict):
            local = PortfolioStateSnapshot(
                timestamp=datetime.now(timezone.utc),
                positions=dict(local_portfolio_state.get("positions", {})),
                open_order_ids=list(local_portfolio_state.get("open_order_ids", [])),
                cash=local_portfolio_state.get("cash"),
                equity=local_portfolio_state.get("equity"),
                source=str(local_portfolio_state.get("source", "engine")),
                metadata=dict(local_portfolio_state.get("metadata", {})),
            )
        else:
            local = local_portfolio_state

        exchange = self.exchange_snapshot_provider()
        divergences = self._compare_snapshots(local, exchange)
        if divergences:
            self._last_divergences = divergences
            return False
        return True

    async def sync_ledger_with_fills(self) -> List[Dict[str, Any]]:
        """Return live fill records for downstream audit/log sync."""
        fills = self.oms.get_fills()
        payload = [
            {
                "order_id": fill.order_id,
                "symbol": fill.symbol,
                "side": fill.side.value,
                "quantity": fill.quantity,
                "price": fill.price,
                "commission": fill.commission,
                "timestamp": fill.timestamp.isoformat(),
                "execution_id": fill.execution_id,
                "metadata": dict(fill.metadata),
            }
            for fill in fills
        ]
        self._last_audit_at = datetime.now(timezone.utc)
        return payload

    def _compare_snapshots(
        self,
        local: PortfolioStateSnapshot,
        exchange: PortfolioStateSnapshot,
    ) -> List[StateDivergence]:
        divergences: List[StateDivergence] = []

        symbols = sorted(set(local.positions) | set(exchange.positions))
        for symbol in symbols:
            local_qty = float(local.positions.get(symbol, 0.0))
            exchange_qty = float(exchange.positions.get(symbol, 0.0))
            delta = abs(local_qty - exchange_qty)
            if delta > self.tolerance_qty:
                divergences.append(
                    StateDivergence(
                        timestamp=datetime.now(timezone.utc),
                        symbol=symbol,
                        local_quantity=local_qty,
                        exchange_quantity=exchange_qty,
                        absolute_difference=delta,
                        details={
                            "local_open_order_ids": local.open_order_ids,
                            "exchange_open_order_ids": exchange.open_order_ids,
                            "local_source": local.source,
                            "exchange_source": exchange.source,
                        },
                    )
                )

        local_open = set(local.open_order_ids)
        exchange_open = set(exchange.open_order_ids)
        if local_open != exchange_open:
            divergences.append(
                StateDivergence(
                    timestamp=datetime.now(timezone.utc),
                    symbol="__open_orders__",
                    local_quantity=float(len(local_open)),
                    exchange_quantity=float(len(exchange_open)),
                    absolute_difference=float(abs(len(local_open) - len(exchange_open))),
                    details={
                        "local_open_order_ids": sorted(local_open),
                        "exchange_open_order_ids": sorted(exchange_open),
                    },
                )
            )

        return divergences
