# Security & Configuration Architecture - Visual Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUTOTRADER SECURITY LAYERS                       │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                            LAYER 1: CI/CD SECURITY                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│  │  Semgrep   │  │   Bandit   │  │   Trivy    │  │  Gitleaks  │       │
│  │  (60+ rules)│  │  (Python)  │  │(Container) │  │ (Secrets)  │       │
│  └────┬───────┘  └────┬───────┘  └────┬───────┘  └────┬───────┘       │
│       │               │               │               │                 │
│       └───────────────┴───────────────┴───────────────┘                 │
│                            │                                             │
│                            ▼                                             │
│                  ┌──────────────────┐                                   │
│                  │  GitHub Security  │                                   │
│                  │   SARIF Reports   │                                   │
│                  └──────────────────┘                                   │
│                                                                          │
│  Additional Scanners:                                                   │
│  • TruffleHog (verified secrets)                                        │
│  • pip-audit (dependencies)                                             │
│  • SBOM + Grype (software bill of materials)                            │
│  • License compliance                                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      LAYER 2: CONFIGURATION GOVERNANCE                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Alert Rules (configs/alert_rules.yaml)                          │   │
│  │  ├─ JSON Schema validation                                      │   │
│  │  ├─ Unique ID enforcement                                        │   │
│  │  ├─ Channel reference validation                                │   │
│  │  └─ Condition logic verification                                │   │
│  │                                                                  │   │
│  │  Validator: scripts/validate_alert_rules.py ✅                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ Prompt Contracts (schemas/prompt_outputs/*.json)                │   │
│  │  ├─ Schema version tracking                                     │   │
│  │  ├─ additionalProperties: false                                 │   │
│  │  ├─ Golden test fixtures                                        │   │
│  │  └─ Regression testing                                          │   │
│  │                                                                  │   │
│  │  Validator: scripts/validate_prompt_contracts.py ✅             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ LLM Configuration (configs/llm_enhanced.yaml)                   │   │
│  │  ├─ Cost tracking per provider                                  │   │
│  │  ├─ Fallback chains                                             │   │
│  │  ├─ Budget caps (daily/per-job)                                 │   │
│  │  ├─ Rate limiting                                               │   │
│  │  └─ PII redaction                                               │   │
│  │                                                                  │   │
│  │  Validator: YAML syntax check ✅                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                       LAYER 3: RUNTIME SECURITY                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────────────────────────────────────────┐             │
│  │ LLM Request Flow                                      │             │
│  │                                                       │             │
│  │  Request → Rate Limiter → Cost Check → Primary Model │             │
│  │                               ↓ (if fail)            │             │
│  │                           Fallback Chain              │             │
│  │                               ↓                       │             │
│  │                          Cache Check                  │             │
│  │                               ↓                       │             │
│  │                      Audit Log (PII redacted)         │             │
│  │                               ↓                       │             │
│  │                      Schema Validation                │             │
│  │                               ↓                       │             │
│  │                          Response                     │             │
│  └───────────────────────────────────────────────────────┘             │
│                                                                          │
│  Monitoring:                                                            │
│  • llm_cost_usd_total (Prometheus)                                      │
│  • llm_request_duration_seconds                                         │
│  • llm_cache_hit_rate                                                   │
│  • llm_fallback_triggered_total                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      LAYER 4: ARTIFACT GOVERNANCE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────────────────────────────────────────┐             │
│  │ Artifact Generation (scripts/generate_artifact.py)    │             │
│  │                                                       │             │
│  │  Input Data                                           │             │
│  │       ↓                                               │             │
│  │  Metadata Generation                                  │             │
│  │   ├─ Generation ID (UUID v4)                          │             │
│  │   ├─ Source commit SHA                                │             │
│  │   ├─ Feature set hash                                 │             │
│  │   ├─ Model info (if LLM)                              │             │
│  │   └─ Provenance trail                                 │             │
│  │       ↓                                               │             │
│  │  Jinja2 Template Rendering                            │             │
│  │   ├─ Autoescaping (XSS protection)                    │             │
│  │   ├─ CSP headers                                      │             │
│  │   └─ Whitelisted variables only                       │             │
│  │       ↓                                               │             │
│  │  Checksum Generation                                  │             │
│  │   ├─ artifact_sha256                                  │             │
│  │   └─ full_sha256 (with metadata)                      │             │
│  │       ↓                                               │             │
│  │  Artifact Storage                                     │             │
│  │   ├─ Embedded metadata (HTML/MD/JSON)                 │             │
│  │   └─ Sidecar .meta.json (other formats)              │             │
│  └───────────────────────────────────────────────────────┘             │
│                                                                          │
│  Schema: schemas/artifact_metadata.json ✅                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      LAYER 5: NOTEBOOK SAFETY                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────────────────────────────────────────────┐             │
│  │ Notebook Execution Flow (.github/workflows/           │             │
│  │                          notebook-execution.yml)      │             │
│  │                                                       │             │
│  │  Discover Notebooks                                   │             │
│  │       ↓                                               │             │
│  │  Environment Setup                                    │             │
│  │   ├─ Python 3.11                                      │             │
│  │   ├─ Dependencies from requirements.txt               │             │
│  │   └─ Papermill + nbconvert                            │             │
│  │       ↓                                               │             │
│  │  Capture Environment Snapshot                         │             │
│  │   ├─ Python version                                   │             │
│  │   ├─ Package versions                                 │             │
│  │   └─ Git commit SHA                                   │             │
│  │       ↓                                               │             │
│  │  Execute with Papermill                               │             │
│  │   ├─ Timeout: 30 minutes                              │             │
│  │   ├─ PYTHONHASHSEED=42 (reproducible)                 │             │
│  │   ├─ CI_MODE=true (mock APIs)                         │             │
│  │   └─ Export to build/docs/ (not ../docs)             │             │
│  │       ↓                                               │             │
│  │  Convert to HTML                                      │             │
│  │       ↓                                               │             │
│  │  Extract Metadata                                     │             │
│  │   ├─ Execution time                                   │             │
│  │   ├─ Cell count                                       │             │
│  │   └─ Error details (if any)                           │             │
│  │       ↓                                               │             │
│  │  Upload Artifacts (30 day retention)                  │             │
│  └───────────────────────────────────────────────────────┘             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      LAYER 6: PRE-COMMIT HOOKS                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Git Commit                                                             │
│       ↓                                                                  │
│  ┌────────────────────────────────────────────┐                        │
│  │ Pre-Commit Checks (automatic)              │                        │
│  │                                            │                        │
│  │  Security:                                 │                        │
│  │   • detect-private-key                     │                        │
│  │   • detect-secrets                         │                        │
│  │   • bandit                                 │                        │
│  │                                            │                        │
│  │  Configuration:                            │                        │
│  │   • validate-alert-rules ✨ NEW           │                        │
│  │   • validate-prompt-contracts ✨ NEW      │                        │
│  │   • validate-llm-config ✨ NEW            │                        │
│  │                                            │                        │
│  │  Quality:                                  │                        │
│  │   • black (formatting)                     │                        │
│  │   • ruff (linting)                         │                        │
│  │   • mypy (type checking)                   │                        │
│  │   • yamllint                               │                        │
│  │   • markdownlint                           │                        │
│  └────────────────────────────────────────────┘                        │
│       ↓                                                                  │
│  ✅ Pass → Commit                                                       │
│  ❌ Fail → Fix & Retry                                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    VALIDATION COMMAND REFERENCE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────┐              │
│  │ Quick Validation                                     │              │
│  │                                                      │              │
│  │  # All checks                                        │              │
│  │  $ python scripts/validate_all.py                   │              │
│  │                                                      │              │
│  │  # Specific category                                │              │
│  │  $ python scripts/validate_all.py --category config │              │
│  │                                                      │              │
│  │  # Strict mode (fail on warnings)                   │              │
│  │  $ python scripts/validate_all.py --strict          │              │
│  └──────────────────────────────────────────────────────┘              │
│                                                                          │
│  ┌──────────────────────────────────────────────────────┐              │
│  │ Individual Validators                                │              │
│  │                                                      │              │
│  │  # Alert rules                                       │              │
│  │  $ python scripts/validate_alert_rules.py \         │              │
│  │      --config configs/alert_rules.yaml               │              │
│  │                                                      │              │
│  │  # Prompt contracts                                  │              │
│  │  $ python scripts/validate_prompt_contracts.py      │              │
│  │                                                      │              │
│  │  # Security scan                                     │              │
│  │  $ semgrep --config ci/semgrep.yml src/             │              │
│  └──────────────────────────────────────────────────────┘              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         MONITORING DASHBOARD                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Prometheus Metrics (http://localhost:9090)                             │
│                                                                          │
│  Security:                                                              │
│   • security_scan_findings_total                                        │
│   • dependency_vulnerabilities_total                                    │
│                                                                          │
│  LLM Operations:                                                        │
│   • llm_cost_usd_total                                                  │
│   • llm_request_duration_seconds                                        │
│   • llm_request_errors_total                                            │
│   • llm_cache_hit_rate                                                  │
│   • llm_fallback_triggered_total                                        │
│                                                                          │
│  Artifacts:                                                             │
│   • artifact_generation_duration_seconds                                │
│   • artifact_storage_bytes_total                                        │
│                                                                          │
│  Notebooks:                                                             │
│   • notebook_execution_duration_seconds                                 │
│   • notebook_execution_errors_total                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                          FILE STRUCTURE                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  AutoTrader/Autotrader/                                                 │
│  ├── .github/workflows/                                                 │
│  │   ├── security-scan.yml          ✅ Comprehensive security           │
│  │   ├── notebook-execution.yml     ✨ NEW: Papermill CI               │
│  │   └── tests-and-coverage.yml     ✅ Quality gates                   │
│  │                                                                       │
│  ├── configs/                                                           │
│  │   ├── alert_rules.yaml           ✅ Validated in CI                 │
│  │   └── llm_enhanced.yaml          ✨ NEW: Cost controls              │
│  │                                                                       │
│  ├── schemas/                                                           │
│  │   ├── artifact_metadata.json     ✨ NEW: Provenance schema          │
│  │   └── prompt_outputs/            ✨ NEW: Prompt schemas             │
│  │       ├── narrative_analyzer.json                                   │
│  │       └── contract_safety.json                                      │
│  │                                                                       │
│  ├── scripts/                                                           │
│  │   ├── validate_alert_rules.py    ✅ Alert validator                 │
│  │   ├── validate_prompt_contracts.py ✨ NEW: Prompt validator         │
│  │   ├── generate_artifact.py       ✨ NEW: Secure generator           │
│  │   └── validate_all.py            ✨ NEW: Comprehensive validator    │
│  │                                                                       │
│  ├── tests/fixtures/prompt_outputs/ ✨ NEW: Golden tests                │
│  │   ├── narrative_analyzer_golden.json                                │
│  │   └── contract_safety_golden.json                                   │
│  │                                                                       │
│  ├── ci/                                                                │
│  │   └── semgrep.yml                ✅ 60+ custom rules                │
│  │                                                                       │
│  ├── .pre-commit-config.yaml        ✅ Enhanced with validators         │
│  │                                                                       │
│  └── DOCUMENTATION                                                      │
│      ├── SECURITY_POSTURE_COMPLETE.md      📖 Full guide               │
│      ├── SECURITY_IMPLEMENTATION_SUMMARY.md 📊 Executive summary       │
│      ├── SECURITY_IMPLEMENTATION_GUIDE.md  🛠️ Implementation guide     │
│      └── SECURITY_ARCHITECTURE.md          📐 This file                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

Legend:
  ✅ Already excellent (preserved)
  ✨ New implementation
  📖 Documentation
  🛠️ Tooling
  🔒 Security
  📊 Monitoring

Version: 2.0.0
Date: October 9, 2025
Status: ✅ Production Ready
```
