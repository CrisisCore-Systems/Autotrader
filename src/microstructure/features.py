"""Microstructure feature engineering for orderflow detection."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional

import numpy as np

from src.microstructure.stream import OrderBookSnapshot, Trade
from src.microstructure.bocpd import BOCPDDetector


@dataclass
class OrderBookFeatures:
    """Features derived from L2 order book."""

    timestamp: float

    # Imbalance metrics
    imbalance_top5: float  # (bid_vol - ask_vol) / (bid_vol + ask_vol) for top 5
    imbalance_top10: float  # Same for top 10

    # Microprice and drift
    microprice: float  # Volume-weighted mid price
    microprice_drift: float  # Change vs previous

    # Spread metrics
    spread_bps: float  # Spread in basis points
    spread_compression: float  # Spread / rolling mean spread

    # Depth metrics
    bid_depth: float  # Total bid volume
    ask_depth: float  # Total ask volume
    depth_ratio: float  # bid_depth / ask_depth

    # Price levels
    best_bid: float
    best_ask: float
    mid_price: float


@dataclass
class TradeFeatures:
    """Features derived from trade flow."""

    timestamp: float

    # Imbalance across windows
    trade_imbalance_1s: float  # Buy volume - sell volume (1s)
    trade_imbalance_5s: float  # Same for 5s
    trade_imbalance_30s: float  # Same for 30s

    # Volume metrics
    volume_1s: float
    volume_5s: float
    volume_30s: float

    # Volume z-scores (standardized bursts)
    volume_zscore_1s: float
    volume_zscore_5s: float
    volume_zscore_30s: float

    # Volatility
    realized_vol_1s: float  # Realized volatility from tick changes
    realized_vol_5s: float
    realized_vol_30s: float

    # Trade intensity
    trade_count_1s: int
    trade_count_5s: int
    trade_count_30s: int


@dataclass
class MicrostructureFeatures:
    """Combined microstructure features for detection."""

    timestamp: float
    orderbook: OrderBookFeatures
    trades: TradeFeatures

    # Time-of-day features
    hour_of_day: int
    minute_of_hour: int
    is_market_open: bool  # For traditional markets; always True for crypto

    # Regime indicators (to be filled by BOCPD)
    regime_id: Optional[int] = None
    changepoint_prob: Optional[float] = None


class OrderBookFeatureExtractor:
    """Extract features from order book snapshots."""

    def __init__(self, lookback: int = 100, enable_bocpd: bool = True):
        """
        Initialize feature extractor.

        Args:
            lookback: Number of historical snapshots for rolling stats
            enable_bocpd: Whether to run BOCPD regime detection
        """
        self.lookback = lookback
        self.enable_bocpd = enable_bocpd
        self.history: Deque[OrderBookSnapshot] = deque(maxlen=lookback)
        self.microprice_history: Deque[float] = deque(maxlen=lookback)
        self.spread_history: Deque[float] = deque(maxlen=lookback)

        # BOCPD detectors
        if enable_bocpd:
            self.bocpd_imbalance = BOCPDDetector(hazard_rate=0.01, threshold=0.5)
            self.bocpd_spread = BOCPDDetector(hazard_rate=0.01, threshold=0.5)
        else:
            self.bocpd_imbalance = None
            self.bocpd_spread = None

    def _calculate_basic_metrics(self, snapshot: OrderBookSnapshot) -> tuple[float, float, float, float]:
        """Calculate basic price and spread metrics."""
        best_bid = snapshot.bids[0][0]
        best_ask = snapshot.asks[0][0]
        mid_price = (best_bid + best_ask) / 2
        spread_bps = ((best_ask - best_bid) / mid_price) * 10000
        return best_bid, best_ask, mid_price, spread_bps

    def _calculate_microprice(
        self, best_bid: float, best_ask: float, mid_price: float, snapshot: OrderBookSnapshot
    ) -> tuple[float, float]:
        """Calculate microprice and drift."""
        bid_vol_5 = sum(size for _, size in snapshot.bids[:5])
        ask_vol_5 = sum(size for _, size in snapshot.asks[:5])
        total_vol = bid_vol_5 + ask_vol_5

        if total_vol > 0:
            microprice = (best_bid * ask_vol_5 + best_ask * bid_vol_5) / total_vol
        else:
            microprice = mid_price

        self.microprice_history.append(microprice)

        if len(self.microprice_history) >= 2:
            microprice_drift = microprice - self.microprice_history[-2]
        else:
            microprice_drift = 0.0

        return microprice, microprice_drift

    def _calculate_spread_compression(self, spread_bps: float) -> float:
        """Calculate spread compression metric."""
        self.spread_history.append(spread_bps)
        if len(self.spread_history) >= 10:
            mean_spread = np.mean(self.spread_history)
            return spread_bps / mean_spread if mean_spread > 0 else 1.0
        return 1.0

    def _calculate_depth_metrics(self, snapshot: OrderBookSnapshot) -> tuple[float, float, float]:
        """Calculate depth metrics."""
        bid_depth = sum(size for _, size in snapshot.bids)
        ask_depth = sum(size for _, size in snapshot.asks)
        depth_ratio = bid_depth / ask_depth if ask_depth > 0 else 1.0
        return bid_depth, ask_depth, depth_ratio

    def extract(self, snapshot: OrderBookSnapshot) -> OrderBookFeatures:
        """Extract features from order book snapshot."""
        self.history.append(snapshot)

        # Basic metrics
        if not snapshot.bids or not snapshot.asks:
            return self._empty_features(snapshot.timestamp)

        best_bid, best_ask, mid_price, spread_bps = self._calculate_basic_metrics(snapshot)

        # Imbalance calculations
        imbalance_top5 = self._compute_imbalance(snapshot.bids[:5], snapshot.asks[:5])
        imbalance_top10 = self._compute_imbalance(snapshot.bids[:10], snapshot.asks[:10])

        # Microprice
        microprice, microprice_drift = self._calculate_microprice(best_bid, best_ask, mid_price, snapshot)

        # Spread compression
        spread_compression = self._calculate_spread_compression(spread_bps)

        # Depth metrics
        bid_depth, ask_depth, depth_ratio = self._calculate_depth_metrics(snapshot)

        # Update BOCPD detectors (optional)
        if self.enable_bocpd and self.bocpd_imbalance and self.bocpd_spread:
            self.bocpd_imbalance.update(imbalance_top5)
            self.bocpd_spread.update(spread_bps)

        return OrderBookFeatures(
            timestamp=snapshot.timestamp,
            imbalance_top5=imbalance_top5,
            imbalance_top10=imbalance_top10,
            microprice=microprice,
            microprice_drift=microprice_drift,
            spread_bps=spread_bps,
            spread_compression=spread_compression,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            depth_ratio=depth_ratio,
            best_bid=best_bid,
            best_ask=best_ask,
            mid_price=mid_price,
        )

    @staticmethod
    def _compute_imbalance(bids: List[tuple[float, float]], asks: List[tuple[float, float]]) -> float:
        """Compute order book imbalance: (bid_vol - ask_vol) / (bid_vol + ask_vol)."""
        bid_vol = sum(size for _, size in bids)
        ask_vol = sum(size for _, size in asks)
        total_vol = bid_vol + ask_vol

        if total_vol == 0:
            return 0.0

        return (bid_vol - ask_vol) / total_vol

    def _empty_features(self, timestamp: float) -> OrderBookFeatures:
        """Return empty features when order book is invalid."""
        return OrderBookFeatures(
            timestamp=timestamp,
            imbalance_top5=0.0,
            imbalance_top10=0.0,
            microprice=0.0,
            microprice_drift=0.0,
            spread_bps=0.0,
            spread_compression=1.0,
            bid_depth=0.0,
            ask_depth=0.0,
            depth_ratio=1.0,
            best_bid=0.0,
            best_ask=0.0,
            mid_price=0.0,
        )

    def get_regime_info(self) -> Optional[tuple[int, float]]:
        """
        Get current regime information from BOCPD.

        Returns:
            (regime_id, changepoint_prob) or None if BOCPD disabled
        """
        if not self.enable_bocpd or not self.bocpd_imbalance:
            return None

        # Use imbalance detector as primary regime indicator
        regime_stats = self.bocpd_imbalance.get_regime_stats()
        regime_id = regime_stats["current_regime"]

        # Get latest changepoint probability
        if self.bocpd_imbalance.changepoint_probs:
            cp_prob = self.bocpd_imbalance.changepoint_probs[-1]
        else:
            cp_prob = 0.0

        return regime_id, cp_prob


class TradeFeatureExtractor:
    """Extract features from trade flow."""

    def __init__(self):
        """Initialize trade feature extractor."""
        self.trades: Deque[Trade] = deque(maxlen=10000)  # Keep 10k recent trades
        self.volume_history: Deque[float] = deque(maxlen=1000)

    def add_trade(self, trade: Trade) -> None:
        """Add a trade to history."""
        self.trades.append(trade)

    def extract(self, current_time: float) -> TradeFeatures:
        """Extract features from recent trades."""
        if not self.trades:
            return self._empty_features(current_time)

        # Filter trades by window
        trades_1s = [t for t in self.trades if current_time - t.timestamp <= 1.0]
        trades_5s = [t for t in self.trades if current_time - t.timestamp <= 5.0]
        trades_30s = [t for t in self.trades if current_time - t.timestamp <= 30.0]

        # Trade imbalance (buy - sell volume)
        imbalance_1s = self._compute_trade_imbalance(trades_1s)
        imbalance_5s = self._compute_trade_imbalance(trades_5s)
        imbalance_30s = self._compute_trade_imbalance(trades_30s)

        # Volume metrics
        volume_1s = sum(t.size for t in trades_1s)
        volume_5s = sum(t.size for t in trades_5s)
        volume_30s = sum(t.size for t in trades_30s)

        # Track volume for z-score
        self.volume_history.append(volume_1s)

        # Volume z-scores
        volume_zscore_1s = self._compute_zscore(volume_1s, self.volume_history)
        volume_zscore_5s = self._compute_zscore(volume_5s, self.volume_history)
        volume_zscore_30s = self._compute_zscore(volume_30s, self.volume_history)

        # Realized volatility (from price changes)
        realized_vol_1s = self._compute_realized_vol(trades_1s)
        realized_vol_5s = self._compute_realized_vol(trades_5s)
        realized_vol_30s = self._compute_realized_vol(trades_30s)

        return TradeFeatures(
            timestamp=current_time,
            trade_imbalance_1s=imbalance_1s,
            trade_imbalance_5s=imbalance_5s,
            trade_imbalance_30s=imbalance_30s,
            volume_1s=volume_1s,
            volume_5s=volume_5s,
            volume_30s=volume_30s,
            volume_zscore_1s=volume_zscore_1s,
            volume_zscore_5s=volume_zscore_5s,
            volume_zscore_30s=volume_zscore_30s,
            realized_vol_1s=realized_vol_1s,
            realized_vol_5s=realized_vol_5s,
            realized_vol_30s=realized_vol_30s,
            trade_count_1s=len(trades_1s),
            trade_count_5s=len(trades_5s),
            trade_count_30s=len(trades_30s),
        )

    @staticmethod
    def _compute_trade_imbalance(trades: List[Trade]) -> float:
        """Compute trade imbalance: buy_volume - sell_volume."""
        buy_vol = sum(t.size for t in trades if t.side == "buy")
        sell_vol = sum(t.size for t in trades if t.side == "sell")
        return buy_vol - sell_vol

    @staticmethod
    def _compute_zscore(value: float, history: Deque[float]) -> float:
        """Compute z-score of value vs history."""
        if len(history) < 2:
            return 0.0

        mean = np.mean(history)
        std = np.std(history)

        if std == 0:
            return 0.0

        return float((value - mean) / std)

    @staticmethod
    def _compute_realized_vol(trades: List[Trade]) -> float:
        """Compute realized volatility from trade prices."""
        if len(trades) < 2:
            return 0.0

        prices = np.array([t.price for t in trades])
        returns = np.diff(np.log(prices))

        if len(returns) == 0:
            return 0.0

        return float(np.std(returns) * np.sqrt(len(returns)))

    def _empty_features(self, timestamp: float) -> TradeFeatures:
        """Return empty features when no trades available."""
        return TradeFeatures(
            timestamp=timestamp,
            trade_imbalance_1s=0.0,
            trade_imbalance_5s=0.0,
            trade_imbalance_30s=0.0,
            volume_1s=0.0,
            volume_5s=0.0,
            volume_30s=0.0,
            volume_zscore_1s=0.0,
            volume_zscore_5s=0.0,
            volume_zscore_30s=0.0,
            realized_vol_1s=0.0,
            realized_vol_5s=0.0,
            realized_vol_30s=0.0,
            trade_count_1s=0,
            trade_count_5s=0,
            trade_count_30s=0,
        )
