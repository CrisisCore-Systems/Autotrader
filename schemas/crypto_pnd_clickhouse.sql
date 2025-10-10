-- ClickHouse schema for crypto pump & dump detection feature storage
CREATE TABLE IF NOT EXISTS market_features (
    event_time DateTime,
    token_id String,
    momentum Float64,
    volume_anomaly Float64,
    gas_spike Float64
) ENGINE = MergeTree()
ORDER BY (token_id, event_time);

CREATE TABLE IF NOT EXISTS social_features (
    event_time DateTime,
    token_id String,
    avg_sentiment Float64,
    bot_ratio Float64,
    hype Float64
) ENGINE = MergeTree()
ORDER BY (token_id, event_time);
