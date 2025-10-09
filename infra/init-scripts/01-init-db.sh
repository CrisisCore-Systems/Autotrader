#!/bin/bash
# PostgreSQL initialization script
# Executed on first container start

set -e

echo "Initializing AutoTrader database..."

# Create extensions
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable TimescaleDB extension
    CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
    
    -- Enable pg_stat_statements for query performance monitoring
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
    
    -- Enable pgcrypto for cryptographic functions
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    
    -- Create schemas
    CREATE SCHEMA IF NOT EXISTS public;
    CREATE SCHEMA IF NOT EXISTS metrics;
    CREATE SCHEMA IF NOT EXISTS experiments;
    
    -- Create tables (basic schema - extend as needed)
    CREATE TABLE IF NOT EXISTS public.tokens (
        id SERIAL PRIMARY KEY,
        address VARCHAR(42) UNIQUE NOT NULL,
        symbol VARCHAR(20),
        name VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS public.token_metrics (
        id SERIAL PRIMARY KEY,
        token_address VARCHAR(42) NOT NULL,
        timestamp TIMESTAMPTZ NOT NULL,
        price_usd NUMERIC(20, 8),
        volume_24h NUMERIC(20, 8),
        market_cap NUMERIC(20, 8),
        gem_score NUMERIC(5, 2),
        FOREIGN KEY (token_address) REFERENCES public.tokens(address)
    );
    
    -- Convert to hypertable for time-series optimization
    SELECT create_hypertable('public.token_metrics', 'timestamp', if_not_exists => TRUE);
    
    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_token_metrics_token_time 
        ON public.token_metrics (token_address, timestamp DESC);
    
    CREATE INDEX IF NOT EXISTS idx_token_metrics_gem_score 
        ON public.token_metrics (gem_score DESC, timestamp DESC);
    
    -- Create experiments table
    CREATE TABLE IF NOT EXISTS experiments.runs (
        id SERIAL PRIMARY KEY,
        config_hash VARCHAR(64) UNIQUE NOT NULL,
        description TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        status VARCHAR(20) DEFAULT 'running',
        metadata JSONB
    );
    
    CREATE INDEX IF NOT EXISTS idx_experiments_hash 
        ON experiments.runs (config_hash);
    
    -- Grant permissions
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA metrics TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA experiments TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $POSTGRES_USER;
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA experiments TO $POSTGRES_USER;
    
    -- Set up retention policy (keep data for 90 days)
    SELECT add_retention_policy('public.token_metrics', INTERVAL '90 days', if_not_exists => TRUE);
    
    -- Create continuous aggregate for hourly rollups
    CREATE MATERIALIZED VIEW IF NOT EXISTS public.token_metrics_hourly
    WITH (timescaledb.continuous) AS
    SELECT 
        token_address,
        time_bucket('1 hour', timestamp) AS bucket,
        AVG(price_usd) AS avg_price,
        MAX(price_usd) AS max_price,
        MIN(price_usd) AS min_price,
        SUM(volume_24h) AS total_volume,
        AVG(gem_score) AS avg_gem_score
    FROM public.token_metrics
    GROUP BY token_address, bucket
    WITH NO DATA;
    
    -- Add refresh policy for continuous aggregate
    SELECT add_continuous_aggregate_policy('public.token_metrics_hourly',
        start_offset => INTERVAL '3 hours',
        end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour',
        if_not_exists => TRUE);
EOSQL

echo "AutoTrader database initialization complete."
