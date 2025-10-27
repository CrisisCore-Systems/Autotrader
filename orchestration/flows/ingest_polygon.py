"""Prefect flow for ingesting historical data from Polygon.io."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
from prefect import flow, task
from prefect.tasks import task_input_hash

import logging

logger = logging.getLogger(__name__)

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "")
POLYGON_BASE_URL = "https://api.polygon.io"


@task(cache_key_fn=task_input_hash, retries=3, retry_delay_seconds=10)
async def fetch_daily_bars(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetch daily OHLCV bars from Polygon.io.
    
    Args:
        symbol: Stock symbol (e.g., 'AAPL')
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    
    Returns:
        DataFrame with columns: timestamp, open, high, low, close, volume
    """
    url = f"{POLYGON_BASE_URL}/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}"
    params = {"apiKey": POLYGON_API_KEY, "adjusted": "true", "sort": "asc"}
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
    
    if data.get("status") != "OK" or not data.get("results"):
        logger.warning(f"No data returned for {symbol} from {start_date} to {end_date}")
        return pd.DataFrame()
    
    results = data["results"]
    df = pd.DataFrame(results)
    
    # Rename columns to match schema
    df = df.rename(columns={
        "t": "timestamp",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "vw": "vwap",
        "n": "trade_count"
    })
    
    # Convert timestamp from milliseconds to datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    
    # Add metadata
    df["symbol"] = symbol
    df["venue"] = "POLYGON"
    df["asset_class"] = "EQUITY"
    df["interval"] = "1d"
    
    logger.info(f"Fetched {len(df)} daily bars for {symbol}")
    
    return df


@task
async def write_to_clickhouse(df: pd.DataFrame) -> None:
    """
    Write DataFrame to ClickHouse market_data.bars table.
    
    TODO: Implement actual ClickHouse client.
    For now, writes to Parquet as placeholder.
    """
    if df.empty:
        logger.warning("Empty DataFrame, skipping write")
        return
    
    # Placeholder: Write to Parquet
    output_dir = Path("data/historical/polygon")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    symbol = df["symbol"].iloc[0]
    start = df["timestamp"].min().strftime("%Y%m%d")
    end = df["timestamp"].max().strftime("%Y%m%d")
    
    output_file = output_dir / f"{symbol}_{start}_{end}.parquet"
    df.to_parquet(output_file, index=False)
    
    logger.info(f"Wrote {len(df)} rows to {output_file}")
    
    # TODO: Replace with ClickHouse insert
    # async with clickhouse_connect.get_async_client(host='localhost', port=9000) as client:
    #     await client.insert("market_data.bars", df.to_dict('records'))


@task
def check_existing_data(symbol: str, start_date: str, end_date: str) -> list[tuple[str, str]]:
    """
    Check for gaps in existing data and return date ranges to fetch.
    
    Returns:
        List of (start_date, end_date) tuples for missing ranges
    """
    # TODO: Query ClickHouse for existing data
    # For now, assume we need to fetch the full range
    logger.info(f"Checking existing data for {symbol} from {start_date} to {end_date}")
    return [(start_date, end_date)]


@flow(name="polygon-ingest-daily", log_prints=True)
async def ingest_polygon_daily(
    symbols: list[str],
    start_date: str,
    end_date: str,
    skip_existing: bool = True
) -> None:
    """
    Ingest daily bars from Polygon.io for multiple symbols.
    
    Args:
        symbols: List of stock symbols (e.g., ['AAPL', 'MSFT', 'TSLA'])
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        skip_existing: If True, skip date ranges that already exist in storage
    """
    if not POLYGON_API_KEY:
        raise ValueError("POLYGON_API_KEY environment variable not set")
    
    logger.info(f"Starting Polygon ingestion for {len(symbols)} symbols from {start_date} to {end_date}")
    
    for symbol in symbols:
        # Check for existing data
        if skip_existing:
            date_ranges = check_existing_data(symbol, start_date, end_date)
        else:
            date_ranges = [(start_date, end_date)]
        
        # Fetch and write each range
        for range_start, range_end in date_ranges:
            df = await fetch_daily_bars(symbol, range_start, range_end)
            if not df.empty:
                await write_to_clickhouse(df)
    
    logger.info("Polygon ingestion complete")


# Example invocation
if __name__ == "__main__":
    import asyncio
    
    # Fetch last 30 days of data for SPY and QQQ
    end = datetime.now()
    start = end - timedelta(days=30)
    
    asyncio.run(
        ingest_polygon_daily(
            symbols=["SPY", "QQQ", "AAPL"],
            start_date=start.strftime("%Y-%m-%d"),
            end_date=end.strftime("%Y-%m-%d")
        )
    )
