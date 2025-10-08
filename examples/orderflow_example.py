"""Example usage of order flow and liquidity aggregators."""

import os
from datetime import datetime

# Set up API keys (optional, will use defaults if not set)
# os.environ["BINANCE_API_KEY"] = "your_key_here"
# os.environ["BYBIT_API_KEY"] = "your_key_here"

from src.core.orderflow_clients import BinanceClient, BybitClient, DexscreenerClient
from src.services.orderflow import (
    DerivativesAggregator,
    LiquidityAggregator,
    OrderFlowAggregator,
)


def example_order_book_aggregation():
    """Demonstrate order book depth aggregation from multiple CEXes."""
    print("=" * 80)
    print("ORDER BOOK AGGREGATION EXAMPLE")
    print("=" * 80)

    aggregator = OrderFlowAggregator()

    # Aggregate BTC order book
    snapshot = aggregator.aggregate_order_book("BTC", depth_limit=50)

    print(f"\nToken: {snapshot.token_symbol}")
    print(f"Timestamp: {snapshot.timestamp}")
    print(f"Exchanges: {snapshot.total_exchanges}")
    print(f"Data Quality: {snapshot.data_quality_score:.2f}")
    print(f"\nBest Bid: ${snapshot.best_bid:,.2f}")
    print(f"Best Ask: ${snapshot.best_ask:,.2f}")
    print(f"Spread: {snapshot.spread_bps:.2f} bps")
    print(f"\nBid Depth (1%): {snapshot.bid_depth_1pct:,.2f} BTC")
    print(f"Ask Depth (1%): {snapshot.ask_depth_1pct:,.2f} BTC")
    print(f"Bid Depth (2%): {snapshot.bid_depth_2pct:,.2f} BTC")
    print(f"Ask Depth (2%): {snapshot.ask_depth_2pct:,.2f} BTC")

    print(f"\nExchanges with data: {list(snapshot.exchange_bids.keys())}")


def example_dex_liquidity_aggregation():
    """Demonstrate DEX liquidity aggregation for a token."""
    print("\n" + "=" * 80)
    print("DEX LIQUIDITY AGGREGATION EXAMPLE")
    print("=" * 80)

    aggregator = LiquidityAggregator()

    # Example: USDC on Ethereum
    usdc_address = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

    snapshot = aggregator.aggregate_dex_liquidity(
        token_address=usdc_address,
        token_symbol="USDC",
        chain="ethereum",
        min_liquidity_usd=50000.0,
    )

    print(f"\nToken: {snapshot.token_symbol} ({snapshot.token_address})")
    print(f"Chain: {snapshot.chain}")
    print(f"Timestamp: {snapshot.timestamp}")
    print(f"Data Quality: {snapshot.data_quality_score:.2f}")
    print(f"\nTotal Liquidity: ${snapshot.total_liquidity_usd:,.2f}")
    print(f"24h Volume: ${snapshot.total_volume_24h_usd:,.2f}")
    print(f"Pool Count: {snapshot.pool_count}")
    print(f"Liquidity Concentration (HHI): {snapshot.liquidity_concentration:.4f}")

    if snapshot.top_pools:
        print(f"\nTop 5 Pools:")
        for i, pool in enumerate(snapshot.top_pools[:5], 1):
            print(f"{i}. {pool['dex']} - {pool['base_token']}/{pool['quote_token']}")
            print(f"   Liquidity: ${pool['liquidity_usd']:,.2f}")
            print(f"   24h Volume: ${pool['volume_24h_usd']:,.2f}")


def example_derivatives_aggregation():
    """Demonstrate derivatives metrics aggregation (funding rates, OI)."""
    print("\n" + "=" * 80)
    print("DERIVATIVES METRICS AGGREGATION EXAMPLE")
    print("=" * 80)

    aggregator = DerivativesAggregator()

    # Aggregate BTC derivatives metrics
    snapshot = aggregator.aggregate_derivatives_metrics("BTC")

    print(f"\nToken: {snapshot.token_symbol}")
    print(f"Timestamp: {snapshot.timestamp}")
    print(f"Data Quality: {snapshot.data_quality_score:.2f}")
    print(f"\nFunding Rate (8h, annualized): {snapshot.funding_rate_8h * 100:.4f}%")

    if snapshot.funding_rate_sources:
        print(f"\nFunding Rate Sources:")
        for exchange, rate in snapshot.funding_rate_sources.items():
            print(f"  {exchange}: {rate * 100:.4f}% annually")

    print(f"\nOpen Interest: ${snapshot.open_interest_usd:,.2f}")
    print(f"OI Change (24h): {snapshot.open_interest_change_24h:+.2f}%")


def example_direct_client_usage():
    """Demonstrate direct usage of individual clients."""
    print("\n" + "=" * 80)
    print("DIRECT CLIENT USAGE EXAMPLES")
    print("=" * 80)

    # Binance client
    print("\n--- Binance Funding Rate ---")
    binance = BinanceClient()
    funding = binance.fetch_funding_rate("BTCUSDT")
    if funding:
        latest = funding[-1]
        print(f"Symbol: {latest.get('symbol')}")
        print(f"Funding Rate: {float(latest.get('fundingRate', 0)) * 100:.4f}%")
        print(f"Funding Time: {latest.get('fundingTime')}")

    # Dexscreener client
    print("\n--- Dexscreener Token Pairs ---")
    dex = DexscreenerClient()

    # Example: Search for PEPE
    results = dex.search_pairs("PEPE")
    pairs = results.get("pairs", [])[:3]

    if pairs:
        for pair in pairs:
            print(f"\nDEX: {pair.get('dexId')}")
            print(f"Pair: {pair.get('baseToken', {}).get('symbol')}/{pair.get('quoteToken', {}).get('symbol')}")
            print(f"Price USD: ${pair.get('priceUsd', '0')}")
            liquidity = pair.get("liquidity", {}).get("usd", 0)
            print(f"Liquidity: ${liquidity:,.2f}")


if __name__ == "__main__":
    try:
        example_order_book_aggregation()
    except Exception as e:
        print(f"Error in order book aggregation: {e}")

    try:
        example_dex_liquidity_aggregation()
    except Exception as e:
        print(f"Error in DEX liquidity aggregation: {e}")

    try:
        example_derivatives_aggregation()
    except Exception as e:
        print(f"Error in derivatives aggregation: {e}")

    try:
        example_direct_client_usage()
    except Exception as e:
        print(f"Error in direct client usage: {e}")

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)
