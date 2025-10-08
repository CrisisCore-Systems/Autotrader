"""Example: Applying reliability patterns to existing data source clients."""

import asyncio
from typing import Dict, Any

# Import existing clients
from src.core.orderflow_clients import BinanceClient, BybitClient, DexscreenerClient
from src.core.twitter_client import TwitterClientV2

# Import reliability integration
from src.services.reliability import (
    reliable_cex_call,
    reliable_dex_call,
    reliable_twitter_call,
    get_system_health,
    SLA_REGISTRY,
    CIRCUIT_REGISTRY,
)


# ============================================================================
# Enhanced Client Wrappers
# ============================================================================

class ReliableBinanceClient:
    """Binance client with reliability patterns applied."""

    def __init__(self, api_key: str, api_secret: str):
        """Initialize reliable Binance client.

        Args:
            api_key: Binance API key
            api_secret: Binance API secret
        """
        self._client = BinanceClient(api_key, api_secret)

    @reliable_cex_call(
        cache_ttl=5.0,
        cache_key_func=lambda self, symbol, limit: f"binance:orderbook:{symbol}:{limit}"
    )
    async def get_order_book_depth(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """Get order book depth with monitoring, circuit breaker, and caching.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            limit: Depth limit

        Returns:
            Order book snapshot
        """
        return await self._client.get_order_book_depth(symbol, limit)

    @reliable_cex_call(
        cache_ttl=10.0,
        cache_key_func=lambda self, symbol: f"binance:funding:{symbol}"
    )
    async def get_funding_rate(self, symbol: str) -> Dict[str, Any]:
        """Get funding rate with reliability patterns.

        Args:
            symbol: Futures symbol

        Returns:
            Funding rate data
        """
        return await self._client.get_funding_rate(symbol)


class ReliableBybitClient:
    """Bybit client with reliability patterns applied."""

    def __init__(self, api_key: str, api_secret: str):
        """Initialize reliable Bybit client.

        Args:
            api_key: Bybit API key
            api_secret: Bybit API secret
        """
        self._client = BybitClient(api_key, api_secret)

    @reliable_cex_call(
        cache_ttl=10.0,
        cache_key_func=lambda self, symbol: f"bybit:derivatives:{symbol}"
    )
    async def get_derivatives_metrics(self, symbol: str) -> Dict[str, Any]:
        """Get derivatives metrics with reliability patterns.

        Args:
            symbol: Symbol to query

        Returns:
            Derivatives metrics
        """
        return await self._client.get_derivatives_metrics(symbol)


class ReliableDexscreenerClient:
    """Dexscreener client with reliability patterns applied."""

    def __init__(self):
        """Initialize reliable Dexscreener client."""
        self._client = DexscreenerClient()

    @reliable_dex_call(
        cache_ttl=30.0,
        cache_key_func=lambda self, chain_id, pair_address: f"dex:{chain_id}:{pair_address}"
    )
    async def get_pair_info(self, chain_id: str, pair_address: str) -> Dict[str, Any]:
        """Get pair info with reliability patterns.

        Args:
            chain_id: Blockchain ID
            pair_address: Pair contract address

        Returns:
            Pair information
        """
        return await self._client.get_pair_info(chain_id, pair_address)


class ReliableTwitterClient:
    """Twitter client with reliability patterns applied."""

    def __init__(self, bearer_token: str):
        """Initialize reliable Twitter client.

        Args:
            bearer_token: Twitter API bearer token
        """
        self._client = TwitterClientV2(bearer_token)

    @reliable_twitter_call(
        cache_ttl=300.0,
        cache_key_func=lambda self, query, max_results: f"twitter:search:{query}:{max_results}"
    )
    async def search_recent_tweets(
        self,
        query: str,
        max_results: int = 100,
    ) -> Dict[str, Any]:
        """Search tweets with reliability patterns.

        Args:
            query: Search query
            max_results: Max number of results

        Returns:
            Tweet search results
        """
        return await self._client.search_recent_tweets(query, max_results)


# ============================================================================
# Example Usage
# ============================================================================

async def example_reliable_data_fetching():
    """Example: Fetch data with reliability patterns applied."""
    import os

    # Initialize reliable clients
    binance = ReliableBinanceClient(
        api_key=os.getenv("BINANCE_API_KEY", ""),
        api_secret=os.getenv("BINANCE_API_SECRET", ""),
    )

    dex = ReliableDexscreenerClient()

    twitter = ReliableTwitterClient(
        bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
    )

    # Fetch data (automatically monitored, circuit-protected, cached)
    try:
        # CEX order book
        orderbook = await binance.get_order_book_depth("BTCUSDT", limit=100)
        print(f"✅ Binance orderbook: {len(orderbook.get('bids', []))} bids")

        # DEX liquidity
        pair = await dex.get_pair_info(
            chain_id="ethereum",
            pair_address="0x0d4a11d5eeaac28ec3f61d100daf4d40471f1852"  # WETH/USDT
        )
        print(f"✅ DEX pair: {pair.get('pairAddress', 'unknown')}")

        # Twitter sentiment
        tweets = await twitter.search_recent_tweets(
            query="(BTC OR Bitcoin) (bullish OR pump) -is:retweet lang:en",
            max_results=10,
        )
        print(f"✅ Twitter results: {len(tweets.get('data', []))} tweets")

    except Exception as exc:
        print(f"❌ Error: {exc}")

    # Check system health
    health = get_system_health()
    print("\n📊 System Health:")
    print(f"  Overall: {health['overall_status']}")

    print("\n  Data Sources:")
    for source, status in health["data_sources"].items():
        print(f"    {source}: {status['status']} "
              f"(p95={status.get('latency_p95', 'N/A')}s, "
              f"success={status.get('success_rate', 'N/A')})")

    print("\n  Circuit Breakers:")
    for breaker, status in health["circuit_breakers"].items():
        print(f"    {breaker}: {status['state']} "
              f"(failures={status['failure_count']})")

    print("\n  Cache Stats:")
    for cache_name, stats in health["cache_stats"].items():
        print(f"    {cache_name}: {stats['size']}/{stats['max_size']} entries, "
              f"hit_rate={stats['hit_rate']:.2%}")


async def example_circuit_breaker_recovery():
    """Example: Circuit breaker recovery after failures."""
    import os

    binance = ReliableBinanceClient(
        api_key="invalid_key",  # Force failures
        api_secret="invalid_secret",
    )

    print("🔄 Simulating circuit breaker behavior...")

    # Attempt calls until circuit opens
    for i in range(10):
        try:
            await binance.get_order_book_depth("BTCUSDT")
            print(f"  [{i+1}] ✅ Success")
        except Exception as exc:
            print(f"  [{i+1}] ❌ Failed: {exc}")

        # Check circuit breaker state
        breaker = CIRCUIT_REGISTRY.get("binance_api")
        if breaker:
            state = breaker.get_state().value
            print(f"       Circuit: {state}")

            if state == "OPEN":
                print("\n⚠️  Circuit OPEN - calls blocked for 30s")
                break

        await asyncio.sleep(1)

    # Wait for timeout
    print("\n⏳ Waiting for circuit timeout...")
    await asyncio.sleep(35)

    # Circuit should be in HALF_OPEN, testing recovery
    try:
        await binance.get_order_book_depth("BTCUSDT")
    except Exception:
        print("❌ Recovery test failed, circuit returns to OPEN")

    breaker = CIRCUIT_REGISTRY.get("binance_api")
    if breaker:
        print(f"Final circuit state: {breaker.get_state().value}")


async def example_cache_effectiveness():
    """Example: Demonstrate cache effectiveness."""
    import os
    import time

    twitter = ReliableTwitterClient(
        bearer_token=os.getenv("TWITTER_BEARER_TOKEN", ""),
    )

    query = "Bitcoin pump lang:en -is:retweet"

    print("🚀 Testing cache effectiveness...")

    # First call: cache miss
    start = time.time()
    try:
        await twitter.search_recent_tweets(query, max_results=10)
        first_duration = time.time() - start
        print(f"  First call (cache miss): {first_duration:.2f}s")
    except Exception as exc:
        print(f"  First call failed: {exc}")
        return

    # Second call: cache hit
    start = time.time()
    try:
        await twitter.search_recent_tweets(query, max_results=10)
        second_duration = time.time() - start
        print(f"  Second call (cache hit): {second_duration:.2f}s")

        speedup = first_duration / second_duration if second_duration > 0 else 0
        print(f"  🎯 Speedup: {speedup:.1f}x faster")
    except Exception as exc:
        print(f"  Second call failed: {exc}")


async def example_sla_monitoring():
    """Example: Monitor SLA compliance over time."""
    import os

    binance = ReliableBinanceClient(
        api_key=os.getenv("BINANCE_API_KEY", ""),
        api_secret=os.getenv("BINANCE_API_SECRET", ""),
    )

    print("📈 Monitoring SLA over 20 requests...")

    for i in range(20):
        try:
            await binance.get_order_book_depth("BTCUSDT")
            print(f"  [{i+1}/20] ✅")
        except Exception:
            print(f"  [{i+1}/20] ❌")

        await asyncio.sleep(0.5)

    # Check SLA status
    monitor = SLA_REGISTRY.get("binance_orderbook")
    if monitor:
        metrics = monitor.get_current_metrics()
        status = monitor.get_status()

        print(f"\n📊 SLA Report:")
        print(f"  Status: {status.value}")
        if metrics:
            print(f"  Latency P50: {metrics.latency_p50_seconds:.3f}s")
            print(f"  Latency P95: {metrics.latency_p95_seconds:.3f}s")
            print(f"  Latency P99: {metrics.latency_p99_seconds:.3f}s")
            print(f"  Success Rate: {metrics.success_rate:.1%}")
            print(f"  Uptime: {metrics.uptime_percentage:.1%}")


# ============================================================================
# Main Entry Point
# ============================================================================

async def main():
    """Run all examples."""
    print("=" * 60)
    print("RELIABILITY PATTERNS DEMONSTRATION")
    print("=" * 60)

    print("\n1️⃣  Example: Reliable Data Fetching")
    print("-" * 60)
    await example_reliable_data_fetching()

    print("\n\n2️⃣  Example: Cache Effectiveness")
    print("-" * 60)
    await example_cache_effectiveness()

    print("\n\n3️⃣  Example: SLA Monitoring")
    print("-" * 60)
    await example_sla_monitoring()

    # Uncomment to test circuit breaker recovery (takes ~35s)
    # print("\n\n4️⃣  Example: Circuit Breaker Recovery")
    # print("-" * 60)
    # await example_circuit_breaker_recovery()


if __name__ == "__main__":
    asyncio.run(main())
