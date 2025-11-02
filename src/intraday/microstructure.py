"""
Microstructure Features for Intraday Trading

Extracts market microstructure features from tick data:
- Bid-ask spread dynamics
- Volume imbalance (buy vs sell pressure)
- Order flow toxicity (VPIN indicator)
- Order book depth analysis
- Large trade detection
- Market impact estimation

Returns 15-dimensional feature vector.
"""

from __future__ import annotations

import numpy as np
from typing import List, Optional
from collections import deque
import logging

from src.intraday.data_pipeline import IntradayDataPipeline, TickData
from src.intraday.utils import (
    safe_zscore,
    winsorize,
    validate_features,
    drop_constant_cols,
    safe_corrcoef,
)
from src.common.normalize import safe_zscore as safe_zscore_common, winsorize as winsorize_common

logger = logging.getLogger(__name__)


class MicrostructureFeatures:
    """
    Compute market microstructure features from tick data.
    
    Features (15 dimensions):
    1. bid_ask_spread - Dollar spread
    2. spread_pct - Spread as % of price
    3. spread_volatility - Rolling std of spread
    4. volume_imbalance - Buy/sell pressure (-1 to +1)
    5. large_trade_ratio - % volume in large trades
    6. trade_intensity - Trades per second
    7. bid_depth_1 - Level 1 bid size
    8. ask_depth_1 - Level 1 ask size
    9. bid_depth_5 - Total top 5 bid sizes (if depth available)
    10. ask_depth_5 - Total top 5 ask sizes
    11. depth_imbalance - Order book imbalance
    12. toxic_flow_score - VPIN indicator
    13. adverse_selection - Post-trade price movement
    14. market_impact - Estimated impact per trade
    15. liquidity_score - Depth / volatility ratio
    
    Example:
        >>> pipeline = IntradayDataPipeline(ib, 'SPY')
        >>> pipeline.start()
        >>> features = MicrostructureFeatures(pipeline)
        >>> feature_vector = features.compute()
        >>> print(feature_vector.shape)  # (15,)
    """

    BASE_FEATURE_NAMES = [
        "bid_ask_spread",
        "spread_pct",
        "spread_volatility",
        "volume_imbalance",
        "large_trade_ratio",
        "trade_intensity",
        "bid_depth_1",
        "ask_depth_1",
        "bid_depth_5",
        "ask_depth_5",
        "depth_imbalance",
        "toxic_flow_score",
        "adverse_selection",
        "market_impact",
        "liquidity_score",
    ]
    
    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        lookback_ticks: int = 100,
        large_trade_threshold: int = 10000,  # Shares
        check_stale: bool = True,  # Disable for historical replay
    ):
        """
        Initialize microstructure feature engine.
        
        Args:
            pipeline: IntradayDataPipeline instance
            lookback_ticks: Number of ticks to analyze
            large_trade_threshold: Minimum size for "large" trade
            check_stale: Enable staleness checks (disable for historical)
        """
        self.pipeline = pipeline
        self.lookback_ticks = lookback_ticks
        self.large_trade_threshold = large_trade_threshold
        self.check_stale = check_stale
        
        # Feature history for volatility calculations
        self.spread_history: deque = deque(maxlen=100)
        self.price_history: deque = deque(maxlen=100)
        
        logger.info(
            f"Initialized MicrostructureFeatures "
            f"(lookback={lookback_ticks}, large_threshold={large_trade_threshold})"
        )
    
    def compute(self) -> np.ndarray:
        """
        Compute all microstructure features.
        
        Returns:
            15-dimensional numpy array
        """
        ticks = self.pipeline.get_latest_ticks(self.lookback_ticks)
        
        if not ticks:
            return np.zeros(15)
        
        # Update history
        if ticks:
            self.spread_history.append(ticks[-1].spread)
            self.price_history.append(ticks[-1].price)
        
        # Compute each feature
        features = np.array([
            self._spread(ticks),
            self._spread_pct(ticks),
            self._spread_volatility(),
            self._volume_imbalance(ticks),
            self._large_trade_ratio(ticks),
            self._trade_intensity(ticks),
            self._bid_depth_1(ticks),
            self._ask_depth_1(ticks),
            self._bid_depth_5(),  # Requires order book
            self._ask_depth_5(),
            self._depth_imbalance(),
            self._toxic_flow_score(ticks),
            self._adverse_selection(ticks),
            self._market_impact(ticks),
            self._liquidity_score(ticks),
        ])
        
        return features
    
    # === Feature Calculations ===
    
    def _spread(self, ticks: List[TickData]) -> float:
        """1. Dollar bid-ask spread."""
        if not ticks:
            return 0.0
        return ticks[-1].spread
    
    def _spread_pct(self, ticks: List[TickData]) -> float:
        """2. Spread as percentage of price."""
        if not ticks:
            return 0.0
        return ticks[-1].spread_pct
    
    def _spread_volatility(self) -> float:
        """3. Rolling standard deviation of spread."""
        if len(self.spread_history) < 2:
            return 0.0
        return float(np.std(self.spread_history))
    
    def _volume_imbalance(self, ticks: List[TickData]) -> float:
        """
        4. Volume imbalance (-1 to +1).
        
        Positive = buy pressure (trades at ask)
        Negative = sell pressure (trades at bid)
        """
        if not ticks:
            return 0.0
        
        buy_volume = sum(
            t.size for t in ticks 
            if t.price >= t.ask  # Aggressive buy
        )
        sell_volume = sum(
            t.size for t in ticks 
            if t.price <= t.bid  # Aggressive sell
        )
        
        total = buy_volume + sell_volume
        if total == 0:
            return 0.0
        
        return (buy_volume - sell_volume) / total
    
    def _large_trade_ratio(self, ticks: List[TickData]) -> float:
        """
        5. Percentage of volume from large trades.
        
        Large trades often indicate institutional activity.
        """
        if not ticks:
            return 0.0
        
        total_volume = sum(t.size for t in ticks)
        large_volume = sum(
            t.size for t in ticks 
            if t.size >= self.large_trade_threshold
        )
        
        if total_volume == 0:
            return 0.0
        
        return large_volume / total_volume
    
    def _trade_intensity(self, ticks: List[TickData]) -> float:
        """
        6. Trades per second.
        
        High intensity can indicate momentum or news event.
        """
        if len(ticks) < 2:
            return 0.0
        
        time_span = ticks[-1].timestamp - ticks[0].timestamp
        if time_span == 0:
            return 0.0
        
        return len(ticks) / time_span
    
    def _bid_depth_1(self, ticks: List[TickData]) -> float:
        """7. Level 1 bid size (best bid)."""
        if not ticks:
            return 0.0
        return float(ticks[-1].bid_size)
    
    def _ask_depth_1(self, ticks: List[TickData]) -> float:
        """8. Level 1 ask size (best ask)."""
        if not ticks:
            return 0.0
        return float(ticks[-1].ask_size)
    
    def _bid_depth_5(self) -> float:
        """
        9. Total top 5 bid sizes.
        
        Requires Level 2 data (order book).
        Returns 0 if not available.
        """
        if not self.pipeline.order_book.bids:
            return 0.0
        
        top_5 = self.pipeline.order_book.bids[:5]
        return float(sum(level.size for level in top_5))
    
    def _ask_depth_5(self) -> float:
        """
        10. Total top 5 ask sizes.
        
        Requires Level 2 data (order book).
        """
        if not self.pipeline.order_book.asks:
            return 0.0
        
        top_5 = self.pipeline.order_book.asks[:5]
        return float(sum(level.size for level in top_5))
    
    def _depth_imbalance(self) -> float:
        """
        11. Order book depth imbalance (-1 to +1).
        
        Positive = more buying interest (bid depth > ask depth)
        Negative = more selling interest
        """
        return self.pipeline.order_book.get_depth_imbalance(levels=5)
    
    def _toxic_flow_score(self, ticks: List[TickData]) -> float:
        """
        12. Volume-Synchronized Probability of Informed Trading (VPIN).
        
        Measures order flow toxicity - how likely recent trades
        are from informed traders.
        
        Higher values = more toxic flow = potentially adverse selection
        
        Simplified VPIN calculation:
        VPIN = |buy_volume - sell_volume| / total_volume
        """
        if not ticks or len(ticks) < 10:
            return 0.0
        
        # Calculate volume imbalance magnitude
        buy_volume = sum(t.size for t in ticks if t.price >= t.ask)
        sell_volume = sum(t.size for t in ticks if t.price <= t.bid)
        total_volume = buy_volume + sell_volume
        
        if total_volume == 0:
            return 0.0
        
        # VPIN = absolute imbalance
        vpin = abs(buy_volume - sell_volume) / total_volume
        
        return vpin
    
    def _adverse_selection(self, ticks: List[TickData]) -> float:
        """
        13. Adverse selection cost.
        
        Measures how much price moves against you after trade.
        
        Calculation: Average price movement over next N ticks
        after each trade in the lookback window.
        
        Positive = price tends to move up after buys (adverse for sellers)
        Negative = price tends to move down after sells (adverse for buyers)
        """
        if len(ticks) < 20:
            return 0.0
        
        # Sample recent trades and measure post-trade price movement
        adverse_costs = []
        
        for i in range(len(ticks) - 10):  # Look at all but last 10 ticks
            entry_price = ticks[i].price
            
            # Average price over next 10 ticks
            future_prices = [ticks[j].price for j in range(i+1, min(i+11, len(ticks)))]
            if not future_prices:
                continue
            
            avg_future_price = np.mean(future_prices)
            
            # Classify as buy/sell and calculate adverse movement
            if ticks[i].price >= ticks[i].ask:  # Buy trade
                adverse = avg_future_price - entry_price  # Hope price goes up
            elif ticks[i].price <= ticks[i].bid:  # Sell trade
                adverse = entry_price - avg_future_price  # Hope price goes down
            else:
                continue  # Mid-spread trade
            
            adverse_costs.append(adverse)
        
        if not adverse_costs:
            return 0.0
        
        return float(np.mean(adverse_costs))
    
    def _market_impact(self, ticks: List[TickData]) -> float:
        """
        14. Estimated market impact per 1000 shares.
        
        Measures how much a trade of standard size moves the price.
        
        Calculation: Regression of price change on trade size
        
        Returns: Estimated price impact (bps) per 1000 shares
        """
        if len(ticks) < 20:
            return 0.0
        
        # Calculate price changes and corresponding trade sizes
        price_changes = []
        trade_sizes = []
        
        for i in range(1, len(ticks)):
            price_change = (ticks[i].price - ticks[i-1].price) / ticks[i-1].price
            size = ticks[i].size
            
            if size > 0:
                price_changes.append(price_change)
                trade_sizes.append(size)
        
        if len(price_changes) < 5:
            return 0.0
        
        # Simple linear approximation: impact = slope * 1000
        # (price_change vs size)
        try:
            # Use safe_corrcoef to avoid NaN from constant columns
            X = np.vstack([trade_sizes, price_changes]).T
            X_filtered, keep_mask = drop_constant_cols(X, eps=1e-8)
            if X_filtered.shape[1] < 2:
                # Not enough variance for correlation
                return 0.0
            C = safe_corrcoef(X_filtered)
            correlation = C[0, 1]
            
            # Normalize to 1000 shares
            avg_size = np.mean(trade_sizes)
            if avg_size == 0:
                return 0.0
            
            # Estimated impact in basis points per 1000 shares
            impact = correlation * (1000 / avg_size) * 10000  # Convert to bps
            
            return float(impact)
        
        except Exception:
            return 0.0
    
    def _liquidity_score(self, ticks: List[TickData]) -> float:
        """
        15. Liquidity score = depth / volatility.
        
        Higher score = more liquid (large depth, low volatility)
        Lower score = less liquid (thin depth, high volatility)
        
        Normalized to 0-1 range.
        """
        if not ticks or len(self.price_history) < 10:
            return 0.5  # Neutral
        
        # Get total depth (bid + ask)
        bid_depth = self._bid_depth_1(ticks)
        ask_depth = self._ask_depth_1(ticks)
        total_depth = bid_depth + ask_depth
        
        # Get realized volatility (std of prices)
        price_vol = np.std(self.price_history)
        
        if price_vol == 0 or total_depth == 0:
            return 0.5
        
        # Liquidity score (higher = more liquid)
        # Normalize using sigmoid
        raw_score = total_depth / (price_vol * 1000)  # Scale factor
        liquidity_score = 1 / (1 + np.exp(-raw_score))  # Sigmoid
        
        return float(liquidity_score)
    
    # === Utility Methods ===
    
    def get_feature_names(self) -> List[str]:
        """Get names of all features."""
        return list(self.BASE_FEATURE_NAMES)
    
    def compute_dict(self) -> dict:
        """Compute features as dictionary (for debugging)."""
        features = self.compute()
        names = self.get_feature_names()
        return dict(zip(names, features))
    
    def __repr__(self) -> str:
        return (
            f"MicrostructureFeatures("
            f"lookback={self.lookback_ticks}, "
            f"large_threshold={self.large_trade_threshold})"
        )


