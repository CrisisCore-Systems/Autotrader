"""Service for derivatives market data analysis and monitoring."""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio
import numpy as np
import pandas as pd

from src.core.derivatives_client import DerivativesClient
from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class FundingRateData:
    """Funding rate data for a symbol."""
    exchange: str
    symbol: str
    funding_rate: float
    mark_price: float
    index_price: Optional[float]
    timestamp: datetime


@dataclass
class OpenInterestData:
    """Open interest data for a symbol."""
    exchange: str
    symbol: str
    open_interest: float
    timestamp: datetime


@dataclass
class LiquidationEvent:
    """Liquidation event data."""
    exchange: str
    symbol: str
    side: str  # "LONG" or "SHORT"
    price: float
    quantity: float
    average_price: float
    timestamp: datetime


@dataclass
class DerivativesSnapshot:
    """Complete derivatives data snapshot for a symbol."""
    symbol: str
    funding_rates: Dict[str, FundingRateData] = None
    open_interest: Dict[str, OpenInterestData] = None
    recent_liquidations: List[LiquidationEvent] = None
    liquidation_spike_detected: bool = False
    spike_severity: str = "none"  # "none", "moderate", "high", "extreme"

    def __post_init__(self):
        if self.funding_rates is None:
            self.funding_rates = {}
        if self.open_interest is None:
            self.open_interest = {}
        if self.recent_liquidations is None:
            self.recent_liquidations = []


