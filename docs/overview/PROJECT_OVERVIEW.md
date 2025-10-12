# VoidBloom / CrisisCore Hidden-Gem Scanner

**🆓 Now 100% FREE** - Zero API keys required with FREE data sources!

This repository contains the foundational blueprint and implementation for **VoidBloom / CrisisCore**, a Hidden-Gem Scanner that fuses on-chain telemetry, narrative intelligence, technical analysis, and safety gating into actionable trade intelligence and ritualized "Collapse Artifact" outputs.

> **Disclaimer:** All outputs are informational only and **not financial advice**. Always retain a human-in-the-loop for execution decisions.

## 🎯 Current Status (October 2025)

### ✅ **Production Ready**
- ✅ All 21 tests passing (13 smoke + 8 integration)
- ✅ Repository corruption fixed (15+ syntax errors resolved)
- ✅ FREE data sources fully integrated ($0/month cost)
- ✅ Zero API keys required when using FREE tier
- ✅ Full backward compatibility maintained
- ✅ Security hardened (no secrets in repository)
- ✅ Comprehensive documentation (10+ guides)

### 💰 **Cost Savings**
| Tier | Monthly Cost | API Keys | Status |
|------|--------------|----------|--------|
| **FREE (Recommended)** | **$0** | **0** | ✅ **Ready** |
| Paid (Optional) | ~$50 | 3 | ✅ Supported |

### 🚀 **Recent Updates**
- **FREE Data Sources**: BlockscoutClient, EthereumRPCClient, DexscreenerClient
- **Corruption Fixes**: 15+ syntax errors fixed across 4 core files
- **Security**: All hardcoded API keys removed, environment variables required
- **Testing**: Comprehensive test suite with 21 passing tests
- **Documentation**: Complete guides for FREE data sources and integration

## System Overview

The system ingests multi-modal crypto intelligence, transforms it into hybrid feature vectors, scores each asset with the `GemScore` ensemble, and renders both operational dashboards and Collapse Artifacts for archival lore. The architecture keeps safety as a hard gate while providing a tunable scoring surface for discovery experiments.

### High-Level Architecture

```
├── README.md                     # System blueprint & operating guide
├── requirements.txt              # Python dependencies
├── requirements-py313.txt        # Python 3.13 compatible dependencies
├── pyproject.toml               # Project configuration
├── simple_api.py                # Compatibility shim for legacy imports
├── sitecustomize.py             # Ensures UTF-8 output on interpreters
├── scripts/
│   ├── api/                     # FastAPI launchers and helpers
│   ├── dashboard/               # Frontend tooling
│   ├── demo/
│   │   ├── main.py              # Hidden Gem scanner demo entry point
│   │   └── main.ts              # TypeScript pipeline skeleton (Phase 1-2)
│   ├── monitoring/
│   │   └── status_check.py      # System health check script
│   ├── notebooks/
│   │   └── create_notebook.py   # Notebook repair helper
│   ├── powershell/              # Windows automation scripts
│   ├── testing/
│   │   ├── run_tests.py         # Pytest convenience runner
│   │   ├── validate_fixes.py    # Namespace/schema/notebook validator
│   │   ├── validate_system.py   # Post-installation system checks
│   │   └── verify_cli.py        # CLI verification harness
│   └── manual/                  # Interactive regression experiments
├── prompts/
│   ├── narrative_analyzer.md    # LLM prompt for narrative analysis
│   ├── onchain_activity.md      # LLM prompt for on-chain metrics
│   ├── contract_safety.md       # LLM prompt for safety analysis
│   └── technical_pattern.md     # LLM prompt for technical patterns
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
```
    subgraph Delivery
        C1[FastAPI Service]
        C2[Next.js Dashboard]
        C3[Alerts\n(Telegram, Slack)]
        C4[Collapse Artifacts\n(Obsidian Export)]
    end

    A1 & A2 & A3 & A4 & A5 --> B1
    P1 & P2 -.-> B1
    B1 --> B2
    B1 --> B3
    B3 --> B4
    B2 --> B4
    B4 --> C1
    C1 --> C2
    C1 --> C3
    C1 --> C4
```

## 🚀 Quick Start (FREE Tier - $0/month)

### Installation

```bash
# Clone the repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Optional: Install Python 3.13 compatible requirements
pip install -r requirements-py313.txt
```

### Run Tests

```bash
# Run all tests (21 tests should pass)
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v

# Run smoke tests only
pytest tests/test_smoke.py -v

# Run integration tests
pytest tests/test_free_clients_integration.py -v
```

### Usage with FREE Data Sources

```python
from src.core.pipeline import HiddenGemScanner, TokenConfig
from src.core.clients import CoinGeckoClient
from src.core.free_clients import BlockscoutClient, EthereumRPCClient
from src.core.orderflow_clients import DexscreenerClient

# Initialize scanner with 100% FREE data sources (no API keys needed!)
with CoinGeckoClient() as coin_client, \
     DexscreenerClient() as dex_client, \
     BlockscoutClient() as blockscout_client, \
     EthereumRPCClient() as rpc_client:
    
    scanner = HiddenGemScanner(
        coin_client=coin_client,
        dex_client=dex_client,           # FREE - replaces DeFiLlama
        blockscout_client=blockscout_client,  # FREE - replaces Etherscan
        rpc_client=rpc_client,           # FREE - on-chain data
    )
    
    # Scan a token
    config = TokenConfig(
        contract_address="0x6982508145454Ce325dDbE47a25d4ec3d2311933",  # PEPE
        token_id="pepe",
        symbol="PEPE",
    )
    
    result = scanner.scan(config)
    print(f"GemScore: {result.gem_score}")
    print(f"Confidence: {result.confidence}")
    print(f"Flagged: {result.flagged}")
```

### API Keys (Optional - Only for Paid Tier)

If you want to use paid data sources for enhanced reliability:

```bash
# Set environment variables (not required for FREE tier)
export GROQ_API_KEY="your-groq-key-here"          # Optional for Groq AI
export ETHERSCAN_API_KEY="your-etherscan-key"    # Optional for Etherscan
export COINGECKO_API_KEY="your-coingecko-key"    # Optional for CoinGecko Pro
```

**Note**: The FREE tier works without any API keys!

### Tree-of-Thought Execution Trace

Every scan executes the hardened Tree-of-Thought plan described in the strategy memo. Each branch in the tree is materialized as
an executable node that records its own outcome, summary, and data payload, and the trace explicitly tags deferred/pruned workstreams (wallet clustering, social ingestion, fuzzing, alert fan-out) as `skipped` for roadmap visibility. Inspect the trace directly from the CLI:

```bash
python -m src.cli.run_scanner configs/example.yaml --tree --tree-format pretty
```

Switch to `--tree-format json` to export a machine-readable structure for Collapse Artifact enrichment or downstream tooling.

### Component Breakdown

| Layer | Responsibilities | Key Tech | Cost |
|-------|------------------|----------|------|
| Ingestion | Pull structured price, on-chain, contract, and narrative datasets. | CoinGecko (FREE), Dexscreener (FREE), Blockscout (FREE), Ethereum RPC (FREE) | **$0/mo** |
| Feature Extraction | Compute time-series indicators, tokenomics ratios, narrative embeddings, and risk flags. | `pandas`, `numpy`, `ta`, Groq AI (FREE) | **$0/mo** |
| Analysis & Scoring | Aggregate features into `GemScore` with confidence bands. | Custom Python module, `scikit-learn`, `HDBSCAN` | **$0/mo** |
| Safety | Static analysis, heuristics, liquidity checks. | `slither`, bespoke rules engine | **$0/mo** |
| Delivery | API, dashboard, alerts, Collapse Artifacts. | FastAPI, PostgreSQL/TimescaleDB, Next.js, Telegram Bot API | **$0/mo** |

## Data & Feature Model

### Core Feature Families

1. **Sentiment & Narrative** – embedding-driven sentiment score, narrative volatility, memetic motifs.
2. **On-chain Behavior** – wallet cohort accumulation, transaction size skew, smart-money overlap.
3. **Market Microstructure** – liquidity depth, order-book spread, volatility regime.
4. **Tokenomics** – supply distribution, vesting cliffs, unlock schedule risk (heavy penalty if ≥10% supply unlocks within 30 days).
5. **Contract Safety** – verification status, privileged functions, proxy patterns, honeypot flags.

### GemScore Formula

`GemScore = Σ(wᵢ · featureᵢ)` with weights: `S=0.15`, `A=0.20`, `O=0.15`, `L=0.10`, `T=0.12`, `C=0.12`, `N=0.08`, `G=0.08`. Scores are normalized 0–100.

Confidence is computed as `0.5 · Recency + 0.5 · DataCompleteness` and reported alongside the score. Assets require **≥3 independent positive signals** and a **safety gate pass** before surfacing to operators.

## Infrastructure Blueprint

### Deployment Topology

- **Data Plane:** Batch + streaming ingestion workers (Python) deployed on Render/DO. Prefect or Celery orchestrates ETL cadences.
- **Storage:**
  - PostgreSQL/TimescaleDB for structured + time-series data.
  - Vector database (Pinecone for hosted MVP, Milvus/Weaviate for self-hosted).
  - Object storage (S3-compatible) for raw artifacts and provenance bundles.
- **Model Services:** Containerized prompt workers (LLM calls) behind FastAPI microservice with rate limiting.
- **Delivery:** FastAPI core API, Next.js dashboard on Vercel, alert bots via serverless functions or lightweight worker.

### CI/CD Skeleton

1. GitHub Actions workflow for lint/test/build (see [github-actions.yml](https://github.com/CrisisCore-Systems/Autotrader/blob/main/ci/github-actions.yml)).
2. Infrastructure-as-code stubs in [`infra/`](infra/) for Terraform or Pulumi expansion.
3. Secrets stored in Vault/Secrets Manager. Local development uses `.env` managed by Doppler or `direnv`.

### Observability & Safety

- Structured logging with OpenTelemetry.
- Metrics pipeline (Prometheus + Grafana) tracking ingestion latency, API SLIs, false positive rates.
- Alerting for safety violations (e.g., contract analyzer flagged HIGH severity) before user notifications.

### Artifact Provenance & Glossary (NEW)

**Full lineage tracking and technical documentation generation**

Track the complete lifecycle of every data artifact from ingestion through to GemScore calculation:

```python
from src.core.provenance_tracking import complete_pipeline_tracked
from src.core.provenance import get_provenance_tracker

