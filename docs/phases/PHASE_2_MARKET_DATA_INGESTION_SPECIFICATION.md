# Phase 2 — Market Data Ingestion Blueprint

## 1. Mission Statement
- Deliver robust real-time and historical data connectivity across equities, crypto, and forex markets.
- Normalize ingestion streams to a unified schema, enabling downstream strategies to operate asset-class agnostically.
- Establish layered storage (raw, cleaned, feature-ready) with measurable latency metrics and reproducible backfill workflows.

## 1.1 Phase 2 at a Glance
- **Stocks (Equities):** Interactive Brokers TWS/Gateway API for real-time streaming; Polygon, Tiingo, and Nasdaq Data Link for historical data retrieval.
- **Crypto (Digital Assets):** WebSocket and REST connectors for Binance, Coinbase, and OKX, capturing trades and order book snapshots (L2 depth).
- **Forex (FX):** Oanda and FXCM APIs for real-time tick and quote feeds; Dukascopy historical tick data for backtesting.
- **Data Store:** Time-series database options evaluated (ClickHouse, InfluxDB, Parquet on S3); unified schema design ensures cross-venue compatibility.
- **Latency & Quality:** End-to-end timestamp tracking (exchange → ingestion → storage), raw/cleaned/feature layers, and latency dashboards in Grafana.
- **Primary Deliverables:** Production-ready connectors for all three asset classes, schema normalization library, reproducible historical download pipelines, and latency monitoring dashboards.

---

## 2. Data Sources & Connectivity

### 2.1 Equities (Stocks)
#### Real-Time Sources
- **Interactive Brokers (IB) TWS/Gateway API**
  - **Protocol:** IB Client Portal API (REST) and native Python `ib_insync` wrapper for TWS socket interface.
  - **Data Coverage:** Live tick-by-tick trades, BBO (best bid/offer), market depth (Level II), and scanner results.
  - **Latency Target:** <100ms from exchange timestamp to local ingestion (measured via `reqCurrentTime` sync).
  - **Authentication:** TWS session tokens and Gateway REST API bearer tokens; credentials stored in AWS Secrets Manager.
  - **Rate Limits:** 50 concurrent market data subscriptions on free tier; upgrade to professional for 100+ instruments.
  - **Error Handling:** Auto-reconnect logic on socket drops; fallback to delayed data if subscription limits exceeded.

#### Historical Sources
- **Polygon.io**
  - **Endpoints:** Aggregates (bars), ticks, quotes, trades.
  - **Coverage:** All US equities and options; minute/hour/day granularity.
  - **API Key Management:** Rotated monthly; stored in `.env.production` secret.
  - **Caching Strategy:** Daily bars cached in S3 (`s3://autotrader-historical-data/stocks/polygon/`) to minimize quota burn.
- **Tiingo**
  - **Endpoints:** IEX real-time and historical EOD prices, news sentiment.
  - **Use Case:** Cross-validation of Polygon data and fundamental signals.
- **Nasdaq Data Link (formerly Quandl)**
  - **Datasets:** WIKI Prices (free), premium bundles for corporate actions and split adjustments.
  - **Format:** CSV downloads via REST API, ingested into ClickHouse `stocks.historical_eod` table.

### 2.2 Crypto (Digital Assets)
#### Real-Time Sources
- **Binance**
  - **WebSocket Streams:** `wss://stream.binance.com:9443/ws/<symbol>@trade` for trades, `<symbol>@depth` for order book L2 snapshots.
  - **REST API:** `/api/v3/ticker/24hr` for periodic snapshots, `/api/v3/klines` for candlestick history.
  - **Rate Limits:** 1200 requests/minute (IP-based); WebSocket streams unlimited.
  - **Data Fields:** `price`, `quantity`, `timestamp`, `isBuyerMaker`, `depth` (bids/asks up to 20 levels).
