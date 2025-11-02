"""Quick sanity check for IBKR historical bar data.

Usage
-----
From repository root with an active IB Gateway/TWS on 127.0.0.1:7497:

    python Autotrader\\scripts\\inspect_ib_data.py --symbol SPY --duration "1 M"

It prints the min/max close prices, the first & last few bars, and writes the
full dataset to CSV if requested.
"""

import argparse
import logging
import sys
from pathlib import Path

from ib_insync import IB

# Ensure the Autotrader package root is on sys.path so `src` imports resolve.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.intraday.enhanced_pipeline import EnhancedDataPipeline


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect IBKR historical bar data")
    parser.add_argument("--symbol", type=str, default="SPY", help="Symbol, e.g. SPY")
    parser.add_argument(
        "--duration",
        type=str,
        default="1 M",
        help="IB duration string (e.g. 5 D, 1 M, 3 M, 1 Y)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="IB host",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7497,
        help="IB port (paper=7497, live=7496 by default)",
    )
    parser.add_argument(
        "--client-id",
        type=int,
        default=998,
        help="Client ID for the temporary connection",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Optional path to write the bars as CSV",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()

    logger.info(
        "Connecting to IBKR @ %s:%s (clientId=%s)",
        args.host,
        args.port,
        args.client_id,
    )

    ib = IB()
    ib.connect(args.host, args.port, clientId=args.client_id)

    pipeline = EnhancedDataPipeline(
        mode="historical",
        ib=ib,
        symbol=args.symbol,
        duration=args.duration,
        replay_speed=1.0,
    )

    try:
        pipeline.start()

        bars = []
        data_source = getattr(pipeline, "data_source", None)
        if data_source and hasattr(data_source, "bars"):
            # Historical data fetch happens synchronously before replay begins.
            bars = list(data_source.bars)

        if not bars:
            logger.info("Waiting for pipeline to load bars...")
            while pipeline.bars_generated == 0:
                ib.waitOnUpdate(timeout=1)
            bars = list(pipeline.bar_buffer)

        if not bars:
            raise RuntimeError("No bars collected; ensure IBKR historical data is available")

        num_bars = len(bars)

        closes = [bar.close for bar in bars]
        volumes = [bar.volume for bar in bars]

        logger.info("Loaded %s bars for %s (%s)", num_bars, args.symbol, args.duration)
        logger.info("Close range: %.2f - %.2f", min(closes), max(closes))
        logger.info("Volume range: %s - %s", min(volumes), max(volumes))
        logger.info("First 5 closes: %s", [round(c, 2) for c in closes[:5]])
        logger.info("Last 5 closes: %s", [round(c, 2) for c in closes[-5:]])

        if args.csv:
            import csv

            logger.info("Writing %s bars to %s", num_bars, args.csv)
            args.csv.parent.mkdir(parents=True, exist_ok=True)
            with args.csv.open("w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "open", "high", "low", "close", "volume", "vwap", "num_trades"])
                for bar in bars:
                    writer.writerow(
                        [
                            bar.timestamp,
                            bar.open,
                            bar.high,
                            bar.low,
                            bar.close,
                            bar.volume,
                            bar.vwap,
                            bar.num_trades,
                        ]
                    )
            logger.info("CSV written.")
    finally:
        pipeline.stop()
        logger.info("Disconnecting from IBKR")
        ib.disconnect()


if __name__ == "__main__":
    main()
