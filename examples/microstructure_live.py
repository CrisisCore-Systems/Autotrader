"""Example: Real-time microstructure detection on Binance BTC/USDT."""

import asyncio
from datetime import datetime

from src.microstructure.stream import BinanceOrderBookStream, OrderBookSnapshot, Trade
from src.microstructure.features import (
    OrderBookFeatureExtractor,
    TradeFeatureExtractor,
    MicrostructureFeatures,
)
from src.microstructure.detector import MicrostructureDetector, DetectionSignal


async def main():
    """Run real-time microstructure detection."""
    
    # Initialize components
    symbol = "BTC/USDT"
    
    print(f"🚀 Starting microstructure detector for {symbol}")
    print("=" * 60)
    
    # Create stream
    stream = BinanceOrderBookStream(
        symbol=symbol,
        depth=20,
        trade_buffer_size=1000,
    )
    
    # Create feature extractors
    ob_extractor = OrderBookFeatureExtractor(lookback=100)
    trade_extractor = TradeFeatureExtractor()
    
    # Create detector
    detector = MicrostructureDetector(
        drift_threshold=3.0,
        burst_threshold=2.5,
        cooldown_seconds=30.0,
    )
    
    # Statistics
    book_updates = 0
    trade_count = 0
    signal_count = 0
    
    def on_orderbook(snapshot: OrderBookSnapshot) -> None:
        """Handle order book updates."""
        nonlocal book_updates, signal_count
        
        book_updates += 1
        
        # Extract features
        ob_features = ob_extractor.extract(snapshot)
        trade_features = trade_extractor.extract(snapshot.timestamp)
        
        # Combine features
        now = datetime.now()
        features = MicrostructureFeatures(
            timestamp=snapshot.timestamp,
            orderbook=ob_features,
            trades=trade_features,
            hour_of_day=now.hour,
            minute_of_hour=now.minute,
            is_market_open=True,
        )
        
        # Detect signals
        signal = detector.process(features)
        
        if signal:
            signal_count += 1
            print(f"\n🔔 SIGNAL #{signal_count}")
            print(f"   Type: {signal.signal_type}")
            print(f"   Score: {signal.score:.3f}")
            print(f"   Time: {datetime.fromtimestamp(signal.timestamp)}")
            print(f"   Features:")
            for key, value in signal.features.items():
                print(f"     {key}: {value:.6f}")
            if signal.metadata:
                print(f"   Metadata: {signal.metadata}")
            print()
        
        # Print stats every 100 updates
        if book_updates % 100 == 0:
            stats = stream.get_stats()
            det_stats = detector.get_stats()
            
            print(f"\n📊 Stats (updates: {book_updates})")
            print(f"   Trades: {trade_count}")
            print(f"   Signals: {signal_count}")
            print(f"   Latency (p50/p95): {stats['median_latency_ms']:.1f}ms / {stats['p95_latency_ms']:.1f}ms")
            print(f"   Clock drift: {stats['clock_drift_ms']:.1f}ms")
            print(f"   Reconnects: {stats['reconnect_count']}")
            print(f"   Gaps: {stats['gap_count']}")
            print(f"   Detections by type: {det_stats['signal_counts']}")
            print()
    
    def on_trade(trade: Trade) -> None:
        """Handle trade events."""
        nonlocal trade_count
        trade_count += 1
        trade_extractor.add_trade(trade)
    
    def on_gap(gap_size: int) -> None:
        """Handle detected gaps."""
        print(f"⚠️  Gap detected: {gap_size} messages")
    
    # Register callbacks
    stream.register_book_callback(on_orderbook)
    stream.register_trade_callback(on_trade)
    stream.register_gap_callback(on_gap)
    
    # Start streaming
    print(f"📡 Connecting to Binance WebSocket...")
    print(f"   Symbol: {symbol}")
    print(f"   Depth: {stream.depth}")
    print()
    
    try:
        await stream.start()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        await stream.stop()
        
        # Final stats
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"Order book updates: {book_updates}")
        print(f"Trades processed: {trade_count}")
        print(f"Signals generated: {signal_count}")
        print()
        
        stats = stream.get_stats()
        print(f"Stream stats:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print()
        det_stats = detector.get_stats()
        print(f"Detector stats:")
        for key, value in det_stats.items():
            print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
