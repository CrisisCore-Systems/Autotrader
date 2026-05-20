"""Prefect flow for ingesting Dukascopy historical forex tick data."""

from __future__ import annotations

import lzma
import logging
import struct
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pandas as pd
from prefect import flow, task
from prefect.tasks import task_input_hash

logger = logging.getLogger(__name__)

DUKASCOPY_BASE_URL = "https://datafeed.dukascopy.com/datafeed"
DUKASCOPY_RETRY_ATTEMPTS = 3
DUKASCOPY_RETRY_DELAY_SECONDS = 5


def normalize_dukascopy_instrument(symbol: str) -> str:
    return str(symbol).replace("/", "").replace("-", "").upper()


def normalize_display_symbol(symbol: str) -> str:
    raw = normalize_dukascopy_instrument(symbol)
    if len(raw) == 6:
        return f"{raw[:3]}/{raw[3:]}"
    return raw


async def fetch_bi5_file(instrument: str, year: int, month: int, day: int, hour: int) -> bytes | None:
    """Download a single Dukascopy .bi5 file for a specific hour."""
    normalized_instrument = normalize_dukascopy_instrument(instrument)
    url = f"{DUKASCOPY_BASE_URL}/{normalized_instrument}/{year}/{month:02d}/{day:02d}/{hour:02d}h_ticks.bi5"

    async with httpx.AsyncClient() as client:
        for attempt in range(1, DUKASCOPY_RETRY_ATTEMPTS + 1):
            try:
                response = await client.get(url, timeout=30.0)

                if response.status_code == 404:
                    logger.debug("File not found: %s", url)
                    return None

                response.raise_for_status()
                logger.debug("Downloaded %d bytes from %s", len(response.content), url)
                return response.content

            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                if status_code == 404:
                    return None
                if status_code >= 500 and attempt < DUKASCOPY_RETRY_ATTEMPTS:
                    logger.warning(
                        "Transient Dukascopy server error %s for %s on attempt %d/%d",
                        status_code,
                        url,
                        attempt,
                        DUKASCOPY_RETRY_ATTEMPTS,
                    )
                    await asyncio.sleep(DUKASCOPY_RETRY_DELAY_SECONDS)
                    continue
                raise
            except httpx.HTTPError:
                if attempt < DUKASCOPY_RETRY_ATTEMPTS:
                    logger.warning(
                        "Transient Dukascopy network error for %s on attempt %d/%d",
                        url,
                        attempt,
                        DUKASCOPY_RETRY_ATTEMPTS,
                    )
                    await asyncio.sleep(DUKASCOPY_RETRY_DELAY_SECONDS)
                    continue
                raise

    return None


def decompress_bi5_payload(data: bytes) -> list[tuple[int, float, float, float, float]]:
    """Decompress and parse a Dukascopy .bi5 payload."""
    if not data:
        return []

    try:
        decompressed = lzma.decompress(data)
    except Exception as exc:
        logger.error("Failed to decompress .bi5 file: %s", exc)
        return []

    ticks = []
    tick_size = 20
    num_ticks = len(decompressed) // tick_size

    for index in range(num_ticks):
        offset = index * tick_size
        chunk = decompressed[offset:offset + tick_size]

        if len(chunk) < tick_size:
            break

        timestamp_ms, ask_int, bid_int, ask_vol, bid_vol = struct.unpack(">IIIff", chunk)
        point_value = 0.00001
        bid = bid_int * point_value
        ask = ask_int * point_value
        ticks.append((timestamp_ms, bid, ask, bid_vol, ask_vol))

    return ticks


def write_ticks_parquet(
    instrument: str,
    ticks: list[tuple[int, float, float, float, float]],
    base_time: datetime,
    output_dir: str | Path = "data/historical/dukascopy",
) -> Path | None:
    """Write parsed ticks to a Parquet file and return the output path."""
    if not ticks:
        return None

    normalized_instrument = normalize_dukascopy_instrument(instrument)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(ticks, columns=["timestamp_offset_ms", "bid", "ask", "bid_vol", "ask_vol"])
    df["timestamp"] = base_time + pd.to_timedelta(df["timestamp_offset_ms"], unit="ms")
    df["symbol"] = normalize_display_symbol(normalized_instrument)
    df["venue"] = "DUKASCOPY"
    df["asset_class"] = "FOREX"
    df["price"] = (df["bid"] + df["ask"]) / 2.0
    df["quantity"] = 0.0
    df["side"] = "UNKNOWN"

    date_str = base_time.strftime("%Y%m%d_%H")
    output_file = output_root / f"{normalized_instrument}_{date_str}.parquet"
    df.to_parquet(output_file, index=False)
    logger.info("Wrote %d ticks to %s", len(df), output_file)
    return output_file


async def ingest_dukascopy_range(
    instruments: list[str],
    start_time: datetime,
    end_time: datetime,
    output_dir: str | Path = "data/historical/dukascopy",
) -> list[Path]:
    """Ingest Dukascopy ticks over a local time range [start_time, end_time)."""
    if end_time <= start_time:
        raise ValueError("end_time must be later than start_time")

    written_files: list[Path] = []
    current_time = start_time.replace(minute=0, second=0, microsecond=0)

    while current_time < end_time:
        duka_month = current_time.month - 1
        duka_day = current_time.day - 1

        for instrument in instruments:
            bi5_data = await fetch_bi5_file(
                instrument,
                current_time.year,
                duka_month,
                duka_day,
                current_time.hour,
            )
            if not bi5_data:
                continue

            ticks = decompress_bi5_payload(bi5_data)
            output_path = write_ticks_parquet(instrument, ticks, current_time, output_dir=output_dir)
            if output_path is not None:
                written_files.append(output_path)

        current_time += timedelta(hours=1)

    return written_files


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
    return await fetch_bi5_file(instrument, year, month, day, hour)


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
    return decompress_bi5_payload(data)


@task
async def write_ticks_to_storage(
    instrument: str,
    ticks: list[tuple],
    base_time: datetime,
    output_dir: str | Path = "data/historical/dukascopy",
) -> str | None:
    """
    Write ticks to ClickHouse or Parquet.
    
    TODO: Implement ClickHouse writer.
    For now, writes to Parquet as placeholder.
    """
    output_path = write_ticks_parquet(instrument, ticks, base_time, output_dir=output_dir)
    if output_path is None:
        return None
    # TODO: Replace with ClickHouse insert
    # await clickhouse_client.insert("market_data.tick", df.to_dict('records'))
    return str(output_path)


@flow(name="dukascopy-ingest-monthly", log_prints=True)
async def ingest_dukascopy_monthly(
    instruments: list[str],
    year: int,
    month: int,
    output_dir: str | Path = "data/historical/dukascopy",
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
                        await write_ticks_to_storage(instrument, ticks, base_time, output_dir=output_dir)
        
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
