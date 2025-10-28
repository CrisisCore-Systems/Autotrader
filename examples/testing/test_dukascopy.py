"""Test script for Dukascopy historical tick ingestion - downloads 1 hour of data."""

import asyncio
import logging
import struct
import lzma
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DUKASCOPY_BASE_URL = "https://datafeed.dukascopy.com/datafeed"


async def download_bi5_file(instrument: str, year: int, month: int, day: int, hour: int) -> bytes | None:
    """Download a single Dukascopy .bi5 file."""
    url = f"{DUKASCOPY_BASE_URL}/{instrument}/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=30.0)
            
            if response.status_code == 404:
                logger.debug(f"File not found: {url}")
                return None
            
            response.raise_for_status()
            logger.info(f"Downloaded {len(response.content)} bytes from {url}")
            return response.content
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


def decompress_bi5(data: bytes) -> list[tuple[int, float, float, float, float]]:
    """Decompress and parse .bi5 file."""
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
        
        # Convert prices
        point_value = 0.00001
        bid = bid_int * point_value
        ask = ask_int * point_value
        
        ticks.append((timestamp_ms, bid, ask, bid_vol, ask_vol))
    
    return ticks


async def write_ticks_to_storage(instrument: str, ticks: list[tuple], base_time: datetime) -> None:
    """Write ticks to Parquet."""
    if not ticks:
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(ticks, columns=["timestamp_offset_ms", "bid", "ask", "bid_vol", "ask_vol"])
    
    # Compute absolute timestamps
    df["timestamp"] = base_time + pd.to_timedelta(df["timestamp_offset_ms"], unit="ms")
    
    # Add metadata
    df["symbol"] = instrument.replace("USD", "/USD")
    df["venue"] = "DUKASCOPY"
    df["asset_class"] = "FOREX"
    df["price"] = (df["bid"] + df["ask"]) / 2.0
    df["quantity"] = 0.0
    df["side"] = "UNKNOWN"
    
    # Write to Parquet
    output_dir = Path("data/historical/dukascopy")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    date_str = base_time.strftime("%Y%m%d_%H")
    output_file = output_dir / f"{instrument}_{date_str}.parquet"
    
    df.to_parquet(output_file, index=False)
    logger.info(f"Wrote {len(df)} ticks to {output_file}")


async def test_single_hour():
    """Download and parse 1 hour of EUR/USD ticks."""
    
    # Test data: October 18, 2024 (Friday), 10:00 UTC (active market hours)
    instrument = "EURUSD"
    year = 2024
    month = 9  # October (0-indexed, so 9 = October)
    day = 17   # Day 18 (0-indexed, so 17 = October 18)
    hour = 10  # 10 AM UTC (London/EU session)
    
    logger.info(f"Downloading {instrument} tick data for 2024-10-18 10:00 UTC...")
    
    # Download .bi5 file
    bi5_data = await download_bi5_file(instrument, year, month, day, hour)
    
    if not bi5_data:
        logger.error("Failed to download data - file not found or network error")
        return
    
    logger.info(f"Downloaded {len(bi5_data)} bytes")
    
    # Decompress and parse
    logger.info("Decompressing and parsing binary ticks...")
    ticks = decompress_bi5(bi5_data)
    
    if not ticks:
        logger.error("No ticks found in file")
        return
    
    logger.info(f"Parsed {len(ticks)} ticks")
    
    # Print first 5 ticks
    logger.info("First 5 ticks:")
    for i, (ts_offset, bid, ask, bid_vol, ask_vol) in enumerate(ticks[:5]):
        logger.info(f"  Tick {i+1}: bid={bid:.5f}, ask={ask:.5f}, spread={ask-bid:.5f}")
    
    # Write to storage
    base_time = datetime(2024, 10, 18, 10, 0, 0)
    await write_ticks_to_storage(instrument, ticks, base_time)
    
    logger.info("✅ Test completed successfully!")
    logger.info(f"📁 Data saved to: data/historical/dukascopy/{instrument}_20241018_10.parquet")


if __name__ == "__main__":
    asyncio.run(test_single_hour())
