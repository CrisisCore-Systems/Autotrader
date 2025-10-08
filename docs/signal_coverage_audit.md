# Signal Coverage Audit
**Date**: October 7, 2025  
**Purpose**: Map current data feeds against the desired universe and identify blind spots for VoidBloom

## Executive Summary
This audit evaluates the completeness and quality of data ingestion across all signal categories to identify gaps that could limit alpha generation, increase latency, or miss critical risk events.

---

## 1. Current Signal Inventory

### 1.1 News & Media Signals ✅ OPERATIONAL
**Status**: Partial Coverage

| Feed | Status | Latency | Coverage |
|------|--------|---------|----------|
| CoinDesk RSS | ✅ Implemented | ~5 min | Major crypto news |
| Cointelegraph RSS | ✅ Implemented | ~5 min | Altcoin & DeFi news |
| Decrypt RSS | ✅ Implemented | ~5 min | Culture & narrative |
| The Block RSS | ✅ Implemented | ~5 min | Institutional & protocol news |
| CoinTelegraph | ✅ Implemented | ~5 min | General crypto news |

**Clients**: `NewsFeedClient`, `NewsAggregator`  
**Storage**: SQLite FTS5 index in `artifacts/voidbloom.db`  
**Integration Point**: `src/services/news.py`, `src/core/news_pipeline.py`

### 1.2 Social Signals 🟡 PARTIAL
**Status**: Stub Implementation

| Platform | Status | Latency | Coverage |
|----------|--------|---------|----------|
| Reddit | 🟡 Stub | N/A | Not fetching real data |
| StockTwits | 🟡 Stub | N/A | Not fetching real data |
| Twitter/X (Nitter) | 🟡 Stub | N/A | RSS mirror not configured |
| Discord | ❌ Not Implemented | N/A | No coverage |
| Telegram | ❌ Not Implemented | N/A | No coverage |
| Farcaster | ❌ Not Implemented | N/A | No coverage |

**Clients**: `SocialFeedClient`  
**Storage**: Planned for SQLite  
**Integration Point**: `src/services/social.py` (stub)

### 1.3 On-Chain Metrics ✅ OPERATIONAL
**Status**: Core Metrics Available

| Provider | Status | Metrics | Refresh Rate |
|----------|--------|---------|--------------|
| CoinGecko | ✅ Implemented | Price, volume, market cap, 24h change | 5 min cache |
| DefiLlama | ✅ Implemented | TVL, protocol metrics, chain breakdown | 10 min cache |
| Etherscan | ✅ Implemented | Contract verification, source code | 5 min cache |
| Dexscreener | ❌ Not Implemented | DEX liquidity depth, pair analytics | N/A |
| Nansen | ❌ Not Implemented | Smart money flows, wallet labels | N/A |
| Dune Analytics | ❌ Not Implemented | Custom on-chain queries | N/A |

**Clients**: `CoinGeckoClient`, `DefiLlamaClient`, `EtherscanClient`  
**Storage**: SQLite + in-memory cache  
**Integration Point**: `src/core/clients.py`, `src/core/pipeline.py`

### 1.4 Order Flow & Derivatives ❌ BLIND SPOT
**Status**: Not Implemented

| Signal Type | Priority | Use Case | Status |
|-------------|----------|----------|--------|
| CEX Order Book Depth | 🔴 HIGH | Liquidity quality, support/resistance | ❌ Missing |
| DEX Liquidity Pools | 🔴 HIGH | Real-time DEX depth, impermanent loss | ❌ Missing |
| Perpetual Funding Rates | 🟡 MEDIUM | Sentiment proxy, overheated positions | ❌ Missing |
| Open Interest | 🟡 MEDIUM | Leverage exposure, liquidation risk | ❌ Missing |
| Options Flow | 🟢 LOW | Sophisticated trader positioning | ❌ Missing |
| Futures Basis | 🟢 LOW | Arbitrage opportunities, market structure | ❌ Missing |

**Potential Providers**: Binance API, Bybit API, dYdX, Paradigm, Skew  
**Impact**: Missing critical alpha signals for timing and risk management

### 1.5 GitHub Activity 🟡 PARTIAL
**Status**: Client Available, Not Integrated

| Metric | Status | Coverage |
|--------|--------|----------|
| Commit Frequency | 🟡 Available | Client exists, not used in pipeline |
| Contributor Growth | 🟡 Available | Client exists, not used in pipeline |
| Release Cadence | 🟡 Available | Client exists, not used in pipeline |
| Issue/PR Velocity | 🟡 Available | Client exists, not used in pipeline |

**Client**: `GitHubClient`  
**Storage**: Not persisted  
**Integration Point**: `src/services/github.py` (not wired to scanner)

