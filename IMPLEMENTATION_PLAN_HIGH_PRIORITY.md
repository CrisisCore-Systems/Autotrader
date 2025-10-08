# Implementation Plan - High Priority GitHub Issues
**Repository:** CrisisCore-Systems/Autotrader  
**Created:** October 8, 2025  
**Status:** 🎯 READY FOR IMPLEMENTATION

---

## 🎯 Executive Summary

This plan addresses 4 high-priority GitHub issues that will enhance the production readiness, security, and reliability of the AutoTrader system. All plans leverage our existing FREE tier implementation and 21/21 passing tests as a foundation.

**Estimated Timeline:** 3-4 weeks  
**Effort:** Medium-High  
**Dependencies:** Minimal - can work in parallel on most items

---

## 📋 High Priority Issues

### 1. Issue #29: Add Structured Logging and Observability
**Priority:** 🔴 HIGH  
**Effort:** Medium (2-3 days)  
**Impact:** Production readiness, debugging, SLA monitoring

#### Current State
- Basic Python logging exists
- No structured (JSON) logging
- No metrics exporters
- No distributed tracing
- Difficult to debug production issues

#### Implementation Plan

**Phase 1: Structured Logging (Day 1)**
```python
# Install dependencies
pip install structlog python-json-logger opentelemetry-api opentelemetry-sdk

# Create src/core/logging_config.py
import structlog
import logging
from pythonjsonlogger import jsonlogger

def setup_logging(service_name="autotrader", level="INFO"):
    """Configure structured JSON logging"""
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Setup JSON handler
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    
    return structlog.get_logger(service_name)
```

**Phase 2: Instrument Key Modules (Day 2)**

Update `src/core/pipeline.py`:
```python
import structlog

logger = structlog.get_logger(__name__)

class HiddenGemScanner:
    def scan(self, config: TokenConfig) -> ScanResult:
        logger.info(
            "scan_started",
            token_id=config.token_id,
            symbol=config.symbol,
            contract_address=config.contract_address
        )
        
        try:
            result = self._execute_scan(config)
            logger.info(
                "scan_completed",
                token_id=config.token_id,
                gem_score=result.gem_score,
                confidence=result.confidence,
                flagged=result.flagged,
                duration_ms=result.duration_ms
            )
            return result
        except Exception as e:
            logger.error(
                "scan_failed",
                token_id=config.token_id,
                error=str(e),
                exc_info=True
            )
            raise
```

**Phase 3: Prometheus Metrics (Day 3)**
```python
# Install prometheus_client
pip install prometheus-client

# Create src/core/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# Define metrics
SCAN_REQUESTS = Counter('scan_requests_total', 'Total scan requests', ['token_id'])
SCAN_DURATION = Histogram('scan_duration_seconds', 'Scan duration', ['token_id'])
SCAN_ERRORS = Counter('scan_errors_total', 'Total scan errors', ['token_id', 'error_type'])
GEM_SCORE_DIST = Histogram('gem_score_distribution', 'GemScore distribution', buckets=[0, 20, 40, 60, 80, 100])
DATA_SOURCE_LATENCY = Histogram('data_source_latency_seconds', 'Data source latency', ['source'])
CIRCUIT_BREAKER_STATE = Gauge('circuit_breaker_open', 'Circuit breaker state', ['source'])

def start_metrics_server(port=9090):
    """Start Prometheus metrics HTTP server"""
    start_http_server(port)
```

**Phase 4: OpenTelemetry Tracing (Day 3)**
```python
# Create src/core/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

def setup_tracing(service_name="autotrader"):
    provider = TracerProvider()
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
```

#### Files to Modify
- ✅ Create `src/core/logging_config.py`
- ✅ Create `src/core/metrics.py`
- ✅ Create `src/core/tracing.py`
- ⚠️ Update `src/core/pipeline.py`
- ⚠️ Update `src/core/clients.py`
- ⚠️ Update `src/core/free_clients.py`
- ⚠️ Update `src/api/dashboard_api.py`
- ✅ Create `configs/observability.yaml`
- ✅ Update `requirements.txt`

#### Testing
- Unit tests for logging configuration
- Integration tests for metrics collection
- Verify JSON log output format
- Test Prometheus metrics endpoint

#### Success Criteria
- ✅ All logs output in JSON format
- ✅ Prometheus metrics endpoint running on :9090
- ✅ Key operations instrumented (scan, data fetch)
- ✅ Errors and latencies tracked
- ✅ Tests passing

---

