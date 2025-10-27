# Phase 1 — Environment & Infrastructure Blueprint

## 1. Mission Statement
- Stand up a reproducible developer environment and packaging workflow for modeling and execution services.
- Standardize experiment management and artifact versioning to support rapid iteration under auditability constraints.
- Deliver the foundational orchestration, messaging, and observability stack required for production hardening in later phases.

## 1.1 Phase 1 at a Glance
- **Repository & Packaging:** Python-centric codebase with Markdown documentation, Dockerized runtime, and `.env`-driven configuration hygiene.
- **Experiment Tracking:** MLflow as the default tracker with W&B adapters, ensuring datasets and models are versioned and reproducible.
- **Orchestration & Messaging:** Prefect-led pipeline skeletons backed by Redis and Kafka for coordination and event flow.
- **Monitoring & Logging:** Prometheus + Grafana dashboards, structured logging, and automated alerting to Slack and email.
- **Primary Deliverables:** Dockerized developer environment, experiment tracker, orchestration skeleton, and observability stack configured and documented.

## 2. Repository & Packaging Strategy
- **Language Footprint:** Python 3.11+ for modeling, execution engines, and task orchestration. Supporting assets captured as Markdown documentation under `docs/`.
- **Project Layout:**
  - `autotrader/` — core services, execution adapters, utilities.
  - `backtest/` — simulation and research toolchain.
  - `dashboard/` — UI bundle (kept in sync with Docker runtime).
  - `docs/specs/phase1/` — phase deliverables, runbooks, and architecture diagrams.
- **Packaging:**
  - Adopt [`pyproject.toml`](pyproject.toml) with Poetry-style dependency grouping (`[tool.poetry.group.dev]`, `[tool.poetry.group.docs]`).
  - Enforce semantic versioning (`0.1.0` at Phase 1 GA) with automated bump via CI workflow.
  - Publish internal wheel artifacts to the private package index (Artifactory/ECR) on tagged releases.
- **Environment Files:**
  - `.env` templates committed as `.env.example` and `.env.development`. Secrets loaded at runtime using `python-dotenv` in local mode and AWS/GCP secret managers in deployed stacks.
  - CI validates that no `.env` with secrets is committed via pre-commit hooks.
- **Containerization:**
  - Base image: `python:3.11-slim` hardened with `pip --no-cache`, `non-root` user (`autotrader`).
  - Multi-stage Dockerfile: builder stage for dependencies (Poetry/UV pip), runtime stage with only required wheels and entrypoints.
  - Compose stack providing services: `app`, `scheduler`, `mlflow`, `postgres`, `redis`, `kafka`, `prometheus`, `grafana`.
  - Devcontainers support via `.devcontainer/devcontainer.json` that reuses the compose file.

## 3. Environment Bootstrapping
- **Local Dev Workflow:**
  1. Copy `.env.example` → `.env.development` and populate local secrets (API keys, DB URIs).
  2. `make bootstrap` runs `poetry install --with dev,docs`, seeds pre-commit hooks, and initializes git LFS for large artifacts.
  3. `docker compose up app scheduler mlflow redis kafka` to launch core services.
- **Continuous Integration:**
  - GitHub Actions pipeline with separate jobs for lint/type-check (`ruff`, `mypy`), unit tests (`pytest`), integration tests (docker-compose with mock venues), and container build/push.
  - Security scanning: `trivy` on images and dependency auditing via `pip-audit`.
- **Runtime Targets:**
  - Dev/Staging: single-node Kubernetes namespace (k3d/kind for local, EKS/GKE for cloud) orchestrating Prefect agents and MLflow tracking server.
  - Production: autoscaling node pool with dedicated namespaces per environment, secrets via cloud secret manager, ingress handled by NGINX controller with mTLS.

## 4. Experiment Tracking & Artifact Management
- **Primary Tracker:** MLflow (self-hosted) with `postgres` backend and S3-compatible artifact store (MinIO in dev, S3 in cloud).
- **Alternative Integration:** Provide adapters for Weights & Biases (WANDB) behind feature flag to support research teams already using it.
- **Experiment Taxonomy:**
  - Run naming convention: `<strategy>-<horizon>-<date>-<run-id>`.
  - Tagging: `phase`, `data_version`, `model_hash`, `latency_budget`.
  - Model registry enabling promotion from `Staging` → `Production` with automated validation steps.
