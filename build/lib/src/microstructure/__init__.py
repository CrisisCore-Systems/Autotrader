"""Microstructure detection module for high-frequency trading signals."""

from src.microstructure.stream import BinanceOrderBookStream
from src.microstructure.features import (
    OrderBookFeatures,
    TradeFeatures,
    MicrostructureFeatures,
)
from src.microstructure.detector import MicrostructureDetector
from src.microstructure.backtester import TickBacktester, BacktestConfig
from src.microstructure.alerting import (
    AlertManager,
    AlertConfig,
    AlertPriority,
)

# BOCPD not yet implemented
# from src.microstructure.bocpd import BOCPDDetector, MultivariateBOCPD, RegimeInfo

__all__ = [
    "BinanceOrderBookStream",
    "OrderBookFeatures",
    "TradeFeatures",
    "MicrostructureFeatures",
    "MicrostructureDetector",
    "TickBacktester",
    "BacktestConfig",
    "AlertManager",
    "AlertConfig",
    "AlertPriority",
]