### 2. Issue #28: Implement Data Validation Guardrails in Feature Store
**Priority:** 🔴 HIGH  
**Effort:** Medium (2-3 days)  
**Impact:** Data quality, model reliability

#### Current State
- No validation on feature writes
- Risk of silent data poisoning
- No range checks or null policies
- No data quality monitoring

#### Implementation Plan

**Phase 1: Define Validation Schema (Day 1)**
```python
# Create src/core/feature_validation.py
from dataclasses import dataclass
from typing import Optional, Tuple, List
from enum import Enum

class ValidationType(Enum):
    RANGE = "range"
    NON_NULL = "non_null"
    ENUM = "enum"
    REGEX = "regex"
    CUSTOM = "custom"

@dataclass
class FeatureValidator:
    """Validation rules for a feature"""
    feature_name: str
    validation_type: ValidationType
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List] = None
    required: bool = False
    custom_validator: Optional[callable] = None
    
    def validate(self, value) -> Tuple[bool, Optional[str]]:
        """Validate a feature value"""
        if value is None:
            if self.required:
                return False, f"{self.feature_name} is required but got None"
            return True, None
        
        if self.validation_type == ValidationType.RANGE:
            if self.min_value is not None and value < self.min_value:
                return False, f"{self.feature_name}={value} below min {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"{self.feature_name}={value} above max {self.max_value}"
        
        elif self.validation_type == ValidationType.ENUM:
            if value not in self.allowed_values:
                return False, f"{self.feature_name}={value} not in {self.allowed_values}"
        
        elif self.validation_type == ValidationType.CUSTOM:
            if self.custom_validator:
                return self.custom_validator(value)
        
        return True, None

# Define validators for all features
FEATURE_VALIDATORS = {
    "gem_score": FeatureValidator(
        feature_name="gem_score",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        max_value=100.0,
        required=True
    ),
    "confidence": FeatureValidator(
        feature_name="confidence",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        max_value=1.0,
        required=True
    ),
    "liquidity_usd": FeatureValidator(
        feature_name="liquidity_usd",
        validation_type=ValidationType.RANGE,
        min_value=0.0,
        required=True
    ),
    "sentiment_score": FeatureValidator(
        feature_name="sentiment_score",
        validation_type=ValidationType.RANGE,
        min_value=-1.0,
        max_value=1.0,
        required=False
    ),
    "flagged": FeatureValidator(
        feature_name="flagged",
        validation_type=ValidationType.ENUM,
        allowed_values=[True, False],
        required=True
    ),
}
```

**Phase 2: Integrate into Feature Store (Day 2)**
```python
# Update src/services/feature_store.py
from src.core.feature_validation import FEATURE_VALIDATORS, ValidationType

class FeatureStore:
    def write_features(self, token_id: str, features: dict) -> None:
        """Write features with validation"""
        # Validate all features
        validation_errors = []
        for feature_name, value in features.items():
            if feature_name in FEATURE_VALIDATORS:
                validator = FEATURE_VALIDATORS[feature_name]
                is_valid, error_msg = validator.validate(value)
                if not is_valid:
                    validation_errors.append(error_msg)
        
        # Check required features
        for validator in FEATURE_VALIDATORS.values():
            if validator.required and validator.feature_name not in features:
                validation_errors.append(
                    f"Required feature {validator.feature_name} missing"
                )
        
        if validation_errors:
            logger.error(
                "feature_validation_failed",
                token_id=token_id,
                errors=validation_errors
            )
            raise FeatureValidationError(validation_errors)
        
        # Write features
        self._write_validated_features(token_id, features)
        logger.info(
            "features_written",
            token_id=token_id,
            feature_count=len(features)
        )
```

**Phase 3: Add Monitoring (Day 3)**
```python
# Add to src/core/metrics.py
FEATURE_VALIDATION_FAILURES = Counter(
    'feature_validation_failures_total',
    'Feature validation failures',
    ['feature_name', 'validation_type']
)

FEATURE_VALUE_DISTRIBUTION = Histogram(
    'feature_value_distribution',
    'Feature value distribution',
    ['feature_name'],
    buckets=[0, 10, 25, 50, 75, 90, 100]
)
```

#### Files to Modify
- ✅ Create `src/core/feature_validation.py`
- ⚠️ Update `src/services/feature_store.py`
- ⚠️ Update `src/core/metrics.py`
- ⚠️ Update `src/core/pipeline.py` (add validation calls)
- ✅ Create `tests/test_feature_validation.py`
- ✅ Update `requirements.txt`

