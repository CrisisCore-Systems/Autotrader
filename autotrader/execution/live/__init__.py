"""
Live execution contracts and runtime scaffolding.

Phase 5 starts here: explicit OMS event contracts, portfolio snapshots,
and a live wrapper around the existing order manager.
"""

from .contracts import (
    LiveEventType,
    LiveOrderEvent,
    PortfolioStateSnapshot,
    StateDivergence,
    StateDivergenceException,
    LiveOMSProtocol,
)
from .oms import LiveOMS
from .engine import LiveExecutionEngine, LiveExecutionEngineConfig, LiveExecutionEngineStatus
from .market_data import LiveMarketDataAdapter
from .reconciler import LiveReconciler
from .testnet_transport import BinanceTestnetTransportAdapter

__all__ = [
    "LiveEventType",
    "LiveOrderEvent",
    "PortfolioStateSnapshot",
    "StateDivergence",
    "StateDivergenceException",
    "LiveOMSProtocol",
    "LiveOMS",
    "LiveExecutionEngineConfig",
    "LiveExecutionEngineStatus",
    "LiveExecutionEngine",
    "LiveMarketDataAdapter",
    "LiveReconciler",
    "BinanceTestnetTransportAdapter",
]