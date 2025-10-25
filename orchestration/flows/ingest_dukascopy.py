"""Prefect flow for ingesting Dukascopy historical forex tick data."""

from __future__ import annotations

import os
import struct
import lzma
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
from prefect import flow, task
from prefect.tasks import task_input_hash

import logging

logger = logging.getLogger(__name__)

DUKASCOPY_BASE_URL = "https://datafeed.dukascopy.com/datafeed"


@task(cache_key_fn=task_input_hash, retries=3, retry_delay_seconds=5)
async def download_bi5_file(instrument: str, year: int, month: int, day: int, hour: int) -> bytes | None:
    """
    Download a single Dukascopy .bi5 file for a specific hour.
    
    Args:
        instrument: Forex pair (e.g., 'EURUSD')
        year: Year (e.g., 2024)
        month: Month (0-11, 0=January)
        day: Day of month (0-30)
        hour: Hour (0-23)
    
    Returns:
        Raw .bi5 file bytes, or None if file doesn't exist
    """
    # Dukascopy URL format: /{instrument}/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5
    url = f"{DUKASCOPY_BASE_URL}/{instrument}/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            
            if response.status_code == 404:
                logger.debug(f"File not found: {url}")
                return None
            
            response.raise_for_status()
            logger.debug(f"Downloaded {len(response.content)} bytes from {url}")
            return response.content
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


@task
def decompress_bi5(data: bytes) -> list[tuple[int, float, float, float, float]]:
    """
    Decompress and parse .bi5 file.
    
    .bi5 format:
    - LZMA compressed
    - Each tick: 20 bytes (timestamp_ms: 4 bytes, ask: 4 bytes, bid: 4 bytes, ask_vol: 4 bytes, bid_vol: 4 bytes)
    - Prices stored as integers (multiply by point value, typically 0.00001 for most pairs)
    
    Returns:
        List of (timestamp_ms, bid, ask, bid_vol, ask_vol) tuples
    """
    if not data:
        return []
    
    try:
        decompressed = lzma.decompress(data)
    except Exception as e:
        logger.error(f"Failed to decompress .bi5 file: {e}")
        return []
    
    # Parse binary ticks
    ticks = []
    tick_size = 20  # bytes per tick
    num_ticks = len(decompressed) // tick_size
    
    for i in range(num_ticks):
        offset = i * tick_size
        chunk = decompressed[offset:offset + tick_size]
        
        if len(chunk) < tick_size:
            break
        
        # Unpack: timestamp (int32), ask (int32), bid (int32), ask_vol (float32), bid_vol (float32)
        timestamp_ms, ask_int, bid_int, ask_vol, bid_vol = struct.unpack(">IIIff", chunk)
        
        # Convert prices (stored as integers, divide by 100000 for most pairs)
        point_value = 0.00001
        bid = bid_int * point_value
        ask = ask_int * point_value
        
        ticks.append((timestamp_ms, bid, ask, bid_vol, ask_vol))
    
    return ticks


@task
async def write_ticks_to_storage(instrument: str, ticks: list[tuple], base_time: datetime) -> None:
    """
    Write ticks to ClickHouse or Parquet.
    
    TODO: Implement ClickHouse writer.
    For now, writes to Parquet as placeholder.
    """
    if not ticks:
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(ticks, columns=["timestamp_offset_ms", "bid", "ask", "bid_vol", "ask_vol"])
    
    # Compute absolute timestamps
    df["timestamp"] = base_time + pd.to_timedelta(df["timestamp_offset_ms"], unit="ms")
    
    # Add metadata
    df["symbol"] = instrument.replace("USD", "/USD")  # Normalize to EUR/USD format
    df["venue"] = "DUKASCOPY"
    df["asset_class"] = "FOREX"
    df["price"] = (df["bid"] + df["ask"]) / 2.0  # Mid price
    df["quantity"] = 0.0  # Forex quotes don't have size
    df["side"] = "UNKNOWN"
    
    # Write to Parquet
    output_dir = Path("data/historical/dukascopy")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    date_str = base_time.strftime("%Y%m%d_%H")
    output_file = output_dir / f"{instrument}_{date_str}.parquet"
    
    df.to_parquet(output_file, index=False)
    logger.info(f"Wrote {len(df)} ticks to {output_file}")
    
    # TODO: Replace with ClickHouse insert
    # await clickhouse_client.insert("market_data.tick", df.to_dict('records'))


@flow(name="dukascopy-ingest-monthly", log_prints=True)
async def ingest_dukascopy_monthly(
    instruments: list[str],
    year: int,
    month: int
) -> None:
    """
    Ingest a full month of Dukascopy tick data for given instruments.
    
    Args:
        instruments: List of instruments (e.g., ['EURUSD', 'GBPUSD'])
        year: Year (e.g., 2024)
        month: Month (1-12)
    """
    logger.info(f"Starting Dukascopy ingestion for {len(instruments)} instruments: {year}-{month:02d}")
    
    # Convert month from 1-12 to 0-11 (Dukascopy uses 0-indexed months)
    duka_month = month - 1
    
    # Determine days in month
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    
    current_day = datetime(year, month, 1)
    
    while current_day < next_month:
        day = current_day.day - 1  # Dukascopy uses 0-indexed days
        
        for hour in range(24):
            for instrument in instruments:
                # Download .bi5 file
                bi5_data = await download_bi5_file(instrument, year, duka_month, day, hour)
                
                if bi5_data:
                    # Decompress and parse
                    ticks = decompress_bi5(bi5_data)
                    
                    if ticks:
                        # Write to storage
                        base_time = datetime(year, month, current_day.day, hour)
                        await write_ticks_to_storage(instrument, ticks, base_time)
        
        current_day += timedelta(days=1)
    
    logger.info(f"Dukascopy ingestion complete for {year}-{month:02d}")


# Example invocation
if __name__ == "__main__":
    import asyncio
    
    # Fetch EUR/USD data for January 2024
    asyncio.run(
        ingest_dukascopy_monthly(
            instruments=["EURUSD", "GBPUSD"],
            year=2024,
            month=1
        )
    )