#### Testing
- Unit tests for each validator
- Integration tests for feature store writes
- Test validation error handling
- Test with invalid data
- Test performance impact

#### Success Criteria
- ✅ All feature writes validated
- ✅ Invalid data rejected with clear errors
- ✅ Validation metrics tracked
- ✅ No performance degradation
- ✅ Tests passing

---

### 3. Issue #26: Harden Security (CI Scanning, Dependencies, Docker)
**Priority:** 🔴 HIGH  
**Effort:** Medium (3-4 days)  
**Impact:** Security posture, compliance

#### Current State
- ✅ Environment variables used (not hardcoded)
- ✅ GitHub push protection enabled
- ⚠️ No CI secret scanning
- ⚠️ No dependency scanning
- ⚠️ Docker images not hardened

#### Implementation Plan

**Phase 1: CI Secret Scanning (Day 1)**
```yaml
# Create .github/workflows/security-scan.yml
name: Security Scanning

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC

jobs:
  secret-scan:
    name: Secret Scanning
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for trufflehog
      
      - name: TruffleHog Secret Scan
        uses: trufflesecurity/trufflehog@main
        with:
          path: ./
          base: main
          head: HEAD
          extra_args: --debug --only-verified
      
      - name: GitLeaks Secret Scan
        uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

  dependency-scan:
    name: Dependency Scanning
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pip-audit safety
      
      - name: pip-audit scan
        run: pip-audit -r requirements.txt
      
      - name: Safety scan
        run: safety check -r requirements.txt --json
      
      - name: Trivy vulnerability scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          format: 'sarif'
          output: 'trivy-results.sarif'
      
      - name: Upload Trivy results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: 'trivy-results.sarif'

  semgrep-scan:
    name: Semgrep Security Scan
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Run Semgrep
        uses: returntocorp/semgrep-action@v1
        with:
          config: >-
            p/security-audit
            p/secrets
            p/owasp-top-ten
            p/python
```

**Phase 2: Harden Docker Images (Day 2-3)**
```dockerfile
# Update infra/Dockerfile (create multi-stage build)
# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Create non-root user
RUN useradd -m -u 1000 autotrader && \
    mkdir -p /app && \
    chown -R autotrader:autotrader /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder --chown=autotrader:autotrader /root/.local /home/autotrader/.local

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=autotrader:autotrader . .

# Switch to non-root user
USER autotrader

# Set PATH to include user packages
ENV PATH=/home/autotrader/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Run application
CMD ["python", "simple_api.py"]
```

**Phase 3: SBOM and Supply Chain (Day 4)**
```yaml
# Add to .github/workflows/security-scan.yml
  sbom-generation:
    name: Generate SBOM
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Generate SBOM with Syft
        uses: anchore/sbom-action@v0
        with:
          format: spdx-json
          output-file: sbom.spdx.json
      
      - name: Upload SBOM
        uses: actions/upload-artifact@v3
        with:
          name: sbom
          path: sbom.spdx.json
      
      - name: Scan SBOM with Grype
        uses: anchore/scan-action@v3
        with:
          sbom: sbom.spdx.json
          fail-build: true
          severity-cutoff: high
```

**Phase 4: Dependabot Configuration**
```yaml
# Create .github/dependabot.yml
version: 2
updates:
  # Python dependencies
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "security"
    reviewers:
      - "CrisisCore-Systems"
    commit-message:
      prefix: "deps"
    
  # GitHub Actions
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
    labels:
      - "dependencies"
      - "ci"
```

#### Files to Create/Modify
- ✅ Create `.github/workflows/security-scan.yml`
- ✅ Create `.github/dependabot.yml`
- ⚠️ Update `infra/Dockerfile` (multi-stage, non-root)
- ⚠️ Update `infra/docker-compose.yml`
- ✅ Create `docs/SECURITY.md`
- ✅ Create `.gitleaks.toml`
- ✅ Update `Makefile` (add security targets)

#### Testing
- Test Docker build with new multi-stage setup
- Verify non-root user works
- Run security scans locally
- Test CI workflow
- Verify Dependabot PRs

#### Success Criteria
- ✅ CI runs secret scanning on every push
- ✅ Dependency scanning in CI
- ✅ Docker images use non-root user
- ✅ Multi-stage builds reduce image size
- ✅ Dependabot enabled for weekly updates
- ✅ SBOM generated and scanned
- ✅ All security scans passing

---

### 4. Issue #30: Enforce JSON Schema Validation for LLM Outputs
**Priority:** 🟡 MEDIUM-HIGH  
**Effort:** Low-Medium (1-2 days)  
**Impact:** LLM reliability, error handling