- **Configuration Artifacts:**
  - Tracking profiles codified in `configs/mlflow/tracking.yaml`.
  - Registry utilities under `mlops/model_registry/` providing CLI for promotion.
  - Prefect flow `orchestration/flows/experiment_pipeline.py` orchestrates DVC → training → registry pipeline.
- **Dataset Versioning:**
  - Source data tracked with DVC (`dvc.yaml`, `.dvcignore`) and Git LFS patterns under `.gitattributes` for large artifacts.
  - Remote storage on S3 bucket `autotrader-data-dev` with encryption at rest.
  - Metadata snapshots stored in MLflow runs and accessible through Prefect deployments.
- **Reproducibility:** containerized backtest runners capture `git SHA`, `pyproject.lock`, `.env` hash, and dataset version in every run artifact.

## 5. Orchestration & Messaging Architecture
- **Workflow Orchestrator:** Prefect 2.x chosen for Phase 1 due to lightweight agents and Python-native DSL.
  - Deployments: `ingest`, `feature-build`, `model-train`, `paper-trade` flows.
  - Schedules defined per flow (cron / interval) with concurrency limits per instrument class.
  - Work queues mapped to environment (`dev`, `staging`, `prod`) enabling progressive rollout.
- **Dagster Evaluation:** Proof-of-concept branch maintained to validate asset graph capabilities; decision checkpoint at Phase 2.
- **Messaging Layer:**
  - **Redis**: low-latency task queue, caching, and rate-limit state.
  - **Kafka**: high-throughput market data ingestion, event sourcing for executions, backpressure handling.
  - Topics standardized as `md.<asset_class>.<instrument>`, `orders.execution`, `risk.alerts`.
  - Schema registry (Confluent/Redpanda) ensures Avro/JSON schema validation.
- **Infrastructure as Code:** Terraform module library for VPC, ECS/EKS, Kafka clusters, Prometheus stack; Terragrunt for environment layering.

## 6. Observability & Alerting Stack
- **Metrics:**
  - Prometheus scrapes application exporters (FastAPI/uvicorn, Prefect agents, MLflow) and system metrics.
  - Custom exporters for queue depth, latency histograms, order fill success, cost metrics.
- **Visualization:** Grafana dashboards packaged as JSON in `infrastructure/grafana/dashboards/` and provisioned via ConfigMaps.
- **Logging:**
  - Structured logs (JSON) using `structlog` + `uvicorn` built-in formatters.
  - Log shipping through OpenTelemetry collector → Loki/CloudWatch.
  - Correlation IDs propagate via Prefect context and Kafka headers.
- **Alerting:**
  - Grafana Alertmanager routes SEV-1/2 alerts to Slack `#trading-ops` and email DL `ops@autotrader`.
  - On-call rotation maintained in PagerDuty; integration via webhook from Alertmanager.
  - Synthetic probes validate key APIs every 60 seconds using `blackbox_exporter`.

## 7. Security & Compliance Considerations
- Base images scanned (Grype/Trivy) weekly; high CVEs block release.
- Secrets sourced from `.env` only in local; staging/prod use AWS Secrets Manager with IAM roles and short-lived tokens.
- Strict network policies (Kubernetes) isolating Kafka/Redis to internal namespaces; TLS enforced via service mesh (Linkerd/Istio).
- Audit logging captured for orchestration actions, MLflow model promotions, and Prefect deployments.

## 8. Deliverables & Timeline
| Week | Deliverable | Acceptance Criteria |
| --- | --- | --- |
| 1 | Dockerized dev environment | `docker compose up` yields running app, scheduler, dependencies; devcontainer attaches successfully. |
| 2 | Experiment tracking stack | MLflow server operational with S3/MinIO backing store; sample experiment logged and visible. |
| 3 | Orchestration skeleton | Prefect flows deployed, Redis/Kafka infrastructure provisioned, sample ETL job scheduled. |
| 4 | Observability stack | Prometheus + Grafana dashboards active; alerting wired to Slack/email with test fire drill. |

All deliverables documented in runbooks under `docs/specs/phase1/` with IaC modules stored in `infrastructure/` and CI pipelines referencing the Docker images built in this phase.

---
**Exit Criteria:** Phase 1 is complete when all deliverables meet acceptance criteria, security scans pass, and operations runbooks are signed off by DevOps and Quant Engineering leads.
