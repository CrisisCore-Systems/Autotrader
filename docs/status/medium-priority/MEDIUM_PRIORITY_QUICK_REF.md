# Medium-Priority Enhancements - Quick Reference

## 🔍 Enhanced Provenance Tracking

```python
from src.core.provenance import capture_lineage_metadata, get_provenance_tracker

# Capture full lineage
lineage = capture_lineage_metadata(
    feature_hash="sha256:abc123",
    model_route="groq:llama3.1-8b",
    data_snapshot_hash="sha256:def456"
)

# Register with lineage
tracker = get_provenance_tracker()
artifact_id = tracker.register_artifact(
    artifact_type=ArtifactType.GEM_SCORE,
    name="GemScore[Token]",
    data=data,
    lineage_metadata=lineage  # ← Full git commit, feature hash, model route
)
```

**What's Captured:**
- ✅ Git commit hash (automatic)
- ✅ Feature code hash
- ✅ Model version/route
- ✅ Pipeline version
- ✅ Python & package versions
- ✅ Data snapshot hash

---

## 📊 Normalized Alert Thresholds

**File:** `config/alert_thresholds.yaml`

```yaml
holder_change_thresholds:
  significant_increase:
    threshold: 10.0
    unit: percentage_points  # ← Explicit
    data_type: float
    operator: gte
    annotation: "Absolute change, not relative"
```

**Units Available:**
- `percentage` - 0-100 scale (15.5 = 15.5%)
- `ratio` - 0-1 scale (0.155 = 15.5%)
- `percentage_points` - Absolute change (+5pp)
- `basis_points` - 150bp = 1.5%
- `usd`, `count`, `boolean`, `score`, `seconds`

---

## 🔒 Expanded Security Rules

**File:** `ci/semgrep.yml`

**Coverage:** 45+ rules including:
- ✅ Subprocess injection
- ✅ Insecure deserialization (pickle, marshal)
- ✅ Request timeouts
- ✅ Broad exception swallowing
- ✅ SQL injection
- ✅ Path traversal
- ✅ Weak cryptography
- ✅ Session security
- ✅ File permissions

**Run locally:**
```bash
semgrep --config ci/semgrep.yml src/
```

---

## ✅ Quality Gates

**File:** `.github/workflows/tests-and-coverage.yml`

**Enforced:**
```yaml
- Coverage: ≥80% (fails if below)
- Ruff: No errors allowed
- MyPy: --strict mode
- Pylint: ≥8.0/10
- NO continue-on-error flags
```

**Result:** Pipeline fails on any quality violation

---

## 📸 Snapshot Mode (Reproducibility)

```python
from src.core.snapshot_mode import (
    enable_record_mode,
    enable_snapshot_mode,
    get_snapshot_registry
)

# Phase 1: Record snapshots
enable_record_mode()
data = fetch_data()  # Auto-saved with SHA-256 hash

# Phase 2: Reproduce exactly
enable_snapshot_mode()
data = fetch_data()  # Loads from snapshot, fails if missing

# Verify integrity
registry = get_snapshot_registry()
results = registry.verify_all()
```

**Modes:**
- `DYNAMIC` - Normal operation
- `RECORD` - Fetch & save snapshots
- `SNAPSHOT` - Immutable, pinned data only

---

## 📓 Notebook CI Validation

**File:** `.github/workflows/notebook-validation.yml`

**Validates:**
- ✅ Format (JSON structure)
- ✅ Execution (10min timeout)
- ✅ Error detection in outputs
- ✅ Deterministic behavior (PYTHONHASHSEED=42)
- ✅ Size limits (max 1MB)
- ✅ Drift detection (weekly)
- ✅ Code quality (ruff, black, isort)

**Run locally:**
```bash
jupyter nbconvert --execute notebooks/hidden_gem_scanner.ipynb
```

---

## 📋 Schema Registry

```python
from src.core.schema_registry import get_schema_registry

# Validate output
registry = get_schema_registry()
is_valid, errors = registry.validate_data(
    schema_id="gem_score_result",
    data=output_data,
    version="1.0.0"  # Optional, defaults to latest
)

if not is_valid:
    print("Errors:", errors)
```

**Schemas Defined:**
- `gem_score_result` v1.0.0
- `market_snapshot` v1.0.0
- `notebook_scan_output` v1.0.0

**Location:** `schemas/*.json`

---

## 🚀 Quick Start

### 1. Enable Full Provenance
```python
from src.core.provenance import capture_lineage_metadata

lineage = capture_lineage_metadata(
    feature_hash="sha256:...",
    model_route="groq:model-name"
)
# Use in artifact registration
```

### 2. Load Alert Thresholds
```python
import yaml
with open("config/alert_thresholds.yaml") as f:
    config = yaml.safe_load(f)

threshold = config["gem_score_thresholds"]["high_potential"]
print(f"{threshold['threshold']} {threshold['unit']}")
```

### 3. Enable Snapshot Mode
```python
from src.core.snapshot_mode import enable_snapshot_mode
enable_snapshot_mode()
# All data fetches now use snapshots
```

### 4. Validate Outputs
```python
from src.core.schema_registry import get_schema_registry

registry = get_schema_registry()
is_valid, errors = registry.validate_data(
    schema_id="gem_score_result",
    data=my_output
)
```

---

## 📁 Files Created

**Core Modules:**
- `src/core/provenance.py` (enhanced)
- `src/core/snapshot_mode.py` (new)
- `src/core/schema_registry.py` (new)

**Configuration:**
- `config/alert_thresholds.yaml` (new)

**CI/CD:**
- `.github/workflows/tests-and-coverage.yml` (enhanced)
- `.github/workflows/notebook-validation.yml` (new)

**Security:**
- `ci/semgrep.yml` (expanded 2→45+ rules)

**Schemas:**
- `schemas/gem_score_result_v1_0_0.json`
- `schemas/market_snapshot_v1_0_0.json`
- `schemas/notebook_scan_output_v1_0_0.json`

**Documentation:**
- `MEDIUM_PRIORITY_RESOLUTION.md`
- `MEDIUM_PRIORITY_QUICK_REF.md` (this file)

---

## ✅ Checklist

Before committing changes:

- [ ] Run tests: `pytest --cov=src --cov-fail-under=80`
- [ ] Lint check: `ruff check src/`
- [ ] Type check: `mypy src/ --strict`
- [ ] Security scan: `semgrep --config ci/semgrep.yml src/`
- [ ] Validate schemas: Test schema validation
- [ ] Test snapshot mode: Enable and verify
- [ ] Check notebooks: Format and execution
- [ ] Review thresholds: Load and verify units

---

## 🔗 References

- Full docs: [MEDIUM_PRIORITY_RESOLUTION.md](./MEDIUM_PRIORITY_RESOLUTION.md)
- Provenance: [PROVENANCE_GLOSSARY_GUIDE.md](../../provenance/PROVENANCE_GLOSSARY_GUIDE.md)
- CI workflows: `.github/workflows/`
- Schemas: `schemas/`

---

**Updated:** October 9, 2025  
**Status:** ✅ All medium-priority issues resolved