#### Current State
- LLM outputs parsed as text
- No schema validation
- Risk of malformed responses
- No golden fixtures for testing

#### Implementation Plan

**Phase 1: Define Pydantic Schemas (Day 1)**
```python
# Create src/core/llm_schemas.py
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from enum import Enum

class SentimentType(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"

class NarrativeAnalysis(BaseModel):
    """Schema for narrative analysis output"""
    sentiment: SentimentType
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    momentum: float = Field(ge=-1.0, le=1.0)
    key_themes: List[str] = Field(min_items=1, max_items=10)
    narrative_summary: str = Field(min_length=10, max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    
    @validator('key_themes')
    def validate_themes(cls, v):
        if not v:
            raise ValueError('key_themes cannot be empty')
        return [theme.strip() for theme in v if theme.strip()]

class ContractSafetyAnalysis(BaseModel):
    """Schema for contract safety output"""
    is_verified: bool
    risk_level: str = Field(regex="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    risk_factors: List[str]
    safety_score: float = Field(ge=0.0, le=100.0)
    recommendations: List[str]
    
    @validator('risk_factors', 'recommendations')
    def validate_lists(cls, v):
        if len(v) > 20:
            raise ValueError('Too many items in list')
        return v

class TechnicalPattern(BaseModel):
    """Schema for technical pattern output"""
    pattern_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    support_levels: List[float]
    resistance_levels: List[float]
    trend: str = Field(regex="^(UPTREND|DOWNTREND|SIDEWAYS)$")
```

**Phase 2: Integrate Validation (Day 1-2)**
```python
# Update src/core/narrative.py
from src.core.llm_schemas import NarrativeAnalysis
import json
from pydantic import ValidationError

class NarrativeAnalyzer:
    def analyze(self, text: str) -> NarrativeAnalysis:
        """Analyze with schema validation"""
        try:
            # Get LLM response
            raw_response = self._call_llm(text)
            
            # Parse JSON
            data = json.loads(raw_response)
            
            # Validate with Pydantic
            validated = NarrativeAnalysis(**data)
            
            logger.info(
                "narrative_analysis_validated",
                sentiment=validated.sentiment,
                confidence=validated.confidence
            )
            
            return validated
            
        except json.JSONDecodeError as e:
            logger.error("llm_invalid_json", error=str(e))
            # Fallback to heuristics
            return self._fallback_analysis(text)
            
        except ValidationError as e:
            logger.error("llm_schema_validation_failed", errors=e.errors())
            # Fallback to heuristics
            return self._fallback_analysis(text)
```

**Phase 3: Golden Fixtures (Day 2)**
```python
# Create tests/fixtures/llm_golden_outputs.py
GOLDEN_NARRATIVE_ANALYSIS = {
    "bullish_example": {
        "input": "Strong community growth, positive partnerships announced",
        "expected_output": {
            "sentiment": "bullish",
            "sentiment_score": 0.75,
            "momentum": 0.65,
            "key_themes": ["community", "partnerships", "growth"],
            "narrative_summary": "Positive momentum with community and partnership developments",
            "confidence": 0.8
        }
    },
    "bearish_example": {
        "input": "Major sell-off, negative news, regulatory concerns",
        "expected_output": {
            "sentiment": "bearish",
            "sentiment_score": -0.65,
            "momentum": -0.5,
            "key_themes": ["sell-off", "negative news", "regulatory"],
            "narrative_summary": "Negative sentiment due to regulatory and market concerns",
            "confidence": 0.75
        }
    }
}

# Create tests/test_llm_validation.py
import pytest
from src.core.llm_schemas import NarrativeAnalysis
from pydantic import ValidationError

def test_valid_narrative_analysis():
    data = {
        "sentiment": "bullish",
        "sentiment_score": 0.8,
        "momentum": 0.6,
        "key_themes": ["growth", "adoption"],
        "narrative_summary": "Strong positive momentum",
        "confidence": 0.75
    }
    result = NarrativeAnalysis(**data)
    assert result.sentiment == "bullish"

def test_invalid_sentiment_score():
    data = {
        "sentiment": "bullish",
        "sentiment_score": 1.5,  # Invalid: > 1.0
        "momentum": 0.6,
        "key_themes": ["growth"],
        "narrative_summary": "Test",
        "confidence": 0.75
    }
    with pytest.raises(ValidationError):
        NarrativeAnalysis(**data)
```

