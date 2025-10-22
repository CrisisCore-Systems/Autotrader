# AutoTrader System Architecture

**Version:** 1.0.0  
**Last Updated:** October 22, 2025  
**Status:** Production

---

## Table of Contents

1. [Overview](#overview)
2. [Core Modules](#core-modules)
3. [Data Flow Architecture](#data-flow-architecture)
4. [Feature Engineering Pipeline](#feature-engineering-pipeline)
5. [Reliability Layer](#reliability-layer)
6. [Model Lifecycle](#model-lifecycle)
7. [Trading System Architecture](#trading-system-architecture)
8. [Module Dependencies](#module-dependencies)
9. [Deployment Architecture](#deployment-architecture)

---

## Overview

AutoTrader is a multi-strategy algorithmic trading system that combines:

- **Hidden-Gem Scanner**: On-chain telemetry, narrative intelligence, and technical analysis for cryptocurrency markets
- **BounceHunter/PennyHunter**: Gap trading strategy for equities with mean-reversion detection
- **Multi-Broker Integration**: Support for Paper, Alpaca, Questrade, and Interactive Brokers
- **Agentic Architecture**: 8-agent orchestration system with persistent memory

### Key Design Principles

1. **Reliability First**: Circuit breakers, caching, and SLA monitoring for all external dependencies
2. **Feature Store Pattern**: Centralized feature management with validation and versioning
3. **Observability**: Comprehensive logging, metrics, and distributed tracing
4. **Safety Gating**: Multi-layer risk filters and contract safety validation
5. **Human-in-the-Loop**: All trading decisions require explicit operator approval

---

## Core Modules

### 1. Core (`src/core/`)

The foundational layer providing shared infrastructure for all trading strategies.

#### Key Components

- **`pipeline.py`**: High-level orchestration engine for scanning workflows
- **`feature_store.py`**: Unified feature storage with validation and versioning
- **`feature_validation.py`**: Feature quality checks and data contracts
- **`scoring.py`**: GemScore calculation with weighted feature contributions
- **`safety.py`**: Contract safety analysis and liquidity guardrails
- **`narrative.py`**: Narrative intelligence and momentum tracking

#### Data Clients

- **Market Data**: `clients.py` (CoinGecko, DefiLlama, Etherscan)
- **Free Sources**: `free_clients.py` (Blockscout, Ethereum RPC)
- **Order Flow**: `orderflow_clients.py` (Dexscreener)
- **Derivatives**: `derivatives_client.py` (CEX funding rates)
- **News**: `news_client.py`, `news_client_enhanced.py`
- **On-Chain**: `onchain_client.py` (holder distribution, transaction patterns)

#### Observability Stack

- **Logging**: `logging_config.py` - Structured JSON logging
- **Metrics**: `metrics.py`, `metrics_registry.py` - Prometheus-compatible metrics
- **Tracing**: `tracing.py` - OpenTelemetry distributed tracing
- **Provenance**: `provenance.py`, `provenance_tracking.py` - Data lineage tracking

### 2. BounceHunter (`src/bouncehunter/`)

Gap trading strategy implementation for equity markets.

#### Core Engine

- **`engine.py`**: Mean-reversion signal generation and probability estimation
- **`agentic.py`**: Multi-agent orchestration with memory persistence
- **`pennyhunter_agentic.py`**: 8-agent system (Sentinel, Screener, Forecaster, RiskOfficer, NewsSentry, Trader, Historian, Auditor)
- **`backtest.py`**: Strategy validation and performance metrics

#### Market Intelligence

- **`market_regime.py`**: SPY/VIX regime detection (normal, high_vix, spy_stress)
- **`advanced_filters.py`**: 5-module risk filter system:
  - Liquidity delta monitoring
  - Slippage estimation
  - Cash runway validation
  - Sector diversification
  - Volume fade detection

#### Broker Abstraction

- **`broker.py`**: Unified broker interface
- **`alpaca_broker.py`**: Alpaca API implementation
- **`questrade_client.py`**: Questrade integration with auto-token refresh
- **`ib_broker.py`**: Interactive Brokers integration

#### Scoring & Ensemble

- **`signal_scoring.py`**: Multi-factor signal quality assessment
- **`pennyhunter_scoring.py`**: BounceHunter Confidence Score (BCS) calculation
- **`ensemble.py`**: Model ensemble and voting mechanisms
- **`reasoning.py`**: Explainability and decision rationale generation

### 3. Features (`src/features/`)

Cross-asset feature engineering modules.

- **`cross_exchange_features.py`**: Multi-exchange dislocation detection
  - Price dispersion and arbitrage opportunities
  - Volume-weighted price metrics
  - Lead-lag correlations
  - Order book depth imbalances

### 4. Models (`src/models/`)

Machine learning pipeline implementations.

- **`lightgbm_pipeline.py`**: Gradient boosting model training with time-series CV
- **`hyperparameter_optimization.py`**: Bayesian hyperparameter tuning
- **`walk_forward.py`**: Walk-forward optimization and validation
- **`meta_labeling.py`**: Secondary model for position sizing
- **`spectral_residual.py`**: Anomaly detection for regime changes

### 5. Microstructure (`src/microstructure/`)

High-frequency market microstructure analysis.

- **`stream.py`**: Real-time order book processing
- **`multi_exchange_stream.py`**: Multi-venue aggregation
- **`detector.py`**: Dislocation and anomaly detection
- **`bocpd.py`**: Bayesian Online Changepoint Detection
- **`backtester.py`**: Microstructure strategy backtesting

### 6. Services (`src/services/`)

Supporting services for system reliability and observability.

#### Reliability

- **`circuit_breaker.py`**: Circuit breaker pattern for fault tolerance
- **`cache_policy.py`**: Adaptive caching with TTL management
- **`sla_monitor.py`**: SLA tracking and alerting
- **`reliability.py`**: Integration layer applying reliability patterns to data sources

#### Data Services

- **`exporter.py`**: Artifact rendering (HTML, Markdown)
- **`feature_engineering.py`**: Feature transformation pipelines
- **`feature_gate.py`**: Feature flag management for gradual rollouts

#### External Integrations

- **`llm_client.py`**: LLM integration for narrative analysis
- **`llm_guardrails.py`**: Safety guardrails for LLM outputs
- **`alerting.py`, `alerting_v2.py`**: Multi-channel alerting (email, SMS, Slack)
- **`job_queue.py`**: Asynchronous job processing
- **`scheduler.py`**: Cron-like job scheduling

### 7. API (`src/api/`)

REST API for system access and dashboard integration.

- **`main.py`**: Primary FastAPI application with rate limiting
- **`dashboard_api.py`**: Dashboard-specific endpoints
- **Routes**:
  - `tokens.py`: Token scanning and scoring
  - `experiments.py`: Experiment tracking and results
  - `health.py`: Health checks and system status

### 8. Monitoring (`src/monitoring/`)

Model and data drift detection.

- **`drift_monitor.py`**: Statistical drift detection (KS test, PSI, wasserstein distance)
  - Feature drift monitoring
  - Prediction drift tracking
  - Automatic retraining triggers

### 9. Security (`src/security/`)

Security controls and validation.

- **`artifact_integrity.py`**: Cryptographic integrity verification for artifacts
- **`prompt_validator.py`**: LLM prompt injection detection and sanitization

### 10. Pipeline (`src/pipeline/`)

Backtesting and strategy evaluation.

- **`backtest.py`**: Historical strategy simulation
- **`backtest_statistics.py`**: Performance metrics (Sharpe, Sortino, max drawdown, win rate)

---

## Data Flow Architecture

### Hidden-Gem Scanner Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES                             │
├─────────────────────────────────────────────────────────────────┤
│ Market Data  │ On-Chain   │ News/Social │ Derivatives │ DEX     │
│ (CoinGecko)  │ (Etherscan)│ (Twitter)   │ (CEX APIs)  │ (Dex-  │
│ (DefiLlama)  │ (RPC)      │ (RSS)       │             │ screener)│
└──────┬───────┴──────┬─────┴──────┬──────┴──────┬──────┴────┬────┘
       │              │            │             │           │
       ▼              ▼            ▼             ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    RELIABILITY LAYER                             │
│  Circuit Breakers | Caching | Retry Logic | SLA Monitoring      │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FEATURE STORE                               │
│  Write Features → Validate → Version → Store (Time-Series)      │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  FEATURE ENGINEERING                             │
│  Raw Features → Transformations → Aggregations → Derived        │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SAFETY GATING                                 │
│  Contract Safety | Liquidity Check | Tokenomics Risk            │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SCORING ENGINE                                 │
│  GemScore = Σ(weight_i × feature_i) | Confidence Score          │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   FLAGGING LOGIC                                 │
│  Score ≥ 70 & Safety Pass & Signal Count ≥ 3 → Review Queue     │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  ARTIFACT GENERATION                             │
│  HTML Report | Markdown Summary | JSON Payload                  │
└─────────────────────────────────────────────────────────────────┘
```

### BounceHunter Trading Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    MARKET DATA INGESTION                         │
│  yfinance: OHLCV, Earnings | SPY/VIX: Regime Context            │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FEATURE ENGINEERING                           │
│  z5, rsi2, bb_dev, dist_200, trend_63, gap_dn, vix_regime       │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   UNIVERSE FILTERING                             │
│  ADV ≥ $5M | Price: $0.50-$20 | Market Cap ≥ $50M               │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                 PROBABILITY ESTIMATION                           │
│  Calibrated Classifier → P(mean_reversion)                      │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTIC AGENTS                                │
│  Sentinel → Screener → Forecaster → RiskOfficer → NewsSentry    │
│  → Trader (generates orders) → Historian → Auditor              │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ADVANCED FILTERS                               │
│  Liquidity Delta | Slippage | Runway | Sector | Volume Fade     │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   POSITION SIZING                                │
│  Normal: 1.2% | High VIX: 0.6% | Stop Loss: -8% | Target: +6%   │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                  BROKER EXECUTION                                │
│  Paper | Alpaca | Questrade | IBKR (with FA field scrubbing)    │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   MEMORY PERSISTENCE                             │
│  SQLite: signals, actions, outcomes, policy_history              │
└─────────────────────────────────────────────────────────────────┘
```

---

## Feature Engineering Pipeline

### Pipeline Stages

1. **Data Acquisition**
   - Multiple data source clients with failover
   - Rate limiting and backoff strategies
   - Data freshness validation

2. **Feature Extraction**
   - Raw feature computation from market data
   - Time-series aggregations (rolling windows)
   - Cross-sectional features (relative to universe)

3. **Feature Transformation**
   - Normalization (min-max, z-score)
   - Log transformations for skewed distributions
   - Winsorization for outlier handling

4. **Feature Validation**
   - Schema validation (type, range, nullability)
   - Statistical validation (distribution checks)
   - Freshness checks (max age enforcement)

5. **Feature Storage**
   - Write to Feature Store with metadata
   - Version tracking for reproducibility
   - Efficient time-series retrieval

6. **Feature Serving**
   - Point-in-time correct feature lookup
   - Batch feature retrieval for backtesting
   - Real-time feature computation for live trading

### Feature Categories

See [FEATURE_CATALOG.md](FEATURE_CATALOG.md) for complete feature inventory.

| Category | Examples | Source |
|----------|----------|--------|
| **Market** | price, volume, market_cap | CoinGecko, yfinance |
| **Liquidity** | order_book_depth, pool_liquidity | DEX APIs, Dexscreener |
| **Order Flow** | cex_flow, dex_flow, bid_ask_imbalance | Orderflow clients |
| **Derivatives** | funding_rate, open_interest | CEX APIs |
| **Sentiment** | twitter_sentiment, news_sentiment | Twitter, RSS |
| **On-Chain** | holder_count, transaction_activity | Etherscan, RPC |
| **Technical** | rsi, macd, bollinger_bands | Computed |
| **Quality** | data_recency, completeness | Validation layer |
| **Scoring** | gem_score, bcs, confidence | Scoring engine |

---

## Reliability Layer

### Circuit Breaker Pattern

Prevents cascading failures from external dependencies.

**States:**
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Failure threshold exceeded, requests fail fast
- **HALF_OPEN**: Testing if service recovered, limited requests

**Configuration by Service Type:**

```python
# CEX APIs: Fail fast
CEX_CIRCUIT_CONFIG = {
    "failure_threshold": 5,      # Open after 5 failures
    "timeout_seconds": 30.0,     # Stay open for 30s
    "success_threshold": 2,      # Close after 2 successes
}

# DEX APIs: More tolerant
DEX_CIRCUIT_CONFIG = {
    "failure_threshold": 10,
    "timeout_seconds": 60.0,
    "success_threshold": 3,
}

# Twitter API: Very tolerant (rate limits)
TWITTER_CIRCUIT_CONFIG = {
    "failure_threshold": 3,
    "timeout_seconds": 120.0,
    "success_threshold": 1,
}
```

### Adaptive Caching

Cache TTL adapts based on data volatility and freshness requirements.

**Cache Policies:**

| Data Type | Default TTL | Min TTL | Max TTL | Adaptive |
|-----------|-------------|---------|---------|----------|
| Order Books | 5s | 2s | 15s | ✓ |
| DEX Liquidity | 30s | 10s | 120s | ✓ |
| Twitter Data | 300s | 60s | 900s | ✓ |
| Market Data | 60s | 30s | 300s | ✓ |

### SLA Monitoring

Tracks latency and success rate for all external dependencies.

**Thresholds:**

```python
# CEX Order Books: Fast, high-frequency
CEX_ORDERBOOK_THRESHOLDS = {
    "max_latency_p95": 1000,        # 1s
    "max_latency_p99": 2000,        # 2s
    "min_success_rate": 0.95,       # 95%
    "max_consecutive_failures": 3,
}

# DEX Aggregators: Slower, less critical
DEX_THRESHOLDS = {
    "max_latency_p95": 3000,        # 3s
    "max_latency_p99": 5000,        # 5s
    "min_success_rate": 0.90,       # 90%
    "max_consecutive_failures": 5,
}
```

**Alerting:**
- SLA violations trigger immediate alerts
- Metrics exported to Prometheus
- Dashboard visualization for ops team

---

## Model Lifecycle

### 1. Training Phase

**Data Preparation:**
- Historical data collection (minimum 2 years)
- Feature engineering and validation
- Label generation (forward returns, event detection)

**Model Training:**
- Time-series cross-validation (no data leakage)
- Hyperparameter optimization (Bayesian search)
- Model checkpointing and versioning

**Evaluation:**
- Out-of-sample testing
- Metrics: Precision, Recall, F1, ROC-AUC, Average Precision
- Feature importance analysis

### 2. Validation Phase

**Walk-Forward Testing:**
- Rolling window validation
- Realistic transaction costs
- Slippage modeling

**Backtesting:**
- Historical strategy simulation
- Performance metrics (Sharpe, Sortino, max drawdown)
- Trade-level analysis

### 3. Deployment Phase

**Model Registry:**
- Versioned model artifacts
- Metadata (training date, features, hyperparameters)
- A/B testing framework

**Shadow Mode:**
- Run new model alongside production
- Compare predictions without affecting trades
- Monitor for drift and anomalies

### 4. Monitoring Phase

**Drift Detection:**
- Feature drift (input distribution changes)
- Prediction drift (output distribution changes)
- Performance drift (live metrics vs. backtest)

**Triggers:**
- Statistical tests: KS test, PSI, Wasserstein distance
- Thresholds: p-value < 0.05 triggers alert
- Automatic retraining on severe drift

### 5. Retraining Phase

**Triggers:**
- Scheduled (monthly)
- Performance degradation
- Significant drift detected
- Market regime change

**Process:**
- Incremental training on new data
- Validation against hold-out set
- Staged rollout (canary → shadow → full)

---

## Trading System Architecture

### Multi-Broker Abstraction

**Unified Interface:**
```python
class Broker:
    def get_account_info() -> AccountInfo
    def get_positions() -> List[Position]
    def place_order(order: Order) -> OrderStatus
    def cancel_order(order_id: str) -> bool
    def get_market_data(symbol: str) -> MarketData
```

**Implementations:**
- **Paper Broker**: In-memory simulation
- **Alpaca**: REST API integration
- **Questrade**: OAuth with auto-token refresh
- **IBKR**: TWS API with FA field scrubbing

### Agentic System

**8-Agent Architecture:**

1. **Sentinel**: Market regime detection (SPY/VIX monitoring)
2. **Screener**: Universe filtering and signal generation
3. **Forecaster**: Probability estimation and prediction
4. **RiskOfficer**: Position sizing and risk limits
5. **NewsSentry**: News monitoring and sentiment analysis
6. **Trader**: Order generation and execution
7. **Historian**: Trade logging and performance tracking
8. **Auditor**: Compliance checks and reporting

**Memory Persistence:**
- SQLite database for agent state
- Tables: signals, actions, outcomes, policy_history
- Query patterns for adaptive learning

### Risk Management

**Pre-Trade Filters:**
1. **Liquidity Delta**: ADV ≥ $5M, recent volume within 40% of 20-day average
2. **Slippage Estimation**: Expected slippage < 0.5%
3. **Cash Runway**: Available cash > 3× position size
4. **Sector Diversification**: Max 3 positions per sector
5. **Volume Fade**: No declining volume trend

**Position Sizing:**
- Normal regime: 1.2% of portfolio per trade
- High VIX regime: 0.6% of portfolio per trade
- Max concurrent positions: 8
- Max sector allocation: 3 positions

**Exit Rules:**
- Stop loss: -8% from entry
- Profit target: +6% from entry
- Time-based exit: 5 days if no target/stop hit
- News-based emergency exit: Earnings surprises, adverse events

---

## Module Dependencies

### Dependency Graph

```
src/
├── core/              (foundational layer, no internal deps)
│   ├── logging_config
│   ├── metrics
│   ├── tracing
│   └── feature_store
│
├── services/          (depends on: core)
│   ├── reliability → core.metrics
│   ├── feature_engineering → core.feature_store
│   └── exporter → core.logging_config
│
├── features/          (depends on: core)
│   └── cross_exchange_features → core.logging_config
│
├── models/            (depends on: core)
│   ├── lightgbm_pipeline → core.logging_config
│   └── meta_labeling → core.logging_config
│
├── bouncehunter/      (depends on: core, services, models)
│   ├── engine → models.lightgbm_pipeline
│   ├── agentic → core.feature_store
│   └── broker → services.reliability
│
├── microstructure/    (depends on: core, features)
│   └── detector → features.cross_exchange_features
│
├── monitoring/        (depends on: core, models)
│   └── drift_monitor → models, core.metrics
│
└── api/               (depends on: core, bouncehunter, services)
    └── main → core.pipeline, bouncehunter.engine
```

### External Dependencies

**Core Libraries:**
- `pandas`, `numpy`: Data manipulation
- `lightgbm`, `scikit-learn`: Machine learning
- `fastapi`, `uvicorn`: API framework
- `sqlalchemy`, `alembic`: Database ORM and migrations
- `opentelemetry`: Distributed tracing
- `prometheus_client`: Metrics export

**Data Providers:**
- `yfinance`: Yahoo Finance API
- `requests`: HTTP client for various APIs
- `websocket-client`: WebSocket for real-time data

**Broker Libraries:**
- `alpaca-trade-api`: Alpaca integration
- `ib_insync`: Interactive Brokers integration
- Custom: Questrade client (REST API)

---

## Deployment Architecture

### Development Environment

```
┌────────────────────────────────────────────────┐
│           Local Development                     │
├────────────────────────────────────────────────┤
│  IDE/Editor                                     │
│  │                                              │
│  ├─→ pytest (unit tests)                       │
│  ├─→ pre-commit hooks                          │
│  │   ├─→ black (formatting)                    │
│  │   ├─→ ruff (linting)                        │
│  │   └─→ detect-secrets (security)             │
│  │                                              │
│  └─→ docker-compose (local services)           │
│      ├─→ API server                            │
│      ├─→ Dashboard                             │
│      └─→ Database (SQLite/PostgreSQL)          │
└────────────────────────────────────────────────┘
```

### Production Environment

```
┌─────────────────────────────────────────────────────────────┐
│                    LOAD BALANCER                             │
└────────────────┬───────────────────────┬────────────────────┘
                 │                       │
     ┌───────────▼────────┐  ┌──────────▼───────────┐
     │   API Server 1     │  │   API Server 2       │
     │  (Rate Limited)    │  │  (Rate Limited)      │
     └───────────┬────────┘  └──────────┬───────────┘
                 │                       │
                 └───────────┬───────────┘
                             │
                 ┌───────────▼────────────┐
                 │   PostgreSQL            │
                 │   (Primary + Replica)   │
                 └───────────┬────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
  ┌───────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
  │  Feature Store  │ │ Model Store │ │  Artifact Store │
  │   (TimeSeries)  │ │  (Versions) │ │   (S3/Local)    │
  └─────────────────┘ └─────────────┘ └─────────────────┘
```

### Monitoring Stack

```
┌─────────────────────────────────────────────────────────────┐
│  Application                                                 │
│  ├─→ Structured Logs → Fluentd → Elasticsearch → Kibana     │
│  ├─→ Metrics → Prometheus → Grafana                         │
│  └─→ Traces → Jaeger                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Architectural Decisions

### Why Feature Store?

**Problem**: Features computed multiple times, inconsistency between training and serving.

**Solution**: Centralized feature storage with:
- Single source of truth
- Point-in-time correctness
- Version tracking
- Validation on write

### Why Circuit Breakers?

**Problem**: External API failures cascade through system, causing timeouts and resource exhaustion.

**Solution**: Fail fast on known-bad services, recover automatically:
- Prevents retry storms
- Isolates failures
- Self-healing behavior

### Why Agentic Architecture?

**Problem**: Monolithic trading logic hard to reason about and adapt.

**Solution**: Decompose into specialized agents:
- Clear responsibilities
- Independent testing
- Adaptive behavior through memory
- Explainable decision chains

### Why Multi-Broker Abstraction?

**Problem**: Each broker has unique API, testing difficult.

**Solution**: Unified interface with multiple implementations:
- Paper trading for testing
- Easy broker migration
- Consistent position management

---

## Performance Characteristics

### Latency Budgets

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Feature Read | 1ms | 5ms | 10ms |
| Feature Write | 2ms | 10ms | 20ms |
| GemScore Calculation | 10ms | 50ms | 100ms |
| API Request (scan) | 500ms | 2s | 5s |
| BounceHunter Scan | 2s | 10s | 30s |

### Throughput

- **API**: 120 requests/minute (rate limited)
- **Feature Store**: 10,000 writes/second
- **Scanning**: 100 tokens/hour (Hidden-Gem), 500 stocks/hour (BounceHunter)

### Resource Requirements

**Minimum (Development):**
- CPU: 2 cores
- RAM: 4 GB
- Disk: 10 GB

**Recommended (Production):**
- CPU: 8 cores
- RAM: 16 GB
- Disk: 100 GB SSD
- Network: 100 Mbps

---

## Security Considerations

### Data Privacy

- API keys stored in environment variables
- Secrets rotation (90 days)
- No sensitive data in logs or artifacts

### Input Validation

- LLM prompt injection detection
- API rate limiting (DoS prevention)
- Schema validation on all inputs

### Artifact Integrity

- Cryptographic signatures for all artifacts
- SHA-256 hashes for model files
- Provenance tracking for data lineage

### Broker Security

- OAuth2 for Questrade (auto-refresh tokens)
- API key rotation for Alpaca
- FA field scrubbing for IBKR (remove sensitive fields)

---

## Future Enhancements

### Planned (Q1 2026)

1. **API Consolidation**: Unify 3 separate APIs into single GraphQL endpoint
2. **Redis Caching**: Replace in-memory cache with distributed Redis
3. **Real-Time Processing**: WebSocket streaming for live market data
4. **Advanced Backtesting**: Monte Carlo simulation, walk-forward optimization

### Under Consideration

1. **Multi-Asset Support**: Add futures, options, forex
2. **Portfolio Optimization**: Mean-variance optimization, risk parity
3. **Alternative Data**: Satellite imagery, credit card data
4. **Machine Learning Ops**: Automated retraining, A/B testing framework

---

## References

- [FEATURE_CATALOG.md](FEATURE_CATALOG.md) - Complete feature inventory
- [docs/AGENTIC_ARCHITECTURE.md](docs/AGENTIC_ARCHITECTURE.md) - Detailed agent design
- [docs/BROKER_INTEGRATION.md](docs/BROKER_INTEGRATION.md) - Broker implementation guide
- [docs/PENNYHUNTER_GUIDE.md](docs/PENNYHUNTER_GUIDE.md) - BounceHunter strategy details
- [docs/OPERATOR_GUIDE.md](docs/OPERATOR_GUIDE.md) - Daily operations manual
- [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md) - Full documentation index

---

**Document Owner**: Engineering Team  
**Review Cycle**: Quarterly  
**Last Review**: October 22, 2025  
**Next Review**: January 22, 2026
