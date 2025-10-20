# Quick Start Guide: New Signal Sources

## Overview

AutoTrader now supports three new high-priority signal sources:
1. **CEX/DEX Order Flow** - Real-time liquidity and market depth
2. **Twitter API v2** - Enhanced social sentiment signals
3. **Derivatives Metrics** - Funding rates and open interest

## Prerequisites

### Required Python Packages
All dependencies are included in `requirements.txt`. No additional packages needed.

### Optional API Keys

#### For Order Flow (Optional)
- **Binance API Key**: Free public access available, key only needed for authenticated endpoints
  - Get at: https://www.binance.com/en/my/settings/api-management
  - Set: `BINANCE_API_KEY=your_key` in `.env`

- **Bybit API Key**: Free public access available
  - Get at: https://www.bybit.com/app/user/api-management
  - Set: `BYBIT_API_KEY=your_key` in `.env`

#### For Twitter (Required)
- **Twitter Bearer Token**: Required for Twitter API v2
  - Get at: https://developer.twitter.com/en/portal/dashboard
  - Free tier: 500k tweets/month
  - Set: `TWITTER_BEARER_TOKEN=your_token` in `.env`

## Quick Start Examples

### 1. Order Flow Analysis

```python
from src.services.orderflow import OrderFlowAggregator

# Initialize aggregator (no API key needed for basic usage)
aggregator = OrderFlowAggregator()

# Get BTC order book depth across exchanges
snapshot = aggregator.aggregate_order_book("BTC", depth_limit=100)

print(f"Spread: {snapshot.spread_bps:.2f} bps")
print(f"Bid Depth (1%): {snapshot.bid_depth_1pct:.2f} BTC")
print(f"Exchanges: {snapshot.total_exchanges}")
```

### 2. DEX Liquidity Analysis

```python
from src.services.orderflow import LiquidityAggregator

aggregator = LiquidityAggregator()

# Analyze USDC liquidity on Ethereum
snapshot = aggregator.aggregate_dex_liquidity(
    token_address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    token_symbol="USDC",
    chain="ethereum",
)

print(f"Total Liquidity: ${snapshot.total_liquidity_usd:,.2f}")
print(f"24h Volume: ${snapshot.total_volume_24h_usd:,.2f}")
print(f"Pool Count: {snapshot.pool_count}")
```

### 3. Derivatives Metrics

```python
from src.services.orderflow import DerivativesAggregator

aggregator = DerivativesAggregator()

# Get funding rates and open interest
snapshot = aggregator.aggregate_derivatives_metrics("BTC")

print(f"Funding Rate: {snapshot.funding_rate_8h * 100:.4f}%")
print(f"Open Interest: ${snapshot.open_interest_usd:,.2f}")
```

### 4. Twitter Sentiment Analysis

```python
from src.services.twitter import TwitterAggregator

# Requires TWITTER_BEARER_TOKEN environment variable
aggregator = TwitterAggregator()

# Aggregate ETH sentiment from last 24 hours
snapshot = aggregator.aggregate_token_sentiment(
    token_symbol="ETH",
    hours_back=24,
    max_tweets=100,
)

print(f"Total Tweets: {snapshot.total_tweets}")
print(f"Tweet Velocity: {snapshot.tweet_velocity:.2f}/hour")
print(f"Avg Engagement: {snapshot.avg_engagement_per_tweet:.1f}")
```

### 5. Spike Detection

```python
# Detect sentiment spikes (e.g., viral moments)
result = aggregator.detect_sentiment_spike(
    token_symbol="DOGE",
    baseline_hours=24,
    recent_hours=1,
    spike_threshold=3.0,  # 3x baseline
)

if result['is_spike']:
    print(f"🚨 SPIKE: {result['spike_multiplier']:.1f}x baseline!")
    print(f"Recent tweets: {result['recent_tweets']}")
```

## Running Examples

### Comprehensive Order Flow Demo
```bash
python examples/orderflow_example.py
```

Demonstrates:
- Multi-exchange order book aggregation
- DEX liquidity analysis
- Derivatives metrics
- Direct client usage

### Twitter Sentiment Demo
```bash
python examples/twitter_example.py
```

Demonstrates:
- Tweet search and filtering
- Sentiment aggregation
- Spike detection
- Multi-token monitoring

## Environment Setup

1. **Copy template**:
   ```bash
   cp .env.template .env
   ```

2. **Add your keys** (optional):
   ```bash
   # Order flow (optional)
   BINANCE_API_KEY=your_binance_key_here
   BYBIT_API_KEY=your_bybit_key_here
   
   # Twitter (required for Twitter features)
   TWITTER_BEARER_TOKEN=your_twitter_bearer_token_here
   ```