# Run analysis with full provenance tracking
results = complete_pipeline_tracked(
    snapshot=market_snapshot,
    price_series=prices,
    narrative_embedding_score=0.75,
    contract_report=safety_report,
    data_source="etherscan"
)

# Explore lineage
tracker = get_provenance_tracker()
lineage = tracker.get_lineage(results['provenance']['score_id'])
mermaid_diagram = tracker.export_lineage_graph(score_id, format="mermaid")
```

**Key Features:**
- ✅ **Complete Lineage Tracking**: Track all data transformations and dependencies
- ✅ **Performance Metrics**: Monitor transformation duration and bottlenecks
- ✅ **Quality Assurance**: Track data quality metrics throughout pipeline
- ✅ **Visual Diagrams**: Export lineage as Mermaid diagrams for visualization
- ✅ **Technical Glossary**: Auto-generated documentation for all metrics and features
- ✅ **Search & Browse**: Full-text search and category-based browsing of terms

**Usage:**

```python
# Look up technical terms
from src.core.glossary import get_glossary

glossary = get_glossary()
term = glossary.get_term("GemScore")
print(term.definition)  # Full definition with formula and range
print(term.formula)     # Mathematical formula
print(term.range)       # Valid value range

# Search for terms
results = glossary.search("risk")

# Export documentation
glossary.export_markdown(Path("docs/GLOSSARY.md"))
```

**Documentation:**
- 📖 [Full Guide](../provenance/PROVENANCE_GLOSSARY_GUIDE.md) - Comprehensive documentation
- ⚡ [Quick Reference](../provenance/PROVENANCE_QUICK_REF.md) - Quick examples and patterns
- 📓 [Interactive Notebook](https://github.com/CrisisCore-Systems/Autotrader/blob/main/notebooks/hidden_gem_scanner.ipynb) - Hands-on tutorial
- 📊 [Implementation Summary](../provenance/PROVENANCE_IMPLEMENTATION_SUMMARY.md) - Technical details

**Quick Start:**

```bash
# Run interactive demo
python demo_provenance.py

# Run test suite
python test_provenance_glossary.py

# Explore in Jupyter
jupyter notebook notebooks/hidden_gem_scanner.ipynb
```

## Roadmap

| Sprint | Duration | Milestones |
|--------|----------|------------|
| 0 | Week 0 | Repo scaffold, env bootstrap, secrets vaulting, foundational DB migrations. |
| 1 | Weeks 1–2 | Price + on-chain ingestion, contract verification ingest, feature extractor skeleton. |
| 2 | Weeks 3–4 | GemScore implementation, safety gate, Next.js dashboard, Collapse Artifact exporter. |
| 3 | Weeks 5+ | Wallet clustering integration, narrative embeddings, backtest harness, reinforcement learning for weight tuning. |

## Backtesting Protocol

1. Assemble 12–36 months of historical data across modalities.
2. Recompute features on rolling 24h/7d windows.
3. Emit daily GemScore rankings and evaluate:
   - `precision@K`
   - Return distributions (median/mean) over 7/30/90-day windows
   - False positive rates & drawdown analysis
   - Paper portfolio Sharpe ratio
4. Perform time-based cross-validation (e.g., expanding/rolling windows).
5. Adjust weights and filters iteratively, prioritizing safety over recall.

## Collapse Artifact Output

Artifacts blend operational data with mythic lore for archival memorywear. See [collapse_artifact.html](https://github.com/CrisisCore-Systems/Autotrader/blob/main/artifacts/templates/collapse_artifact.html) for the HTML/CSS zine template and [sample_artifact.md](https://github.com/CrisisCore-Systems/Autotrader/blob/main/artifacts/examples/sample_artifact.md) for Markdown exports. Render as PDF via `weasyprint` or Vercel serverless renderer.

## Repository Structure

```
├── README.md                     # System blueprint & operating guide
├── requirements.txt              # Python dependencies
├── requirements-py313.txt        # Python 3.13 compatible dependencies
├── pyproject.toml               # Project configuration
├── simple_api.py                # Compatibility shim for legacy imports
├── sitecustomize.py             # Ensures UTF-8 output on interpreters
├── scripts/
│   ├── api/                     # FastAPI launchers and helpers
│   ├── dashboard/               # Frontend tooling
│   ├── demo/
│   │   ├── main.py              # Hidden Gem scanner demo entry point
│   │   └── main.ts              # TypeScript pipeline skeleton (Phase 1-2)
│   ├── monitoring/
│   │   └── status_check.py      # System health check script
│   ├── notebooks/
│   │   └── create_notebook.py   # Notebook repair helper
│   ├── powershell/              # Windows automation scripts
│   ├── testing/
│   │   ├── run_tests.py         # Pytest convenience runner
│   │   ├── validate_fixes.py    # Namespace/schema/notebook validator
│   │   ├── validate_system.py   # Post-installation system checks
│   │   └── verify_cli.py        # CLI verification harness
│   └── manual/                  # Interactive regression experiments
├── prompts/
│   ├── narrative_analyzer.md    # LLM prompt for narrative analysis
│   ├── onchain_activity.md      # LLM prompt for on-chain metrics
│   ├── contract_safety.md       # LLM prompt for safety analysis
│   └── technical_pattern.md     # LLM prompt for technical patterns
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
```

## Getting Started

### Prerequisites

- Python 3.11+ (tested on 3.13.7)
- Virtual environment recommended
- No API keys required for FREE tier!

### Installation

```bash
# Clone repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or for Python 3.13:
pip install -r requirements-py313.txt
```

### Validation

```bash
# Run system validation
python scripts/testing/validate_system.py

# Run all tests (21 tests should pass)
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v
```

### Basic Usage (FREE Tier)

```bash
# Configure scanner
cp configs/example.yaml configs/my_scan.yaml
# Edit my_scan.yaml with your target token

# Execute scan with FREE clients
python -m src.cli.run_scanner configs/my_scan.yaml --tree