### 1.6 Tokenomics ✅ PARTIAL
**Status**: Manual Configuration Required

| Metric | Status | Coverage |
|--------|--------|----------|
| Supply Schedule | ✅ Manual | Configured per-token in YAML |
| Unlock Events | ✅ Manual | Configured per-token in YAML |
| Vesting Cliffs | ✅ Manual | Configured per-token in YAML |
| Circulating vs Total Supply | 🟡 Via CoinGecko | Available but not deeply analyzed |
| Holder Distribution | ❌ Not Implemented | No Etherscan holder analysis |

**Client**: `TokenomicsClient` (generic)  
**Storage**: Config files + manual entry  
**Integration Point**: `src/services/tokenomics.py`, config YAML

---

## 2. Blind Spot Analysis

### 2.1 Critical Gaps (Immediate Risk)

#### **A. Order Flow Intelligence** 🔴
- **Missing**: CEX order book depth, bid-ask spread dynamics, DEX pool depth
- **Impact**: Cannot assess real liquidity quality; vulnerable to wash trading signals
- **Risk**: False positives on low-liquidity tokens; missed exit opportunities
- **Priority**: **P0 - Immediate**

#### **B. Derivatives Market Structure** 🔴
- **Missing**: Funding rates, open interest, basis spreads
- **Impact**: No visibility into leveraged positioning or overheat signals
- **Risk**: Enter positions at local tops; miss sentiment extremes
- **Priority**: **P0 - Immediate**

#### **C. Real-Time Social Sentiment** 🟡
- **Missing**: Twitter/X firehose, Discord/Telegram channels, Farcaster casts
- **Impact**: Delayed meme momentum detection; miss viral catalysts
- **Risk**: Late to narrative shifts; reduced alpha capture
- **Priority**: **P1 - Near Term**

### 2.2 Moderate Gaps (Competitive Disadvantage)

#### **D. Smart Money Flows** 🟡
- **Missing**: Nansen wallet labels, Arkham entity tracking, whale alert feeds
- **Impact**: Cannot identify accumulation by sophisticated actors
- **Risk**: Miss early smart-money positioning signals
- **Priority**: **P1 - Near Term**

#### **E. Cross-Chain Activity** 🟡
- **Missing**: Bridge volumes, multi-chain deployment tracking, L2 activity
- **Impact**: Limited visibility on tokens expanding ecosystems
- **Risk**: Miss expansion narratives and cross-chain arbitrage
- **Priority**: **P2 - Mid Term**

### 2.3 Nice-to-Have Enhancements

#### **F. Protocol Revenue & Fees**
- **Partial**: DefiLlama provides some metrics, but not comprehensive
- **Impact**: Cannot assess protocol sustainability and tokenomics health
- **Priority**: **P3 - Long Term**

#### **G. Governance Activity**
- **Missing**: Snapshot votes, on-chain governance participation
- **Impact**: Miss governance-driven catalysts and community engagement signals
- **Priority**: **P3 - Long Term**

---

## 3. Data Quality & Reliability Assessment

### 3.1 Current SLAs (Informal)

| Signal Category | Target Freshness | Actual Freshness | Reliability |
|-----------------|------------------|------------------|-------------|
| News (RSS) | < 5 min | ~5 min | 95% uptime |
| Price Data (CoinGecko) | < 5 min | 5 min (cache) | 98% uptime |
| On-Chain (DefiLlama) | < 10 min | 10 min (cache) | 95% uptime |
| Contract Data (Etherscan) | < 5 min | 5 min (cache) | 90% uptime (V1 deprecated) |
| Social Feeds | N/A | Not operational | N/A |
| Order Flow | N/A | Not implemented | N/A |

### 3.2 Resilience Gaps

| Risk | Current State | Required Improvement |
|------|---------------|----------------------|
| API Rate Limits | Basic rate limiting | Circuit breakers, exponential backoff |
| Network Failures | Retries in HTTP manager | Graceful degradation, fallback sources |
| Stale Data Detection | None | TTL monitoring, staleness alerts |
| Provider Outages | Single-source dependency | Multi-provider failover |
| Cache Invalidation | Time-based only | Event-driven + manual invalidation |

---

## 4. Prioritization Matrix

### Priority Scoring Framework
- **Alpha Impact**: How much edge does this signal provide? (1-5)
- **Risk Mitigation**: Does it prevent losses or bad trades? (1-5)
- **Latency**: How time-sensitive is the signal? (1-5)
- **Effort**: Implementation complexity (1=easy, 5=hard)
- **Score**: (Alpha + Risk + Latency) / Effort

### Ranked Priorities

