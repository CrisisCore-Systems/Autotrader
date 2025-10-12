# Documentation Portal

Welcome! This page consolidates the most useful documentation for the VoidBloom / CrisisCore Hidden Gem Scanner so you can jump straight to the guide you need. The sections are grouped by workflow and discipline. Each link points to an existing, maintained document inside this repository (or an external canonical reference when needed).

> **Tip:** The system is production-ready with a fully functional "FREE" tier. Start with the **Start Here** section if this is your first visit in a while.

---

## Start Here

- [System Snapshot](overview/PROJECT_OVERVIEW.md) – high-level context and current status.
- [Release & Feature Progress](FEATURE_STATUS.md) – single page view of completed and planned work.
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md) – condensed overview of technical accomplishments.
- [System Status Report (external)](https://github.com/CrisisCore-Systems/Autotrader/blob/main/STATUS_REPORT.md) – comprehensive production readiness report.

## Setup & Operations

- [Setup Guide](install/SETUP_GUIDE.md) – environment preparation, dependency installation, and first run checklist.
- [Quickstart: New Signals](QUICKSTART_NEW_SIGNALS.md) – add a new token to the scanner in minutes.
- [CLI Backtest Guide](CLI_BACKTEST_GUIDE.md) – run the backtest harness end-to-end.
- [Deployment Guide](deployment/DEPLOYMENT_GUIDE.md) – promote the stack into production safely.
- [Production Deployment Runbook](deployment/PRODUCTION_DEPLOYMENT.md) – day-of rollout checklist.

## Reliability, Observability & Metrics

- [Reliability Implementation](RELIABILITY_IMPLEMENTATION.md) – circuit breakers, caching, and reliability patterns.
- [Observability Guide](OBSERVABILITY_GUIDE.md) – metrics, tracing, and logging strategy.
- [Extended Backtest Metrics](EXTENDED_BACKTEST_METRICS.md) – advanced performance instrumentation.
- [Extended Metrics Quick Reference](EXTENDED_METRICS_QUICK_REF.md) – field-by-field reference for metrics consumers.
- [Drift Monitoring Guide](DRIFT_MONITORING_GUIDE.md) – detect and respond to model or data drift.

## Alerting & Incident Response

- [Alerting V2 Guide](ALERTING_V2_GUIDE.md) – modernized alerting pipeline and configuration.
- [Alerting Drift Setup](alerting/ALERTING_DRIFT_SETUP.md) – implement signal drift alerting step-by-step.
- [Alerting Drift Quick Reference](alerting/ALERTING_DRIFT_QUICK_REF.md) – operational cheat sheet.
- [Alerting Drift Implementation Report](alerting/ALERTING_DRIFT_COMPLETE.md) – technical deep dive.

## AI, LLM & Narrative Intelligence

- [LLM Validation Guide](LLM_VALIDATION_GUIDE.md) – ensure model outputs stay aligned.
- [LLM Validation Quick Reference](LLM_VALIDATION_QUICK_REF.md) – day-to-day validation checklist.
- [Groq Enhancements](llm/GROQ_ENHANCEMENTS.md) – performance improvements for Groq-hosted models.
- [LLM Validation Completion Notes](LLM_VALIDATION_IMPLEMENTATION_COMPLETE.md) – implementation record and verification notes.

## Feature Engineering & Scoring

- [GemScore Delta Explainability](GEMSCORE_DELTA_EXPLAINABILITY.md) – interpret feature contributions to GemScore.
- [GemScore Delta Quick Reference](GEMSCORE_DELTA_QUICK_REF.md) – fast lookup for key GemScore parameters.
- [Feature Validation Guide](FEATURE_VALIDATION_GUIDE.md) – validate new feature pipelines.
- [Feature Validation Quick Reference](FEATURE_VALIDATION_QUICK_REF.md) – operational checklist for feature rollouts.
- [Feature Validation Completion Log](features/FEATURE_VALIDATION_COMPLETE.md) – proof of completion for feature validation milestones.

## Governance, Roadmap & Process

- [Roadmap Completion Summary](ROADMAP_COMPLETION_SUMMARY.md) – milestone tracking at a glance.
- [Alerting & Backtesting Roadmap](roadmap_alerting_backtesting.md) – detailed alerting/backtesting plan.
- [Technical Debt Final Summary](improvements/TECH_DEBT_FINAL_SUMMARY.md) – close-out report for the tech-debt program.
- [Process Simplification Log](improvements/SIMPLIFICATION_COMPLETE.md) – completed streamlining initiatives.
- [Spec Alignment Review](spec_alignment_review.md) – ensure system behavior stays aligned with design intent.

## Reference

- [Provider Rate Limits](provider_rate_limits.md) – API rate restrictions across data providers.
- [Signal Coverage Audit](signal_coverage_audit.md) – audit of token coverage and data quality.
- [Confidence Representation Standard](CONFIDENCE_REPRESENTATION_STANDARD.md) – canonical rules for confidence scoring.
- [Unified Logging Guide](UNIFIED_LOGGING_GUIDE.md) – logging structure and schema.
- [Orderflow Twitter Implementation](ORDERFLOW_TWITTER_IMPLEMENTATION.md) – architecture and lessons from Twitter ingestion.

---

## How to Use This Portal

1. **Bookmark this page** – it is now linked from the home page and MkDocs navigation.
2. **Use the sections as swim lanes** – pick the category that matches your task.
3. **Update this portal when adding new guides** – add a bullet under the appropriate section so future contributors benefit.

If you spot an outdated link or produce a new major doc, please update this page as part of the same change. This keeps the documentation surface clean and discoverable for the whole team.
