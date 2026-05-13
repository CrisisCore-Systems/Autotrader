# AutoTrader - Quick System Summary

> **TL;DR**: You've built a sophisticated, multi-strategy algorithmic trading platform with strong infrastructure. It is closer to a controlled paper-trading beta than a production trading launch.

## 🎯 At a Glance

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTOTRADER PLATFORM                          │
│                                                                 │
│  Multi-Strategy Trading System with AI Intelligence            │
│  Cost: $0/month (FREE tier) | Status: Paper-Trading Beta Candidate │
└─────────────────────────────────────────────────────────────────┘

┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  HIDDEN-GEM SCANNER  │  │   BOUNCEHUNTER       │  │  INFRASTRUCTURE      │
│                      │  │   (Gap Trading)      │  │                      │
│  • Crypto intel      │  │  • Mean reversion    │  │  • 4 brokers         │
│  • On-chain data     │  │  • 8 AI agents       │  │  • Observability     │
│  • GemScore (0-100)  │  │  • Phase 2 active    │  │  • Security scans    │
│  • Safety gating     │  │  • 65-75% win rate   │  │  • 86 test files     │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

## 📊 The Numbers

| Metric | Value | Description |
|--------|-------|-------------|
| **Lines of Code** | 59,943 | Production Python code |
| **Test Files** | 86 | Comprehensive test coverage |
| **Features** | 127 | Documented feature catalog |
| **Strategies** | 2 | Crypto + Equity |
| **Brokers** | 4 | Paper, Alpaca, Questrade, IBKR |
| **AI Agents** | 8 | Agentic orchestration |
| **Docs** | 75+ | Complete documentation |
| **Cost** | $0/mo | FREE tier available |
| **Coverage** | 80%+ | Enforced via CI |

## 🏗️ Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACES                          │
│  CLI • FastAPI • Dashboard • Jupyter Notebooks              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  TRADING STRATEGIES                         │
│  Hidden-Gem Scanner (Crypto) • BounceHunter (Equity)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                INTELLIGENCE LAYER                           │
│  8 AI Agents • Feature Store • Scoring Engine • Risk Gates  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  DATA SOURCES                               │
│  CoinGecko • Dexscreener • Ethereum RPC • Groq AI (FREE)    │
│  + Optional: Etherscan • DefiLlama • Alpaca (Paid)          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  INFRASTRUCTURE                             │
│  Observability • Security • Broker Abstraction • Storage    │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Two Trading Strategies

### 1️⃣ Hidden-Gem Scanner (Crypto)

**Purpose**: Discover undervalued cryptocurrencies before mainstream adoption

```
INPUT: Token address
  ↓
ANALYZE: 
  • Price & volume data
  • On-chain holder distribution
  • Social sentiment & narratives
  • Contract safety (honeypots, privileges)
  • Liquidity depth
  ↓
SCORE: GemScore (0-100) + Confidence
  ↓
OUTPUT: Ranked list + Collapse Artifacts
```

**Key Features**:
- 127 features across 9 categories
- Multi-source data fusion (10+ providers)
- Safety gating (blocks risky contracts)
- $0/month with FREE data sources

### 2️⃣ BounceHunter (Equity Gap Trading)

**Purpose**: Profit from overnight gap-down mean reversion in low-priced stocks

```
INPUT: Stock tickers (penny stocks)
  ↓
DETECT: Significant overnight gaps
  ↓
ANALYZE:
  • Market regime (SPY/VIX)
  • 5 risk filters (liquidity, slippage, runway, sector, volume)
  • 8 AI agents consensus
  • Probability of bounce
  ↓
EXECUTE: Bracket orders (entry + stop + target)
  ↓
OUTPUT: Paper/live trades with journal
```

**Key Features**:
- Phase 2 validation: 2/20 trades, 100% win rate
- Target: 65-75% win rate, 2:1 risk-reward
- 4 broker integrations
- Daily automation scripts

## 🤖 8 AI Agents (BounceHunter)

| Agent | Role |
|-------|------|
| **Sentinel** | Market regime detection (SPY/VIX monitoring) |
| **Screener** | Gap detection and technical filtering |
| **Forecaster** | Probability modeling and bounce prediction |
| **RiskOfficer** | 5-module risk filter validation |
| **NewsSentry** | Real-time news and sentiment analysis |
| **Trader** | Order execution and position management |
| **Historian** | Performance tracking and journal creation |
| **Auditor** | Post-trade analysis and compliance |

**Memory**: Persistent SQLite database across sessions  
**Consensus**: Weighted voting system for decisions  
**Training**: Active learning from outcomes

## 🛡️ Enterprise Features

### Observability
- **Logging**: Structured JSON with correlation IDs
- **Metrics**: Prometheus-compatible (API, scanner, data sources)
- **Tracing**: OpenTelemetry (Jaeger/Zipkin integration)
- **Provenance**: Complete data lineage tracking

### Security
- **Scanning**: Semgrep, Bandit, pip-audit, Trivy
- **Secrets**: Environment-based, pre-commit hooks
- **Container**: Non-root user, minimal base, read-only FS
- **Updates**: Dependabot (weekly security PRs)