| Priority | Signal | Alpha | Risk | Latency | Effort | Score | Status |
|----------|--------|-------|------|---------|--------|-------|--------|
| **P0** | Order Book Depth (CEX/DEX) | 5 | 5 | 5 | 3 | 5.0 | ❌ |
| **P0** | Perpetual Funding Rates | 4 | 4 | 5 | 2 | 6.5 | ❌ |
| **P1** | Twitter/X Real-Time Feed | 5 | 3 | 5 | 4 | 3.25 | ❌ |
| **P1** | Discord/Telegram Alerts | 4 | 2 | 4 | 3 | 3.33 | ❌ |
| **P1** | Nansen Smart Money Labels | 5 | 4 | 3 | 4 | 3.0 | ❌ |
| **P2** | GitHub Activity (Full) | 3 | 2 | 2 | 2 | 3.5 | 🟡 |
| **P2** | Dexscreener Liquidity | 4 | 3 | 3 | 2 | 5.0 | ❌ |
| **P2** | Open Interest Data | 3 | 3 | 3 | 2 | 4.5 | ❌ |
| **P3** | Options Flow | 3 | 2 | 2 | 4 | 1.75 | ❌ |
| **P3** | Governance Activity | 2 | 1 | 1 | 3 | 1.33 | ❌ |

---

## 5. Recommended Actions

### Immediate (Weeks 1-2)
1. **Implement CEX Order Book Depth** (Binance, Bybit APIs)
   - Target: Real-time bid/ask spread, depth at 1%/5% levels
   - Deliverable: `OrderFlowClient` with depth aggregation
   
2. **Add Perpetual Funding Rates** (Binance, Bybit, dYdX)
   - Target: 8-hour funding rates for top 50 tokens
   - Deliverable: Funding rate time series in SQLite

3. **Etherscan V2 Migration**
   - Target: Replace deprecated V1 API with V2
   - Deliverable: Updated `EtherscanClient` with chainid support

### Near Term (Weeks 3-4)
4. **Real-Time Social Feeds** (Twitter API v2, Telegram Bot API)
   - Target: Keyword tracking, sentiment scoring
   - Deliverable: `SocialFeedClient` upgrade with webhooks

5. **Dexscreener Integration**
   - Target: DEX pair liquidity, volume, price impact
   - Deliverable: `DexscreenerClient` with pair analytics

6. **GitHub Activity Wiring**
   - Target: Connect existing `GitHubClient` to scanner pipeline
   - Deliverable: GitHub metrics in feature vector

### Mid Term (Weeks 5-8)
7. **Smart Money Flows** (Nansen API or Arkham)
   - Target: Whale wallet labels, entity tracking
   - Deliverable: Wallet clustering + accumulation detection

8. **Cross-Chain Bridge Monitoring**
   - Target: Wormhole, LayerZero, Synapse volumes
   - Deliverable: Bridge activity time series

---

## 6. Success Metrics

### Coverage KPIs
- **Signal Coverage**: Achieve 95% coverage of Tier-1 market events within 2 minutes
- **Data Freshness**: <5min for price/news, <10min for on-chain, <1min for order flow
- **Uptime SLA**: 99.5% availability for critical feeds (price, order flow)
- **Latency P95**: <30s from event occurrence to database persistence

### Quality KPIs
- **False Positive Rate**: <10% for liquidity-gated signals
- **Stale Data Incidents**: <1 per week with automated detection
- **Provider Failover**: <60s to fallback on primary provider failure

---

## 7. Next Steps

1. **Week 1**: Staff discovery sprint for Order Flow + Funding Rates (P0)
2. **Week 2**: Implement and test CEX order book depth client
3. **Week 3**: Begin Twitter API v2 integration (P1)
4. **Week 4**: Backfill historical funding rates for backtesting
5. **Monthly**: Review signal coverage KPIs and adjust priorities

---

## Appendix A: Provider API Catalog

### Order Flow Providers
- **Binance API**: `/api/v3/depth`, `/fapi/v1/fundingRate`
- **Bybit API**: `/v5/market/orderbook`, `/v5/market/funding/history`
- **Kraken API**: `/0/public/Depth`, `/0/public/Ticker`
- **Dexscreener API**: `/latest/dex/tokens/{address}`

### Social Feed Providers
- **Twitter API v2**: Filtered stream, recent search
- **Telegram Bot API**: Group message webhooks
- **Discord API**: Guild message webhooks
- **Farcaster Hubs**: `/v1/casts/by-mention`

### Smart Money Providers
- **Nansen API**: Wallet labels, token god mode
- **Arkham Intelligence**: Entity resolution, flow tracking
- **Whale Alert**: Large transaction feeds

---

**Document Status**: ✅ Complete  
**Last Updated**: October 7, 2025  
**Owner**: VoidBloom Engineering