# Or start the lightweight API
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
# Visit http://localhost:8000/docs for API documentation
```

### Advanced Usage (Optional Paid Tier)

If you want enhanced reliability with paid data sources:

```bash
# Set environment variables
export GROQ_API_KEY="your-key-here"
export ETHERSCAN_API_KEY="your-key-here"
export COINGECKO_API_KEY="your-key-here"

# Use enhanced API
python start_enhanced_api.py
```

## Next Steps

- ✅ **Production Ready**: All 21 tests passing
- ✅ **FREE Tier Working**: $0/month, 0 API keys required
- ✅ **Documentation Updated**: Reflects current state
- 🎯 **Future Enhancements**: 
  - Wire Next.js dashboard for UI
  - Add wallet clustering integration
  - Implement reinforcement learning for weight tuning
  - Expand backtest harness with historical data

For questions or collaboration, open an issue or reach out to the VoidBloom / CrisisCore maintainers.


**Phase 1–2 Pipeline Implementation**

This repository contains the foundational skeleton for the VoidBloom Data Oracle, a sophisticated cryptocurrency analysis system that combines multi-source data ingestion, sentiment synthesis, technical intelligence, and contract security analysis.

## 🌌 Vision & Mission

### Mission in One Line

Build a reliable, safety-gated, AI-assisted system that discovers early, high-potential crypto tokens before retail hype, then translates those signals into ranked dashboards, actionable alerts, and mythic “Collapse Artifact” reports you can publish, sell, or archive as lore.

### The Problem It Solves (Bluntly)

- Noise > Signal. Thousands of tokens, shallow reporting, coordinated shilling.
- Fragmented data. On-chain, order books, GitHub, social—never in one place.
- Security blind spots. Great narratives can hide unsafe contracts and toxic tokenomics.
- Creative moat missing. Pure quant tools don’t build brand, community, or artifacts.

This project fuses quant + narrative + security into a single pipeline with a human-in-the-loop, and aestheticizes the output so it becomes both research and product.

### Concrete Objectives

1. Surface hidden gems early by ranking tokens with a multi-signal **GemScore** blending on-chain accumulation, technicals, sentiment/narrative momentum, liquidity depth, tokenomics, and contract safety.
2. Block obvious rugs/exploits via a contract safety gate that checks owner privileges, mintability, upgradeability, and exploit patterns.
3. Make the signal usable with a dashboard (ranked list + charts), alerts (Telegram/Slack), and Obsidian exports for daily operations.
4. Create monetizable artifacts: high-score tokens become “Lore Capsules” rendered as collectible reports with codex glyphs and poetic captioning.
5. Continuously learn by backtesting, measuring precision@K, and re-weighting features in a recursive improvement loop.
6. Stay human-controlled—no auto-trading, no custody; the system suggests, you decide.

### Scope (What It Will Do)

- Ingest multi-source data: price/volume, TVL, whale flows, contract metadata, tokenomics, headlines/social snippets, GitHub activity.
- Normalize then feature-ize: technical indicators (RSI/MACD/MAs), accumulation metrics, liquidity depth, unlock schedules, narrative embeddings.
- Score & rank tokens with GemScore (0–100) and a Confidence metric, gating everything through safety checks.
- Output top candidates with charts, risk notes, and “Collapse Artifact” PDFs while logging feedback for iterative improvement.

### Non-Goals (What It Won’t Do)

- Hold keys, place trades, promise returns, or provide financial advice.
- Replace diligence; it accelerates and augments it.

## 🧠 System at a Glance

**Inputs → Transforms → Outputs**

**Inputs**: On-chain (Etherscan/The Graph/DefiLlama), market data (CoinGecko/exchange APIs), social/news snippets (X, Reddit, headlines), GitHub activity, tokenomics (supply, unlocks, vesting).

**Transforms**: Feature extraction (technicals, accumulation, liquidity), narrative embeddings and clustering (NVI), contract safety analysis (privileges, proxies, mintability), ensemble scoring with time decay.

**Outputs**: Web dashboard (ranked tokens + drilldowns), alerts (score jumps, safety changes), Collapse Artifact reports (Obsidian/PDF zines), API for ecosystem reuse.

## 🧮 Core Scoring Model

Features (normalized 0–1): Sentiment/Narrative (S, NVI), Accumulation (A), On-chain activity (O), Liquidity depth (L), Tokenomics risk (T), Contract safety (C), Meme momentum (M), Community growth (G).

Example weighting (MVP): S:0.15, A:0.20, O:0.15, L:0.10, T:0.12, C:0.12, M:0.08, G:0.08 → Σ=1.0.

**GemScore** = Σ (wᵢ·featureᵢ) reported 0–100 with a separate Confidence score. A safety gate penalizes or blocks assets with severe contract flags or ultra-thin liquidity.

## 👥 Who Uses It and How

- **Researcher-Architect**: Reviews the top list daily, opens token drilldowns, interprets risk notes, and determines watchlists or tranche sizes.
- **Community/Collectors**: Consume stylized Lore Capsules, purchase memorywear PDFs, and follow dashboard updates.
- **Collaborators/Analysts**: Extend data sources, refine heuristics, or craft add-on playbooks.

### User Stories

- “Alert me when a token hits GemScore ≥ 70 with Confidence ≥ 0.75 and no upcoming unlock cliffs.”
- “Export the top 5 weekly as Artifact PDFs with glyphs + a 120-word poetic caption.”

## 📏 Success Metrics

- **Signal quality**: precision@10 (7/30/90-day windows), median forward return vs. baseline, max drawdown on flagged list.
- **Timeliness**: median lead time between flag and mainstream coverage.
- **Safety**: % of blocked assets later flagged as risky by third parties.
- **Adoption**: dashboard DAUs, alert subscriptions, artifact downloads/sales.
- **Learning speed**: improvement in precision after each re-weighting cycle.

## 🛡️ Risks & Mitigations

- **Data bias / survivorship** → Use broad historical datasets, time-split backtests, and log false positives/negatives.
- **Overfitting** → Keep weights simple and interpretable; validate out-of-sample; favor orthogonal features.
- **Security theater** → Gate on objective contract checks, link to evidence, retain human sign-off.
- **Ethical drift** → Publish safety findings, include disclaimers, avoid auto-execution, maintain provenance logs.
- **API fragility / rate limits** → Cache, queue, degrade gracefully, and rotate sources.

## 📦 Deliverables

- Next.js (or Streamlit) dashboard with ranked tokens, mini-charts, and risk badges.
- Telegram/Slack alerts with GemScore, Confidence, and key flags.
- Obsidian export + printable PDF “Lore Capsule” template with glyphs, charts, and prose.
- Python ETL + scoring notebook for reproducible runs and audits.
- Backtest harness and report (precision@K, forward returns, ablation study).
- README + architecture diagram for collaborators.

## 📅 Operating Cadence

- **Every 4 hours**: ingest → score → update dashboard → push alerts.
- **Daily**: human review of top 10; publish 1–3 Lore Capsules.
- **Weekly**: backtest + weight tuning; publish a “Mythic Market Brief.”
- **Monthly**: feature ablation + safety rules refresh; roadmap iteration.

## 🗺️ Roadmap (Compressed)

1. **Phase 1**: Ingest (price/on-chain/contract), compute GemScore, CLI/notebook output.
2. **Phase 2**: Dashboard + safety gate + alerts.
3. **Phase 3**: Narrative embeddings (NVI) + Obsidian/PDF artifact pipeline.
4. **Phase 4**: Backtests, auto-tuning, community publishing flow.
5. **Phase 5**: Enrichment (wallet clustering, DEX depth models), partner feeds.

## 🧭 Why It Matters

Edge arises from curated data, risk gating, and a recursive workflow—not just the model. The system transforms signals into mythic evidence, minting market intelligence as ritualized culture.

## 📁 Repository Structure

```
.
├── ARCHITECTURE.md      # Mermaid architecture diagram and system overview
├── dashboard/          # React dashboard for interactive visualization
├── main.py             # Python pipeline skeleton (Phase 1-2)
├── scripts/
│   ├── api/                     # FastAPI launchers and helpers
│   ├── dashboard/               # Frontend tooling
│   ├── demo/
│   │   ├── main.py              # Hidden Gem scanner demo entry point
│   │   └── main.ts              # TypeScript pipeline skeleton (Phase 1-2)
│   ├── monitoring/
│   │   └── status_check.py      # System health check script
│   ├── notebooks/
│   │   └── create_notebook.py   # Notebook repair helper
│   ├── powershell/              # Windows automation scripts
│   ├── testing/
│   │   ├── run_tests.py         # Pytest convenience runner
│   │   ├── validate_fixes.py    # Namespace/schema/notebook validator
│   │   ├── validate_system.py   # Post-installation system checks
│   │   └── verify_cli.py        # CLI verification harness
│   └── manual/                  # Interactive regression experiments
├── prompts/
│   ├── narrative_analyzer.md    # LLM prompt for narrative analysis
│   ├── onchain_activity.md      # LLM prompt for on-chain metrics
│   ├── contract_safety.md       # LLM prompt for safety analysis
│   └── technical_pattern.md     # LLM prompt for technical patterns
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
```

## Getting Started

### Prerequisites

- Python 3.11+ (tested on 3.13.7)
- Virtual environment recommended
- No API keys required for FREE tier!

### Installation

```bash
# Clone repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or for Python 3.13:
pip install -r requirements-py313.txt
```

### Validation

```bash
# Run system validation
python scripts/testing/validate_system.py

