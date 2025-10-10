"""Example: Complete microstructure detection system with API and alerts."""

import asyncio
import os
import time

from src.core.logging_config import get_logger
from src.microstructure.alerting import AlertConfig, AlertManager, AlertPriority
from src.microstructure.detector import (
    CUSUMConfig,
    DetectionSignal,
    MicrostructureDetector,
)
from src.microstructure.features import (
    MicrostructureFeatures,
    OrderBookFeatureExtractor,
    TradeFeatureExtractor,
)
from src.microstructure.stream import BinanceOrderBookStream, OrderBookSnapshot, Trade

logger = get_logger(__name__)


class MicrostructureAlertSystem:
    """Complete microstructure detection system with alerting."""

    def __init__(
        self,
        symbol: str = "BTC/USDT",
        alert_config: AlertConfig = None,
    ):
        """Initialize alert system."""
        self.symbol = symbol

        # Initialize components
        self.stream = BinanceOrderBookStream(symbol=symbol)
        self.ob_features = OrderBookFeatureExtractor()
        self.trade_features = TradeFeatureExtractor()

        cusum_config = CUSUMConfig(
            threshold=3.0,
            drift=0.5,
            warmup_samples=20,
        )
        self.detector = MicrostructureDetector(cusum_config=cusum_config)

        # Initialize alerting
        self.alert_config = alert_config or AlertConfig()
        self.alert_manager = AlertManager(self.alert_config)

        logger.info(
            "alert_system_initialized",
            symbol=symbol,
            channels=len(self.alert_manager.channels),
        )

    async def on_signal(self, signal: DetectionSignal):
        """Handle detection signal."""
        signal_id = signal.metadata.get("signal_id", "unknown")
        logger.info(
            "signal_detected",
            signal_id=signal_id,
            signal_type=signal.signal_type,
            score=signal.score,
        )

        # Determine priority based on score
        if signal.score >= 0.8:
            priority = AlertPriority.HIGH
        elif signal.score >= 0.6:
            priority = AlertPriority.MEDIUM
        else:
            priority = AlertPriority.LOW

        # Send alerts
        results = await self.alert_manager.send_alert(signal, priority)

        logger.info(
            "alerts_sent",
            signal_id=signal_id,
            results=results,
        )

    async def run(self, duration_seconds: float = 300.0):
        """Run the alert system."""
        logger.info(
            "alert_system_starting",
            symbol=self.symbol,
            duration=duration_seconds,
        )

        try:
            # Register callbacks
            async def on_orderbook(snapshot: OrderBookSnapshot):
                features = self.ob_features.extract(snapshot)
                signal = self.detector.process(features)
                if signal:
                    await self.on_signal(signal)

            async def on_trade(trade: Trade):
                features = self.trade_features.extract(trade)
                signal = self.detector.process(features)
                if signal:
                    await self.on_signal(signal)

            self.stream.register_orderbook_callback(on_orderbook)
            self.stream.register_trade_callback(on_trade)

            # Start streaming
            await self.stream.start()

            # Run for specified duration
            start_time = time.time()
            while time.time() - start_time < duration_seconds:
                await asyncio.sleep(1)

                # Print stats every 30 seconds
                if int(time.time() - start_time) % 30 == 0:
                    stats = self.alert_manager.get_stats()
                    logger.info("alert_stats", **stats)

        finally:
            # Cleanup
            await self.stream.stop()

            final_stats = self.alert_manager.get_stats()
            logger.info(
                "alert_system_stopped",
                final_stats=final_stats,
            )


