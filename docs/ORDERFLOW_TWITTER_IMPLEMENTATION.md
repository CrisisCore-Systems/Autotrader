## High-Priority Blind Spot Implementation Guide

This document describes the implementation of high-priority signal coverage blind spots identified in the Signal Coverage Audit.

## Overview

We've addressed three critical blind spots to enhance VoidBloom's signal coverage:

1. **CEX/DEX Order Book Depth** - Real-time liquidity and order flow analytics
2. **Twitter API v2 Integration** - Enhanced social sentiment signals
3. **DEX Liquidity Analytics** - Cross-pool liquidity aggregation

## 1. CEX/DEX Order Book Clients

### Implemented Clients

#### `BinanceClient` (`src/core/orderflow_clients.py`)
- **Purpose**: Access Binance spot and futures market data
- **Features**:
  - Order book depth (bid/ask levels)
  - Funding rates (perpetual futures)
  - Open interest
  - 24h ticker data
- **Rate Limits**: 1200 req/min (spot), 2400 req/min (futures)
- **Authentication**: Optional API key via `BINANCE_API_KEY` environment variable

**Example Usage:**
```python
from src.core.orderflow_clients import BinanceClient

client = BinanceClient()

# Fetch order book
book = client.fetch_order_book_depth("BTCUSDT", limit=100)

# Fetch funding rate
funding = client.fetch_funding_rate("BTCUSDT")

# Fetch open interest
oi = client.fetch_open_interest("BTCUSDT")
```

#### `BybitClient` (`src/core/orderflow_clients.py`)
- **Purpose**: Access Bybit derivatives exchange data
- **Features**:
  - Order book depth
  - Funding rate history
  - Open interest by interval
- **Rate Limits**: 600 req/min
- **Authentication**: Optional API key via `BYBIT_API_KEY` environment variable

**Example Usage:**
```python
from src.core.orderflow_clients import BybitClient

client = BybitClient()

# Fetch order book
book = client.fetch_order_book("BTCUSDT", category="linear", limit=50)

# Fetch funding history
funding = client.fetch_funding_history("BTCUSDT", limit=200)
```

#### `DexscreenerClient` (`src/core/orderflow_clients.py`)
- **Purpose**: DEX aggregator for liquidity data
- **Features**:
  - Token pair information across DEXes
  - Liquidity depth and reserves
  - Volume and price changes
  - Multi-chain support
- **Rate Limits**: 300 req/min
- **Authentication**: None required

**Example Usage:**
```python
from src.core.orderflow_clients import DexscreenerClient

client = DexscreenerClient()

# Fetch all pairs for a token
pairs = client.fetch_token_pairs(
    token_address="0x...",
    chain="ethereum"
)

# Search for pairs
results = client.search_pairs("PEPE")
```

### Aggregator Services

#### `OrderFlowAggregator` (`src/services/orderflow.py`)
Aggregates order book depth from multiple CEX sources into a unified snapshot.

**Metrics Provided:**
- Best bid/ask across exchanges
- Spread in basis points
- Bid/ask depth at 1% and 2% from mid price
- Exchange-level breakdown
- Data quality score

**Example Usage:**
```python
from src.services.orderflow import OrderFlowAggregator

aggregator = OrderFlowAggregator()
snapshot = aggregator.aggregate_order_book("BTC", depth_limit=100)

print(f"Best Bid: ${snapshot.best_bid:,.2f}")
print(f"Best Ask: ${snapshot.best_ask:,.2f}")
print(f"Spread: {snapshot.spread_bps:.2f} bps")
print(f"Bid Depth (1%): {snapshot.bid_depth_1pct:,.2f} BTC")
```

#### `LiquidityAggregator` (`src/services/orderflow.py`)
Aggregates DEX liquidity metrics across pools and chains.

**Metrics Provided:**
- Total liquidity in USD
- 24h volume
- Top pools by liquidity
- Liquidity concentration (Herfindahl index)
- Pool count

**Example Usage:**
```python
from src.services.orderflow import LiquidityAggregator

aggregator = LiquidityAggregator()
snapshot = aggregator.aggregate_dex_liquidity(
    token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    token_symbol="USDC",
    chain="ethereum",
    min_liquidity_usd=50000.0,
)

print(f"Total Liquidity: ${snapshot.total_liquidity_usd:,.2f}")
print(f"24h Volume: ${snapshot.total_volume_24h_usd:,.2f}")
print(f"Pool Count: {snapshot.pool_count}")
```

#### `DerivativesAggregator` (`src/services/orderflow.py`)
Aggregates derivatives metrics (funding rates, open interest).

**Metrics Provided:**
- Annualized funding rates across exchanges
- Open interest in USD
- Per-exchange breakdown
- Data quality score

