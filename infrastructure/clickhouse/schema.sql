-- ClickHouse schema for market data ingestion (Phase 2)
-- Run this SQL to create the tables for tick, depth, and OHLCV data

-- Database
CREATE DATABASE IF NOT EXISTS market_data;

-- Tick data table
CREATE TABLE IF NOT EXISTS market_data.tick
(
    event_time_us Int64 COMMENT 'Ingestion timestamp (microseconds UTC)',
    exchange_time_us Nullable(Int64) COMMENT 'Exchange-reported timestamp (if available)',
    symbol String COMMENT 'Canonical symbol (e.g., AAPL, BTC/USD, EUR/USD)',
    venue LowCardinality(String) COMMENT 'Exchange/broker identifier (IBKR, BINANCE, OANDA)',
    asset_class Enum8('EQUITY'=1, 'CRYPTO'=2, 'FOREX'=3, 'COMMODITY'=4) COMMENT 'Asset classification',
    price Float64 COMMENT 'Trade price or mid-quote',
    quantity Float64 COMMENT 'Trade size or volume',
    side Enum8('BUY'=1, 'SELL'=2, 'UNKNOWN'=0) COMMENT 'Trade side',
    bid Nullable(Float64) COMMENT 'Best bid price',
    ask Nullable(Float64) COMMENT 'Best ask price',
    bid_size Nullable(Float64) COMMENT 'Bid quantity',
    ask_size Nullable(Float64) COMMENT 'Ask quantity',
    sequence_id Int64 COMMENT 'Monotonic counter per venue-symbol pair',
    flags String COMMENT 'Flags: REPLAY, HALTED, ADJUSTED'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(toDateTime(event_time_us / 1000000))
ORDER BY (venue, symbol, event_time_us)
SETTINGS index_granularity = 8192;

-- Raw tick table (unmodified exchange data for audit)
CREATE TABLE IF NOT EXISTS market_data.tick_raw
(
    event_time_us Int64,
    raw_data String COMMENT 'JSON blob of original exchange message'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(toDateTime(event_time_us / 1000000))
ORDER BY event_time_us
SETTINGS index_granularity = 8192;

-- Order book depth table
CREATE TABLE IF NOT EXISTS market_data.depth
(
    event_time_us Int64 COMMENT 'Ingestion timestamp',
    exchange_time_us Nullable(Int64) COMMENT 'Exchange snapshot timestamp',
    symbol String COMMENT 'Canonical symbol',
    venue LowCardinality(String) COMMENT 'Exchange identifier',
    bids Array(Tuple(Float64, Float64)) COMMENT 'Bid levels (price, size)',
    asks Array(Tuple(Float64, Float64)) COMMENT 'Ask levels (price, size)',
    snapshot_id Int64 COMMENT 'Incremental snapshot counter'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(toDateTime(event_time_us / 1000000))
ORDER BY (venue, symbol, event_time_us)
SETTINGS index_granularity = 8192;

-- OHLCV bars table
CREATE TABLE IF NOT EXISTS market_data.bars
(
    timestamp DateTime COMMENT 'Bar open time (UTC)',
    symbol String COMMENT 'Canonical symbol',
    venue LowCardinality(String) COMMENT 'Exchange identifier',
    asset_class Enum8('EQUITY'=1, 'CRYPTO'=2, 'FOREX'=3, 'COMMODITY'=4),
    interval Enum8('1m'=1, '5m'=2, '15m'=3, '1h'=4, '1d'=5) COMMENT 'Bar interval',
    open Float64 COMMENT 'Open price',
    high Float64 COMMENT 'High price',
    low Float64 COMMENT 'Low price',
    close Float64 COMMENT 'Close price',
    volume Float64 COMMENT 'Traded volume',
    vwap Nullable(Float64) COMMENT 'Volume-weighted average price',
    trade_count Nullable(Int32) COMMENT 'Number of trades in bar'
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (venue, symbol, interval, timestamp)
SETTINGS index_granularity = 8192;

-- Materialized view: Compute 1-minute bars from ticks
CREATE MATERIALIZED VIEW IF NOT EXISTS market_data.bars_1m_mv
TO market_data.bars
AS
SELECT
    toStartOfMinute(toDateTime(event_time_us / 1000000)) AS timestamp,
    symbol,
    venue,
    asset_class,
    '1m' AS interval,
    argMin(price, event_time_us) AS open,
    max(price) AS high,
    min(price) AS low,
    argMax(price, event_time_us) AS close,
    sum(quantity) AS volume,
    sum(price * quantity) / sum(quantity) AS vwap,
    count() AS trade_count
FROM market_data.tick
WHERE side IN ('BUY', 'SELL')  -- Exclude quotes
GROUP BY timestamp, symbol, venue, asset_class;

-- Index for fast symbol lookups
CREATE INDEX IF NOT EXISTS idx_symbol ON market_data.tick (symbol) TYPE bloom_filter GRANULARITY 1;
CREATE INDEX IF NOT EXISTS idx_depth_symbol ON market_data.depth (symbol) TYPE bloom_filter GRANULARITY 1;
CREATE INDEX IF NOT EXISTS idx_bars_symbol ON market_data.bars (symbol) TYPE bloom_filter GRANULARITY 1;

-- TTL for data retention (delete partitions older than 90 days from hot storage)
ALTER TABLE market_data.tick MODIFY TTL toDateTime(event_time_us / 1000000) + INTERVAL 90 DAY;
ALTER TABLE market_data.depth MODIFY TTL toDateTime(event_time_us / 1000000) + INTERVAL 30 DAY;
-- Bars retained indefinitely (comment out if you want TTL)
-- ALTER TABLE market_data.bars MODIFY TTL timestamp + INTERVAL 730 DAY;
