# VoidBloom / CrisisCore Hidden-Gem Scanner

This repository contains the foundational blueprint and implementation assets for **VoidBloom / CrisisCore**, a Hidden-Gem Scanner that fuses on-chain telemetry, narrative intelligence, technical analysis, and safety gating into actionable trade intelligence and ritualized "Collapse Artifact" outputs.

> **Disclaimer:** All outputs are informational only and **not financial advice**. Always retain a human-in-the-loop for execution decisions.

## System Overview

The system ingests multi-modal crypto intelligence, transforms it into hybrid feature vectors, scores each asset with the `GemScore` ensemble, and renders both operational dashboards and Collapse Artifacts for archival lore. The architecture keeps safety as a hard gate while providing a tunable scoring surface for discovery experiments.

### High-Level Architecture

```mermaid
flowchart TD
    subgraph Ingestion
        A1[Price APIs\n(CoinGecko, CEX)]
        A2[On-chain Indexers\n(Etherscan, DefiLlama)]
        A3[Contract Metadata]
        A4[Social & Git Signals]
    end

    subgraph Processing
        B1[Feature Extractors\n(Time-Series, Tokenomics, Narrative)]
        B2[Vector Store\n(Embeddings)]
        B3[Risk Filters\n(Static + Heuristics)]
        B4[GemScore Ensemble]
    end

    subgraph Delivery
        C1[FastAPI Service]
        C2[Next.js Dashboard]
        C3[Alerts\n(Telegram, Slack)]
        C4[Collapse Artifacts\n(Obsidian Export)]
    end

    A1 & A2 & A3 & A4 --> B1
    B1 --> B2
    B1 --> B3
    B3 --> B4
    B2 --> B4
    B4 --> C1
    C1 --> C2
    C1 --> C3
    C1 --> C4
```

### Tree-of-Thought Execution Trace

Every scan executes the hardened Tree-of-Thought plan described in the strategy memo. Each branch in the tree is materialized as
an executable node that records its own outcome, summary, and data payload. Inspect the trace directly from the CLI:

```bash
python -m src.cli.run_scanner configs/example.yaml --tree --tree-format pretty
```

Switch to `--tree-format json` to export a machine-readable structure for Collapse Artifact enrichment or downstream tooling.

### Component Breakdown

| Layer | Responsibilities | Key Tech |
|-------|------------------|----------|
| Ingestion | Pull structured price, on-chain, contract, and narrative datasets. | `aiohttp`, `requests`, Prefect/Celery workers |
| Feature Extraction | Compute time-series indicators, tokenomics ratios, narrative embeddings, and risk flags. | `pandas`, `numpy`, `ta`, OpenAI Embeddings |
| Analysis & Scoring | Aggregate features into `GemScore` with confidence bands. | Custom Python module, `scikit-learn`, `HDBSCAN` |
| Safety | Static analysis, heuristics, liquidity checks. | `slither`, bespoke rules engine |
| Delivery | API, dashboard, alerts, Collapse Artifacts. | FastAPI, PostgreSQL/TimescaleDB, Next.js, Telegram Bot API |

## Data & Feature Model

### Core Feature Families

1. **Sentiment & Narrative** – embedding-driven sentiment score, narrative volatility, memetic motifs.
2. **On-chain Behavior** – wallet cohort accumulation, transaction size skew, smart-money overlap.
3. **Market Microstructure** – liquidity depth, order-book spread, volatility regime.
4. **Tokenomics** – supply distribution, vesting cliffs, unlock schedule risk.
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

1. GitHub Actions workflow for lint/test/build (see [`ci/github-actions.yml`](ci/github-actions.yml)).
2. Infrastructure-as-code stubs in [`infra/`](infra/) for Terraform or Pulumi expansion.
3. Secrets stored in Vault/Secrets Manager. Local development uses `.env` managed by Doppler or `direnv`.

### Observability & Safety

- Structured logging with OpenTelemetry.
- Metrics pipeline (Prometheus + Grafana) tracking ingestion latency, API SLIs, false positive rates.
- Alerting for safety violations (e.g., contract analyzer flagged HIGH severity) before user notifications.

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

Artifacts blend operational data with mythic lore for archival memorywear. See [`artifacts/templates/collapse_artifact.html`](artifacts/templates/collapse_artifact.html) for the HTML/CSS zine template and [`artifacts/examples/sample_artifact.md`](artifacts/examples/sample_artifact.md) for Markdown exports. Render as PDF via `weasyprint` or Vercel serverless renderer.

## Repository Structure

```
├── README.md                     # System blueprint & operating guide
├── prompts/
│   ├── narrative_analyzer.md
│   ├── onchain_activity.md
│   ├── contract_safety.md
│   └── technical_pattern.md
├── notebooks/
│   └── hidden_gem_scanner.ipynb   # Prototype ingest → score workflow
├── artifacts/
│   ├── templates/
│   │   └── collapse_artifact.html
│   └── examples/
│       └── sample_artifact.md
├── backtest/
│   └── harness.py                # Backtest harness scaffold
├── ci/
│   └── github-actions.yml        # CI pipeline skeleton
├── infra/
│   └── docker-compose.yml        # Local stack bootstrap
└── src/
    ├── core/
    │   ├── __init__.py
    │   ├── clients.py              # HTTP data providers (CoinGecko, DefiLlama, Etherscan)
    │   ├── features.py             # Feature engineering utilities
    │   ├── narrative.py            # Narrative sentiment + momentum estimator
    │   ├── pipeline.py             # Hidden-Gem Scanner orchestration layer
    │   ├── scoring.py              # GemScore weighting logic
    │   └── safety.py               # Contract & liquidity safety heuristics
    ├── cli/
    │   └── run_scanner.py          # CLI entrypoint to execute scans
    └── services/
        └── exporter.py
```

## Getting Started

1. Clone repository and create a Python 3.11 virtual environment.
2. Install dependencies (`pip install -r requirements.txt`).
3. Configure environment variables (`cp .env.example .env`) and populate API keys.
4. Prepare a scanner configuration (`configs/example.yaml`) with CoinGecko/DefiLlama identifiers and unlock schedule data.
5. Execute the pipeline via CLI: `python -m src.cli.run_scanner configs/example.yaml` (append `--tree` to emit the Tree-of-Thought
   execution trace).
6. (Optional) Run the prototype notebook or execute `python backtest/harness.py data/example.csv` for historical evaluation.

## Next Steps

- Fill in ingestion connectors under `src/core/features.py`.
- Wire FastAPI service and Next.js dashboard (stubs forthcoming).
- Integrate Vault/Secrets Manager before production deployments.

For questions or collaboration, open an issue or reach out to the VoidBloom / CrisisCore maintainers.
