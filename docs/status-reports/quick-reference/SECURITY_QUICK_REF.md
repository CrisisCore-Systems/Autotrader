# Security Layer Quick Reference

## Prompt Validation

### Validate User Input
```python
from src.security import validate_prompt

result = validate_prompt("User input text here")
if not result.is_valid:
    # Block or sanitize
    print(f"Threat: {result.threat_level}")
    print(f"Errors: {result.errors}")
```

### Validate LLM Output
```python
from src.security import validate_llm_output

# Text output
result = validate_llm_output("LLM response text")

# JSON with schema
result = validate_llm_output(
    json_string,
    expected_format="json",
    schema_name="narrative_analysis"  # or "safety_analysis", "lore_generation"
)
```

## Artifact Integrity

### Sign Content
```python
from src.security import sign_artifact

signature = sign_artifact(
    content="Your artifact content",
    metadata={"title": "Report", "type": "markdown"}
)

# Access signature components
print(signature.content_hash)      # SHA-256 hash
print(signature.hmac_signature)    # HMAC signature
print(signature.timestamp)         # ISO timestamp
```

### Verify Content
```python
from src.security import verify_artifact

is_valid = verify_artifact(content, signature)
if not is_valid:
    raise ValueError("Content has been tampered with!")
```

### Sign JSON Payload
```python
from src.security import get_signer

signer = get_signer()
signed_payload = signer.sign_payload({"key": "value"})
# signed_payload now contains "_signature" field

# Verify later
is_valid = signer.verify_payload(signed_payload)
```

## Threat Levels
- `SAFE` - No threats detected
- `LOW` - Minor warnings
- `MEDIUM` - Potential issues  
- `HIGH` - Likely attack attempt
- `CRITICAL` - Definite attack

## Built-in Schemas

### narrative_analysis
```json
{
  "sentiment": "bullish|bearish|neutral",
  "themes": ["string"],
  "momentum": 0.0-1.0,
  "reasoning": "string"
}
```

### safety_analysis
```json
{
  "is_safe": true|false,
  "risk_level": "low|medium|high|critical",
  "findings": ["string"],
  "confidence": 0.0-1.0
}
```

### lore_generation
```json
{
  "lore": "string (10-10000 chars)",
  "themes": ["string"],
  "glyph": "string"
}
```

## Configuration

Set in environment:
```bash
export ARTIFACT_SECRET_KEY="your-secret-key-here"
```

Or generate automatically (not persistent across restarts).

## Testing

Run tests:
```bash
pytest tests/test_prompt_validator.py -v
pytest tests/test_artifact_integrity.py -v
```

## Integration Points

1. **Pipeline**: Add validation before/after LLM calls
2. **API**: Validate user input at entry points
3. **Exporter**: Artifacts are auto-signed (already integrated)
4. **Storage**: Verify signatures when loading artifacts