- **Coinbase Pro (Advanced Trade API)**
  - **WebSocket:** `wss://ws-feed.exchange.coinbase.com` for `ticker`, `level2`, `matches` channels.
  - **REST API:** `/products/<id>/candles` for historical OHLCV.
  - **Authentication:** API keys with read-only permissions; signature-based signing for REST.
- **OKX (OKEx)**
  - **WebSocket:** `wss://ws.okx.com:8443/ws/v5/public` for trades and order book updates.
  - **REST API:** `/api/v5/market/history-candles` for backfill.
  - **Coverage:** Spot, futures, perpetual swaps; configurable per instrument via `instType` parameter.

#### Historical Sources
- **Binance REST Historical Trades:** `/api/v3/historicalTrades` endpoint (requires API key with trade history access).
- **Coinbase Pro REST:** `/products/<id>/trades` paginated retrieval.
- **OKX REST:** `/api/v5/market/history-trades` for spot; `/api/v5/market/history-mark-price-candles` for derivatives.
- **Backup Archive:** Tardis.dev for tick-level reconstruction of order book states across all major exchanges (paid subscription).

### 2.3 Forex (FX)
#### Real-Time Sources
- **Oanda v20 API**
  - **Streaming Endpoint:** `/v3/accounts/<accountID>/pricing/stream` for live bid/ask ticks.
  - **Instrument Coverage:** 70+ currency pairs including majors, minors, and exotics.
  - **Latency:** Typically <50ms for majors (EUR/USD, GBP/USD) on low-latency plan.
  - **Authentication:** OAuth2 bearer tokens with 24-hour expiration; refresh logic in connector.
- **FXCM REST API**
  - **Endpoints:** `/subscribe` for streaming price updates, `/candles` for historical OHLC.
  - **Rate Limits:** 300 requests/minute; WebSocket preferred for sustained feeds.
  - **Data Fields:** `Bid`, `Ask`, `High`, `Low`, `Timestamp` in ISO 8601.

#### Historical Sources
- **Dukascopy Tick Data**
  - **Format:** Proprietary binary `.bi5` files; decompressed via open-source Python library `dukascopy-node`.
  - **Coverage:** Full tick history back to 2003 for major pairs; minute/hour aggregates for minors.
  - **Storage:** Decompressed ticks stored as Parquet partitions in S3 (`s3://autotrader-historical-data/forex/dukascopy/`).
  - **Download Automation:** Prefect flow `flows/ingest_dukascopy.py` scheduled monthly to backfill new data.
- **Oanda Historical API:** `/v3/instruments/<instrument>/candles` for granularities from S5 (5-second) to M (monthly).

---

## 3. Unified Schema Design

### 3.1 Normalization Principles
- **Asset-Class Agnostic Fields:** All market data records adhere to a common schema enabling cross-asset strategies without adapter layers.
- **Timestamp Standards:** All timestamps stored as UTC UNIX microseconds (`event_time_us`); exchange-provided timestamps preserved in `exchange_time_us` for latency calculation.
- **Symbology Mapping:** Proprietary venue symbols (e.g., `BTCUSDT` on Binance, `BTC-USD` on Coinbase) mapped to canonical identifiers via `symbols.mapping` table.

### 3.2 Core Schema: `market_data.tick`
| Field | Type | Description |
|---|---|---|
| `event_time_us` | Int64 | Ingestion timestamp (microseconds UTC) |
| `exchange_time_us` | Int64 | Exchange-reported timestamp (if available) |
| `symbol` | String | Canonical symbol (e.g., `AAPL`, `BTC/USD`, `EUR/USD`) |
| `venue` | String | Exchange/broker identifier (`IBKR`, `BINANCE`, `OANDA`) |
| `asset_class` | Enum | `EQUITY`, `CRYPTO`, `FOREX`, `COMMODITY` |
| `price` | Float64 | Trade price or mid-quote |
| `quantity` | Float64 | Trade size or volume |
| `side` | Enum | `BUY`, `SELL`, `UNKNOWN` (for quotes) |
| `bid` | Nullable Float64 | Best bid price (for BBO snapshots) |
| `ask` | Nullable Float64 | Best ask price |
| `bid_size` | Nullable Float64 | Bid quantity |
| `ask_size` | Nullable Float64 | Ask quantity |
| `sequence_id` | Int64 | Monotonic counter per venue-symbol pair |
| `flags` | String | Flags: `REPLAY`, `HALTED`, `ADJUSTED` |