# Run all tests (21 tests should pass)
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v
```

### Basic Usage (FREE Tier)

```bash
# Configure scanner
cp configs/example.yaml configs/my_scan.yaml
# Edit my_scan.yaml with your target token

# Execute scan with FREE clients
python -m src.cli.run_scanner configs/my_scan.yaml --tree

# Or start the lightweight API
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
# Visit http://localhost:8000/docs for API documentation
```

### Advanced Usage (Optional Paid Tier)

If you want enhanced reliability with paid data sources:

```bash
# Set environment variables
export GROQ_API_KEY="your-key-here"
export ETHERSCAN_API_KEY="your-key-here"
export COINGECKO_API_KEY="your-key-here"

# Use enhanced API
python start_enhanced_api.py
```

## Next Steps

- ✅ **Production Ready**: All 21 tests passing
- ✅ **FREE Tier Working**: $0/month, 0 API keys required
- ✅ **Documentation Updated**: Reflects current state
- 🎯 **Future Enhancements**: 
  - Wire Next.js dashboard for UI
  - Add wallet clustering integration
  - Implement reinforcement learning for weight tuning
  - Expand backtest harness with historical data

For questions or collaboration, open an issue or reach out to the VoidBloom / CrisisCore maintainers.


**Phase 1–2 Pipeline Implementation**

This repository contains the foundational skeleton for the VoidBloom Data Oracle, a sophisticated cryptocurrency analysis system that combines multi-source data ingestion, sentiment synthesis, technical intelligence, and contract security analysis.

## 🌌 Vision & Mission

### Mission in One Line

Build a reliable, safety-gated, AI-assisted system that discovers early, high-potential crypto tokens before retail hype, then translates those signals into ranked dashboards, actionable alerts, and mythic “Collapse Artifact” reports you can publish, sell, or archive as lore.

### The Problem It Solves (Bluntly)

- Noise > Signal. Thousands of tokens, shallow reporting, coordinated shilling.
- Fragmented data. On-chain, order books, GitHub, social—never in one place.
- Security blind spots. Great narratives can hide unsafe contracts and toxic tokenomics.
- Creative moat missing. Pure quant tools don’t build brand, community, or artifacts.

This project fuses quant + narrative + security into a single pipeline with a human-in-the-loop, and aestheticizes the output so it becomes both research and product.

### Concrete Objectives

1. Surface hidden gems early by ranking tokens with a multi-signal **GemScore** blending on-chain accumulation, technicals, sentiment/narrative momentum, liquidity depth, tokenomics, and contract safety.
2. Block obvious rugs/exploits via a contract safety gate that checks owner privileges, mintability, upgradeability, and exploit patterns.
3. Make the signal usable with a dashboard (ranked list + charts), alerts (Telegram/Slack), and Obsidian exports for daily operations.
4. Create monetizable artifacts: high-score tokens become “Lore Capsules” rendered as collectible reports with codex glyphs and poetic captioning.
5. Continuously learn by backtesting, measuring precision@K, and re-weighting features in a recursive improvement loop.
6. Stay human-controlled—no auto-trading, no custody; the system suggests, you decide.

### Scope (What It Will Do)

- Ingest multi-source data: price/volume, TVL, whale flows, contract metadata, tokenomics, headlines/social snippets, GitHub activity.
- Normalize then feature-ize: technical indicators (RSI/MACD/MAs), accumulation metrics, liquidity depth, unlock schedules, narrative embeddings.
- Score & rank tokens with GemScore (0–100) and a Confidence metric, gating everything through safety checks.
- Output top candidates with charts, risk notes, and “Collapse Artifact” PDFs while logging feedback for iterative improvement.

### Non-Goals (What It Won’t Do)

- Hold keys, place trades, promise returns, or provide financial advice.
- Replace diligence; it accelerates and augments it.

## 🧠 System at a Glance

**Inputs → Transforms → Outputs**

**Inputs**: On-chain (Etherscan/The Graph/DefiLlama), market data (CoinGecko/exchange APIs), social/news snippets (X, Reddit, headlines), GitHub activity, tokenomics (supply, unlocks, vesting).

**Transforms**: Feature extraction (technicals, accumulation, liquidity), narrative embeddings and clustering (NVI), contract safety analysis (privileges, proxies, mintability), ensemble scoring with time decay.

**Outputs**: Web dashboard (ranked tokens + drilldowns), alerts (score jumps, safety changes), Collapse Artifact reports (Obsidian/PDF zines), API for ecosystem reuse.

## 🧮 Core Scoring Model

Features (normalized 0–1): Sentiment/Narrative (S, NVI), Accumulation (A), On-chain activity (O), Liquidity depth (L), Tokenomics risk (T), Contract safety (C), Meme momentum (M), Community growth (G).

Example weighting (MVP): S:0.15, A:0.20, O:0.15, L:0.10, T:0.12, C:0.12, M:0.08, G:0.08 → Σ=1.0.

**GemScore** = Σ (wᵢ·featureᵢ) reported 0–100 with a separate Confidence score. A safety gate penalizes or blocks assets with severe contract flags or ultra-thin liquidity.

## 👥 Who Uses It and How

- **Researcher-Architect**: Reviews the top list daily, opens token drilldowns, interprets risk notes, and determines watchlists or tranche sizes.
- **Community/Collectors**: Consume stylized Lore Capsules, purchase memorywear PDFs, and follow dashboard updates.
- **Collaborators/Analysts**: Extend data sources, refine heuristics, or craft add-on playbooks.

### User Stories

- “Alert me when a token hits GemScore ≥ 70 with Confidence ≥ 0.75 and no upcoming unlock cliffs.”
- “Export the top 5 weekly as Artifact PDFs with glyphs + a 120-word poetic caption.”

## 📏 Success Metrics

- **Signal quality**: precision@10 (7/30/90-day windows), median forward return vs. baseline, max drawdown on flagged list.
- **Timeliness**: median lead time between flag and mainstream coverage.
- **Safety**: % of blocked assets later flagged as risky by third parties.
- **Adoption**: dashboard DAUs, alert subscriptions, artifact downloads/sales.
- **Learning speed**: improvement in precision after each re-weighting cycle.

## 🛡️ Risks & Mitigations

- **Data bias / survivorship** → Use broad historical datasets, time-split backtests, and log false positives/negatives.
- **Overfitting** → Keep weights simple and interpretable; validate out-of-sample; favor orthogonal features.
- **Security theater** → Gate on objective contract checks, link to evidence, retain human sign-off.
- **Ethical drift** → Publish safety findings, include disclaimers, avoid auto-execution, maintain provenance logs.
- **API fragility / rate limits** → Cache, queue, degrade gracefully, and rotate sources.

## 📦 Deliverables

- Next.js (or Streamlit) dashboard with ranked tokens, mini-charts, and risk badges.
- Telegram/Slack alerts with GemScore, Confidence, and key flags.
- Obsidian export + printable PDF “Lore Capsule” template with glyphs, charts, and prose.
- Python ETL + scoring notebook for reproducible runs and audits.
- Backtest harness and report (precision@K, forward returns, ablation study).
- README + architecture diagram for collaborators.

## 📅 Operating Cadence

- **Every 4 hours**: ingest → score → update dashboard → push alerts.
- **Daily**: human review of top 10; publish 1–3 Lore Capsules.
- **Weekly**: backtest + weight tuning; publish a “Mythic Market Brief.”
- **Monthly**: feature ablation + safety rules refresh; roadmap iteration.

## 🗺️ Roadmap (Compressed)

1. **Phase 1**: Ingest (price/on-chain/contract), compute GemScore, CLI/notebook output.
2. **Phase 2**: Dashboard + safety gate + alerts.
3. **Phase 3**: Narrative embeddings (NVI) + Obsidian/PDF artifact pipeline.
4. **Phase 4**: Backtests, auto-tuning, community publishing flow.
5. **Phase 5**: Enrichment (wallet clustering, DEX depth models), partner feeds.

## 🧭 Why It Matters

Edge arises from curated data, risk gating, and a recursive workflow—not just the model. The system transforms signals into mythic evidence, minting market intelligence as ritualized culture.

## 📁 Repository Structure

```
.
├── ARCHITECTURE.md      # Mermaid architecture diagram and system overview
├── dashboard/          # React dashboard for interactive visualization
├── main.py             # Python pipeline skeleton (Phase 1-2)
├── scripts/
│   ├── api/                     # FastAPI launchers and helpers
│   ├── dashboard/               # Frontend tooling
│   ├── demo/
│   │   ├── main.py              # Hidden Gem scanner demo entry point
│   │   └── main.ts              # TypeScript pipeline skeleton (Phase 1-2)
│   ├── monitoring/
│   │   └── status_check.py      # System health check script
│   ├── notebooks/
│   │   └── create_notebook.py   # Notebook repair helper
│   ├── powershell/              # Windows automation scripts
│   ├── testing/
│   │   ├── run_tests.py         # Pytest convenience runner
│   │   ├── validate_fixes.py    # Namespace/schema/notebook validator
│   │   ├── validate_system.py   # Post-installation system checks
│   │   └── verify_cli.py        # CLI verification harness
│   └── manual/                  # Interactive regression experiments
├── prompts/
│   ├── narrative_analyzer.md    # LLM prompt for narrative analysis
│   ├── onchain_activity.md      # LLM prompt for on-chain metrics
│   ├── contract_safety.md       # LLM prompt for safety analysis
│   └── technical_pattern.md     # LLM prompt for technical patterns
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
```

## Getting Started

### Prerequisites

- Python 3.11+ (tested on 3.13.7)
- Virtual environment recommended
- No API keys required for FREE tier!

### Installation

```bash
# Clone repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or for Python 3.13:
pip install -r requirements-py313.txt
```

### Validation

```bash
# Run system validation
python scripts/testing/validate_system.py

