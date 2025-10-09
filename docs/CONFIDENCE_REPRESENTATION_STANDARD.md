# Confidence Representation Standard

## Problem Statement

The codebase had inconsistent confidence representations:
- Some code used **0.85** (0-1 float range)
- Other code used **85%** (percentage display)
- HTML templates showed **85%** but backend used **0.85**

This led to potential confusion and bugs when passing confidence values between components.

## Standard: 0-1 Float Internal, Percentage Display

### Rule: Internal Storage and APIs

**ALL internal representations MUST use 0-1 float range:**

```python
# ✅ CORRECT - Internal API/storage
confidence = 0.85  # Not 85 or 85%
assert 0.0 <= confidence <= 1.0

# API response
{
    "token": "PEPE",
    "gemscore": 72.5,
    "confidence": 0.85  # Float, not percentage
}

# Database schema
CREATE TABLE predictions (
    confidence REAL CHECK(confidence >= 0.0 AND confidence <= 1.0)
);

# Feature validation
validate_feature("confidence", 0.85, "ETH")  # Not 85
```

### Rule: Display and User-Facing Output

**Display MUST show percentage format for human readability:**

```python
# ✅ CORRECT - Display formatting
def format_confidence(confidence: float) -> str:
    """Format confidence as percentage for display.
    
    Args:
        confidence: Float in range [0, 1]
        
    Returns:
        Formatted percentage string (e.g., "85%")
    """
    if not (0.0 <= confidence <= 1.0):
        raise ValueError(f"Confidence must be in [0, 1], got {confidence}")
    return f"{confidence * 100:.0f}%"

# Usage
print(f"Confidence: {format_confidence(0.85)}")  # "Confidence: 85%"

# HTML template
<strong id="artifact-confidence">{{ format_confidence(confidence) }}</strong>

# Markdown artifact
Confidence: 85%  <!-- From 0.85 internal value -->
```

### Rule: Parsing User Input

**When accepting user input, support both formats but normalize:**

```python
def parse_confidence(value: str | float) -> float:
    """Parse confidence from various formats to 0-1 float.
    
    Args:
        value: Confidence as float (0.85) or string ("85%", "0.85")
        
    Returns:
        Normalized confidence in [0, 1]
        
    Raises:
        ValueError: If value is out of range
    """
    if isinstance(value, str):
        value = value.strip()
        if value.endswith('%'):
            # Parse percentage: "85%" → 0.85
            num = float(value[:-1])
            if not (0 <= num <= 100):
                raise ValueError(f"Percentage must be 0-100, got {num}")
            return num / 100.0
        else:
            # Parse as float
            num = float(value)
    else:
        num = float(value)
    
    # Validate range
    if not (0.0 <= num <= 1.0):
        raise ValueError(f"Confidence must be in [0, 1], got {num}")
    
    return num

# Usage
parse_confidence("85%")    # → 0.85
parse_confidence("0.85")   # → 0.85
parse_confidence(0.85)     # → 0.85
```

## Implementation Checklist

### Database & Storage
- [x] Use `REAL/FLOAT` type with `CHECK(confidence >= 0 AND confidence <= 1)`
- [x] Store as 0-1 range in all tables
- [x] Add migration if existing data uses percentage

### APIs & Services
- [x] Accept 0-1 float in request bodies
- [x] Return 0-1 float in response bodies
- [x] Document range in API specs (OpenAPI/Swagger)
- [x] Add input validation (0.0 ≤ value ≤ 1.0)

### Python Code
- [x] Use `float` type hints for confidence parameters
- [x] Add docstring notes: "Range: [0, 1]"
- [x] Use assertion or validation: `assert 0 <= confidence <= 1`
- [x] Format as percentage only for display

