"""Cross-exchange feature engineering for dislocation detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from scipy import stats

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CrossExchangeFeatures:
    """Features derived from cross-exchange analysis."""

    # Price dislocation features
    price_dispersion: float  # Coefficient of variation of prices
    max_price_spread_bps: float  # Maximum spread between exchanges in bps
    min_price_spread_bps: float  # Minimum spread between exchanges in bps
    price_entropy: float  # Shannon entropy of price distribution

    # Arbitrage features
    best_arb_opportunity_bps: float  # Best arbitrage profit in bps
    arb_opportunity_count: int  # Number of profitable arb opportunities
    avg_arb_profit_bps: float  # Average arbitrage profit

    # Volume-weighted features
    vw_price_dispersion: float  # Volume-weighted price dispersion
    volume_concentration: float  # Herfindahl index of volume distribution

    # Temporal features
    price_sync_correlation: float  # Correlation of price movements
    lead_lag_coefficient: float  # Lead-lag relationship strength
    dominant_exchange: Optional[str]  # Exchange with highest liquidity

    # Order book depth features
    depth_imbalance_ratio: float  # Ratio of max to min depth
    consolidated_spread_bps: float  # Weighted average spread

    # Volatility features
    cross_exchange_vol_ratio: float  # Ratio of highest to lowest volatility
    vol_dispersion: float  # Standard deviation of volatilities

    timestamp: float


class CrossExchangeFeatureExtractor:
    """Extract features from multiple exchange order books."""

    def __init__(
        self,
        lookback_window: int = 100,
        price_history_size: int = 1000,
    ) -> None:
        """
        Initialize feature extractor.

        Args:
            lookback_window: Window size for rolling calculations
            price_history_size: Size of price history buffer per exchange
        """
        self.lookback_window = lookback_window
        self.price_history_size = price_history_size

        # Price history per exchange
        self.price_history: Dict[str, List[float]] = {}
        self.volume_history: Dict[str, List[float]] = {}
        self.timestamp_history: Dict[str, List[float]] = {}

    def update(
        self,
        exchange_name: str,
        mid_price: float,
        volume: float,
        timestamp: float,
    ) -> None:
        """
        Update price history for an exchange.

        Args:
            exchange_name: Name of the exchange
            mid_price: Mid price (bid+ask)/2
            volume: Total volume at top of book
            timestamp: Timestamp of update
        """
        if exchange_name not in self.price_history:
            self.price_history[exchange_name] = []
            self.volume_history[exchange_name] = []
            self.timestamp_history[exchange_name] = []

        self.price_history[exchange_name].append(mid_price)
        self.volume_history[exchange_name].append(volume)
        self.timestamp_history[exchange_name].append(timestamp)

        # Trim to max size
        if len(self.price_history[exchange_name]) > self.price_history_size:
            self.price_history[exchange_name] = self.price_history[exchange_name][
                -self.price_history_size :
            ]
            self.volume_history[exchange_name] = self.volume_history[exchange_name][
                -self.price_history_size :
            ]
            self.timestamp_history[exchange_name] = self.timestamp_history[exchange_name][
                -self.price_history_size :
            ]

    def extract_features(
        self,
        current_books: Dict[str, Dict],
        arb_opportunities: List[Dict],
    ) -> Optional[CrossExchangeFeatures]:
        """
        Extract cross-exchange features.

        Args:
            current_books: Current order books from all exchanges
                Format: {exchange: {"best_bid": float, "best_ask": float, ...}}
            arb_opportunities: List of arbitrage opportunities

        Returns:
            CrossExchangeFeatures or None if insufficient data
        """
        if len(current_books) < 2:
            return None

        exchanges = list(current_books.keys())
        prices = []
        spreads = []
        volumes = []
        depths = []

        # Collect current metrics
        for exchange in exchanges:
            book = current_books[exchange]
            mid_price = (book["best_bid"] + book["best_ask"]) / 2
            spread = book["best_ask"] - book["best_bid"]
            volume = book.get("bid_size", 0) + book.get("ask_size", 0)
            depth = min(book.get("bid_size", 0), book.get("ask_size", 0))

            prices.append(mid_price)
            spreads.append(spread)
            volumes.append(volume)
            depths.append(depth)

        prices = np.array(prices)
        spreads = np.array(spreads)
        volumes = np.array(volumes)
        depths = np.array(depths)

        # Price dispersion
        price_mean = np.mean(prices)
        price_std = np.std(prices)
        price_dispersion = price_std / price_mean if price_mean > 0 else 0.0

        # Price spreads in bps
        max_price_spread_bps = ((np.max(prices) / np.min(prices)) - 1) * 10000
        min_price_spread_bps = ((np.min(prices) / price_mean) - 1) * 10000 if price_mean > 0 else 0

        # Price entropy
        price_probs = prices / np.sum(prices)
        price_entropy = -np.sum(price_probs * np.log(price_probs + 1e-10))

        # Arbitrage features
        if arb_opportunities:
            best_arb = max([opp["profit_bps"] for opp in arb_opportunities])
            avg_arb = np.mean([opp["profit_bps"] for opp in arb_opportunities])
            arb_count = len(arb_opportunities)
        else:
            best_arb = 0.0
            avg_arb = 0.0
            arb_count = 0

        # Volume-weighted features
        total_volume = np.sum(volumes)
        if total_volume > 0:
            volume_weights = volumes / total_volume
            vw_prices = prices * volume_weights
            vw_price_mean = np.sum(vw_prices)
            vw_price_std = np.sqrt(np.sum(volume_weights * (prices - vw_price_mean) ** 2))
            vw_price_dispersion = vw_price_std / vw_price_mean if vw_price_mean > 0 else 0.0

            # Herfindahl index (concentration)
            volume_concentration = np.sum(volume_weights ** 2)
        else:
            vw_price_dispersion = 0.0
            volume_concentration = 1.0 / len(exchanges)

        # Temporal correlation (if we have history)
        price_sync_correlation = 0.0
        lead_lag_coefficient = 0.0

        if len(exchanges) >= 2:
            # Get recent price history for correlation
            histories = []
            for exchange in exchanges[:2]:  # Compare first two exchanges
                if exchange in self.price_history and len(self.price_history[exchange]) >= self.lookback_window:
                    histories.append(self.price_history[exchange][-self.lookback_window :])

            if len(histories) == 2:
                # Calculate correlation
                corr = np.corrcoef(histories[0], histories[1])[0, 1]
                price_sync_correlation = corr if not np.isnan(corr) else 0.0

                # Calculate lead-lag with cross-correlation
                try:
                    cross_corr = np.correlate(
                        histories[0] - np.mean(histories[0]),
                        histories[1] - np.mean(histories[1]),
                        mode="same",
                    )
                    lead_lag_coefficient = float(np.max(np.abs(cross_corr)))
                except Exception:
                    lead_lag_coefficient = 0.0

        # Dominant exchange (by volume)
        dominant_idx = np.argmax(volumes)
        dominant_exchange = exchanges[dominant_idx]

        # Order book depth features
        depth_imbalance_ratio = np.max(depths) / (np.min(depths) + 1e-10)

        # Consolidated spread (volume-weighted)
        if total_volume > 0:
            consolidated_spread = np.sum((spreads / prices) * volume_weights) * 10000  # bps
        else:
            consolidated_spread = np.mean(spreads / prices) * 10000

        # Volatility features (from recent history)
        volatilities = []
        for exchange in exchanges:
            if exchange in self.price_history and len(self.price_history[exchange]) >= self.lookback_window:
                recent_prices = self.price_history[exchange][-self.lookback_window :]
                returns = np.diff(np.log(recent_prices))
                vol = np.std(returns) if len(returns) > 0 else 0.0
                volatilities.append(vol)

        if volatilities:
            vol_array = np.array(volatilities)
            cross_exchange_vol_ratio = np.max(vol_array) / (np.min(vol_array) + 1e-10)
            vol_dispersion = np.std(vol_array)
        else:
            cross_exchange_vol_ratio = 1.0
            vol_dispersion = 0.0

        return CrossExchangeFeatures(
            price_dispersion=float(price_dispersion),
            max_price_spread_bps=float(max_price_spread_bps),
            min_price_spread_bps=float(min_price_spread_bps),
            price_entropy=float(price_entropy),
            best_arb_opportunity_bps=float(best_arb),
            arb_opportunity_count=int(arb_count),
            avg_arb_profit_bps=float(avg_arb),
            vw_price_dispersion=float(vw_price_dispersion),
            volume_concentration=float(volume_concentration),
            price_sync_correlation=float(price_sync_correlation),
            lead_lag_coefficient=float(lead_lag_coefficient),
            dominant_exchange=dominant_exchange,
            depth_imbalance_ratio=float(depth_imbalance_ratio),
            consolidated_spread_bps=float(consolidated_spread),
            cross_exchange_vol_ratio=float(cross_exchange_vol_ratio),
            vol_dispersion=float(vol_dispersion),
            timestamp=current_books[exchanges[0]]["timestamp"],
        )

    def to_dict(self, features: CrossExchangeFeatures) -> Dict[str, float]:
        """Convert features to dictionary for ML training."""
        return {
            "price_dispersion": features.price_dispersion,
            "max_price_spread_bps": features.max_price_spread_bps,
            "min_price_spread_bps": features.min_price_spread_bps,
            "price_entropy": features.price_entropy,
            "best_arb_opportunity_bps": features.best_arb_opportunity_bps,
            "arb_opportunity_count": float(features.arb_opportunity_count),
            "avg_arb_profit_bps": features.avg_arb_profit_bps,
            "vw_price_dispersion": features.vw_price_dispersion,
            "volume_concentration": features.volume_concentration,
            "price_sync_correlation": features.price_sync_correlation,
            "lead_lag_coefficient": features.lead_lag_coefficient,
            "depth_imbalance_ratio": features.depth_imbalance_ratio,
            "consolidated_spread_bps": features.consolidated_spread_bps,
            "cross_exchange_vol_ratio": features.cross_exchange_vol_ratio,
            "vol_dispersion": features.vol_dispersion,
        }