class RobustMicrostructureFeatures(MicrostructureFeatures):
    """Extended feature engine with validation, advanced metrics, and scaling."""

    _ROBUST_DEFAULTS = {
        "bid_ask_spread": (0.02, 0.01),
        "spread_pct": (0.0002, 0.0001),
        "spread_volatility": (0.005, 0.002),
        "volume_imbalance": (0.0, 0.3),
        "large_trade_ratio": (0.1, 0.15),
        "trade_intensity": (2.0, 1.5),
        "bid_depth_1": (5000.0, 3000.0),
        "ask_depth_1": (5000.0, 3000.0),
        "bid_depth_5": (25000.0, 15000.0),
        "ask_depth_5": (25000.0, 15000.0),
        "depth_imbalance": (0.0, 0.4),
        "toxic_flow_score": (0.3, 0.2),
        "adverse_selection": (0.0, 0.001),
        "market_impact": (0.5, 0.3),
        "liquidity_score": (0.5, 0.2),
        "order_flow_imbalance": (0.0, 0.5),
        "regime_normal_prob": (0.7, 0.2),
        "regime_stressed_prob": (0.1, 0.1),
        "regime_jump_prob": (0.05, 0.05),
        "regime_news_prob": (0.1, 0.1),
        "regime_illiquid_prob": (0.05, 0.05),
        "liquidity_consumption_ratio": (0.5, 0.3),
        "market_maker_presence": (0.6, 0.25),
        "adverse_selection_risk": (0.3, 0.2),
        "inventory_risk": (0.2, 0.15),
    }

    _MINMAX_DEFAULTS = {
        "bid_ask_spread": (0.0, 0.1),
        "spread_pct": (0.0, 0.005),
        "spread_volatility": (0.0, 0.02),
        "volume_imbalance": (-1.0, 1.0),
        "large_trade_ratio": (0.0, 1.0),
        "trade_intensity": (0.0, 20.0),
        "bid_depth_1": (0.0, 20000.0),
        "ask_depth_1": (0.0, 20000.0),
        "bid_depth_5": (0.0, 100000.0),
        "ask_depth_5": (0.0, 100000.0),
        "depth_imbalance": (-1.0, 1.0),
        "toxic_flow_score": (0.0, 1.0),
        "adverse_selection": (-0.01, 0.01),
        "market_impact": (-5.0, 5.0),
        "liquidity_score": (0.0, 1.0),
        "order_flow_imbalance": (-1.0, 1.0),
        "regime_normal_prob": (0.0, 1.0),
        "regime_stressed_prob": (0.0, 1.0),
        "regime_jump_prob": (0.0, 1.0),
        "regime_news_prob": (0.0, 1.0),
        "regime_illiquid_prob": (0.0, 1.0),
        "liquidity_consumption_ratio": (0.0, 1.0),
        "market_maker_presence": (0.0, 1.0),
        "adverse_selection_risk": (0.0, 1.0),
        "inventory_risk": (0.0, 1.0),
    }

    def __init__(
        self,
        pipeline: IntradayDataPipeline,
        lookback_ticks: int = 100,
        large_trade_threshold: int = 10000,
        *,
        min_valid_ticks: int = 5,
        data_quality_threshold: float = 0.7,
        include_order_flow: bool = True,
        include_regimes: bool = True,
        include_liquidity_metrics: bool = True,
        normalized: bool = False,
        normalization_method: str = "robust",
        check_stale: bool = True,  # Disable for historical replay
    ):
        super().__init__(
            pipeline=pipeline,
            lookback_ticks=lookback_ticks,
            large_trade_threshold=large_trade_threshold,
            check_stale=check_stale,
        )
        self.min_valid_ticks = max(1, min_valid_ticks)
        self.data_quality_threshold = data_quality_threshold
        self.include_order_flow = include_order_flow
        self.include_regimes = include_regimes
        self.include_liquidity_metrics = include_liquidity_metrics
        self.normalized = normalized
        self.normalization_method = normalization_method
        logger.info(
            "Initialized RobustMicrostructureFeatures "
            f"(lookback={lookback_ticks}, large_threshold={large_trade_threshold}, "
            f"normalized={normalized}, method={normalization_method})"
        )

    def compute(self) -> np.ndarray:
        ticks = self.pipeline.get_latest_ticks(self.lookback_ticks)
        raw_features = self._compute_features(ticks)
        if self.normalized:
            return self._normalize_features(raw_features, self.normalization_method)
        return raw_features

    def compute_normalized(self, method: str = "robust") -> np.ndarray:
        ticks = self.pipeline.get_latest_ticks(self.lookback_ticks)
        raw_features = self._compute_features(ticks)
        return self._normalize_features(raw_features, method)

    def get_feature_names(self) -> List[str]:
        names = super().get_feature_names().copy()
        if self.include_order_flow:
            names.append("order_flow_imbalance")
        if self.include_regimes:
            names.extend(
                [
                    "regime_normal_prob",
                    "regime_stressed_prob",
                    "regime_jump_prob",
                    "regime_news_prob",
                    "regime_illiquid_prob",
                ]
            )
        if self.include_liquidity_metrics:
            names.extend(
                [
                    "liquidity_consumption_ratio",
                    "market_maker_presence",
                    "adverse_selection_risk",
                    "inventory_risk",
                ]
            )
        return names

    def _compute_features(self, ticks: List[TickData]) -> np.ndarray:
        feature_length = len(self.get_feature_names())
        if not ticks:
            return np.zeros(feature_length)

        if not self._validate_ticks(ticks):
            logger.warning("Invalid tick data detected - returning neutral features")
            return np.zeros(feature_length)

        latest_tick = ticks[-1]
        if self._validate_tick(latest_tick):
            self.spread_history.append(latest_tick.spread)
            self.price_history.append(latest_tick.price)

        features: List[float] = [
            self._ensure_scalar(self._safe_compute(self._spread, ticks)),
            self._ensure_scalar(self._safe_compute(self._spread_pct, ticks)),
            self._ensure_scalar(self._safe_compute(self._spread_volatility)),
            self._ensure_scalar(self._safe_compute(self._volume_imbalance, ticks)),
            self._ensure_scalar(self._safe_compute(self._large_trade_ratio, ticks)),
            self._ensure_scalar(self._safe_compute(self._trade_intensity, ticks)),
            self._ensure_scalar(self._safe_compute(self._bid_depth_1, ticks)),
            self._ensure_scalar(self._safe_compute(self._ask_depth_1, ticks)),
            self._ensure_scalar(self._safe_compute(self._bid_depth_5)),
            self._ensure_scalar(self._safe_compute(self._ask_depth_5)),
            self._ensure_scalar(self._safe_compute(self._depth_imbalance)),
            self._ensure_scalar(self._safe_compute(self._enhanced_toxic_flow_score, ticks)),
            self._ensure_scalar(self._safe_compute(self._adverse_selection, ticks)),
            self._ensure_scalar(self._safe_compute(self._enhanced_market_impact, ticks)),
            self._ensure_scalar(self._safe_compute(self._liquidity_score, ticks)),
        ]

        if self.include_order_flow:
            ofi = self._safe_compute(self._order_flow_imbalance, ticks)
            features.append(self._ensure_scalar(ofi))

        if self.include_regimes:
            regimes = self._safe_compute(
                self._market_regime_features,
                ticks,
                default=np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=float),
            )
            features.extend(np.asarray(regimes, dtype=float).tolist())

        if self.include_liquidity_metrics:
            liquidity_metrics = self._safe_compute(
                self._liquidity_provision_metrics,
                ticks,
                default=np.zeros(4, dtype=float),
            )
            features.extend(np.asarray(liquidity_metrics, dtype=float).tolist())

        feature_vector = np.asarray(features, dtype=float)

        if not self._validate_features(feature_vector):
            logger.warning("Feature validation failed - returning neutral features")
            return np.zeros(feature_length)

        return feature_vector

    def _safe_compute(self, func, *args, default=0.0, **kwargs):
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            name = getattr(func, "__name__", repr(func))
            logger.debug(f"Feature {name} failed: {exc}")
            return default
        if result is None:
            return default
        return result

    def _ensure_scalar(self, value, default: float = 0.0) -> float:
        if value is None:
            return float(default)
        if np.isscalar(value):
            return float(value)
        array = np.asarray(value)
        if array.ndim == 0 and array.size == 1:
            return float(array.item())
        return float(default)

    def _validate_ticks(self, ticks: List[TickData]) -> bool:
        if not ticks or len(ticks) < self.min_valid_ticks:
            return False

        # Only check staleness in live mode
        if self.check_stale and (ticks[-1].timestamp - ticks[0].timestamp > 3600):
            logger.warning("Stale tick window detected")
            return False

        valid_prices = sum(
            1
            for tick in ticks
            if tick.price > 0 and tick.bid > 0 and tick.ask > 0 and tick.ask >= tick.bid
        )
        quality_ratio = valid_prices / len(ticks)
        return quality_ratio >= self.data_quality_threshold

    def _validate_tick(self, tick: TickData) -> bool:
        return (
            tick.price > 0
            and tick.bid > 0
            and tick.ask > 0
            and tick.ask >= tick.bid
            and tick.timestamp > 0
        )

    def _validate_features(self, features: np.ndarray) -> bool:
        if np.any(np.isnan(features)) or np.any(np.isinf(features)):
            return False
        return np.all(np.abs(features) < 1e6)

    def _enhanced_toxic_flow_score(self, ticks: List[TickData], volume_buckets: int = 10) -> float:
        if len(ticks) < 20:
            return 0.0
        try:
            total_volume = sum(t.size for t in ticks)
            bucket_volume = total_volume / max(volume_buckets, 1)
            if bucket_volume <= 0:
                return 0.0

            imbalances = []
            current_volume = 0
            buy_volume = 0
            sell_volume = 0

            for tick in ticks:
                if tick.price >= tick.ask:
                    buy_volume += tick.size
                elif tick.price <= tick.bid:
                    sell_volume += tick.size

                current_volume += tick.size

                if current_volume >= bucket_volume:
                    imbalance = abs(buy_volume - sell_volume) / max(current_volume, 1)
                    imbalances.append(imbalance)
                    current_volume = 0
                    buy_volume = 0
                    sell_volume = 0

            if current_volume > 0:
                imbalance = abs(buy_volume - sell_volume) / max(current_volume, 1)
                imbalances.append(imbalance)

            if not imbalances:
                return 0.0

            vpin = float(np.mean(imbalances))
            return float(np.clip(vpin, 0.0, 1.0))
        except Exception as exc:
            logger.debug(f"Enhanced VPIN calculation failed: {exc}")
            return super()._toxic_flow_score(ticks)

    def _order_flow_imbalance(self, ticks: List[TickData], window: int = 20) -> float:
        if len(ticks) < 5:
            return 0.0
        try:
            relevant_ticks = ticks[-window:]
            decay_factor = 0.9
            ofi_scores = []
            for idx, tick in enumerate(relevant_ticks):
                mid_price = (tick.bid + tick.ask) / 2
                if tick.price > mid_price:
                    direction = 1.0
                elif tick.price < mid_price:
                    direction = -1.0
                else:
                    direction = 0.0

                recency_weight = decay_factor ** (len(relevant_ticks) - idx - 1)
                size_weight = np.log1p(tick.size) / np.log1p(1000.0)
                ofi_scores.append(direction * recency_weight * size_weight)

            if not ofi_scores:
                return 0.0

            max_possible = sum(decay_factor ** i for i in range(len(ofi_scores)))
            if max_possible <= 0:
                return 0.0

            ofi = sum(ofi_scores) / max_possible
            return float(np.clip(ofi, -1.0, 1.0))
        except Exception as exc:
            logger.debug(f"Order flow imbalance calculation failed: {exc}")
            return super()._volume_imbalance(ticks)

    def _market_regime_features(self, ticks: List[TickData]) -> np.ndarray:
        if len(ticks) < 10:
            return np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=float)
        try:
            spread_ratio = self._ensure_scalar(self._safe_compute(self._spread_pct, ticks)) / 0.0005
            volume_intensity = self._ensure_scalar(self._safe_compute(self._trade_intensity, ticks)) / 10.0
            large_trade_ratio = self._ensure_scalar(self._safe_compute(self._large_trade_ratio, ticks))
            toxic_flow = self._ensure_scalar(self._safe_compute(self._enhanced_toxic_flow_score, ticks))

            regime_scores = np.zeros(5, dtype=float)

            if spread_ratio < 2.0 and 0.5 < volume_intensity < 3.0:
                regime_scores[0] = 1.0
            if spread_ratio > 3.0 and toxic_flow > 0.7:
                regime_scores[1] = 1.0
            if large_trade_ratio > 0.3 and volume_intensity > 2.0:
                regime_scores[2] = 1.0
            if volume_intensity > 4.0 and 0.3 < toxic_flow < 0.7:
                regime_scores[3] = 1.0
            if volume_intensity < 0.5 and spread_ratio > 2.0:
                regime_scores[4] = 1.0

            total = np.sum(regime_scores)
            if total == 0:
                regime_scores[0] = 1.0
                total = 1.0
            return regime_scores / total
        except Exception as exc:
            logger.debug(f"Regime detection failed: {exc}")
            return np.array([1.0, 0.0, 0.0, 0.0, 0.0], dtype=float)

    def _enhanced_market_impact(self, ticks: List[TickData]) -> float:
        if len(ticks) < 30:
            return super()._market_impact(ticks)
        try:
            price_changes = []
            order_flows = []
            volumes = []

            for i in range(1, len(ticks)):
                prev_tick = ticks[i - 1]
                tick = ticks[i]
                prev_price = max(prev_tick.price, 1e-8)
                price_change = (tick.price - prev_tick.price) / prev_price * 10000.0
                mid_price = (prev_tick.bid + prev_tick.ask) / 2
                if tick.price > mid_price:
                    signed_flow = tick.size
                elif tick.price < mid_price:
                    signed_flow = -tick.size
                else:
                    signed_flow = 0

                if signed_flow != 0:
                    price_changes.append(price_change)
                    order_flows.append(signed_flow)
                    volumes.append(tick.size)

            if len(price_changes) < 10:
                return super()._market_impact(ticks)

            order_flows_arr = np.asarray(order_flows, dtype=float)
            price_changes_arr = np.asarray(price_changes, dtype=float)
            volumes_arr = np.asarray(volumes, dtype=float)

            flow_std = np.std(order_flows_arr)
            price_std = np.std(price_changes_arr)
            if flow_std == 0 or price_std == 0:
                return 0.0

            valid_mask = (
                np.abs(order_flows_arr) < 3 * flow_std
            ) & (np.abs(price_changes_arr) < 3 * price_std)

            order_flows_arr = order_flows_arr[valid_mask]
            price_changes_arr = price_changes_arr[valid_mask]
            volumes_arr = volumes_arr[valid_mask]

            if order_flows_arr.size < 5:
                return super()._market_impact(ticks)

            # Use safe weighted covariance (still using numpy's cov with guard)
            try:
                weighted_cov = np.cov(order_flows_arr, price_changes_arr, fweights=volumes_arr)[0, 1]
                weighted_var = np.cov(order_flows_arr, fweights=volumes_arr)
            except (ValueError, IndexError):
                return super()._market_impact(ticks)
            
            if not np.isfinite(weighted_cov) or not np.isfinite(weighted_var) or weighted_var == 0:
                return 0.0

            kyle_lambda = weighted_cov / weighted_var
            impact_per_1000 = kyle_lambda * 1000.0
            return float(np.clip(impact_per_1000, -10.0, 10.0))
        except Exception as exc:
            logger.debug(f"Enhanced market impact calculation failed: {exc}")
            return super()._market_impact(ticks)

    def _liquidity_provision_metrics(self, ticks: List[TickData]) -> np.ndarray:
        if len(ticks) < 20:
            return np.zeros(4, dtype=float)
        try:
            aggressive_trades = 0
            passive_trades = 0
            for tick in ticks[-20:]:
                if tick.price >= tick.ask or tick.price <= tick.bid:
                    aggressive_trades += 1
                else:
                    passive_trades += 1

            total_trades = aggressive_trades + passive_trades
            if total_trades == 0:
                consumption_ratio = 0.5
            else:
                consumption_ratio = aggressive_trades / total_trades

            spread_vol = self._ensure_scalar(self._safe_compute(self._spread_volatility))
            mm_presence = 1.0 / (1.0 + spread_vol * 1000.0) if spread_vol > 0 else 0.5
            mm_presence = float(np.clip(mm_presence, 0.0, 1.0))

            adverse_risk = self._ensure_scalar(self._safe_compute(self._enhanced_toxic_flow_score, ticks))

            trade_signs = []
            for tick in ticks[-30:]:
                mid_price = (tick.bid + tick.ask) / 2
                if tick.price > mid_price:
                    trade_signs.append(1.0)
                elif tick.price < mid_price:
                    trade_signs.append(-1.0)
            if len(trade_signs) > 1:
                # Use safe_corrcoef for autocorrelation
                ts_arr = np.array(trade_signs)
                X = np.vstack([ts_arr[:-1], ts_arr[1:]]).T
                X_filtered, keep_mask = drop_constant_cols(X, eps=1e-8)
                if X_filtered.shape[1] < 2:
                    autocorr = 0.0
                else:
                    C = safe_corrcoef(X_filtered)
                    autocorr = C[0, 1]
                inventory_risk = abs(autocorr)
            else:
                inventory_risk = 0.0

            metrics = np.array(
                [
                    float(np.clip(consumption_ratio, 0.0, 1.0)),
                    mm_presence,
                    float(np.clip(adverse_risk, 0.0, 1.0)),
                    float(np.clip(inventory_risk, 0.0, 1.0)),
                ],
                dtype=float,
            )
            return metrics
        except Exception as exc:
            logger.debug(f"Liquidity provision metrics failed: {exc}")
            return np.zeros(4, dtype=float)

    def _normalize_features(self, features: np.ndarray, method: str) -> np.ndarray:
        """Normalize features with winsorization and safe z-score."""
        method_lower = method.lower()
        
        # First winsorize outliers to prevent explosion (use common utility)
        features_win = winsorize_common(features.reshape(-1, 1), p=0.005).ravel()
        
        if method_lower == "robust":
            # Apply safe z-score from common utils
            scaled = safe_zscore_common(features_win.reshape(-1, 1), axis=0).ravel()
            return validate_features(scaled, name="RobustMicrostructure")
        
        if method_lower == "minmax":
            return self._minmax_scale(features_win)
        
        return features_win

    def _robust_scale(self, features: np.ndarray) -> np.ndarray:
        """Robust scaling with safe_zscore fallback."""
        names = self.get_feature_names()
        medians = np.array([self._ROBUST_DEFAULTS.get(name, (0.0, 1.0))[0] for name in names], dtype=float)
        iqrs = np.array([self._ROBUST_DEFAULTS.get(name, (0.0, 1.0))[1] for name in names], dtype=float)
        
        # Use safe division
        iqrs = np.where(iqrs < 1e-8, 1e-8, iqrs)
        scaled = (features - medians) / iqrs
        scaled = np.clip(scaled, -5.0, 5.0)
        
        return validate_features(scaled, name="RobustMicrostructure")

    def _minmax_scale(self, features: np.ndarray) -> np.ndarray:
        """Min-max scaling with safe division."""
        names = self.get_feature_names()
        mins = np.array([self._MINMAX_DEFAULTS.get(name, (0.0, 1.0))[0] for name in names], dtype=float)
        maxs = np.array([self._MINMAX_DEFAULTS.get(name, (0.0, 1.0))[1] for name in names], dtype=float)
        
        # Use safe division
        ranges = maxs - mins
        ranges = np.where(ranges < 1e-8, 1e-8, ranges)
        scaled = (features - mins) / ranges
        scaled = np.clip(scaled, 0.0, 1.0)
        
        return validate_features(scaled, name="MinMaxMicrostructure")