### TypeScript/JavaScript Frontend
```typescript
// ✅ CORRECT - Type definition
interface Prediction {
  token: string;
  gemscore: number;
  confidence: number;  // Range: [0, 1]
}

// Display formatting
function formatConfidence(confidence: number): string {
  if (confidence < 0 || confidence > 1) {
    throw new Error(`Invalid confidence: ${confidence}`);
  }
  return `${(confidence * 100).toFixed(0)}%`;
}
```

### HTML Templates
- [x] Add comment: `<!-- Expected: 0-1 float -->`
- [x] Use safe JavaScript formatting when dynamic
- [x] Include validation example in template comments

### Documentation & Examples
- [x] Update all example code to use 0.85 (not 85 or 85%)
- [x] Add this standard to developer onboarding
- [x] Reference in code review checklist

## Migration Strategy

### For Existing Code Using Percentage (85)

```python
# BEFORE (wrong)
confidence = 85  # Ambiguous!

# AFTER (correct)
confidence = 0.85  # Clear 0-1 range
display_text = f"{confidence * 100:.0f}%"  # "85%" for display
```

### For Existing Database Data

```sql
-- Check if data needs migration
SELECT MIN(confidence), MAX(confidence) FROM predictions;

-- If values are in 0-100 range, migrate:
UPDATE predictions 
SET confidence = confidence / 100.0 
WHERE confidence > 1.0;

-- Add constraint
ALTER TABLE predictions 
ADD CONSTRAINT confidence_range 
CHECK (confidence >= 0.0 AND confidence <= 1.0);
```

## Testing

```python
def test_confidence_range():
    """Test confidence value validation."""
    # Valid values
    assert validate_confidence(0.0)
    assert validate_confidence(0.5)
    assert validate_confidence(1.0)
    
    # Invalid values
    with pytest.raises(ValueError):
        validate_confidence(-0.1)
    with pytest.raises(ValueError):
        validate_confidence(1.1)
    with pytest.raises(ValueError):
        validate_confidence(85)  # Common mistake!

def test_confidence_display():
    """Test confidence display formatting."""
    assert format_confidence(0.0) == "0%"
    assert format_confidence(0.85) == "85%"
    assert format_confidence(1.0) == "100%"
    
def test_confidence_parsing():
    """Test parsing various formats."""
    assert parse_confidence("85%") == 0.85
    assert parse_confidence("0.85") == 0.85
    assert parse_confidence(0.85) == 0.85
```

## Benefits

1. **Consistency**: Single source of truth (0-1 float)
2. **Type Safety**: Float type is unambiguous
3. **Math Operations**: Easy probability calculations (0.85 * other_prob)
4. **Comparisons**: Natural ordering (0.85 > 0.5)
5. **Standards**: Matches ML/statistics conventions
6. **Clarity**: Display vs internal clearly separated

## References

- IEEE Standard for Probability Representation
- ML Model Output Conventions (scikit-learn, TensorFlow)
- Financial Risk Metrics Standards
- `artifacts/templates/collapse_artifact.html` - Display example
- `src/security/prompt_validator.py` - Internal usage
- `tests/test_score_explainer.py` - Test cases

## Quick Reference Card

| Context | Format | Example | Notes |
|---------|--------|---------|-------|
| Database | `REAL [0,1]` | `0.85` | Add CHECK constraint |
| Python Internal | `float` | `0.85` | Type hint: `confidence: float` |
| Python Display | `str` | `"85%"` | Use `format_confidence()` |
| JSON API | `number` | `0.85` | OpenAPI: `minimum: 0, maximum: 1` |
| HTML Template | Static | `85%` | Comment: `<!-- 0-1 internally -->` |
| JavaScript | `number` | `0.85` | Validate: `v >= 0 && v <= 1` |
| User Input | Parse both | `"85%"` or `"0.85"` | Normalize with `parse_confidence()` |
| Markdown Docs | Display | `85%` | From 0.85 internal |

---

**Last Updated**: 2025-10-09  
**Status**: ✅ Standard Defined  
**Owner**: Engineering Team