**Example Usage:**
```python
from src.services.orderflow import DerivativesAggregator

aggregator = DerivativesAggregator()
snapshot = aggregator.aggregate_derivatives_metrics("BTC")

print(f"Funding Rate (8h): {snapshot.funding_rate_8h * 100:.4f}%")
print(f"Open Interest: ${snapshot.open_interest_usd:,.2f}")
```

## 2. Twitter API v2 Integration

### Client Implementation

#### `TwitterClientV2` (`src/core/twitter_client.py`)
Full-featured Twitter API v2 client for crypto sentiment analysis.

**Features:**
- Recent tweet search (last 7 days)
- Tweet lookup with engagement metrics
- User timeline access
- Optimized query building for crypto tokens
- Automatic rate limit handling

**Authentication:**
Requires Twitter API v2 Bearer Token:
1. Create developer account at https://developer.twitter.com/
2. Create a project and app
3. Generate Bearer Token
4. Set `TWITTER_BEARER_TOKEN` environment variable

**Example Usage:**
```python
from src.core.twitter_client import TwitterClientV2

client = TwitterClientV2()  # Reads TWITTER_BEARER_TOKEN from env

# Build optimized crypto query
query = client.build_crypto_query(
    token_symbol="BTC",
    token_name="Bitcoin",
    exclude_retweets=True,
    min_likes=10,
    language="en",
)

# Search recent tweets
results = client.search_recent_tweets(
    query=query,
    max_results=100,
)

# Convenience method for sentiment analysis
signals = client.fetch_sentiment_signals(
    token_symbol="ETH",
    hours_back=24,
    max_results=100,
    min_engagement=5,
)
```

### Aggregator Service

#### `TwitterAggregator` (`src/services/twitter.py`)
High-level service for Twitter sentiment aggregation and signal extraction.

**Features:**
- Token sentiment snapshots
- Engagement metrics
- Influence scoring
- Spike detection
- Multi-token monitoring

**Metrics Provided:**
- Volume: total tweets, unique authors, verified %
- Engagement: likes, retweets, replies, quotes
- Velocity: tweets per hour
- Top influencers and tweets
- Sentiment distribution (when integrated with sentiment analyzer)

**Example Usage:**
```python
from src.services.twitter import TwitterAggregator

aggregator = TwitterAggregator()

# Aggregate sentiment for a token
snapshot = aggregator.aggregate_token_sentiment(
    token_symbol="ETH",
    include_token_name="Ethereum",
    hours_back=24,
    max_tweets=100,
    min_engagement=5,
)

print(f"Total Tweets: {snapshot.total_tweets}")
print(f"Unique Authors: {snapshot.unique_authors}")
print(f"Tweet Velocity: {snapshot.tweet_velocity:.2f} tweets/hour")
print(f"Avg Engagement: {snapshot.avg_engagement_per_tweet:.1f}")

# Detect sentiment spikes
result = aggregator.detect_sentiment_spike(
    token_symbol="DOGE",
    baseline_hours=24,
    recent_hours=1,
    spike_threshold=3.0,  # 3x baseline
)

if result['is_spike']:
    print(f"🚨 SPIKE! {result['spike_multiplier']:.1f}x baseline")

# Monitor multiple tokens
snapshots = aggregator.monitor_real_time_mentions(
    token_symbols=["BTC", "ETH", "SOL"],
)
```

## 3. Integration with Existing Pipeline

### Adding to HiddenGemScanner

To integrate these new data sources into the existing pipeline:

```python
# In src/core/pipeline.py

from src.services.orderflow import (
    OrderFlowAggregator,
    LiquidityAggregator,
    DerivativesAggregator,
)
from src.services.twitter import TwitterAggregator

class HiddenGemScanner:
    def __init__(self, ...):
        # ...existing init...
        self.orderflow_agg = OrderFlowAggregator()
        self.liquidity_agg = LiquidityAggregator()
        self.derivatives_agg = DerivativesAggregator()
        self.twitter_agg = TwitterAggregator()
    
    def _action_fetch_orderflow(self, context: ScanContext) -> NodeOutcome:
        """Fetch and store order flow metrics."""
        try:
            snapshot = self.orderflow_agg.aggregate_order_book(
                context.config.symbol,
                depth_limit=100,
            )
            context.orderflow_snapshot = snapshot
            return NodeOutcome(
                status="success",
                summary=f"Order book depth: {snapshot.total_exchanges} exchanges",
                data={
                    "spread_bps": snapshot.spread_bps,
                    "bid_depth_1pct": snapshot.bid_depth_1pct,
                    "ask_depth_1pct": snapshot.ask_depth_1pct,
                },
            )
        except Exception as exc:
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch order flow: {exc}",
                data={},
                proceed=True,
            )
    
    def _action_fetch_twitter_sentiment(self, context: ScanContext) -> NodeOutcome:
        """Fetch Twitter sentiment signals."""
        try:
            snapshot = self.twitter_agg.aggregate_token_sentiment(
                token_symbol=context.config.symbol,
                hours_back=24,
                max_tweets=100,
            )
            context.twitter_sentiment = snapshot
            return NodeOutcome(
                status="success",
                summary=f"Twitter: {snapshot.total_tweets} tweets, velocity {snapshot.tweet_velocity:.1f}/hr",
                data={
                    "total_tweets": snapshot.total_tweets,
                    "tweet_velocity": snapshot.tweet_velocity,
                    "avg_engagement": snapshot.avg_engagement_per_tweet,
                },
            )
        except Exception as exc:
            return NodeOutcome(
                status="failure",
                summary=f"Failed to fetch Twitter sentiment: {exc}",
                data={},
                proceed=True,
            )
```

