# Monitoring and Automation Roadmap

This document outlines the plan to close the primary operational gaps identified in the Autotrader stack. Each section captures the desired capabilities, suggested implementation steps, and open questions that require validation.

## 1. Alerting System

### Goal
Introduce proactive alerting so that anomalous behaviors are surfaced in near real-time rather than being discovered manually.

### Initial Scope
- Portfolio drawdown thresholds (e.g., >5% in 1 hour, >10% daily).
- Strategy-specific performance deviations measured against historical baselines.
- Infrastructure health (failed data ingests, stale model weights).

### Proposed Implementation
1. **Event Bus**: Extend the existing task pipeline to emit structured events after every inference cycle (success/failure, metrics snapshot).
2. **Rules Engine**: Add a light-weight rule processor (e.g., simple YAML/JSON rules interpreted by a Python module) that evaluates incoming events against thresholds.
3. **Notification Channels**:
   - Slack webhook integration for team-wide alerts.
   - Optional email integration through AWS SES.
   - PagerDuty escalation for critical incidents (future phase).
4. **Alert Suppression & Deduplication**: Maintain a short-term cache to suppress repeated alerts for the same condition within a configurable window.

### Open Questions
- What constitutes a "critical" alert versus informational updates?
- Which environments (prod, staging, paper trading) require alert coverage?
- Do we need alert acknowledgement tracking in the MVP?

## 2. Scheduling & Backtesting Automation

### Goal
Provide a unified orchestration layer that can run live strategies, periodic risk checks, and historical backtests without manual triggering.

### Proposed Implementation
1. **Scheduler**: Introduce an APScheduler-based service that supports cron-like triggers and ad-hoc executions. Persist job definitions in Postgres or a simple JSON registry.
2. **Job Templates**:
   - Live strategy execution: ensure consistent start/end times and health checks.
   - Daily PnL reconciliation and reporting.
   - Batch backtesting jobs that fan out across historical data slices.
3. **CLI Support**: Extend `main.py` to expose commands for scheduling (add/list/remove) and to enqueue backtests.
4. **Distributed Runs (Stretch Goal)**: Integrate with Prefect or Airflow if we outgrow a single-node scheduler.

### Backtesting Framework Enhancements
- Standardize on a `BacktestConfig` schema (YAML/JSON) that captures strategy parameters, date ranges, assets, and evaluation metrics.
- Store backtest results and metadata in `artifacts/` with automatic versioning for reproducibility.
- Implement a results dashboard (streamlit or existing dashboard app) that visualizes returns, drawdowns, and precision@K over time.

## 3. Feedback Loops & Precision@K Tracking

### Goal
Continuously measure and improve recommendation quality by tracking ranking metrics and using them to tune model weights.

### Proposed Implementation
1. **Metrics Logging**: Extend inference code to capture top-K predictions, executed trades, and realized outcomes.
2. **Precision@K Pipeline**: Nightly job aggregates the logged data, computes precision@K, recall, and other relevant metrics.
3. **Model Weight Optimization**: Use the metrics history to drive automated hyperparameter sweeps or weight adjustments (e.g., Bayesian optimization over strategy weightings).
4. **Dashboard Widgets**: Add charts displaying precision@K trends, comparison across strategies, and correlation with PnL.

### Open Questions
- Which K values matter most for current trading strategies?
- How do we capture ground-truth labels for recommendations that were not executed?
- What is the acceptable computation latency for nightly aggregation jobs?

## 4. Expanded Data Sources

### Goal
Incorporate additional signals—GitHub activity, social sentiment, and tokenomics—to enrich model inputs and downstream analytics.

### Proposed Data Integrations
1. **GitHub Activity**
   - Use the GitHub REST API to fetch repo commit frequencies, issue velocity, and release cadence for tracked projects.
   - Cache raw API responses and normalize metrics to align with existing factor pipelines.
2. **Social Sentiment**
   - Integrate with Twitter API v2 and Discord webhooks/bots for sentiment extraction.
   - Employ an NLP sentiment model or third-party service (e.g., LunarCRUSH) to obtain sentiment scores.
   - Rate-limit handling and retry logic required due to API constraints.
3. **Tokenomics APIs**
   - Target data providers such as CoinMetrics or TokenTerminal for circulating supply, staking ratios, and treasury analytics.
   - Map token identifiers across providers to prevent mismatches.

### Data Quality & Monitoring
- Implement freshness checks (expected update cadence per source).
- Validate schema changes when external APIs evolve.
- Add synthetic tests that compare new signals against baseline expectations (e.g., zero/negative values).

## Next Steps
1. Validate priorities with stakeholders and phase the roadmap (e.g., start with alerting + scheduling).
2. Create issues/tasks in the project tracker for each workstream.
3. Prototype minimal alerting and scheduler modules in a feature branch to test assumptions.
4. Iterate based on feedback from initial deployments.