# Run all tests (21 tests should pass)
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v
```

### Basic Usage (FREE Tier)

```bash
# Configure scanner
cp configs/example.yaml configs/my_scan.yaml
# Edit my_scan.yaml with your target token

# Execute scan with FREE clients
python -m src.cli.run_scanner configs/my_scan.yaml --tree

# Or start the lightweight API
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
# Visit http://localhost:8000/docs for API documentation
```

### Advanced Usage (Optional Paid Tier)

If you want enhanced reliability with paid data sources:

```bash
# Set environment variables
export GROQ_API_KEY="your-key-here"
export ETHERSCAN_API_KEY="your-key-here"
export COINGECKO_API_KEY="your-key-here"

# Use enhanced API
python start_enhanced_api.py
```

## Next Steps

- ✅ **Production Ready**: All 21 tests passing
- ✅ **FREE Tier Working**: $0/month, 0 API keys required
- ✅ **Documentation Updated**: Reflects current state
- 🎯 **Future Enhancements**: 
  - Wire Next.js dashboard for UI
  - Add wallet clustering integration
  - Implement reinforcement learning for weight tuning
  - Expand backtest harness with historical data

For questions or collaboration, open an issue or reach out to the VoidBloom / CrisisCore maintainers.


**Phase 1–2 Pipeline Implementation**

This repository contains the foundational skeleton for the VoidBloom Data Oracle, a sophisticated cryptocurrency analysis system that combines multi-source data ingestion, sentiment synthesis, technical intelligence, and contract security analysis.

## 🌌 Vision & Mission

### Mission in One Line

Build a reliable, safety-gated, AI-assisted system that discovers early, high-potential crypto tokens before retail hype, then translates those signals into ranked dashboards, actionable alerts, and mythic “Collapse Artifact” reports you can publish, sell, or archive as lore.

### The Problem It Solves (Bluntly)

- Noise > Signal. Thousands of tokens, shallow reporting, coordinated shilling.
- Fragmented data. On-chain, order books, GitHub, social—never in one place.
- Security blind spots. Great narratives can hide unsafe contracts and toxic tokenomics.
- Creative moat missing. Pure quant tools don’t build brand, community, or artifacts.

This project fuses quant + narrative + security into a single pipeline with a human-in-the-loop, and aestheticizes the output so it becomes both research and product.

### Concrete Objectives

1. Surface hidden gems early by ranking tokens with a multi-signal **GemScore** blending on-chain accumulation, technicals, sentiment/narrative momentum, liquidity depth, tokenomics, and contract safety.
2. Block obvious rugs/exploits via a contract safety gate that checks owner privileges, mintability, upgradeability, and exploit patterns.
3. Make the signal usable with a dashboard (ranked list + charts), alerts (Telegram/Slack), and Obsidian exports for daily operations.
4. Create monetizable artifacts: high-score tokens become “Lore Capsules” rendered as collectible reports with codex glyphs and poetic captioning.
5. Continuously learn by backtesting, measuring precision@K, and re-weighting features in a recursive improvement loop.
6. Stay human-controlled—no auto-trading, no custody; the system suggests, you decide.

### Scope (What It Will Do)

- Ingest multi-source data: price/volume, TVL, whale flows, contract metadata, tokenomics, headlines/social snippets, GitHub activity.
- Normalize then feature-ize: technical indicators (RSI/MACD/MAs), accumulation metrics, liquidity depth, unlock schedules, narrative embeddings.
- Score & rank tokens with GemScore (0–100) and a Confidence metric, gating everything through safety checks.
- Output top candidates with charts, risk notes, and “Collapse Artifact” PDFs while logging feedback for iterative improvement.

### Non-Goals (What It Won’t Do)

- Hold keys, place trades, promise returns, or provide financial advice.
- Replace diligence; it accelerates and augments it.

## 🧠 System at a Glance

**Inputs → Transforms → Outputs**

**Inputs**: On-chain (Etherscan/The Graph/DefiLlama), market data (CoinGecko/exchange APIs), social/news snippets (X, Reddit, headlines), GitHub activity, tokenomics (supply, unlocks, vesting).

**Transforms**: Feature extraction (technicals, accumulation, liquidity), narrative embeddings and clustering (NVI), contract safety analysis (privileges, proxies, mintability), ensemble scoring with time decay.

**Outputs**: Web dashboard (ranked tokens + drilldowns), alerts (score jumps, safety changes), Collapse Artifact reports (Obsidian/PDF zines), API for ecosystem reuse.

## 🧮 Core Scoring Model

Features (normalized 0–1): Sentiment/Narrative (S, NVI), Accumulation (A), On-chain activity (O), Liquidity depth (L), Tokenomics risk (T), Contract safety (C), Meme momentum (M), Community growth (G).

Example weighting (MVP): S:0.15, A:0.20, O:0.15, L:0.10, T:0.12, C:0.12, M:0.08, G:0.08 → Σ=1.0.

**GemScore** = Σ (wᵢ·featureᵢ) reported 0–100 with a separate Confidence score. A safety gate penalizes or blocks assets with severe contract flags or ultra-thin liquidity.

## 👥 Who Uses It and How

- **Researcher-Architect**: Reviews the top list daily, opens token drilldowns, interprets risk notes, and determines watchlists or tranche sizes.
- **Community/Collectors**: Consume stylized Lore Capsules, purchase memorywear PDFs, and follow dashboard updates.
- **Collaborators/Analysts**: Extend data sources, refine heuristics, or craft add-on playbooks.

### User Stories

- “Alert me when a token hits GemScore ≥ 70 with Confidence ≥ 0.75 and no upcoming unlock cliffs.”
- “Export the top 5 weekly as Artifact PDFs with glyphs + a 120-word poetic caption.”

## 📏 Success Metrics

- **Signal quality**: precision@10 (7/30/90-day windows), median forward return vs. baseline, max drawdown on flagged list.
- **Timeliness**: median lead time between flag and mainstream coverage.
- **Safety**: % of blocked assets later flagged as risky by third parties.
- **Adoption**: dashboard DAUs, alert subscriptions, artifact downloads/sales.
- **Learning speed**: improvement in precision after each re-weighting cycle.

## 🛡️ Risks & Mitigations

- **Data bias / survivorship** → Use broad historical datasets, time-split backtests, and log false positives/negatives.
- **Overfitting** → Keep weights simple and interpretable; validate out-of-sample; favor orthogonal features.
- **Security theater** → Gate on objective contract checks, link to evidence, retain human sign-off.
- **Ethical drift** → Publish safety findings, include disclaimers, avoid auto-execution, maintain provenance logs.
- **API fragility / rate limits** → Cache, queue, degrade gracefully, and rotate sources.

## 📦 Deliverables

- Next.js (or Streamlit) dashboard with ranked tokens, mini-charts, and risk badges.
- Telegram/Slack alerts with GemScore, Confidence, and key flags.
- Obsidian export + printable PDF “Lore Capsule” template with glyphs, charts, and prose.
- Python ETL + scoring notebook for reproducible runs and audits.
- Backtest harness and report (precision@K, forward returns, ablation study).
- README + architecture diagram for collaborators.

## 📅 Operating Cadence

- **Every 4 hours**: ingest → score → update dashboard → push alerts.
- **Daily**: human review of top 10; publish 1–3 Lore Capsules.
- **Weekly**: backtest + weight tuning; publish a “Mythic Market Brief.”
- **Monthly**: feature ablation + safety rules refresh; roadmap iteration.

## 🗺️ Roadmap (Compressed)

1. **Phase 1**: Ingest (price/on-chain/contract), compute GemScore, CLI/notebook output.
2. **Phase 2**: Dashboard + safety gate + alerts.
3. **Phase 3**: Narrative embeddings (NVI) + Obsidian/PDF artifact pipeline.
4. **Phase 4**: Backtests, auto-tuning, community publishing flow.
5. **Phase 5**: Enrichment (wallet clustering, DEX depth models), partner feeds.

## 🧭 Why It Matters

Edge arises from curated data, risk gating, and a recursive workflow—not just the model. The system transforms signals into mythic evidence, minting market intelligence as ritualized culture.

## 📁 Repository Structure

```
.
├── ARCHITECTURE.md      # Mermaid architecture diagram and system overview
├── dashboard/          # React dashboard for interactive visualization
├── main.py             # Python pipeline skeleton (Phase 1-2)
├── scripts/
│   ├── api/                     # FastAPI launchers and helpers
│   ├── dashboard/               # Frontend tooling
│   ├── demo/
│   │   ├── main.py              # Hidden Gem scanner demo entry point
│   │   └── main.ts              # TypeScript pipeline skeleton (Phase 1-2)
│   ├── monitoring/
│   │   └── status_check.py      # System health check script
│   ├── notebooks/
│   │   └── create_notebook.py   # Notebook repair helper
│   ├── powershell/              # Windows automation scripts
│   ├── testing/
│   │   ├── run_tests.py         # Pytest convenience runner
│   │   ├── validate_fixes.py    # Namespace/schema/notebook validator
│   │   ├── validate_system.py   # Post-installation system checks
│   │   └── verify_cli.py        # CLI verification harness
│   └── manual/                  # Interactive regression experiments
├── prompts/
│   ├── narrative_analyzer.md    # LLM prompt for narrative analysis
│   ├── onchain_activity.md      # LLM prompt for on-chain metrics
│   ├── contract_safety.md       # LLM prompt for safety analysis
│   └── technical_pattern.md     # LLM prompt for technical patterns
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
```

## Getting Started

### Prerequisites

- Python 3.11+ (tested on 3.13.7)
- Virtual environment recommended
- No API keys required for FREE tier!

### Installation

```bash
# Clone repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or for Python 3.13:
pip install -r requirements-py313.txt
```

### Validation

```bash
# Run system validation
python scripts/testing/validate_system.py

