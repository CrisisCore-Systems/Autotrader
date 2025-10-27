# ClickHouse Infrastructure

This directory contains ClickHouse schema definitions and utilities for the market data storage layer (Phase 2).

## Quick Start

### 1. Run ClickHouse via Docker

```bash
docker run -d \
  --name clickhouse-server \
  -p 8123:8123 \
  -p 9000:9000 \
  --ulimit nofile=262144:262144 \
  clickhouse/clickhouse-server:latest
```

### 2. Initialize Schema

```bash
# Using clickhouse-client
clickhouse-client --host localhost --port 9000 --multiquery < infrastructure/clickhouse/schema.sql

# Or via HTTP
curl -X POST 'http://localhost:8123' --data-binary @infrastructure/clickhouse/schema.sql
```

### 3. Verify Tables

```bash
clickhouse-client --query "SHOW TABLES FROM market_data"
```

Expected output:
```
bars
bars_1m_mv
depth
tick
tick_raw
```

## Schema Overview

### Tables

- **`market_data.tick`**: Normalized tick data (trades and quotes) from all venues
- **`market_data.tick_raw`**: Raw JSON messages for audit/replay
- **`market_data.depth`**: Order book L2 snapshots
- **`market_data.bars`**: OHLCV bars (1m, 5m, 15m, 1h, 1d)
- **`market_data.bars_1m_mv`**: Materialized view auto-computing 1-minute bars from ticks

### Partitioning

- **Ticks & Depth**: Partitioned by day (`YYYYMMDD`)
- **Bars**: Partitioned by month (`YYYYMM`)

### Retention (TTL)

- **Ticks**: 90 days (configurable)
- **Depth**: 30 days (configurable)
- **Bars**: Indefinite (archive to S3/Parquet for cold storage)

## Querying Examples

### Latest 100 ticks for BTC/USD from Binance
```sql
SELECT
    toDateTime(event_time_us / 1000000) AS time,
    symbol,
    price,
    quantity,
    side
FROM market_data.tick
WHERE symbol = 'BTC/USDT'
  AND venue = 'BINANCE'
ORDER BY event_time_us DESC
LIMIT 100;
```

### 1-hour OHLCV for EUR/USD
```sql
SELECT
    timestamp,
    open,
    high,
    low,
    close,
    volume
FROM market_data.bars
WHERE symbol = 'EUR/USD'
  AND venue = 'OANDA'
  AND interval = '1h'
  AND timestamp >= now() - INTERVAL 7 DAY
ORDER BY timestamp;
```

### Top 10 most active symbols today
```sql
SELECT
    symbol,
    venue,
    count() AS tick_count,
    sum(quantity) AS total_volume
FROM market_data.tick
WHERE toDate(toDateTime(event_time_us / 1000000)) = today()
GROUP BY symbol, venue
ORDER BY tick_count DESC
LIMIT 10;
```

## Performance Tuning

### Index Granularity
Default: 8192 rows per granule. Adjust for your data volume:
- High-frequency data (>1M ticks/day): 4096
- Medium frequency: 8192 (default)
- Low frequency: 16384

### Compression
ClickHouse automatically uses LZ4 compression. For archival, use ZSTD:
```sql
ALTER TABLE market_data.tick MODIFY SETTING compress = 'ZSTD';
```

## Backup & Export

### Export to Parquet (for S3 cold storage)
```sql
SELECT *
FROM market_data.tick
WHERE toDate(toDateTime(event_time_us / 1000000)) BETWEEN '2024-01-01' AND '2024-01-31'
INTO OUTFILE '/var/lib/clickhouse/user_files/2024-01-ticks.parquet'
FORMAT Parquet;
```

### Restore from Parquet
```sql
INSERT INTO market_data.tick
FROM INFILE '/var/lib/clickhouse/user_files/2024-01-ticks.parquet'
FORMAT Parquet;
```

## Monitoring

ClickHouse exposes metrics at:
- Prometheus: `http://localhost:9363/metrics` (requires clickhouse_exporter)
- System tables: `system.metrics`, `system.query_log`

Example query for table sizes:
```sql
SELECT
    table,
    formatReadableSize(sum(bytes)) AS size,
    sum(rows) AS rows
FROM system.parts
WHERE database = 'market_data'
  AND active
GROUP BY table
ORDER BY sum(bytes) DESC;
```
