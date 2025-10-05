# VoidBloom Data Oracle - Autotrader

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

- Ingest multi-source data: price/volume, TVL, whale flows, contract metadata, tokenomics, headlines/social snippets, GitHub commits.
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
├── main.ts             # TypeScript pipeline skeleton (Phase 1-2)
├── tsconfig.json       # TypeScript configuration
├── .gitignore          # Git ignore patterns
└── README.md           # This file
```

## 🏗️ Architecture Overview

The system is built on six core layers:

1. **Data Infusion Layer** - Multi-source data ingestion (News, Social, On-chain, Technical)
2. **Sentiment Synthesis Layer** - NVI, Meme Momentum, Archetypal Analysis
3. **Technical Intelligence Layer** - Indicators, Signals, Hype Validation
4. **Contract & Security Layer** - Risk Assessment, Audit Verification
5. **Signal Fusion Matrix** - Composite Scoring Algorithm
6. **Visualization/Dashboard** - Output Layer (Future Phase)

See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed architecture diagram and component descriptions.

## 🚀 Getting Started

### Python Implementation

The Python skeleton (`main.py`) provides the core pipeline structure:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Running the pipeline generates both `artifacts/dashboard.md` and a richer `artifacts/dashboard.html` loreboard containing fused metrics, ascii trend sparklines, and nearest-narrative references. Historical payloads, embeddings, and a fast full-text search index are persisted in `artifacts/voidbloom.db`.

### TypeScript Implementation

The TypeScript skeleton (`main.ts`) provides an async/await-based pipeline:

```bash
# Install dependencies (when ready to implement)
npm install @supabase/supabase-js axios

# Compile and run
tsc
node main.js
```

### Visualization Dashboard

An interactive dashboard is available in the `dashboard/` directory. It couples a
FastAPI service that exposes pipeline results with a React/Vite front-end.

```bash
# Start the API (default: http://localhost:8000)
uvicorn src.services.dashboard_api:app --reload

