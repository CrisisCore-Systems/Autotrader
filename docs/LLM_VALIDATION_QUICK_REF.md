# LLM Validation Quick Reference 🚀

## ✅ What's Enforced

Every LLM output is validated with **Pydantic schemas** - fail-fast + detailed logging.

## 📦 Available Schemas

```python
from src.core.llm_schemas import (
    NarrativeAnalysisResponse,      # Narrative/sentiment analysis
    ContractSafetyResponse,          # Contract security (future)
    TechnicalPatternResponse,        # Technical patterns (future)
    validate_llm_response,           # Graceful validation
    validate_llm_response_strict,    # Fail-fast validation
)
```

## 🔧 Usage

### Current Integration (NarrativeAnalyzer)

```python
from src.core.narrative import NarrativeAnalyzer

analyzer = NarrativeAnalyzer()
result = analyzer.analyze(["Market news..."])
# Automatically validated with fallback on failure
print(f"Sentiment: {result.sentiment_score}")
```

### New LLM Integrations

```python
from src.core.llm_schemas import validate_llm_response, NarrativeAnalysisResponse

raw_json = llm_client.complete(prompt)

validated = validate_llm_response(
    raw_json,
    NarrativeAnalysisResponse,
    context="my_feature"
)

if validated is None:
    return fallback()  # Validation failed

data = validated.model_dump()  # Convert to dict
```

## 📊 NarrativeAnalysisResponse Schema

```json
{
  "sentiment": "positive|neutral|negative",  // Required literal
  "sentiment_score": 0.75,                   // Required: 0.0-1.0
  "emergent_themes": ["DeFi", "L2"],         // Optional: max 10 items
  "memetic_hooks": ["#WAGMI"],               // Optional: max 10 items
  "fake_or_buzz_warning": false,             // Optional: default false
  "rationale": "Strong fundamentals..."      // Required: 10-2000 chars
}
```

**Validation Rules:**
- ✅ Extra fields **FORBIDDEN** (extra='forbid')
- ✅ Whitespace auto-stripped
- ✅ Empty strings in lists filtered
- ✅ Range validation (0.0-1.0)
- ✅ Required fields enforced

## 📝 Log Events

| Event | Level | When |
|-------|-------|------|
| `llm_validation_success` | INFO | Valid response |
| `llm_invalid_json` | ERROR | JSON parse failed |
| `llm_schema_validation_failed` | ERROR | Schema violation |
| `llm_validation_failed_using_fallback` | WARNING | Using fallback |

## 🧪 Testing

```bash
# Run validation tests
pytest tests/test_llm_validation.py -v

# Test specific schema
pytest tests/test_llm_validation.py::TestNarrativeAnalysisValidation -v

# With coverage
pytest tests/test_llm_validation.py --cov=src.core.llm_schemas
```

## 🔍 Debugging

### Check Validation Errors
```bash
grep "llm_schema_validation_failed" app.log | jq .extra.errors
```

### Analyze Error Patterns
```bash
grep "llm_schema_validation_failed" app.log | \
  jq -r '.extra.errors[].type' | \
  sort | uniq -c | sort -rn
```

### View Raw LLM Responses
```bash
grep "llm_invalid_json" app.log | jq .extra.raw_response_preview
```

## 🚨 Alerts (Recommended)

```yaml
# Alert on high validation failure rate
- name: llm_validation_failures
  condition: rate(llm_schema_validation_failed[5m]) > 0.1
  severity: warning

# Alert on JSON parse errors
- name: llm_json_errors
  condition: count(llm_invalid_json[1m]) > 5
  severity: critical

# Alert on excessive fallback
- name: llm_fallback_overuse
  condition: rate(llm_validation_failed_using_fallback[10m]) > 0.3
  severity: warning
```

## 📈 Key Metrics

| Metric | Target | Critical Threshold |
|--------|--------|-------------------|
| Validation Success Rate | > 95% | < 90% |
| JSON Parse Error Rate | < 1% | > 2% |
| Schema Violation Rate | < 5% | > 10% |
| Fallback Usage Rate | < 10% | > 20% |

## 🎯 Common Issues & Fixes

### High Validation Failure Rate
**Cause**: Schema mismatch or prompt issues  
**Fix**: Review prompt, check LLM model updates

### JSON Parse Errors
**Cause**: LLM returning non-JSON  
**Fix**: Update prompt: "Respond with ONLY valid JSON"

### Extra Fields Errors
**Cause**: LLM adding unexpected fields  
**Fix**: Update prompt with explicit schema

### Score Out of Range
**Cause**: LLM returning invalid values  
**Fix**: Add range examples to prompt

## 🔒 Security

- ✅ All inputs validated & sanitized
- ✅ Extra fields blocked (prevents injection)
- ✅ Length limits enforced (prevents DoS)
- ✅ Type safety guaranteed
- ✅ No code execution (pure data validation)

## 📚 Full Documentation

- **Implementation Guide**: `docs/LLM_VALIDATION_GUIDE.md`
- **Completion Summary**: `docs/LLM_VALIDATION_IMPLEMENTATION_COMPLETE.md`
- **Source Code**: `src/core/llm_schemas.py`
- **Tests**: `tests/test_llm_validation.py` (22 tests ✅)

## 💡 Adding New Schemas

1. Define Pydantic model in `llm_schemas.py`
2. Add field validators
3. Use `validate_llm_response()` helper
4. Implement fallback
5. Add tests with golden fixtures
6. Configure monitoring

---

**Status**: ✅ Production Ready | **Tests**: 22/22 Passing | **Coverage**: 100%