### Adding to Feature Vector

Incorporate orderflow and Twitter metrics into the feature vector:

```python
def build_enhanced_feature_vector(context: ScanContext) -> Dict[str, float]:
    features = build_feature_vector(...)  # Existing features
    
    # Add order flow features
    if context.orderflow_snapshot:
        features["SpreadBPS"] = context.orderflow_snapshot.spread_bps
        features["BidDepth1pct"] = context.orderflow_snapshot.bid_depth_1pct
        features["AskDepth1pct"] = context.orderflow_snapshot.ask_depth_1pct
        features["OrderFlowQuality"] = context.orderflow_snapshot.data_quality_score
    
    # Add Twitter sentiment features
    if context.twitter_sentiment:
        features["TwitterVelocity"] = context.twitter_sentiment.tweet_velocity
        features["TwitterEngagement"] = context.twitter_sentiment.avg_engagement_per_tweet
        features["TwitterInfluencers"] = len(context.twitter_sentiment.top_influencer_usernames)
        features["TwitterVerifiedPct"] = context.twitter_sentiment.verified_author_pct
    
    # Add derivatives features
    if context.derivatives_snapshot:
        features["FundingRate"] = context.derivatives_snapshot.funding_rate_8h
        features["OpenInterest"] = context.derivatives_snapshot.open_interest_usd
    
    return features
```

## 4. Testing and Validation

### Running Examples

Two comprehensive example scripts are provided:

**Order Flow Example:**
```bash
python examples/orderflow_example.py
```

Demonstrates:
- Order book aggregation across CEXes
- DEX liquidity aggregation
- Derivatives metrics aggregation
- Direct client usage

**Twitter Example:**
```bash
python examples/twitter_example.py
```

Demonstrates:
- Basic tweet search
- Sentiment aggregation
- Spike detection
- Multi-token monitoring
- Custom query building

### Unit Tests

Create unit tests for the new clients and aggregators:

```bash
pytest tests/test_orderflow_clients.py
pytest tests/test_twitter_client.py
pytest tests/test_orderflow_aggregators.py
pytest tests/test_twitter_aggregator.py
```

## 5. Monitoring and Alerts

### SLA Metrics to Track

- **API Response Times**: Track latency for each provider
- **Data Freshness**: Time since last successful fetch
- **Data Quality Scores**: Monitor aggregated quality metrics
- **Rate Limit Usage**: Track API quota consumption

### Alert Conditions

- Order flow spread exceeds threshold (potential manipulation)
- Twitter sentiment spike detected (viral moment)
- Funding rate extreme (high leverage risk)
- Liquidity concentration above threshold (rug pull risk)

## 6. Cost Considerations

### API Quotas

- **Binance**: Free tier up to 1200 req/min
- **Bybit**: Free tier up to 600 req/min
- **Dexscreener**: Free tier up to 300 req/min
- **Twitter**: Free tier (v2 Basic) up to 500k tweets/month

### Caching Strategy

All clients use the `CachePolicy` system with appropriate TTLs:
- Order books: 5-10 seconds (highly dynamic)
- Funding rates: 60 seconds
- DEX liquidity: 30 seconds
- Twitter sentiment: 60 seconds

## 7. Next Steps

1. **Integration Testing**: Integrate new signals into production pipeline
2. **Feature Engineering**: Develop derived features from new signals
3. **Backtesting**: Validate signal effectiveness on historical data
4. **ML Model Updates**: Retrain models with enhanced feature set
5. **Dashboard Updates**: Add visualizations for new metrics
6. **Documentation**: Update API docs and runbooks

## 8. References

- Signal Coverage Audit: `docs/signal_coverage_audit.md`
- Greatness Roadmap: `docs/vision/greatness_roadmap.md`
- Provider Rate Limits: `docs/provider_rate_limits.md`
- API Documentation:
  - Binance: https://binance-docs.github.io/apidocs/
  - Bybit: https://bybit-exchange.github.io/docs/v5/intro
  - Dexscreener: https://docs.dexscreener.com/
  - Twitter: https://developer.twitter.com/en/docs/twitter-api

---

**Status**: ✅ Implementation Complete
**Last Updated**: October 7, 2025
**Owner**: VoidBloom Engineering
