# Microstructure Detector - MVP (Weeks 1-2)

High-frequency orderflow detection system for cryptocurrency markets using WebSocket streaming, advanced feature engineering, and CUSUM drift detection.

## 🎯 Overview

The Microstructure Detector identifies actionable trading signals from real-time order book and trade flow data by detecting:

- **Drift**: Persistent shifts in orderbook imbalance or trade flow
- **Bursts**: Sudden volume or volatility spikes  
- **Regime Changes**: Transitions in market microstructure (via BOCPD)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  • ccxt.pro WebSocket (Binance spot)                        │
│  • L2 order book + trade streaming                          │
│  • Reconnection + gap filling + clock sync                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Feature Engineering                          │
│  Order Book Features:                                        │
│    • Imbalance (top 5/10)                                   │
│    • Microprice drift                                        │
│    • Spread compression                                      │
│  Trade Features:                                             │
│    • Trade imbalance (1s/5s/30s)                            │
│    • Volume z-scores                                         │
│    • Realized volatility                                     │
│  Time Features:                                              │
│    • Hour/minute of day                                      │
│    • BOCPD regime indicators                                 │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Detection Engine                            │
│  • CUSUM drift detectors (imbalance, microprice, spread)    │
│  • Burst detection (volume z-scores)                        │
│  • Ensemble scoring with dynamic thresholds                 │
│  • Cooldown management                                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backtesting                                │
│  • Event-driven tick backtester                             │
│  • Triple-barrier labeling                                   │
│  • Fees + slippage modeling                                 │
│  • Purged time-series CV                                    │
│  • Precision@k, lead-time, PnL metrics                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 API & Observability                          │
│  • FastAPI alert endpoint                                    │
│  • Prometheus metrics                                        │
│  • Grafana dashboard                                         │
│  • Paper-trading alerts (Slack/Discord/Telegram)            │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Installation

```bash
# Install ccxt.pro for WebSocket support
pip install ccxt.pro numpy pandas fastapi prometheus-client

# Or add to requirements.txt
echo "ccxt.pro>=4.0.0" >> requirements.txt
pip install -r requirements.txt
```

## 🚀 Quick Start

### Real-Time Detection

```python
import asyncio
from src.microstructure import (
    BinanceOrderBookStream,
    OrderBookFeatureExtractor,
    TradeFeatureExtractor,
    MicrostructureDetector,
)

async def detect():
    # Initialize stream
    stream = BinanceOrderBookStream("BTC/USDT", depth=20)
    
    # Initialize feature extractors
    ob_extractor = OrderBookFeatureExtractor()
    trade_extractor = TradeFeatureExtractor()
    
    # Initialize detector
    detector = MicrostructureDetector(
        drift_threshold=3.0,
        burst_threshold=2.5,
        cooldown_seconds=30.0,
    )
    
    # Register callback
    def on_orderbook(snapshot):
        # Extract features
        ob_features = ob_extractor.extract(snapshot)
        trade_features = trade_extractor.extract(snapshot.timestamp)
        
        # Combine and detect
        features = MicrostructureFeatures(
            timestamp=snapshot.timestamp,
            orderbook=ob_features,
            trades=trade_features,
            # ... time features
        )
        
        signal = detector.process(features)
        if signal:
            print(f"🔔 Signal: {signal.signal_type} (score: {signal.score:.3f})")
    
    stream.register_book_callback(on_orderbook)
    stream.register_trade_callback(lambda t: trade_extractor.add_trade(t))
    
    # Start streaming
    await stream.start()

asyncio.run(detect())
```

### Run Example

```bash
cd examples
python microstructure_live.py
```

## 📊 Features

### Data Layer

**WebSocket Streaming** (`src/microstructure/stream.py`)
- Real-time L2 order book updates
- Individual trade streaming
- Automatic reconnection with exponential backoff
- Gap detection and alerting
- Clock synchronization (local vs exchange)
- Latency tracking (p50, p95)

### Feature Engineering

**Order Book Features** (`src/microstructure/features.py`)
- **Imbalance**: `(bid_vol - ask_vol) / (bid_vol + ask_vol)` for top 5/10 levels
- **Microprice**: Volume-weighted mid price
- **Microprice Drift**: Change vs previous snapshot
- **Spread Compression**: Current spread / rolling mean spread
- **Depth Metrics**: Total bid/ask volume and ratio

**Trade Features**
- **Trade Imbalance**: `buy_vol - sell_vol` over 1s/5s/30s windows
- **Volume Z-Scores**: Standardized volume bursts
- **Realized Volatility**: From tick-to-tick price changes
- **Trade Intensity**: Trade counts per window

### Detection Engine

**CUSUM Drift Detection** (`src/microstructure/detector.py`)
- Detects persistent shifts in key metrics
- Separate detectors for:
  - Order book imbalance
  - Microprice drift
  - Spread compression
  - Trade imbalance