# Run all tests (21 tests should pass)
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v
```

### Basic Usage (FREE Tier)

```bash
# Configure scanner
cp configs/example.yaml configs/my_scan.yaml
# Edit my_scan.yaml with your target token

# Execute scan with FREE clients
python -m src.cli.run_scanner configs/my_scan.yaml --tree

# Or start the lightweight API
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
# Visit http://localhost:8000/docs for API documentation
```

### Advanced Usage (Optional Paid Tier)

If you want enhanced reliability with paid data sources:

```bash
# Set environment variables
export GROQ_API_KEY="your-key-here"
export ETHERSCAN_API_KEY="your-key-here"
export COINGECKO_API_KEY="your-key-here"

# Use enhanced API
python start_enhanced_api.py
```

## Next Steps

- ✅ **Production Ready**: All 21 tests passing
- ✅ **FREE Tier Working**: $0/month, 0 API keys required
- ✅ **Documentation Updated**: Reflects current state
- 🎯 **Future Enhancements**: 
  - Wire Next.js dashboard for UI
  - Add wallet clustering integration
  - Implement reinforcement learning for weight tuning
  - Expand backtest harness with historical data

For questions or collaboration, open an issue or reach out to the VoidBloom / CrisisCore maintainers.


**Phase 1–2 Pipeline Implementation**

This repository contains the foundational skeleton for the VoidBloom Data Oracle, a sophisticated cryptocurrency analysis system that combines multi-source data ingestion, sentiment synthesis, technical intelligence, and contract security analysis.

## 🌌 Vision & Mission

### Mission in One Line

Build a reliable, safety-gated, AI-assisted system that discovers early, high-potential crypto tokens before retail hype, then translates those signals into ranked dashboards, actionable alerts, and mythic “Collapse Artifact” reports you can publish, sell, or archive as lore.

### The Problem It Solves (Bluntly)

- Noise > Signal. Thousands of tokens, shallow reporting, coordinated shilling.
- Fragmented data. On-chain, order books, GitHub, social—never in one place.
- Security blind spots. Great narratives can hide unsafe contracts and toxic tokenomics.
- Creative moat missing. Pure quant tools don’t build brand, community, or artifacts.

This project fuses quant + narrative + security into a single pipeline with a human-in-the-loop, and aestheticizes the output so it becomes both research and product.

### Concrete Objectives

1. Surface hidden gems early by ranking tokens with a multi-signal **GemScore** blending on-chain accumulation, technicals, sentiment/narrative momentum, liquidity depth, tokenomics, and contract safety.
2. Block obvious rugs/exploits via a contract safety gate that checks owner privileges, mintability, upgradeability, and exploit patterns.
3. Make the signal usable with a dashboard (ranked list + charts), alerts (Telegram/Slack), and Obsidian exports for daily operations.
4. Create monetizable artifacts: high-score tokens become “Lore Capsules” rendered as collectible reports with codex glyphs and poetic captioning.
5. Continuously learn by backtesting, measuring precision@K, and re-weighting features in a recursive improvement loop.
6. Stay human-controlled—no auto-trading, no custody; the system suggests, you decide.

### Scope (What It Will Do)

- Ingest multi-source data: price/volume, TVL, whale flows, contract metadata, tokenomics, headlines/social snippets, GitHub activity.
- Normalize then feature-ize: technical indicators (RSI/MACD/MAs), accumulation metrics, liquidity depth, unlock schedules, narrative embeddings.
- Score & rank tokens with GemScore (0–100) and a Confidence metric, gating everything through safety checks.
- Output top candidates with charts, risk notes, and “Collapse Artifact” PDFs while logging feedback for iterative improvement.

### Non-Goals (What It Won’t Do)

- Hold keys, place trades, promise returns, or provide financial advice.
- Replace diligence; it accelerates and augments it.

## 🧠 System at a Glance

**Inputs → Transforms → Outputs**

**Inputs**: On-chain (Etherscan/The Graph/DefiLlama), market data (CoinGecko/exchange APIs), social/news snippets (X, Reddit, headlines), GitHub activity, tokenomics (supply, unlocks, vesting).

**Transforms**: Feature extraction (technicals, accumulation, liquidity), narrative embeddings and clustering (NVI), contract safety analysis (privileges, proxies, mintability), ensemble scoring with time decay.

**Outputs**: Web dashboard (ranked tokens + drilldowns), alerts (score jumps, safety changes), Collapse Artifact reports (Obsidian/PDF zines), API for ecosystem reuse.

## 🧮 Core Scoring Model

Features (normalized 0–1): Sentiment/Narrative (S, NVI), Accumulation (A), On-chain activity (O), Liquidity depth (L), Tokenomics risk (T), Contract safety (C), Meme momentum (M), Community growth (G).

Example weighting (MVP): S:0.15, A:0.20, O:0.15, L:0.10, T:0.12, C:0.12, M:0.08, G:0.08 → Σ=1.0.

**GemScore** = Σ (wᵢ·featureᵢ) reported 0–100 with a separate Confidence score. A safety gate penalizes or blocks assets with severe contract flags or ultra-thin liquidity.

## 👥 Who Uses It and How

- **Researcher-Architect**: Reviews the top list daily, opens token drilldowns, interprets risk notes, and determines watchlists or tranche sizes.
- **Community/Collectors**: Consume stylized Lore Capsules, purchase memorywear PDFs, and follow dashboard updates.
- **Collaborators/Analysts**: Extend data sources, refine heuristics, or craft add-on playbooks.

### User Stories

- “Alert me when a token hits GemScore ≥ 70 with Confidence ≥ 0.75 and no upcoming unlock cliffs.”
- “Export the top 5 weekly as Artifact PDFs with glyphs + a 120-word poetic caption.”

## 📏 Success Metrics

- **Signal quality**: precision@10 (7/30/90-day windows), median forward return vs. baseline, max drawdown on flagged list.
- **Timeliness**: median lead time between flag and mainstream coverage.
- **Safety**: % of blocked assets later flagged as risky by third parties.
- **Adoption**: dashboard DAUs, alert subscriptions, artifact downloads/sales.
- **Learning speed**: improvement in precision after each re-weighting cycle.

## 🛡️ Risks & Mitigations

- **Data bias / survivorship** → Use broad historical datasets, time-split backtests, and log false positives/negatives.
- **Overfitting** → Keep weights simple and interpretable; validate out-of-sample; favor orthogonal features.
- **Security theater** → Gate on objective contract checks, link to evidence, retain human sign-off.
- **Ethical drift** → Publish safety findings, include disclaimers, avoid auto-execution, maintain provenance logs.
- **API fragility / rate limits** → Cache, queue, degrade gracefully, and rotate sources.

## 📦 Deliverables

- Next.js (or Streamlit) dashboard with ranked tokens, mini-charts, and risk badges.
- Telegram/Slack alerts with GemScore, Confidence, and key flags.
- Obsidian export + printable PDF “Lore Capsule” template with glyphs, charts, and prose.
- Python ETL + scoring notebook for reproducible runs and audits.
- Backtest harness and report (precision@K, forward returns, ablation study).
- README + architecture diagram for collaborators.

## 📅 Operating Cadence

- **Every 4 hours**: ingest → score → update dashboard → push alerts.
- **Daily**: human review of top 10; publish 1–3 Lore Capsules.
- **Weekly**: backtest + weight tuning; publish a “Mythic Market Brief.”
- **Monthly**: feature ablation + safety rules refresh; roadmap iteration.

## 🗺️ Roadmap (Compressed)

1. **Phase 1**: Ingest (price/on-chain/contract), compute GemScore, CLI/notebook output.
2. **Phase 2**: Dashboard + safety gate + alerts.
3. **Phase 3**: Narrative embeddings (NVI) + Obsidian/PDF artifact pipeline.
4. **Phase 4**: Backtests, auto-tuning, community publishing flow.
5. **Phase 5**: Enrichment (wallet clustering, DEX depth models), partner feeds.

## 🧭 Why It Matters

Edge arises from curated data, risk gating, and a recursive workflow—not just the model. The system transforms signals into mythic evidence, minting market intelligence as ritualized culture.

## 📁 Repository Structure

```
.
├── ARCHITECTURE.md      # Mermaid architecture diagram and system overview
├── dashboard/          # React dashboard for interactive visualization
├── main.py             # Python pipeline skeleton (Phase 1-2)
├── scripts/
│   ├── api/                     # FastAPI launchers and helpers
│   ├── dashboard/               # Frontend tooling
│   ├── demo/
│   │   ├── main.py              # Hidden Gem scanner demo entry point
│   │   └── main.ts              # TypeScript pipeline skeleton (Phase 1-2)
│   ├── monitoring/
│   │   └── status_check.py      # System health check script
│   ├── notebooks/
│   │   └── create_notebook.py   # Notebook repair helper
│   ├── powershell/              # Windows automation scripts
│   ├── testing/
│   │   ├── run_tests.py         # Pytest convenience runner
│   │   ├── validate_fixes.py    # Namespace/schema/notebook validator
│   │   ├── validate_system.py   # Post-installation system checks
│   │   └── verify_cli.py        # CLI verification harness
│   └── manual/                  # Interactive regression experiments
├── prompts/
│   ├── narrative_analyzer.md    # LLM prompt for narrative analysis
│   ├── onchain_activity.md      # LLM prompt for on-chain metrics
│   ├── contract_safety.md       # LLM prompt for safety analysis
│   └── technical_pattern.md     # LLM prompt for technical patterns
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
```

## Getting Started

### Prerequisites

- Python 3.11+ (tested on 3.13.7)
- Virtual environment recommended
- No API keys required for FREE tier!

### Installation

```bash
# Clone repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or for Python 3.13:
pip install -r requirements-py313.txt
```

### Validation

```bash
# Run system validation
python scripts/testing/validate_system.py

