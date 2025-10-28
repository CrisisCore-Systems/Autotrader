"""
Test bar constructors with real Binance WebSocket data.

This script streams live BTC/USDT trades from Binance and constructs
bars in real-time to validate volume/dollar/imbalance bars with actual
high-frequency trade data.

Usage:
    python test_bars_binance_live.py
"""

import asyncio
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import json

from autotrader.connectors.binance_ws import BinanceConnector
from autotrader.data_prep.bars import BarFactory


class LiveBarTester:
    """Test bar construction with live Binance data."""

    def __init__(self, symbol: str = "BTCUSDT", duration_seconds: int = 60):
        """
        Initialize live bar tester.

        Args:
            symbol: Trading symbol (e.g., 'BTCUSDT')
            duration_seconds: How long to collect data (default 60s)
        """
        self.symbol = symbol.upper()
        self.duration_seconds = duration_seconds
        self.trades = []
        self.connector = None

    async def collect_trades(self):
        """Collect trades from Binance WebSocket."""
        print(f"\n🔄 Connecting to Binance WebSocket for {self.symbol}...")
        print(f"⏱️  Collecting trades for {self.duration_seconds} seconds...")

        self.connector = BinanceConnector(
            symbols=[self.symbol],
            stream_type="trade",
            buffer_size=10000
        )

        # Start connector
        await self.connector.start()

        # Wait for initial connection
        await asyncio.sleep(2)

        # Collect for duration
        start_time = asyncio.get_event_loop().time()
        while (asyncio.get_event_loop().time() - start_time) < self.duration_seconds:
            # Get buffered ticks
            ticks = self.connector.get_buffered_ticks()

            for tick in ticks:
                trade = {
                    "timestamp_utc": tick.timestamp,
                    "symbol": tick.symbol,
                    "price": tick.price,
                    "quantity": tick.quantity,
                    "side": tick.side.value,
                }
                self.trades.append(trade)

            # Print progress
            if len(self.trades) % 100 == 0 and len(self.trades) > 0:
                print(f"  Collected {len(self.trades)} trades...")

            await asyncio.sleep(0.1)

        # Stop connector
        await self.connector.stop()

        print(f"✅ Collected {len(self.trades)} trades")

    def create_bars_and_save(self):
        """Create all bar types and save results."""
        if not self.trades:
            print("❌ No trades collected!")
            return

        # Convert to DataFrame
        df = pd.DataFrame(self.trades)

        print(f"\n📊 Trade Data Summary:")
        print(f"  Trades: {len(df):,}")
        print(f"  Timespan: {(df['timestamp_utc'].max() - df['timestamp_utc'].min()).total_seconds():.1f}s")
        print(f"  Price range: ${df['price'].min():,.2f} - ${df['price'].max():,.2f}")
        print(f"  Total volume: {df['quantity'].sum():,.4f} BTC")
        print(f"  Total dollar volume: ${(df['price'] * df['quantity']).sum():,.2f}")

        # Create output directory
        output_dir = Path("data/bars/binance_live")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save raw trades
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        trades_file = output_dir / f"{self.symbol}_trades_{timestamp}.parquet"
        df.to_parquet(trades_file)
        print(f"\n💾 Saved raw trades to: {trades_file}")

        # Test all 6 bar types
        bar_configs = [
            {"bar_type": "time", "interval": "1min", "name": "1min"},
            {"bar_type": "tick", "num_ticks": 100, "name": "100tick"},
            {"bar_type": "volume", "volume_threshold": 1.0, "name": "1btc_vol"},
            {"bar_type": "dollar", "dollar_threshold": 100_000, "name": "100k_dollar"},
            {"bar_type": "imbalance", "imbalance_threshold": 0.5, "name": "0.5btc_imbal"},
            {"bar_type": "run", "num_runs": 10, "name": "10run"},
        ]

        print("\n" + "=" * 70)
        print("TESTING ALL 6 BAR TYPES WITH BINANCE DATA")
        print("=" * 70)

        results = []

        for config in bar_configs:
            bar_type = config.pop("bar_type")
            name = config.pop("name")

            print(f"\n🔨 Creating {name} bars...")

            try:
                bars = BarFactory.create(
                    bar_type=bar_type,
                    df=df,
                    **config
                )

                if bars.empty:
                    print(f"  ⚠️  No bars created (threshold too high?)")
                    results.append((name, 0, "EMPTY"))
                    continue

                # Validate OHLCV
                high_check = (bars["high"] >= bars["open"]) & (bars["high"] >= bars["close"])
                low_check = (bars["low"] <= bars["open"]) & (bars["low"] <= bars["close"])
                vwap_check = (bars["vwap"] >= bars["low"]) & (bars["vwap"] <= bars["high"])

                if high_check.all() and low_check.all() and vwap_check.all():
                    validation = "✅ PASSED"
                else:
                    validation = "❌ FAILED"

                # Save bars
                bar_file = output_dir / f"{self.symbol}_{name}_bars_{timestamp}.parquet"
                bars.to_parquet(bar_file)

                # Print stats
                stats = BarFactory.get_statistics(bar_type, bars, **config)
                print(f"  Bars created: {len(bars)}")
                print(f"  Avg volume/bar: {stats['volume']['mean']:,.4f} BTC")
                print(f"  Validation: {validation}")
                print(f"  Saved to: {bar_file.name}")

                results.append((name, len(bars), validation))

            except Exception as e:
                print(f"  ❌ Error: {e}")
                results.append((name, 0, f"ERROR: {e}"))

        # Final summary
        print("\n" + "=" * 70)
        print("FINAL SUMMARY — BINANCE LIVE DATA")
        print("=" * 70)
        print(f"\n{'Bar Type':<20} {'Bars Created':<15} {'Validation':<15}")
        print("-" * 50)
        for name, count, validation in results:
            print(f"{name:<20} {count:<15} {validation:<15}")

        print("\n" + "=" * 70)
        print(f"📁 All files saved to: {output_dir.absolute()}")


async def main():
    """Run the live bar test."""
    print("=" * 70)
    print("LIVE BAR CONSTRUCTION TEST — BINANCE BTC/USDT")
    print("=" * 70)

    tester = LiveBarTester(symbol="BTCUSDT", duration_seconds=60)

    try:
        await tester.collect_trades()
        tester.create_bars_and_save()

        print("\n✅ Test complete!")

    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