### 3.3 Order Book Schema: `market_data.depth`
| Field | Type | Description |
|---|---|---|
| `event_time_us` | Int64 | Ingestion timestamp |
| `exchange_time_us` | Int64 | Exchange snapshot timestamp |
| `symbol` | String | Canonical symbol |
| `venue` | String | Exchange identifier |
| `bids` | Array(Tuple(Float64, Float64)) | List of (price, size) tuples for bid levels |
| `asks` | Array(Tuple(Float64, Float64)) | List of (price, size) tuples for ask levels |
| `snapshot_id` | Int64 | Incremental snapshot counter |

### 3.4 OHLCV Schema: `market_data.bars`
| Field | Type | Description |
|---|---|---|
| `timestamp` | DateTime | Bar open time (UTC) |
| `symbol` | String | Canonical symbol |
| `venue` | String | Exchange identifier |
| `asset_class` | Enum | Asset classification |
| `open` | Float64 | Open price |
| `high` | Float64 | High price |
| `low` | Float64 | Low price |
| `close` | Float64 | Close price |
| `volume` | Float64 | Traded volume |
| `vwap` | Nullable Float64 | Volume-weighted average price |
| `trade_count` | Int32 | Number of trades in bar |

---

## 4. Data Storage Architecture

### 4.1 Storage Technology Evaluation
| Solution | Pros | Cons | Decision |
|---|---|---|---|
| **ClickHouse** | Columnar compression; SQL interface; excellent for time-range scans | Requires cluster setup; overkill for <10M rows/day | **Selected for production** (handles multi-asset ingestion at scale) |
| **InfluxDB** | Purpose-built for time-series; simple setup | Limited JOIN support; vendor lock-in | Backup option for IoT-style sensor data |
| **Parquet on S3** | Serverless; queryable via Athena/Trino; cheapest storage | Higher query latency vs. ClickHouse | **Selected for cold storage** (data older than 90 days) |
| **TimescaleDB** | PostgreSQL extension; familiar SQL | Performance lags ClickHouse at scale | Evaluated but not selected |

### 4.2 ClickHouse Table Design
```sql
CREATE TABLE market_data.tick
(
    event_time_us Int64,
    exchange_time_us Int64,
    symbol String,
    venue LowCardinality(String),
    asset_class Enum8('EQUITY'=1, 'CRYPTO'=2, 'FOREX'=3, 'COMMODITY'=4),
    price Float64,
    quantity Float64,
    side Enum8('BUY'=1, 'SELL'=2, 'UNKNOWN'=0),
    bid Nullable(Float64),
    ask Nullable(Float64),
    bid_size Nullable(Float64),
    ask_size Nullable(Float64),
    sequence_id Int64,
    flags String
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(toDateTime(event_time_us / 1000000))
ORDER BY (venue, symbol, event_time_us)
SETTINGS index_granularity = 8192;
```

### 4.3 Data Lifecycle Management
- **Hot Tier (ClickHouse):** Last 90 days, optimized for real-time queries and backtesting.
- **Warm Tier (S3 Parquet):** 90 days to 2 years, queryable via AWS Athena or Trino.
- **Cold Tier (Glacier):** Archived data older than 2 years, retrievable within 12 hours.
- **Retention Policy:** Raw ticks retained for 2 years; aggregated bars (1m, 5m, 1h, 1d) retained indefinitely.

