# Crypto Pump & Dump Detection System Implementation Plan

## Overview

This document captures the actionable roadmap for implementing the proposed crypto pump and dump detection platform. The plan is organized into three phased releases that build from a minimum viable product to a production-grade, low-latency service.

## Phase 1 – Foundation (Weeks 1-6)

### Objectives
- Establish real-time multi-source data ingestion via Apache Pulsar.
- Stand up the analytics data stores (ClickHouse, Neo4j, Redis Streams).
- Deliver baseline supervised and unsupervised detection models with supporting feature pipelines.

### Key Workstreams
1. **Data Collection Pipeline**
   - Integrate Helius gRPC streams for Solana tokens.
   - Implement a multi-exchange WebSocket collector (Binance and other tier-1 venues).
   - Build Twitter API v3 and Telegram MTProto sentiment scrapers with basic bot filtering.
2. **Feature Engineering**
   - Compute market microstructure indicators (momentum, volume anomalies, gas spikes).
   - Generate graph-oriented wallet features leveraging Nansen/Bubble Maps clustering.
   - Extract social amplification metrics, including coordinated hype signals.
3. **Initial Models and Evaluation**
   - Train an XGBoost classifier with SMOTE balancing targeting ≥93% recall.
   - Deploy an Isolation Forest for unsupervised anomaly detection.
   - Prototype an LSTM for temporal pump signatures.
   - Backtest against curated 2024–2025 pump events and document baseline metrics.

## Phase 2 – Advanced ML & Graph Intelligence (Weeks 7-12)

### Objectives
- Introduce heterogeneous graph learning to capture cross-domain relationships.
- Assemble an explainable ensemble that combines classical, temporal, and graph models.
- Launch an active learning loop to accelerate high-quality labeling.

### Key Workstreams
1. **Heterogeneous Graph Transformer (HGT)**
   - Model wallet, token, exchange, and social account nodes with multi-relation edges.
   - Train a three-layer HGT module using PyTorch Geometric on enriched graphs.
2. **Explainable Ensemble Architecture**
   - Stack XGBoost, LSTM, HGT, and Isolation Forest predictions with a LightGBM meta-learner.
   - Provide SHAP-driven explanations highlighting the top five drivers per alert.
3. **Active Learning Pipeline**
   - Implement uncertainty-based sampling with entropy heuristics.
   - Integrate with labeling workflows to prioritize ambiguous pump candidates.

## Phase 3 – Real-Time Production System (Weeks 13-16)

### Objectives
- Achieve <5 second end-to-end detection latency in production.
- Containerize and deploy the inference stack with horizontal scaling.
- Establish comprehensive monitoring, alerting, and automated retraining triggers.

### Key Workstreams
1. **Low-Latency Detection Pipeline**
   - Deploy Pulsar consumers that hydrate features from Redis Streams.
   - Serve ensemble inference through BentoML backed by Triton for GPU acceleration.
   - Trigger multi-channel alerts when pump probability exceeds confidence thresholds.
2. **Deployment & Observability**
   - Package inference services with Docker and Kubernetes manifests (GPU-enabled pods).
   - Configure autoscaling policies and latency budgets via Horizontal Pod Autoscalers.
   - Instrument Evidently AI, Grafana, and Prometheus dashboards for performance, drift, and business KPIs.
3. **Operational Excellence**
   - Monitor recall, precision, F1, AUC-PR, false-positive rate, latency percentiles, and drift metrics.
   - Automate retraining when recall drops below 90% or data drift exceeds tolerances.

## Repository Structure

The implementation will follow the proposed `crypto-pnd-detector/` layout, including modular collectors, feature pipelines, model training scripts, inference services, deployment assets, and tests. Prioritize wiring the skeleton directories in Sprint 1 to unblock parallel development.

## Immediate Next Steps

1. Scaffold the repository with the documented directory structure and placeholder modules.
2. Implement the Pulsar-based ingestion MVP with mock connectors to validate streaming.
3. Define ClickHouse and Neo4j schemas alongside Redis feature store conventions.
4. Stand up CI tooling (pre-commit, pytest skeleton, linting) to enforce quality from day one.

## Autotrader Integration Notes

- The implementation lives in the existing repository under `src/crypto_pnd_detector/` and follows the same packaging conventions that power the rest of the platform. The high-level entry points are `build_realtime_detector` for production-style orchestration and `build_dev_deployment` for deterministic local validation.
- Real-time orchestration is encapsulated by `RealtimePumpDetector`, allowing ingestion collectors from `src/crypto_pnd_detector/data/collectors` to be composed with the explainable ensemble without conflicting with current scanning pipelines.
- Feature storage and training helpers intentionally mirror patterns already used across Autotrader (e.g., in-memory stores for tests, dataclass-based artifacts) so that the module can be imported alongside the existing `HiddenGemScanner` flows.
- The test suite `tests/test_crypto_pnd_detector.py` exercises the streaming loop end-to-end, verifying compatibility with the repository’s pytest configuration and ensuring new dependencies remain pure-Python and local.
- The development harness `tests/test_dev_deployment.py` and `run_dev_deployment` entrypoint simulate a dev deployment by stitching static collectors, the in-memory feature store, and the ensemble detector together.

By executing this roadmap, the team can deliver a modern, explainable, and production-ready pump and dump detection platform over the planned 16-week horizon.