# In another shell launch the React app (default: http://localhost:5173)
cd dashboard
npm install
npm run dev
```

The development server proxies `/api/*` requests to the FastAPI backend. In
production you can set `VITE_API_BASE_URL` to point the UI at a different API
host.

### Operational Shortcuts & Automation

- Copy `.env.template` to `.env` and fill in alert transport credentials, Redis/
  RabbitMQ endpoints, and LLM budget caps before running workers or dispatchers.
- `make backtest` re-runs the walk-forward harness defined in
  [`src/pipeline/backtest.py`](src/pipeline/backtest.py) and writes dated JSON/CSV
  artifacts under `reports/backtests/`.
- `make coverage` executes `pytest --cov` with the thresholds defined in
  [`pyproject.toml`](pyproject.toml), while `make security` chains pip-audit,
  Semgrep (via `ci/semgrep.yml`), and Bandit scans.
- The alert rules and LLM routing defaults live in
  [`configs/alert_rules.yaml`](configs/alert_rules.yaml) and
  [`configs/llm.yaml`](configs/llm.yaml); update these to onboard new channels or
  tweak budget guardrails.
- Day-to-day procedures are documented in runbooks under
  [`docs/runbooks/`](docs/runbooks/) such as
  [alerting operations](docs/runbooks/alerting.md) and
  [backtesting cadence](docs/runbooks/backtesting.md).

## 📊 Key Metrics & Scores

### Sentiment Metrics
- **NVI (Narrative Volatility Index)**: GPT-powered sentiment scoring
- **MMS (Meme Momentum Score)**: Viral content and hype cycle tracking
- **Myth Vectors**: Archetypal narrative patterns

### Technical Metrics
- **APS (Archetype Precision Score)**: Technical indicator precision (0.0-1.0)
- **RSS (Rally Strength Score)**: Momentum and volume analysis (0.0-1.0)
- **RRR (Risk-Reward Ratio)**: Position sizing and risk assessment

### Security Metrics
- **ERR (Exploit Risk Rating)**: Smart contract vulnerability score (0.0-1.0)
- **OCW (On-Chain Wealth)**: Holder distribution analysis (boolean)
- **ACI (Audit Confidence Index)**: Third-party audit verification (0.0-1.0)

## 🔧 Composite Scoring Formula

```
Final Score = (0.4 × APS) + (0.3 × NVI) + (0.2 × ERR⁻¹) + (0.1 × RRR)
```

## 📝 Implementation Status

### Phase 1 - Data Ingestion ✅
- [x] Architecture design
- [x] Python + TypeScript pipelines
- [x] News ingestion (CryptoCompare + CoinDesk/Cointelegraph/Decrypt/The Block RSS)
- [x] Social ingestion (Reddit, StockTwits, Nitter/Twitter mirror)
- [x] On-chain metrics (CoinGecko fundamentals, Dexscreener liquidity, Ethplorer holder splits)
- [x] SQLite persistence + full-text search index

### Phase 2 - Sentiment & Analysis ✅
- [x] VADER + topical TF-IDF sentiment synthesis
- [x] Meme momentum scoring with recency weighting
- [x] Myth vector + narrative extraction heuristics
- [x] EMA/MACD/RSI + volatility, Bollinger bandwidth, ATR enrichments

### Phase 3 - Signal Fusion ✅
- [x] Composite scoring with contract risk modulation
- [x] Embedding similarity lookup across historical runs
- [ ] Hyperparameter optimisation + reinforcement tuning

### Phase 4 - Visualization 🚧
- [x] Markdown + HTML dashboards with lore capsules and sparklines
- [ ] Real-time monitoring channel
- [ ] Interactive front-end controls

## 🗄️ Data Sources

### News APIs
- CryptoCompare
- CoinDesk
- Cointelegraph
- Decrypt
- The Block

### Social Platforms
- Reddit
- StockTwits
- Twitter (via Nitter mirror RSS)

### On-Chain Data
- CoinGecko fundamentals + developer telemetry
- Dexscreener liquidity + volume footprints
- Ethplorer holder distribution (configurable contract map)

### Technical Data
- TradingView API
- Custom indicators

## 💾 Storage Solutions

- **SQLite**: Structured persistence with historical payloads, TF-IDF vectors, and FTS5 search
- **Supabase (TS path)**: Cloud persistence for multi-language parity
- **Vector-ready embeddings**: Deterministic TF-IDF encoding + cosine nearest-neighbour lookups

## 🛠️ Development

### Prerequisites
- Python 3.8+
- Node.js 16+
- TypeScript 4.5+

### Code Style
- Python: Follow PEP 8
- TypeScript: ESLint configuration included

### Testing
```bash
# Python unit tests
pytest

# Python syntax check
python3 -m py_compile main.py

# TypeScript type check
tsc --noEmit
```

### Groq LLM Setup

Narrative analysis now uses Groq's high-speed LPU inference API by default. To enable it locally:

1. Create a free account at [console.groq.com](https://console.groq.com) and generate an API key (`gsk_...`).
2. Install the Python dependency (already listed in `requirements.txt`):
   ```bash
   pip install -r requirements.txt
   ```
3. Export the key or store it in a local `.env` file:
   ```bash
   export GROQ_API_KEY="gsk_your_key_here"
   # or
   echo "GROQ_API_KEY=gsk_your_key_here" >> .env
   ```

If the key is missing or the API is unavailable, the analyzer gracefully falls back to deterministic keyword heuristics so tests remain reproducible.

## 📄 License

This project is part of the CrisisCore-Systems Autotrader initiative.

## 🤝 Contributing

This is a foundational skeleton ready for implementation. Key areas for contribution:
1. API integrations for data sources
2. GPT chain implementation for sentiment analysis
3. Technical indicator calculations
4. Smart contract security scanning
5. Database schema and optimization

## 📞 Contact

For questions or contributions, please open an issue or submit a pull request.

---

**Status**: ✅ Phase 1-2 skeleton complete and ready for PR review

## 🔔 Alerting Outbox

The `src/alerts` package implements an outbox pattern for GemScore notifications. Rules loaded from [`configs/alert_rules.yaml`](configs/alert_rules.yaml) produce deterministic idempotency keys so each token triggers at most one alert per window and rule version. The evaluation engine enqueues matching payloads with audit-friendly metadata ready for Celery or worker delivery.

## 📈 Backtesting CLI

Use the walk-forward harness to regenerate metrics and weight suggestions in a single command:

```bash
make backtest
```

Artifacts are written under `reports/backtests/<run-date>/` including a `summary.json`, `windows.csv`, and `weights_suggestion.json` for downstream automation.

## 🛡️ Security & Quality Gates

Continuous security scanning and coverage enforcement ship with the repo:

- `tests-and-coverage` workflow blocks merges below 75% coverage and publishes the XML artifact.
- `security-scan` workflow runs Semgrep, Bandit, and pip-audit on every push and each morning UTC.
- The new `Makefile` recipes (`security`, `coverage`, `sbom`) provide local mirrors of the CI guardrails.