class DerivativesAggregator:
    """Aggregator for derivatives market data across multiple exchanges."""

    # Exchanges to monitor
    SUPPORTED_EXCHANGES = ["binance", "bybit", "kraken", "huobi", "okx"]

    # Liquidation spike thresholds (in USD equivalent)
    SPIKE_THRESHOLDS = {
        "moderate": 100000,   # $100k
        "high": 500000,       # $500k
        "extreme": 1000000    # $1M
    }

    def __init__(self, client: Optional[DerivativesClient] = None):
        self.client = client or DerivativesClient()
        self._cache: Dict[str, DerivativesSnapshot] = {}
        self._cache_timestamp: Dict[str, datetime] = {}

    async def get_derivatives_snapshot(
        self,
        symbol: str,
        force_refresh: bool = False,
        cache_ttl_seconds: int = 300
    ) -> DerivativesSnapshot:
        """Get complete derivatives snapshot for a symbol."""
        cache_key = symbol.upper()

        # Check cache
        if not force_refresh and cache_key in self._cache:
            cache_time = self._cache_timestamp.get(cache_key)
            if cache_time and (datetime.now() - cache_time).seconds < cache_ttl_seconds:
                return self._cache[cache_key]

        # Collect data from all exchanges
        snapshot = DerivativesSnapshot(symbol=symbol)

        # Collect funding rates
        funding_tasks = [
            self.client.get_funding_rate(exchange, symbol)
            for exchange in self.SUPPORTED_EXCHANGES
        ]
        funding_results = await asyncio.gather(*funding_tasks, return_exceptions=True)

        for i, result in enumerate(funding_results):
            exchange = self.SUPPORTED_EXCHANGES[i]
            if isinstance(result, Exception):
                logger.warning(f"Failed to get funding rate for {exchange}:{symbol}: {result}")
                continue
            if result:
                funding_data = FundingRateData(**result)
                snapshot.funding_rates[exchange] = funding_data

        # Collect open interest
        oi_tasks = [
            self.client.get_open_interest(exchange, symbol)
            for exchange in self.SUPPORTED_EXCHANGES
        ]
        oi_results = await asyncio.gather(*oi_tasks, return_exceptions=True)

        for i, result in enumerate(oi_results):
            exchange = self.SUPPORTED_EXCHANGES[i]
            if isinstance(result, Exception):
                logger.warning(f"Failed to get open interest for {exchange}:{symbol}: {result}")
                continue
            if result:
                oi_data = OpenInterestData(**result)
                snapshot.open_interest[exchange] = oi_data

        # Collect liquidations and detect spikes
        liq_tasks = [
            self.client.get_liquidations(exchange, symbol, limit=50)
            for exchange in self.SUPPORTED_EXCHANGES
        ]
        liq_results = await asyncio.gather(*liq_tasks, return_exceptions=True)

        total_liq_value = 0.0
        for i, result in enumerate(liq_results):
            exchange = self.SUPPORTED_EXCHANGES[i]
            if isinstance(result, Exception):
                logger.warning(f"Failed to get liquidations for {exchange}:{symbol}: {result}")
                continue
            if result:
                for liq_data in result:
                    liq_event = LiquidationEvent(**liq_data)
                    snapshot.recent_liquidations.append(liq_event)
                    # Calculate liquidation value (price * quantity)
                    total_liq_value += liq_event.price * liq_event.quantity

        # Detect liquidation spikes
        snapshot.liquidation_spike_detected, snapshot.spike_severity = self._detect_liquidation_spike(total_liq_value)

        # Cache the result
        self._cache[cache_key] = snapshot
        self._cache_timestamp[cache_key] = datetime.now()

        return snapshot

    def _detect_liquidation_spike(self, total_liquidation_value: float) -> Tuple[bool, str]:
        """Detect if there's a liquidation spike based on total value."""
        if total_liquidation_value >= self.SPIKE_THRESHOLDS["extreme"]:
            return True, "extreme"
        elif total_liquidation_value >= self.SPIKE_THRESHOLDS["high"]:
            return True, "high"
        elif total_liquidation_value >= self.SPIKE_THRESHOLDS["moderate"]:
            return True, "moderate"
        else:
            return False, "none"

    async def get_funding_rate_anomalies(
        self,
        symbols: List[str],
        lookback_hours: int = 24
    ) -> Dict[str, Dict[str, Any]]:
        """Detect funding rate anomalies across symbols."""
        anomalies = {}

        for symbol in symbols:
            try:
                snapshot = await self.get_derivatives_snapshot(symbol)

                # Calculate average funding rate across exchanges
                funding_rates = [
                    fr.funding_rate for fr in snapshot.funding_rates.values()
                    if fr.funding_rate is not None
                ]

                if not funding_rates:
                    continue

                avg_funding_rate = np.mean(funding_rates)
                std_funding_rate = np.std(funding_rates) if len(funding_rates) > 1 else 0

                # Check for anomalies (rates > 2 standard deviations from mean)
                anomaly_threshold = 2 * std_funding_rate if std_funding_rate > 0 else 0.001

                high_anomalies = [
                    exchange for exchange, fr in snapshot.funding_rates.items()
                    if abs(fr.funding_rate - avg_funding_rate) > anomaly_threshold
                ]

                if high_anomalies:
                    anomalies[symbol] = {
                        "average_rate": avg_funding_rate,
                        "anomalous_exchanges": high_anomalies,
                        "severity": "high" if len(high_anomalies) > 1 else "moderate"
                    }

            except Exception as e:
                logger.error(f"Error analyzing funding rates for {symbol}: {e}")
                continue

        return anomalies

    async def get_open_interest_changes(
        self,
        symbols: List[str],
        compare_hours: int = 1
    ) -> Dict[str, Dict[str, Any]]:
        """Track significant open interest changes."""
        changes = {}

        for symbol in symbols:
            try:
                # Get current OI
                current_snapshot = await self.get_derivatives_snapshot(symbol)

                # For now, just return current OI data
                # In a full implementation, you'd compare with historical data
                total_oi = sum(
                    oi.open_interest for oi in current_snapshot.open_interest.values()
                )

                changes[symbol] = {
                    "total_open_interest": total_oi,
                    "exchanges": len(current_snapshot.open_interest),
                    "timestamp": datetime.now()
                }

            except Exception as e:
                logger.error(f"Error getting OI changes for {symbol}: {e}")
                continue

        return changes

    def get_supported_exchanges(self) -> List[str]:
        """Get list of supported exchanges."""
        return self.SUPPORTED_EXCHANGES.copy()

    def set_spike_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Update liquidation spike detection thresholds."""
        self.SPIKE_THRESHOLDS.update(thresholds)