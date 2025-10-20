# AutoTrader Data Oracle v1 – Spec Alignment Review

## Executive Summary
- The repository delivers a focused "Hidden-Gem Scanner" pipeline that ingests CoinGecko price data, DefiLlama protocol metrics, and Etherscan contract metadata, then assembles a GemScore and markdown artifact per token via a Tree-of-Thought execution plan.【F:src/core/clients.py†L34-L105】【F:src/core/pipeline.py†L80-L199】【F:src/services/exporter.py†L195-L214】
- Narrative and feature scoring are implemented with lightweight, deterministic heuristics that emphasise testability rather than the GPT-driven sentiment, meme momentum, and rich feature library promised in the product brief.【F:src/core/narrative.py†L11-L71】【F:src/core/features.py†L108-L147】【F:src/core/scoring.py†L10-L67】
- Critical roadmap items from VoidBloom Data Oracle v1—multi-source news/social ingestion, alerting, dashboard visualisation, backtesting, and reinforcement loops—remain unimplemented in the codebase despite being marked complete in the README checklist.【F:README.md†L84-L106】【F:main.py†L16-L125】

## Alignment by Capability

### Data Ingestion & Normalisation
| Spec Expectation | Repository Implementation | Gap |
| --- | --- | --- |
| Aggregate news, social, on-chain, technical, repo activity, and tokenomics feeds into a unified store. | Only HTTP clients for CoinGecko (market data), DefiLlama (protocol metrics), and Etherscan (contract metadata) are defined, and the demo pipeline runs against offline stubs for these three sources.【F:src/core/clients.py†L34-L105】【F:main.py†L16-L85】 | Social, GitHub, and richer tokenomics sources are absent; the new RSS `NewsAggregator` surfaces curated feeds but lacks persistence and broader data infusion.【F:src/services/news.py†L12-L126】【F:README.md†L84-L135】 |
| Persist historical payloads, embeddings, and search indices. | No persistence layer is wired; the demo writes markdown artifacts to disk without databases or embeddings.【F:main.py†L101-L125】【F:src/services/exporter.py†L195-L214】 | Requires database schema, vector storage, and ingestion history management. |

### Feature Engineering & Scoring
| Spec Expectation | Repository Implementation | Gap |
| --- | --- | --- |
| Compute GemScore from rich sentiment (NVI), meme momentum, liquidity depth, tokenomics risk, community growth, etc., blending multiple windows and decay factors. | Feature vector normalises liquidity, wallet activity, net inflows, unlock pressure, and holder counts, while GemScore weights match the MVP distribution listed in the spec.【F:src/core/features.py†L108-L147】【F:src/core/scoring.py†L10-L67】 | Lacks advanced indicators (EMA/MACD variants beyond basics, ATR, Bollinger), meme metrics, narrative embeddings, and dynamic weight tuning/backtesting. |
| Provide confidence via recency × completeness and support multi-window aggregation. | Recency and data completeness are calculated directly inside the pipeline before GemScore evaluation.【F:src/core/pipeline.py†L429-L446】 | No evidence of cross-window averaging, decay schedules, or learning loops the roadmap calls for. |

### Safety & Risk Controls
| Spec Expectation | Repository Implementation | Gap |
| --- | --- | --- |
| Contract safety gate with exploit detection, owner privilege analysis, liquidity floors, and tokenomics filters. | Safety module penalises liquidity below a configurable threshold and checks contract metadata for verification, mint/withdraw functions, and honeypot tags, feeding a SafetyReport into feature penalties.【F:src/core/safety.py†L10-L45】【F:src/core/pipeline.py†L300-L371】 | Missing static analysis depth (upgradeable proxies, pausable roles), third-party audit ingestion, rug heuristics, and integration with external scanners. |

### Narrative Intelligence
| Spec Expectation | Repository Implementation | Gap |
| --- | --- | --- |
| GPT-powered Narrative Volatility Index, meme momentum, archetypal clustering, and lore-ready summaries. | NarrativeAnalyzer counts positive/negative keywords to derive sentiment, momentum, and top tokens, enabling deterministic tests but not generative insights.【F:src/core/narrative.py†L11-L71】 | Needs LLM-powered embeddings, meme tracking, narrative clustering, and lore generation pipeline. |

### Outputs & Workflow
| Spec Expectation | Repository Implementation | Gap |
| --- | --- | --- |
| Deliver ranked dashboard, charts, alerts, and Obsidian/PDF “Collapse Artifacts,” with human-in-the-loop review cadence. | The Tree-of-Thought pipeline culminates in a markdown Collapse Artifact rendered by `render_markdown_artifact`, and the CLI can print or persist these files.【F:src/core/pipeline.py†L205-L228】【F:src/services/exporter.py†L195-L299】【F:src/cli/run_scanner.py†L92-L154】 | No web dashboard, charts, alert integrations, PDF exporter, or review workflows (watchlists, approvals). |
| Continuous feedback loop (precision@K, backtests, weight tuning) with scheduled runs. | There is no scheduling, telemetry, or evaluation harness in the repository; the README’s checklist marking these tasks complete is aspirational.【F:README.md†L84-L135】 | Requires job scheduler, logging, analytics, and training scripts. |

## Additional Observations
- The README asserts completion of news/social ingestion, SQLite persistence, meme momentum, and visualization deliverables that are not reflected in the Python implementation, risking stakeholder misalignment.【F:README.md†L84-L109】【F:main.py†L16-L125】
- The Tree-of-Thought structure provides a solid foundation for explainable reasoning and could be extended to branch into narrative or safety subtrees once new data sources arrive.【F:src/core/pipeline.py†L117-L228】
- Artifact rendering is markdown-only; extending `render_markdown_artifact` to HTML/PDF would better serve the “Lore Capsule” requirement.【F:src/services/exporter.py†L195-L299】

## Recommended Next Steps
1. **Implement missing ingestion channels** (news, social, GitHub, tokenomics) with persistence to SQLite + vector storage, aligning code with the documented data infusion layer.【F:src/core/clients.py†L34-L105】【F:README.md†L84-L135】
2. **Upgrade narrative and meme analytics** by integrating embedding models or LLM services that deliver the promised Narrative Volatility Index and lore-ready summaries.【F:src/core/narrative.py†L11-L71】
3. **Expand safety analysis** to include advanced contract heuristics, liquidity depth checks across venues, and third-party audit feeds before exposing scores to users.【F:src/core/safety.py†L10-L45】
4. **Ship user-facing outputs**—web dashboard, alerting channels, and PDF exporters—to transform markdown artifacts into operational tooling consistent with the roadmap.【F:src/services/exporter.py†L195-L299】【F:README.md†L103-L115】
5. **Establish evaluation loops and scheduling** so GemScore precision, confidence calibration, and weight tuning can evolve through real-world feedback.【F:src/core/scoring.py†L10-L67】【F:README.md†L96-L135】