### 4.4 Data Layers
1. **Raw Layer (`market_data.tick_raw`):** Unmodified exchange data; preserves original schemas for audit and replay.
2. **Cleaned Layer (`market_data.tick`):** Normalized schema; deduplication, outlier flagging, and timestamp correction applied.
3. **Feature Layer (`features.market_signals`):** Derived metrics (e.g., spread, mid-price volatility, order book imbalance) computed via materialized views or Prefect flows.

---

## 5. Latency Measurement & Monitoring

### 5.1 Timestamp Chain
1. **Exchange Timestamp (`exchange_time_us`):** Reported by venue (if available).
2. **Network Receipt (`recv_time_us`):** Captured by connector immediately upon socket read.
3. **Ingestion Timestamp (`event_time_us`):** Assigned when record enters ClickHouse buffer.
4. **Storage Commit (`commit_time_us`):** Logged after ClickHouse MergeTree part written.

### 5.2 Latency Metrics
- **End-to-End Latency:** `event_time_us - exchange_time_us` (target: p99 <500ms for real-time feeds).
- **Network Latency:** `recv_time_us - exchange_time_us` (target: p99 <100ms for co-located servers).
- **Processing Latency:** `commit_time_us - recv_time_us` (target: p99 <200ms).

### 5.3 Grafana Dashboards
- **Dashboard: Market Data Ingestion**
  - Panels: Ingestion rate (ticks/sec) per venue, latency histograms, error rate, WebSocket reconnection events.
  - Alerts: Latency p99 >1s, ingestion rate drop >50%, connector downtime >60s.
- **Dashboard: Data Quality**
  - Panels: Duplicate tick rate, outlier detection (price deviations >5σ), missing sequence IDs.
  - Alerts: Duplicate rate >1%, outliers >0.1% of total ticks.

### 5.4 Prometheus Metrics
```python
# Example metrics exposed by connectors
ingestion_ticks_total = Counter('ingestion_ticks_total', 'Total ticks ingested', ['venue', 'symbol', 'asset_class'])
ingestion_latency_seconds = Histogram('ingestion_latency_seconds', 'End-to-end latency', ['venue', 'asset_class'])
connector_errors_total = Counter('connector_errors_total', 'Connector error count', ['venue', 'error_type'])
websocket_reconnects_total = Counter('websocket_reconnects_total', 'WebSocket reconnection count', ['venue'])
```

---

## 6. Connector Implementation Guidelines

### 6.1 Architecture Pattern
- **Base Class:** `autotrader.connectors.base.MarketDataConnector` defines abstract methods: `connect()`, `subscribe()`, `on_tick()`, `on_depth()`, `disconnect()`.
- **Venue-Specific Subclasses:** `IBKRConnector`, `BinanceConnector`, `OandaConnector` implement protocol-specific logic.
- **Buffering:** Local ring buffer (1000 ticks) to smooth bursts; flushed to ClickHouse every 1 second or on buffer full.
- **Error Recovery:** Exponential backoff on reconnect (1s, 2s, 4s, …, max 60s); dead-letter queue for unparseable messages.

### 6.2 Example: Binance WebSocket Connector
```python
# autotrader/connectors/binance_ws.py (skeleton)
import asyncio
import websockets
from autotrader.connectors.base import MarketDataConnector
from autotrader.schemas import Tick

class BinanceConnector(MarketDataConnector):
    def __init__(self, symbols: list[str], buffer_size: int = 1000):
        self.symbols = symbols
        self.buffer = []
        self.buffer_size = buffer_size
        self.ws_url = "wss://stream.binance.com:9443/stream"
    
    async def connect(self):
        streams = "/".join([f"{s.lower()}@trade" for s in self.symbols])
        uri = f"{self.ws_url}?streams={streams}"
        async with websockets.connect(uri) as ws:
            async for msg in ws:
                await self.on_message(msg)
    
    async def on_message(self, msg: str):
        data = json.loads(msg)["data"]
        tick = Tick(
            event_time_us=int(time.time() * 1e6),
            exchange_time_us=data["T"] * 1000,  # Binance uses ms
            symbol=self.normalize_symbol(data["s"]),
            venue="BINANCE",
            asset_class="CRYPTO",
            price=float(data["p"]),
            quantity=float(data["q"]),
            side="BUY" if data["m"] else "SELL",
        )
        self.buffer.append(tick)
        if len(self.buffer) >= self.buffer_size:
            await self.flush()
    
    async def flush(self):
        # Batch insert to ClickHouse
        await clickhouse_client.insert("market_data.tick", self.buffer)
        self.buffer.clear()
```

