"""Aggregators for order flow, liquidity depth, and derivatives metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.orderflow_clients import BinanceClient, BybitClient, DexscreenerClient


@dataclass
class OrderBookSnapshot:
    """Snapshot of aggregated order book depth across exchanges."""

    token_symbol: str
    timestamp: datetime

    # Bid/Ask data
    best_bid: float
    best_ask: float
    spread_bps: float  # Basis points

    # Depth metrics (cumulative volume at various % from mid)
    bid_depth_1pct: float  # Volume within 1% of mid price
    ask_depth_1pct: float
    bid_depth_2pct: float
    ask_depth_2pct: float

    # Exchange breakdown
    exchange_bids: Dict[str, List[tuple[float, float]]] = field(default_factory=dict)
    exchange_asks: Dict[str, List[tuple[float, float]]] = field(default_factory=dict)

    # Metadata
    total_exchanges: int = 0
    data_quality_score: float = 1.0  # 0-1, penalized for stale or missing data


@dataclass
class LiquiditySnapshot:
    """DEX liquidity aggregated across pools and chains."""

    token_address: str
    token_symbol: str
    timestamp: datetime
    chain: str

    # Aggregate liquidity
    total_liquidity_usd: float
    total_volume_24h_usd: float

    # Top pools
    top_pools: List[Dict[str, Any]] = field(default_factory=list)

    # Pool concentration (Herfindahl index for liquidity)
    liquidity_concentration: float = 0.0

    # Metadata
    pool_count: int = 0
    data_quality_score: float = 1.0


@dataclass
class DerivativesSnapshot:
    """Aggregated derivatives metrics (funding, OI, etc.)."""

    token_symbol: str
    timestamp: datetime

    # Funding rates
    funding_rate_8h: float  # Annualized funding rate
    funding_rate_sources: Dict[str, float] = field(default_factory=dict)

    # Open interest
    open_interest_usd: float = 0.0
    open_interest_change_24h: float = 0.0

    # Liquidations (if available)
    liquidations_24h_usd: float = 0.0
    long_liquidations_pct: float = 0.0

    # Options (if available)
    put_call_ratio: Optional[float] = None
    implied_volatility: Optional[float] = None

    # Metadata
    data_quality_score: float = 1.0


class OrderFlowAggregator:
    """Aggregates order book depth from multiple CEX sources."""

    def __init__(
        self,
        binance_client: Optional[BinanceClient] = None,
        bybit_client: Optional[BybitClient] = None,
    ) -> None:
        """Initialize with exchange clients.

        Args:
            binance_client: Optional Binance client
            bybit_client: Optional Bybit client
        """
        self.binance = binance_client or BinanceClient()
        self.bybit = bybit_client or BybitClient()

    def aggregate_order_book(
        self,
        token_symbol: str,
        *,
        depth_limit: int = 100,
    ) -> OrderBookSnapshot:
        """Aggregate order book depth from all available exchanges.

        Args:
            token_symbol: Trading symbol (e.g., "BTC", "ETH")
            depth_limit: Number of levels to fetch per exchange

        Returns:
            OrderBookSnapshot with aggregated depth metrics
        """
        timestamp = datetime.utcnow()
        symbol_usdt = f"{token_symbol.upper()}USDT"

        exchange_bids: Dict[str, List[tuple[float, float]]] = {}
        exchange_asks: Dict[str, List[tuple[float, float]]] = {}

        # Fetch from Binance
        try:
            binance_book = self.binance.fetch_order_book_depth(symbol_usdt, limit=depth_limit)
            if "bids" in binance_book and "asks" in binance_book:
                exchange_bids["binance"] = [(float(p), float(q)) for p, q in binance_book["bids"]]
                exchange_asks["binance"] = [(float(p), float(q)) for p, q in binance_book["asks"]]
        except Exception as e:
            print(f"Warning: Failed to fetch Binance order book: {e}")

        # Fetch from Bybit
        try:
            bybit_book = self.bybit.fetch_order_book(symbol_usdt, limit=depth_limit)
            if bybit_book.get("retCode") == 0:
                result = bybit_book.get("result", {})
                bids = result.get("b", [])
                asks = result.get("a", [])
                if bids:
                    exchange_bids["bybit"] = [(float(p), float(q)) for p, q in bids]
                if asks:
                    exchange_asks["bybit"] = [(float(p), float(q)) for p, q in asks]
        except Exception as e:
            print(f"Warning: Failed to fetch Bybit order book: {e}")

        # Calculate aggregate metrics
        all_bids: List[tuple[float, float]] = []
        all_asks: List[tuple[float, float]] = []

        for bids in exchange_bids.values():
            all_bids.extend(bids)
        for asks in exchange_asks.values():
            all_asks.extend(asks)

        if not all_bids or not all_asks:
            # Return empty snapshot if no data
            return OrderBookSnapshot(
                token_symbol=token_symbol,
                timestamp=timestamp,
                best_bid=0.0,
                best_ask=0.0,
                spread_bps=0.0,
                bid_depth_1pct=0.0,
                ask_depth_1pct=0.0,
                bid_depth_2pct=0.0,
                ask_depth_2pct=0.0,
                exchange_bids=exchange_bids,
                exchange_asks=exchange_asks,
                total_exchanges=0,
                data_quality_score=0.0,
            )

        # Sort bids (descending) and asks (ascending)
        all_bids.sort(key=lambda x: x[0], reverse=True)
        all_asks.sort(key=lambda x: x[0])

        best_bid = all_bids[0][0]
        best_ask = all_asks[0][0]
        mid_price = (best_bid + best_ask) / 2
        spread_bps = ((best_ask - best_bid) / mid_price) * 10000

        # Calculate depth within % ranges
        bid_depth_1pct = sum(q for p, q in all_bids if p >= mid_price * 0.99)
        ask_depth_1pct = sum(q for p, q in all_asks if p <= mid_price * 1.01)
        bid_depth_2pct = sum(q for p, q in all_bids if p >= mid_price * 0.98)
        ask_depth_2pct = sum(q for p, q in all_asks if p <= mid_price * 1.02)

        return OrderBookSnapshot(
            token_symbol=token_symbol,
            timestamp=timestamp,
            best_bid=best_bid,
            best_ask=best_ask,
            spread_bps=spread_bps,
            bid_depth_1pct=bid_depth_1pct,
            ask_depth_1pct=ask_depth_1pct,
            bid_depth_2pct=bid_depth_2pct,
            ask_depth_2pct=ask_depth_2pct,
            exchange_bids=exchange_bids,
            exchange_asks=exchange_asks,
            total_exchanges=len(exchange_bids),
            data_quality_score=1.0 if len(exchange_bids) >= 2 else 0.5,
        )


class LiquidityAggregator:
    """Aggregates DEX liquidity metrics across pools."""

    def __init__(
        self,
        dexscreener_client: Optional[DexscreenerClient] = None,
    ) -> None:
        """Initialize with DEX data clients.

        Args:
            dexscreener_client: Optional Dexscreener client
        """
        self.dexscreener = dexscreener_client or DexscreenerClient()

    def aggregate_dex_liquidity(
        self,
        token_address: str,
        token_symbol: str,
        *,
        chain: str = "ethereum",
        min_liquidity_usd: float = 10000.0,
    ) -> LiquiditySnapshot:
        """Aggregate liquidity across DEX pools.

        Args:
            token_address: Token contract address
            token_symbol: Token symbol for display
            chain: Blockchain name
            min_liquidity_usd: Minimum pool liquidity to include

        Returns:
            LiquiditySnapshot with aggregated metrics
        """
        timestamp = datetime.utcnow()

        try:
            data = self.dexscreener.fetch_token_pairs(token_address, chain=chain)
            pairs = data.get("pairs", [])

            if not pairs:
                return LiquiditySnapshot(
                    token_address=token_address,
                    token_symbol=token_symbol,
                    timestamp=timestamp,
                    chain=chain,
                    total_liquidity_usd=0.0,
                    total_volume_24h_usd=0.0,
                    pool_count=0,
                    data_quality_score=0.0,
                )

            # Filter and process pools
            valid_pools: List[Dict[str, Any]] = []
            total_liquidity = 0.0
            total_volume = 0.0

            for pair in pairs:
                liquidity = pair.get("liquidity", {}).get("usd", 0)
                if liquidity and liquidity >= min_liquidity_usd:
                    volume_24h = pair.get("volume", {}).get("h24", 0) or 0

                    valid_pools.append({
                        "dex": pair.get("dexId", "unknown"),
                        "pair_address": pair.get("pairAddress", ""),
                        "base_token": pair.get("baseToken", {}).get("symbol", ""),
                        "quote_token": pair.get("quoteToken", {}).get("symbol", ""),
                        "liquidity_usd": liquidity,
                        "volume_24h_usd": volume_24h,
                        "price_usd": pair.get("priceUsd", "0"),
                        "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
                    })

                    total_liquidity += liquidity
                    total_volume += volume_24h

            # Sort by liquidity
            valid_pools.sort(key=lambda x: x["liquidity_usd"], reverse=True)

            # Calculate liquidity concentration (Herfindahl index)
            concentration = 0.0
            if total_liquidity > 0:
                for pool in valid_pools:
                    share = pool["liquidity_usd"] / total_liquidity
                    concentration += share ** 2

            return LiquiditySnapshot(
                token_address=token_address,
                token_symbol=token_symbol,
                timestamp=timestamp,
                chain=chain,
                total_liquidity_usd=total_liquidity,
                total_volume_24h_usd=total_volume,
                top_pools=valid_pools[:10],  # Top 10 pools
                liquidity_concentration=concentration,
                pool_count=len(valid_pools),
                data_quality_score=1.0 if len(valid_pools) > 0 else 0.0,
            )

        except Exception as e:
            print(f"Warning: Failed to aggregate DEX liquidity: {e}")
            return LiquiditySnapshot(
                token_address=token_address,
                token_symbol=token_symbol,
                timestamp=timestamp,
                chain=chain,
                total_liquidity_usd=0.0,
                total_volume_24h_usd=0.0,
                pool_count=0,
                data_quality_score=0.0,
            )


class DerivativesAggregator:
    """Aggregates derivatives metrics (funding, OI, liquidations)."""

    def __init__(
        self,
        binance_client: Optional[BinanceClient] = None,
        bybit_client: Optional[BybitClient] = None,
    ) -> None:
        """Initialize with exchange clients.

        Args:
            binance_client: Optional Binance client
            bybit_client: Optional Bybit client
        """
        self.binance = binance_client or BinanceClient()
        self.bybit = bybit_client or BybitClient()

    def aggregate_derivatives_metrics(
        self,
        token_symbol: str,
    ) -> DerivativesSnapshot:
        """Aggregate funding rates and open interest.

        Args:
            token_symbol: Trading symbol (e.g., "BTC", "ETH")

        Returns:
            DerivativesSnapshot with aggregated metrics
        """
        timestamp = datetime.utcnow()
        symbol_usdt = f"{token_symbol.upper()}USDT"

        funding_rates: Dict[str, float] = {}
        open_interest_usd = 0.0

        # Fetch Binance funding rate
        try:
            binance_funding = self.binance.fetch_funding_rate(symbol_usdt)
            if binance_funding:
                latest = binance_funding[-1]  # Most recent
                rate = float(latest.get("fundingRate", 0))
                # Convert to annualized rate (funding every 8h = 3x daily)
                funding_rates["binance"] = rate * 3 * 365
        except Exception as e:
            print(f"Warning: Failed to fetch Binance funding rate: {e}")

        # Fetch Binance open interest
        try:
            binance_oi = self.binance.fetch_open_interest(symbol_usdt)
            if "openInterest" in binance_oi:
                open_interest_usd += float(binance_oi["openInterest"])
        except Exception as e:
            print(f"Warning: Failed to fetch Binance open interest: {e}")

        # Fetch Bybit funding rate
        try:
            bybit_funding = self.bybit.fetch_funding_history(symbol_usdt, limit=1)
            if bybit_funding.get("retCode") == 0:
                result = bybit_funding.get("result", {})
                items = result.get("list", [])
                if items:
                    rate = float(items[0].get("fundingRate", 0))
                    funding_rates["bybit"] = rate * 3 * 365
        except Exception as e:
            print(f"Warning: Failed to fetch Bybit funding rate: {e}")

        # Calculate average funding rate
        avg_funding = sum(funding_rates.values()) / len(funding_rates) if funding_rates else 0.0

        return DerivativesSnapshot(
            token_symbol=token_symbol,
            timestamp=timestamp,
            funding_rate_8h=avg_funding,
            funding_rate_sources=funding_rates,
            open_interest_usd=open_interest_usd,
            open_interest_change_24h=0.0,  # Would need historical data
            liquidations_24h_usd=0.0,  # Requires additional endpoints
            long_liquidations_pct=0.0,
            data_quality_score=1.0 if funding_rates else 0.0,
        )
