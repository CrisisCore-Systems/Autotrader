from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Sequence

from autotrader.execution.oms.detector import StructuralTrapDetector
from autotrader.execution.oms.stop_run import StopRunCoordinator, StructuralTrapSignal


class TrapPipeline:
    """Lightweight glue between finalized bars, structural detection, and trap deployment."""

    def __init__(
        self,
        detector: StructuralTrapDetector,
        coordinator: StopRunCoordinator,
        *,
        max_history_bars: int = 64,
    ):
        if max_history_bars < 2:
            raise ValueError("max_history_bars must be at least 2")
        self.detector = detector
        self.coordinator = coordinator
        self.max_history_bars = int(max_history_bars)
        self._bar_history: Dict[str, Deque[Dict[str, Any]]] = defaultdict(lambda: deque(maxlen=self.max_history_bars))
        self._deployed_trap_ids: set[str] = set()

    async def on_finalized_bar(self, bar: Dict[str, Any]) -> List[StructuralTrapSignal]:
        return await self.on_finalized_bars([bar])

    async def on_finalized_bars(self, bars: Sequence[Dict[str, Any]]) -> List[StructuralTrapSignal]:
        deployed: List[StructuralTrapSignal] = []
        for bar in bars:
            symbol = self._symbol_key(bar["symbol"])
            self._bar_history[symbol].append(dict(bar))
            signals = self.detector.detect(list(self._bar_history[symbol]))
            for signal in signals:
                if signal.trap_id in self._deployed_trap_ids or signal.trap_id in self.coordinator.traps:
                    continue
                await self.coordinator.deploy_trap(signal)
                self._deployed_trap_ids.add(signal.trap_id)
                deployed.append(signal)
        return deployed

    async def on_market_snapshot(self, symbol_prices: Dict[str, float]) -> List[str]:
        return await self.coordinator.cancel_invalidated_traps(symbol_prices)

    async def on_clock(self, now: Optional[datetime] = None) -> List[str]:
        return await self.coordinator.cancel_stale_traps(now=now)

    def history_for_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        return list(self._bar_history[self._symbol_key(symbol)])

    @staticmethod
    def _symbol_key(symbol: str) -> str:
        return str(symbol).upper().strip()


__all__ = ["TrapPipeline"]