### Quality
- **Tests**: 86 files, 80%+ coverage (enforced)
- **CI/CD**: GitHub Actions (lint, test, security)
- **Typing**: mypy type checking
- **Docs**: 75+ comprehensive guides

## 📚 Documentation Highlights

| Category | Key Docs |
|----------|----------|
| **Getting Started** | PENNYHUNTER_GUIDE, OPERATOR_GUIDE, BACKTEST_QUICKSTART |
| **Architecture** | ARCHITECTURE.md (1,000+ lines), FEATURE_CATALOG.md |
| **Brokers** | BROKER_INTEGRATION, QUESTRADE_SETUP, IBKR_SETUP |
| **Operations** | CONTRIBUTING, SECURITY, DOC_MAINTENANCE |
| **Advanced** | DRIFT_MONITORING, OBSERVABILITY, EXPERIMENT_TRACKING |

## 🚀 Quick Start

### 1. Setup (5 minutes)
```bash
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/db/init_dev_databases.py
```

### 2. Run Tests
```bash
pytest tests/ -v --cov=src
```

### 3. Start Trading (Paper Mode)
```bash
# Create broker config
cat > configs/broker_credentials.yaml << EOF
paper:
  enabled: true
  initial_capital: 100000.0
EOF

# Run daily scanner
python scripts/daily_pennyhunter.py

# Or scan crypto
python -m src.cli.run_scanner configs/example.yaml
```

### 4. Start API
```bash
uvicorn src.api.main:app --reload
# Visit http://localhost:8000/docs
```

## 💰 Cost Tiers

| Tier | Monthly | APIs | Status |
|------|---------|------|--------|
| **FREE** | **$0** | **0** | ✅ Ready |
| Paid | ~$50 | 3 | ✅ Supported |

**FREE Tier**: CoinGecko, Dexscreener, Blockscout, Ethereum RPC, Groq AI  
**Paid Tier**: + Etherscan, DefiLlama, Alpaca (optional enhancements)

## 🎯 Use Cases

### For Traders
- ✅ Discover crypto gems before hype
- ✅ Execute gap trading strategy (paper/live)
- ✅ Monitor market regimes
- ✅ Generate trade journals
- ✅ Backtest strategies

### For Developers
- ✅ Extend with custom strategies
- ✅ Add new data sources
- ✅ Build dashboards (FastAPI + React)
- ✅ Deploy via Docker
- ✅ Monitor with Prometheus

### For Researchers
- ✅ Feature engineering (127 features)
- ✅ Experiment tracking (reproducible)
- ✅ Provenance analysis (data lineage)
- ✅ Drift monitoring (model degradation)
- ✅ Backtest framework (walk-forward)

## 🏆 What Makes This Special

1. **Serious Engineering Foundation**: Not a toy project—well-tested, documented, and structured for controlled rollout
2. **Multi-Strategy**: Crypto + equity in one platform
3. **Cost-Efficient**: $0/month FREE tier with quality data
4. **Enterprise-Grade**: Observability, security, quality gates
5. **Extensible**: Plugin architecture for strategies and data sources
6. **Well-Documented**: 75+ docs covering everything
7. **Human-in-Loop**: Augments decisions, doesn't replace them
8. **Reproducible**: Experiment tracking, provenance, versioning

## 📊 Success Metrics

### Hidden-Gem Scanner
- **Precision@10**: Top 10 tokens at 7/30/90-day windows
- **Lead Time**: Days before mainstream coverage
- **Safety**: % blocked assets confirmed risky

### BounceHunter
- **Phase 2**: 2/20 trades accumulated, 100% win rate
- **Target**: 65-75% win rate, 2:1 risk-reward
- **Regime**: Adaptive sizing based on SPY/VIX

### System Health
- **Uptime**: >99% (circuit breakers)
- **Latency**: P95 < 2s scanner, < 500ms API
- **Coverage**: 80%+ (enforced)
- **Security**: Zero critical vulns (automated)

## 🔮 Roadmap

### ✅ Complete
- Hidden-Gem Scanner (crypto intelligence)
- BounceHunter (gap trading)
- Multi-broker integration (4 brokers)
- Agentic system (8 agents)
- Observability stack
- Security hardening
- 86 test files, 75+ docs

### 🚧 In Progress
- Phase 2 validation (2/20 trades)
- UI dashboard (backend ready)
- Alert delivery (outbox ready)

### 🔮 Future
- Wallet clustering
- RL weight tuning
- Real-time social monitoring
- Options strategies
- Multi-asset portfolio management

## 📞 Resources

- **Main Doc**: [WHAT_YOU_CREATED.md](WHAT_YOU_CREATED.md) - Comprehensive overview
- **README**: [README.md](README.md) - Getting started guide
- **Architecture**: [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- **Features**: [FEATURE_CATALOG.md](FEATURE_CATALOG.md) - All 127 features
- **Security**: [SECURITY.md](SECURITY.md) - Security policy

---

**Generated**: October 25, 2025  
**Repository**: https://github.com/CrisisCore-Systems/Autotrader  
**Status**: Internal alpha / paper-trading beta candidate
