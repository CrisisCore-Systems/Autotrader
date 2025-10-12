# VoidBloom Data Oracle Architecture

```mermaid
graph TD
  A[Data Infusion Layer] -->|Multi-source ingestion| B[Sentiment Synthesis Layer]
  B -->|Narrative Volatility Index (NVI)| C[Technical Intelligence Layer]
  C -->|Indicators + Signals| D[Contract & Security Layer]
  D -->|Exploit Risk, Audit| E[Signal Fusion Matrix]
  E -->|Composite Scoring| F[Visualization / Dashboard]
  subgraph Core Storage
    G[(SQLite/Supabase)]
    H[(Vector DB: Chroma/Pinecone)]
  end
  A --> G
  B --> H
  C --> G
  D --> G
  E --> G
  G --> F
  H --> F
```

---

## Phase 1–2 Pipeline Overview

**Data Ingestion (Phase 1)**
- Ingest: News, Social, On-chain, Technical (API/scraping)
- Store: Persist raw and normalized data (SQLite/Supabase, Vector DB)

**Sentiment Synthesis (Phase 2)**
- Sentiment: GPT chain for NVI, meme momentum, archetypes
- Technical: Compute indicators, validate hype
- Contract: Scan for risks, audit signals
- Score: Fuse all for composite ranking
- Output: Dashboard-ready objects, Lore Capsules (later phase)

## Key Components

### Data Infusion Layer
Multi-source data ingestion from:
- News APIs (Cointelegraph, The Block, Decrypt)
- Social platforms (Twitter/X, Reddit, Telegram, Discord)
- On-chain data (Etherscan, DefiLlama, Nansen, Token Terminal)
- Technical indicators (TradingView API)

### Sentiment Synthesis Layer
- **Narrative Volatility Index (NVI)**: GPT-powered sentiment scoring
- **Meme Momentum Score (MMS)**: Tracking viral content and hype cycles
- **Myth Vectors**: Archetypal narrative patterns (rebirth, corruption, etc.)

### Technical Intelligence Layer
- **Archetype Precision Score (APS)**: Technical indicator precision
- **Rally Strength Score (RSS)**: Momentum and volume analysis
- **Risk-Reward Ratio (RRR)**: Position sizing and risk assessment

### Contract & Security Layer
- **Exploit Risk Rating (ERR)**: Smart contract vulnerability assessment
- **On-Chain Wealth (OCW)**: Holder distribution analysis
- **Audit Confidence Index (ACI)**: Third-party audit verification

### Signal Fusion Matrix
Composite scoring algorithm combining:
- 40% Technical Intelligence (APS)
- 30% Sentiment (NVI)
- 20% Security (ERR inverse)
- 10% Risk-Reward (RRR)

### Core Storage
- **SQLite/Supabase**: Structured data persistence
- **Vector DB (Chroma/Pinecone)**: Embedding storage for semantic search