3. **Test**:
   ```bash
   # Test order flow (works without API keys)
   python examples/orderflow_example.py
   
   # Test Twitter (requires bearer token)
   python examples/twitter_example.py
   ```

## Common Use Cases

### 1. Market Depth Monitoring
Monitor liquidity across CEX and DEX for rug pull detection:

```python
from src.services.orderflow import OrderFlowAggregator, LiquidityAggregator

orderflow = OrderFlowAggregator()
liquidity = LiquidityAggregator()

# Check CEX liquidity
cex_snapshot = orderflow.aggregate_order_book("TOKEN")
if cex_snapshot.spread_bps > 100:  # Wide spread = low liquidity
    print("⚠️ Low CEX liquidity!")

# Check DEX liquidity
dex_snapshot = liquidity.aggregate_dex_liquidity(
    token_address="0x...",
    token_symbol="TOKEN",
)
if dex_snapshot.liquidity_concentration > 0.8:  # High concentration
    print("⚠️ Liquidity concentrated in few pools!")
```

### 2. Sentiment Spike Alerts
Detect viral moments for early entry:

```python
from src.services.twitter import TwitterAggregator

aggregator = TwitterAggregator()

# Monitor multiple tokens
for symbol in ["BTC", "ETH", "SOL"]:
    result = aggregator.detect_sentiment_spike(symbol)
    if result['is_spike']:
        print(f"🚨 {symbol}: {result['spike_multiplier']:.1f}x spike!")
```

### 3. Funding Rate Arbitrage
Identify overleveraged positions:

```python
from src.services.orderflow import DerivativesAggregator

agg = DerivativesAggregator()
snapshot = agg.aggregate_derivatives_metrics("BTC")

if abs(snapshot.funding_rate_8h) > 0.30:  # >30% annualized
    print(f"⚠️ Extreme funding rate: {snapshot.funding_rate_8h*100:.2f}%")
    print("Potential liquidation cascade risk!")
```

## Integration with Existing Pipeline

To add these signals to your `HiddenGemScanner`:

```python
from src.services.orderflow import OrderFlowAggregator
from src.services.twitter import TwitterAggregator

class HiddenGemScanner:
    def __init__(self, ...):
        # Add new aggregators
        self.orderflow_agg = OrderFlowAggregator()
        self.twitter_agg = TwitterAggregator()
    
    def scan(self, config):
        # Existing scan logic...
        
        # Add order flow signals
        orderflow = self.orderflow_agg.aggregate_order_book(config.symbol)
        
        # Add Twitter signals
        twitter = self.twitter_agg.aggregate_token_sentiment(config.symbol)
        
        # Incorporate into feature vector
        features.update({
            "SpreadBPS": orderflow.spread_bps,
            "BidDepth1pct": orderflow.bid_depth_1pct,
            "TwitterVelocity": twitter.tweet_velocity,
            "TwitterEngagement": twitter.avg_engagement_per_tweet,
        })
```

## Rate Limits & Costs

| Service | Free Tier | Rate Limit | Notes |
|---------|-----------|------------|-------|
| Binance | Unlimited | 1200/min (spot) | Public endpoints free |
| Bybit | Unlimited | 600/min | Public endpoints free |
| Dexscreener | Unlimited | 300/min | No authentication needed |
| Twitter | 500k tweets/month | 450 req/15min | Requires developer account |

**Estimated Cost**: **$0/month** for monitoring 10-20 tokens

## Troubleshooting

### "Twitter API v2 requires a bearer token"
- Get a free developer account at https://developer.twitter.com/
- Create a project and app
- Generate a Bearer Token (found in app settings)
- Set `TWITTER_BEARER_TOKEN` in your `.env` file

### "Failed to fetch order book"
- Check internet connectivity
- Verify symbol format (e.g., "BTC" not "BTC/USD")
- For authenticated endpoints, verify API key is set

### Rate limit errors
- Clients automatically handle rate limits with caching
- Reduce polling frequency if needed
- Consider upgrading to paid tier for higher limits

## Next Steps

1. **Explore Examples**: Run the example scripts to see all features
2. **Read Documentation**: See `docs/ORDERFLOW_TWITTER_IMPLEMENTATION.md`
3. **Integration**: Add to your existing pipeline
4. **Monitoring**: Set up alerts for extreme conditions
5. **Backtesting**: Validate signals against historical data

## Support & Resources

- **Implementation Guide**: `docs/ORDERFLOW_TWITTER_IMPLEMENTATION.md`
- **Signal Coverage Audit**: `docs/signal_coverage_audit.md`
- **Roadmap**: `docs/vision/greatness_roadmap.md`
- **Example Scripts**: `examples/orderflow_example.py`, `examples/twitter_example.py`

---

**Status**: ✅ Production Ready  
**Last Updated**: October 7, 2025  
**Questions?** Check the comprehensive documentation or open an issue.