#### Files to Create/Modify
- ✅ Create `src/core/llm_schemas.py`
- ⚠️ Update `src/core/narrative.py`
- ⚠️ Update `src/core/safety.py` (contract analysis)
- ✅ Create `tests/fixtures/llm_golden_outputs.py`
- ✅ Create `tests/test_llm_validation.py`
- ⚠️ Update `requirements.txt` (add pydantic if not present)

#### Testing
- Unit tests for each schema
- Test validation with golden fixtures
- Test error handling for invalid outputs
- Test fallback mechanisms
- Integration tests with real LLM calls

#### Success Criteria
- ✅ All LLM outputs validated with Pydantic
- ✅ Invalid outputs trigger fallback
- ✅ Golden fixtures for all prompt types
- ✅ Tests passing with 100% coverage
- ✅ Graceful degradation on validation failure

---

## 📊 Implementation Timeline

### Week 1
- **Days 1-3:** Issue #29 (Structured Logging & Observability)
- **Days 4-5:** Issue #28 (Feature Validation) - Start

### Week 2
- **Days 1-2:** Issue #28 (Feature Validation) - Complete
- **Days 3-5:** Issue #26 (Security Hardening) - Start

### Week 3
- **Days 1-2:** Issue #26 (Security Hardening) - Complete
- **Days 3-4:** Issue #30 (LLM Validation)
- **Day 5:** Testing & Integration

### Week 4
- **Days 1-2:** Final testing, bug fixes
- **Day 3:** Documentation updates
- **Day 4:** Code review, PR preparation
- **Day 5:** Deployment & monitoring

---

## 🎯 Success Metrics

### Technical Metrics
- ✅ All new tests passing (target: 100% new code covered)
- ✅ No new security vulnerabilities introduced
- ✅ CI pipeline green with new checks
- ✅ Docker image size reduced by 30%+
- ✅ Prometheus metrics endpoint responding

### Quality Metrics
- ✅ Code review approved
- ✅ Documentation updated
- ✅ Zero critical security findings
- ✅ Performance impact < 5%
- ✅ All validation rules enforced

### Operational Metrics
- ✅ Logs parseable by log aggregators
- ✅ Alerts configured for critical failures
- ✅ Dashboards created for monitoring
- ✅ Runbooks updated
- ✅ Incident response tested

---

## 🚀 Dependencies & Prerequisites

### Required Tools
```bash
# Install development dependencies
pip install structlog python-json-logger prometheus-client
pip install opentelemetry-api opentelemetry-sdk
pip install pydantic pytest pytest-cov
pip install pip-audit safety

# Install Docker (if not present)
# Install trufflehog, gitleaks (for local testing)
```

### Required Access
- GitHub repository write access
- GitHub Actions enabled
- Docker Hub access (for image publishing)
- Prometheus/Grafana instance (optional, for visualization)

---

## 📝 Notes & Considerations

### Backward Compatibility
- All changes are backward compatible
- Validation can be toggled with feature flags
- Logging changes don't affect functionality
- Docker changes don't affect local development

### Risk Mitigation
- Feature flags for gradual rollout
- Fallback mechanisms for validation failures
- Extensive testing before production
- Monitoring for performance impact

### Future Enhancements
- Grafana dashboards for metrics
- Alertmanager for Prometheus alerts
- ELK stack integration for log aggregation
- OpenTelemetry collector for tracing

---

## ✅ Acceptance Criteria

### Issue #29 (Logging & Observability)
- [ ] All logs in JSON format
- [ ] Prometheus endpoint on :9090
- [ ] Key operations instrumented
- [ ] OpenTelemetry tracing configured
- [ ] Tests passing

### Issue #28 (Feature Validation)
- [ ] All features validated on write
- [ ] Clear error messages for violations
- [ ] Validation metrics tracked
- [ ] Performance impact < 5%
- [ ] Tests passing

### Issue #26 (Security Hardening)
- [ ] Secret scanning in CI
- [ ] Dependency scanning daily
- [ ] Docker non-root user
- [ ] Multi-stage builds
- [ ] Dependabot enabled

### Issue #30 (LLM Validation)
- [ ] Pydantic schemas for all LLM outputs
- [ ] Validation errors trigger fallback
- [ ] Golden fixtures created
- [ ] 100% test coverage
- [ ] Graceful degradation

---

**Document Status:** ✅ READY FOR REVIEW  
**Next Action:** Review and approve plan, then begin implementation  
**Owner:** Development Team  
**Estimated Completion:** 3-4 weeks from start