# Run all tests (21 tests should pass)
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v
```

### Basic Usage (FREE Tier)

```bash
# Configure scanner
cp configs/example.yaml configs/my_scan.yaml
# Edit my_scan.yaml with your target token

# Execute scan with FREE clients
python -m src.cli.run_scanner configs/my_scan.yaml --tree

# Or start the lightweight API
uvicorn src.api.main:app --host 127.0.0.1 --port 8000
# Visit http://localhost:8000/docs for API documentation
```

### Advanced Usage (Optional Paid Tier)

If you want enhanced reliability with paid data sources:

```bash
# Set environment variables
export GROQ_API_KEY="your-key-here"
export ETHERSCAN_API_KEY="your-key-here"
export COINGECKO_API_KEY="your-key-here"

# Use enhanced API
python start_enhanced_api.py
```

## Next Steps

- ✅ **Production Ready**: All 21 tests passing
- ✅ **FREE Tier Working**: $0/month, 0 API keys required
- ✅ **Documentation Updated**: Reflects current state
- 🎯 **Future Enhancements**: 
  - Wire Next.js dashboard for UI
  - Add wallet clustering integration
  - Implement reinforcement learning for weight tuning
  - Expand backtest harness with historical data

For questions or collaboration, open an issue or reach out to the VoidBloom / CrisisCore maintainers.


**Phase 1–2 Pipeline Implementation**

This repository contains the foundational skeleton for the VoidBloom Data Oracle, a sophisticated cryptocurrency analysis system that combines multi-source data ingestion, sentiment synthesis, technical intelligence, and contract security analysis.

## 🌌 Vision & Mission

### Mission in One Line

Build a reliable, safety-gated, AI-assisted system that discovers early, high-potential crypto tokens before retail hype, then translates those signals into ranked dashboards, actionable alerts, and mythic “Collapse Artifact” reports you can publish, sell, or archive as lore.

### The Problem It Solves (Bluntly)

- Noise > Signal. Thousands of tokens, shallow reporting, coordinated shilling.
- Fragmented data. On-chain, order books, GitHub, social—never in one place.
- Security blind spots. Great narratives can hide unsafe contracts and toxic tokenomics.
- Creative moat missing. Pure quant tools don’t build brand, community, or artifacts.

This project fuses quant + narrative + security into a single pipeline with a human-in-the-loop, and aestheticizes the output so it becomes both research and product.

### Concrete Objectives

1. Surface hidden gems early by ranking tokens with a multi-signal **GemScore** blending on-chain accumulation, technicals, sentiment/narrative momentum, liquidity depth, tokenomics, and contract safety.
2. Block obvious rugs/exploits via a contract safety gate that checks owner privileges, mintability, upgradeability, and exploit patterns.
3. Make the signal usable with a dashboard (ranked list + charts), alerts (Telegram/Slack), and Obsidian exports for daily operations.
4. Create monetizable artifacts: high-score tokens become “Lore Capsules” rendered as collectible reports with codex glyphs and poetic captioning.
5. Continuously learn by backtesting, measuring precision@K, and re-weighting features in a recursive improvement loop.
6. Stay human-controlled—no auto-trading, no custody; the system suggests, you decide.

### Scope (What It Will Do)

- Ingest multi-source data: price/volume, TVL, whale flows, contract metadata, tokenomics, headlines/social snippets, GitHub activity.
- Normalize then feature-ize: technical indicators (RSI/MACD/MAs), accumulation metrics, liquidity depth, unlock schedules, narrative embeddings.
- Score & rank tokens with GemScore (0–100) and a Confidence metric, gating everything through safety checks.
- Output top candidates with charts, risk notes, and “Collapse Artifact” PDFs while logging feedback for iterative improvement.

### Non-Goals (What It Won’t Do)

- Hold keys, place trades, promise returns, or provide financial advice.
- Replace diligence; it accelerates and augments it.

## 🧠 System at a Glance

**Inputs → Transforms → Outputs**

**Inputs**: On-chain (Etherscan/The Graph/DefiLlama), market data (CoinGecko/exchange APIs), social/news snippets (X, Reddit, headlines), GitHub activity, tokenomics (supply, unlocks, vesting).

**Transforms**: Feature extraction (technicals, accumulation, liquidity), narrative embeddings and clustering (NVI), contract safety analysis (privileges, proxies, mintability), ensemble scoring with time decay.

**Outputs**: Web dashboard (ranked tokens + drilldowns), alerts (score jumps, safety changes), Collapse Artifact reports (Obsidian/PDF zines), API for ecosystem reuse.

## 🧮 Core Scoring Model

Features (normalized 0–1): Sentiment/Narrative (S, NVI), Accumulation (A), On-chain activity (O), Liquidity depth (L), Tokenomics risk (T), Contract safety (C), Meme momentum (M), Community growth (G).

Example weighting (MVP): S:0.15, A:0.20, O:0.15, L:0.10, T:0.12, C:0.12, M:0.08, G:0.08 → Σ=1.0.

**GemScore** = Σ (wᵢ·featureᵢ) reported 0–100 with a separate Confidence score. A safety gate penalizes or blocks assets with severe contract flags or ultra-thin liquidity.

## 👥 Who Uses It and How

- **Researcher-Architect**: Reviews the top list daily, opens token drilldowns, interprets risk notes, and determines watchlists or tranche sizes.
- **Community/Collectors**: Consume stylized Lore Capsules, purchase memorywear PDFs, and follow dashboard updates.
- **Collaborators/Analysts**: Extend data sources, refine heuristics, or craft add-on playbooks.

### User Stories

- “Alert me when a token hits GemScore ≥ 70 with Confidence ≥ 0.75 and no upcoming unlock cliffs.”
- “Export the top 5 weekly as Artifact PDFs with glyphs + a 120-word poetic caption.”

## 📏 Success Metrics

- **Signal quality**: precision@10 (7/30/90-day windows), median forward return vs. baseline, max drawdown on flagged list.
- **Timeliness**: median lead time between flag and mainstream coverage.
- **Safety**: % of blocked assets later flagged as risky by third parties.
- **Adoption**: dashboard DAUs, alert subscriptions, artifact downloads/sales.
- **Learning speed**: improvement in precision after each re-weighting cycle.

## 🛡️ Risks & Mitigations

- **Data bias / survivorship** → Use broad historical datasets, time-split backtests, and log false positives/negatives.
- **Overfitting** → Keep weights simple and interpretable; validate out-of-sample; favor orthogonal features.
- **Security theater** → Gate on objective contract checks, link to evidence, retain human sign-off.
- **Ethical drift** → Publish safety findings, include disclaimers, avoid auto-execution, maintain provenance logs.
- **API fragility / rate limits** → Cache, queue, degrade gracefully, and rotate sources.

## 📦 Deliverables

- Next.js (or Streamlit) dashboard with ranked tokens, mini-charts, and risk badges.
- Telegram/Slack alerts with GemScore, Confidence, and key flags.
- Obsidian export + printable PDF “Lore Capsule” template with glyphs, charts, and prose.
- Python ETL + scoring notebook for reproducible runs and audits.
- Backtest harness and report (precision@K, forward returns, ablation study).
- README + architecture diagram for collaborators.

## 📅 Operating Cadence

- **Every 4 hours**: ingest → score → update dashboard → push alerts.
- **Daily**: human review of top 10; publish 1–3 Lore Capsules.
- **Weekly**: backtest + weight tuning; publish a “Mythic Market Brief.”
- **Monthly**: feature ablation + safety rules refresh; roadmap iteration.

## 🗺️ Roadmap (Compressed)

1. **Phase 1**: Ingest (price/on-chain/contract), compute GemScore, CLI/notebook output.
2. **Phase 2**: Dashboard + safety gate + alerts.
3. **Phase 3**: Narrative embeddings (NVI) + Obsidian/PDF artifact pipeline.
4. **Phase 4**: Backtests, auto-tuning, community publishing flow.
5. **Phase 5**: Enrichment (wallet clustering, DEX depth models), partner feeds.

## 🧭 Why It Matters

Edge arises from curated data, risk gating, and a recursive workflow—not just the model. The system transforms signals into mythic evidence, minting market intelligence as ritualized culture.

## 📁 Repository Structure

```
.
├── ARCHITECTURE.md      # Mermaid architecture diagram and system overview
├── dashboard/          # React dashboard for interactive visualization
├── main.py             # Python pipeline skeleton (Phase 1-2)
├── scripts/
│   ├── api/                     # FastAPI launchers and helpers
│   ├── dashboard/               # Frontend tooling
│   ├── demo/
│   │   ├── main.py              # Hidden Gem scanner demo entry point
│   │   └── main.ts              # TypeScript pipeline skeleton (Phase 1-2)
│   ├── monitoring/
│   │   └── status_check.py      # System health check script
│   ├── notebooks/
│   │   └── create_notebook.py   # Notebook repair helper
│   ├── powershell/              # Windows automation scripts
│   ├── testing/
│   │   ├── run_tests.py         # Pytest convenience runner
│   │   ├── validate_fixes.py    # Namespace/schema/notebook validator
│   │   ├── validate_system.py   # Post-installation system checks
│   │   └── verify_cli.py        # CLI verification harness
│   └── manual/                  # Interactive regression experiments
├── prompts/
│   ├── narrative_analyzer.md    # LLM prompt for narrative analysis
│   ├── onchain_activity.md      # LLM prompt for on-chain metrics
│   ├── contract_safety.md       # LLM prompt for safety analysis
│   └── technical_pattern.md     # LLM prompt for technical patterns
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
```

## Getting Started

### Prerequisites

- Python 3.11+ (tested on 3.13.7)
- Virtual environment recommended
- No API keys required for FREE tier!

### Installation

```bash
# Clone repository
git clone https://github.com/CrisisCore-Systems/Autotrader.git
cd Autotrader/Autotrader

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
# Or for Python 3.13:
pip install -r requirements-py313.txt
```

### Validation

```bash
# Run system validation
python scripts/testing/validate_system.py

# Run all tests (21 tests should pass)
pytest tests/test_smoke.py tests/test_free_clients_integration.py -v
```

### Basic Usage (FREE Tier)

```bash
# Configure scanner
cp configs/example.yaml configs/my_scan.yaml
# Edit my_scan.yaml with your target token

# Execute scan