### 6.3 Historical Download Workflows
- **Prefect Flows:** `flows/ingest_polygon_daily.py`, `flows/ingest_dukascopy_monthly.py`.
- **Idempotency:** Track downloaded date ranges in `metadata.ingestion_runs` table; skip already-fetched intervals.
- **Parallelization:** Prefect task concurrency set to 10 for daily bar downloads (configurable per API rate limit).
- **Validation:** Post-download validation compares row counts and timestamp continuity against expected values.

---

## 7. Deliverables & Acceptance Criteria

| Week | Deliverable | Acceptance Criteria |
|---|---|---|
| 1 | Equities connector (IBKR + Polygon) | Live ticks from IBKR streaming to ClickHouse; Polygon historical bars backfilled for SPY, QQQ. |
| 2 | Crypto connectors (Binance, Coinbase, OKX) | Real-time trades and L2 depth ingested; WebSocket reconnection tested under network failure. |
| 3 | Forex connectors (Oanda, FXCM, Dukascopy) | Live Oanda ticks flowing; Dukascopy historical backfill completed for EUR/USD 2020-2024. |
| 4 | Unified schema & storage | All venues writing to normalized ClickHouse schema; Parquet cold storage pipeline active. |
| 5 | Latency dashboards | Grafana dashboards live with p50/p99 latency, error rates; Prometheus metrics scraped. |

**Exit Criteria:** Phase 2 is complete when all connectors are production-ready, latency p99 <500ms for real-time feeds, historical backfill pipelines reproducible via Prefect, and observability dashboards signed off by DevOps and Quant teams.

---

## 8. Risk Mitigation & Contingencies

### 8.1 API Rate Limits
- **Risk:** Exceeding vendor rate limits during backfill or high-frequency subscriptions.
- **Mitigation:** Implement token bucket rate limiters in connectors; cache frequently accessed historical data in S3.

### 8.2 Exchange Downtime
- **Risk:** Venue outages or WebSocket disconnections leading to data gaps.
- **Mitigation:** Multi-venue redundancy (e.g., cross-validate Binance vs. Coinbase BTC/USD); automatic backfill jobs triggered on reconnect.

### 8.3 Schema Evolution
- **Risk:** Venues change API schemas (field renames, new data types).
- **Mitigation:** Schema versioning in connectors; CI integration tests against mock API responses; alerts on unknown fields.

### 8.4 Storage Costs
- **Risk:** ClickHouse cluster and S3 storage costs scale with tick volume.
- **Mitigation:** Partition pruning (drop partitions older than retention policy); aggressive compression (LZ4 for hot data, Zstd for cold); spot instances for ClickHouse workers.

---

## 9. Future Enhancements (Post-Phase 2)
- **Phase 3 Candidates:**
  - Options chains ingestion (IBKR, CBOE).
  - Futures and perpetual swaps (CME, Binance Futures).
  - Alternative data sources (news sentiment, social media feeds).
  - Real-time anomaly detection on ingestion pipeline (outlier prices, gaps).
  - Multi-region deployment (US East, EU, APAC) for geo-distributed latency optimization.

---

**Document Owner:** Data Engineering & Quant Infrastructure  
**Last Updated:** October 2025  
**Review Cycle:** Monthly during Phase 2; quarterly post-GA