class LegacyMicrostructureAdapter:
    """Adapter that projects extended microstructure features back to legacy shape."""

    def __init__(
        self,
        engine: MicrostructureFeatures,
        target_feature_names: Optional[List[str]] = None,
        *,
        pad_value: float = 0.0,
    ) -> None:
        self._engine = engine
        self._target_feature_names = target_feature_names or MicrostructureFeatures.BASE_FEATURE_NAMES
        self._target_dim = len(self._target_feature_names)
        self._pad_value = pad_value

    def compute(self) -> np.ndarray:
        features = np.asarray(self._engine.compute(), dtype=float)
        if features.size >= self._target_dim:
            return features[: self._target_dim]
        # Pad if upstream returned fewer features than expected
        padding = np.full(self._target_dim - features.size, self._pad_value, dtype=float)
        return np.concatenate([features, padding])

    def compute_dict(self) -> dict:
        values = self.compute()
        return dict(zip(self.get_feature_names(), values))

    def get_feature_names(self) -> List[str]:
        return list(self._target_feature_names)

    def __getattr__(self, item):
        """Delegate attribute access to wrapped engine."""
        return getattr(self._engine, item)

    def __repr__(self) -> str:
        return (
            "LegacyMicrostructureAdapter("
            f"engine={self._engine.__class__.__name__}, "
            f"target_dim={self._target_dim})"
        )


if __name__ == "__main__":
    # Example usage
    import logging
    from ib_insync import IB
    
    logging.basicConfig(level=logging.INFO)
    
    # Connect to IBKR
    ib = IB()
    ib.connect('127.0.0.1', 7497, clientId=1)
    
    # Create pipeline
    from src.intraday.data_pipeline import IntradayDataPipeline
    
    pipeline = IntradayDataPipeline(ib, 'SPY')
    pipeline.start()
    
    # Wait for data
    import time
    print("Collecting data for 60 seconds...")
    time.sleep(60)
    
    # Compute features
    micro = MicrostructureFeatures(pipeline)
    features = micro.compute()
    feature_dict = micro.compute_dict()
    
    print("\n📊 Microstructure Features:")
    for name, value in feature_dict.items():
        print(f"  {name:20s}: {value:10.6f}")
    
    # Cleanup
    pipeline.stop()
    ib.disconnect()