async def demo_with_env_vars():
    """Demo using environment variables for configuration."""
    print("\n" + "=" * 70)
    print(" MICROSTRUCTURE ALERT SYSTEM DEMO")
    print("=" * 70)

    # Load configuration from environment
    alert_config = AlertConfig(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        min_score=0.5,
        cooldown_seconds=60.0,
        max_alerts_per_minute=5,
        max_alerts_per_hour=50,
    )

    # Check if any channels are configured
    channels_configured = sum([
        bool(alert_config.slack_webhook_url),
        bool(alert_config.discord_webhook_url),
        bool(alert_config.telegram_bot_token and alert_config.telegram_chat_id),
    ])

    if channels_configured == 0:
        print("\n⚠️  WARNING: No alert channels configured!")
        print("\nTo enable alerts, set one or more of these environment variables:")
        print("  - SLACK_WEBHOOK_URL")
        print("  - DISCORD_WEBHOOK_URL")
        print("  - TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        print("\nThe system will run without sending alerts.\n")

    # Initialize system
    system = MicrostructureAlertSystem(
        symbol="BTC/USDT",
        alert_config=alert_config,
    )

    # Run for 5 minutes
    print(f"\nRunning alert system for 5 minutes...")
    print(f"Symbol: {system.symbol}")
    print(f"Alert channels configured: {channels_configured}")
    print("\nPress Ctrl+C to stop early\n")

    try:
        await system.run(duration_seconds=300.0)
    except KeyboardInterrupt:
        print("\n\nStopping system...")

    print("\n" + "=" * 70)
    print(" DEMO COMPLETED")
    print("=" * 70)


async def demo_test_alerts():
    """Demo: Test alerts with synthetic signals."""
    print("\n" + "=" * 70)
    print(" TESTING ALERT CHANNELS")
    print("=" * 70)

    # Configure alerts
    alert_config = AlertConfig(
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        min_score=0.0,  # Send all test alerts
        cooldown_seconds=0.0,  # No cooldown for testing
    )

    manager = AlertManager(alert_config)

    if not manager.channels:
        print("\n⚠️  No alert channels configured. Skipping test.\n")
        return

    print(f"\nConfigured channels: {len(manager.channels)}")
    for channel in manager.channels:
        print(f"  - {channel.__class__.__name__}")

    # Create test signals
    test_signals = [
        DetectionSignal(
            timestamp=time.time(),
            signal_type="buy_imbalance",
            score=0.85,
            features={
                "book_imbalance_top5": 0.65,
                "trade_imbalance_1s": 0.72,
                "volume_burst": 3.2,
            },
            cooldown_until=time.time() + 60.0,
            metadata={
                "symbol": "BTC/USDT",
                "signal_id": "test_high_score",
                "test": True,
            },
        ),
        DetectionSignal(
            timestamp=time.time(),
            signal_type="sell_imbalance",
            score=0.55,
            features={
                "book_imbalance_top5": -0.45,
                "trade_imbalance_1s": -0.38,
                "volume_burst": 2.1,
            },
            cooldown_until=time.time() + 60.0,
            metadata={
                "symbol": "ETH/USDT",
                "signal_id": "test_medium_score",
                "test": True,
            },
        ),
    ]

    # Send test alerts
    print("\nSending test alerts...\n")

    for i, signal in enumerate(test_signals, 1):
        signal_id = signal.metadata.get("signal_id", "unknown")
        print(f"Test {i}/{len(test_signals)}: {signal_id}")

        priority = (
            AlertPriority.HIGH if signal.score >= 0.8
            else AlertPriority.MEDIUM
        )

        results = await manager.send_alert(signal, priority)

        for channel, success in results.items():
            status = "✅ Success" if success else "❌ Failed"
            print(f"  {channel}: {status}")

        await asyncio.sleep(2)  # Pause between tests

    # Print stats
    stats = manager.get_stats()
    print("\n" + "=" * 70)
    print("ALERT STATISTICS")
    print("=" * 70)
    print(f"Total alerts sent: {stats['total_alerts_sent']}")
    print("\nBy channel:")
    for channel, count in stats['alerts_by_channel'].items():
        print(f"  {channel}: {count}")

    print("\n✅ Alert channel test completed\n")


def main():
    """Run example based on mode."""
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "live"

    if mode == "test":
        # Test alerts with synthetic signals
        asyncio.run(demo_test_alerts())
    else:
        # Run live with real market data
        asyncio.run(demo_with_env_vars())


if __name__ == "__main__":
    main()