**Burst Detection**
- Volume z-score thresholds across multiple windows
- Volatility spike detection

**Ensemble Scoring**
- Combines multiple signal types
- Dynamic thresholds based on history
- Cooldown management to prevent spam

### Backtesting

**Event-Driven Simulator** (`src/microstructure/backtester.py`)
- Triple-barrier method for labeling:
  - Profit target
  - Stop loss
  - Maximum holding time
- Transaction costs:
  - Maker/taker fees
  - Slippage modeling
- Purged time-series cross-validation

**Metrics**
- **Precision@k**: % of top-k signals that are profitable
- **Lead Time**: Average time between signal and price move
- **PnL Metrics**: Sharpe, max drawdown, win rate
- **Detection Metrics**: False positive rate, recall

## 🔧 Configuration

### Stream Configuration

```python
stream = BinanceOrderBookStream(
    symbol="BTC/USDT",
    depth=20,                    # Order book depth
    trade_buffer_size=1000,      # Recent trades to keep
    reconnect_delay=1.0,         # Initial reconnect delay
    max_reconnect_delay=60.0,    # Max reconnect delay
)
```

### Detector Configuration

```python
detector = MicrostructureDetector(
    drift_threshold=3.0,          # CUSUM threshold (std devs)
    burst_threshold=2.5,          # Z-score threshold for bursts
    regime_threshold=0.7,         # BOCPD probability threshold
    cooldown_seconds=30.0,        # Cooldown between signals
    dynamic_threshold_window=500, # Window for adaptive thresholds
)
```

### Backtest Configuration

```python
config = BacktestConfig(
    initial_capital=10000.0,
    fee_rate=0.001,              # 0.1% per trade
    slippage_bps=5.0,            # 5 basis points
    profit_target_pct=0.005,     # 0.5% profit target
    stop_loss_pct=0.003,         # 0.3% stop loss
    max_holding_seconds=300.0,   # 5 minutes max hold
)
```

## 📈 Metrics & Observability

### Streaming Metrics

```python
stats = stream.get_stats()
# {
#   'message_count': 12500,
#   'reconnect_count': 2,
#   'gap_count': 0,
#   'median_latency_ms': 45.2,
#   'p95_latency_ms': 120.3,
#   'clock_drift_ms': -12.5,
# }
```

### Detection Metrics

```python
stats = detector.get_stats()
# {
#   'total_detections': 42,
#   'signal_counts': {
#     'drift': 25,
#     'burst': 15,
#     'regime_change': 2,
#   },
# }
```

## 🎯 Deliverables (Weeks 1-2)

### ✅ Completed (Week 1)

- [x] WebSocket streaming infrastructure
- [x] Order book feature extraction
- [x] Trade feature extraction  
- [x] CUSUM drift detection
- [x] Ensemble scoring with cooldowns
- [x] Real-time example script
- [x] Comprehensive documentation

### 🚧 In Progress (Week 2)

- [ ] BOCPD regime detection integration
- [ ] Full backtesting implementation
- [ ] Triple-barrier labeling
- [ ] Precision@k and lead-time metrics
- [ ] FastAPI alert endpoint
- [ ] Prometheus metrics export
- [ ] Grafana dashboard config
- [ ] Slack/Discord/Telegram notifications

## 🧪 Testing

```bash
# Test streaming (requires API keys or will use public feed)
python -m pytest tests/test_microstructure_stream.py

# Test feature extraction
python -m pytest tests/test_microstructure_features.py

# Test detection
python -m pytest tests/test_microstructure_detector.py

# Integration test
python examples/microstructure_live.py
```

## 📚 References

- **CUSUM**: Page, E.S. (1954). "Continuous Inspection Schemes"
- **Microprice**: Stoikov, S. (2018). "The Micro-Price: A High-Frequency Estimator"
- **BOCPD**: Adams & MacKay (2007). "Bayesian Online Changepoint Detection"
- **Triple Barrier**: López de Prado, M. (2018). "Advances in Financial Machine Learning"

## 🐛 Known Issues

1. **BOCPD Integration**: Regime detection placeholder - needs full implementation
2. **Backtester**: Currently a stub - full event-driven simulator in progress
3. **API Endpoints**: FastAPI integration pending
4. **Notifications**: Alert channels not yet implemented

## 🗺️ Roadmap

### Week 2 Priorities

1. Complete backtesting framework
2. Implement FastAPI endpoints
3. Add Prometheus metrics
4. Set up Grafana dashboard
5. Integrate notification channels
6. Add BOCPD regime detection

### Future Enhancements

- Multi-symbol support
- L3 order book (individual orders)
- Order flow toxicity metrics
- Market maker inventory tracking
- Cross-venue arbitrage detection

## 📞 Support

For issues or questions, create an issue in the repository or contact the development team.

---

**Status**: 🟢 Week 1 Complete | 🟡 Week 2 In Progress

**Last Updated**: 2025-10-09
