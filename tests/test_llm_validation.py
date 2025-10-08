"""Tests for LLM output validation with Pydantic schemas.

This module validates that all LLM outputs are strictly validated
with fail-fast behavior and proper logging of invalid payloads.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

import pytest
from pydantic import ValidationError

from src.core.llm_schemas import (
    ContractSafetyResponse,
    NarrativeAnalysisResponse,
    TechnicalPatternResponse,
    validate_llm_response,
    validate_llm_response_strict,
)


class TestNarrativeAnalysisValidation:
    """Test validation of narrative analysis LLM outputs."""

    def test_valid_narrative_response(self):
        """Valid response passes validation."""
        valid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.75,
            "emergent_themes": ["DeFi", "Layer 2", "Scaling"],
            "memetic_hooks": ["#ToTheMoon", "#WAGMI"],
            "fake_or_buzz_warning": False,
            "rationale": "Strong fundamentals with institutional backing and technical milestones."
        })
        
        result = validate_llm_response(
            valid_json,
            NarrativeAnalysisResponse,
            context="test_valid"
        )
        
        assert result is not None
        assert result.sentiment == "positive"
        assert result.sentiment_score == 0.75
        assert len(result.emergent_themes) == 3
        assert len(result.memetic_hooks) == 2
        assert result.fake_or_buzz_warning is False

    def test_minimal_valid_response(self):
        """Minimal valid response with required fields only."""
        minimal_json = json.dumps({
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "rationale": "Baseline analysis with no strong signals detected."
        })
        
        result = validate_llm_response(
            minimal_json,
            NarrativeAnalysisResponse,
            context="test_minimal"
        )
        
        assert result is not None
        assert result.sentiment == "neutral"
        assert result.emergent_themes == []
        assert result.memetic_hooks == []
        assert result.fake_or_buzz_warning is False

    def test_invalid_sentiment_value(self):
        """Invalid sentiment literal fails validation."""
        invalid_json = json.dumps({
            "sentiment": "bullish",  # Invalid - must be positive/neutral/negative
            "sentiment_score": 0.75,
            "rationale": "Testing invalid sentiment value."
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_invalid_sentiment"
        )
        
        assert result is None  # Validation failed

    def test_sentiment_score_out_of_range(self):
        """Sentiment score outside [0,1] fails validation."""
        invalid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 1.5,  # Invalid - must be 0.0-1.0
            "rationale": "Testing out of range score."
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_score_range"
        )
        
        assert result is None

    def test_negative_sentiment_score(self):
        """Negative sentiment score fails validation."""
        invalid_json = json.dumps({
            "sentiment": "negative",
            "sentiment_score": -0.5,  # Invalid - must be >= 0.0
            "rationale": "Testing negative score."
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_negative_score"
        )
        
        assert result is None

    def test_missing_required_field(self):
        """Missing required field fails validation."""
        invalid_json = json.dumps({
            "sentiment": "positive",
            # Missing sentiment_score
            "rationale": "Testing missing required field."
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_missing_field"
        )
        
        assert result is None

    def test_empty_rationale(self):
        """Empty or too-short rationale fails validation."""
        invalid_json = json.dumps({
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "rationale": "Short"  # Too short - must be >= 10 chars
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_short_rationale"
        )
        
        assert result is None

    def test_extra_fields_rejected(self):
        """Extra/unexpected fields fail validation (extra='forbid')."""
        invalid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "rationale": "Testing extra fields rejection.",
            "unexpected_field": "This should cause validation to fail"
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_extra_fields"
        )
        
        assert result is None

    def test_invalid_json_format(self):
        """Malformed JSON fails validation."""
        invalid_json = "{sentiment: 'positive', not valid json"
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_invalid_json"
        )
        
        assert result is None

    def test_list_validation_with_empty_strings(self):
        """Empty strings in lists are filtered out."""
        valid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.7,
            "emergent_themes": ["Valid", "", "  ", "Also Valid"],  # Empty strings filtered
            "memetic_hooks": ["#Valid", ""],
            "rationale": "Testing list validation with empty strings."
        })
        
        result = validate_llm_response(
            valid_json,
            NarrativeAnalysisResponse,
            context="test_list_validation"
        )
        
        assert result is not None
        assert len(result.emergent_themes) == 2  # Empty strings removed
        assert "Valid" in result.emergent_themes
        assert "Also Valid" in result.emergent_themes

    def test_list_validation_max_length(self):
        """Lists exceeding max length fail validation."""
        invalid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.7,
            "emergent_themes": [f"Theme{i}" for i in range(15)],  # Max is 10
            "rationale": "Testing max list length."
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_max_list_length"
        )
        
        assert result is None

    def test_whitespace_stripping(self):
        """Whitespace is automatically stripped for string fields."""
        valid_json = json.dumps({
            "sentiment": "positive",  # Literal fields must be exact (validated before strip)
            "sentiment_score": 0.8,
            "emergent_themes": ["  Theme 1  ", "Theme 2  "],
            "rationale": "  Testing whitespace stripping behavior.  "
        })
        
        result = validate_llm_response(
            valid_json,
            NarrativeAnalysisResponse,
            context="test_whitespace"
        )
        
        assert result is not None
        assert result.sentiment == "positive"
        assert result.emergent_themes[0] == "Theme 1"  # Stripped by validator
        assert result.rationale.strip() == "Testing whitespace stripping behavior."  # Stripped


class TestStrictValidation:
    """Test strict fail-fast validation mode."""

    def test_strict_mode_raises_on_invalid_json(self):
        """Strict mode raises JSONDecodeError on invalid JSON."""
        invalid_json = "{not valid json"
        
        with pytest.raises(json.JSONDecodeError):
            validate_llm_response_strict(
                invalid_json,
                NarrativeAnalysisResponse,
                context="test_strict_json"
            )

    def test_strict_mode_raises_on_schema_violation(self):
        """Strict mode raises ValidationError on schema violation."""
        invalid_json = json.dumps({
            "sentiment": "invalid_value",
            "sentiment_score": 0.5,
            "rationale": "Testing strict validation."
        })
        
        with pytest.raises(ValidationError):
            validate_llm_response_strict(
                invalid_json,
                NarrativeAnalysisResponse,
                context="test_strict_schema"
            )

    def test_strict_mode_succeeds_on_valid_data(self):
        """Strict mode returns validated model on valid data."""
        valid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.8,
            "rationale": "Testing successful strict validation."
        })
        
        result = validate_llm_response_strict(
            valid_json,
            NarrativeAnalysisResponse,
            context="test_strict_valid"
        )
        
        assert result is not None
        assert result.sentiment == "positive"


class TestValidationLogging:
    """Test that validation errors are properly logged."""

    def test_validation_failure_logged(self, caplog):
        """Validation failures are logged with structured details."""
        caplog.set_level(logging.ERROR)
        
        invalid_json = json.dumps({
            "sentiment": "invalid",
            "sentiment_score": 2.0,  # Out of range
            "rationale": "Test"  # Too short
        })
        
        result = validate_llm_response(
            invalid_json,
            NarrativeAnalysisResponse,
            context="test_logging"
        )
        
        assert result is None
        # Check that error was logged
        assert any("llm_schema_validation_failed" in record.message for record in caplog.records)

    def test_success_logged(self, caplog):
        """Successful validation is logged."""
        caplog.set_level(logging.INFO)
        
        valid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.75,
            "rationale": "Testing successful validation logging."
        })
        
        result = validate_llm_response(
            valid_json,
            NarrativeAnalysisResponse,
            context="test_success_logging"
        )
        
        assert result is not None
        assert any("llm_validation_success" in record.message for record in caplog.records)


class TestOtherSchemas:
    """Test validation for other LLM response schemas."""

    def test_contract_safety_response(self):
        """Contract safety response validates correctly."""
        valid_json = json.dumps({
            "risk_level": "medium",
            "risk_score": 0.6,
            "findings": ["Centralized ownership", "No timelock"],
            "vulnerabilities": ["Reentrancy risk in withdraw()"],
            "recommendations": ["Add timelock", "Multi-sig wallet"],
            "confidence": 0.8
        })
        
        result = validate_llm_response(
            valid_json,
            ContractSafetyResponse,
            context="test_contract_safety"
        )
        
        assert result is not None
        assert result.risk_level == "medium"
        assert len(result.findings) == 2

    def test_technical_pattern_response(self):
        """Technical pattern response validates correctly."""
        valid_json = json.dumps({
            "pattern_type": "Bull Flag",
            "confidence": 0.85,
            "signal_strength": "strong",
            "price_targets": {
                "support": 0.00012,
                "resistance": 0.00018
            },
            "timeframe": "1-2 days",
            "rationale": "Clear consolidation after uptrend with declining volume."
        })
        
        result = validate_llm_response(
            valid_json,
            TechnicalPatternResponse,
            context="test_technical_pattern"
        )
        
        assert result is not None
        assert result.pattern_type == "Bull Flag"
        assert result.signal_strength == "strong"


class TestBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_model_dump_returns_dict(self):
        """Validated models can be converted to dicts for legacy code."""
        valid_json = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.75,
            "rationale": "Testing backward compatibility."
        })
        
        result = validate_llm_response(
            valid_json,
            NarrativeAnalysisResponse,
            context="test_compat"
        )
        
        assert result is not None
        
        # Convert to dict (used in existing code)
        data = result.model_dump()
        
        assert isinstance(data, dict)
        assert data["sentiment"] == "positive"
        assert data["sentiment_score"] == 0.75
        
        # Can access dict keys
        assert "emergent_themes" in data
        assert "fake_or_buzz_warning" in data


class TestGoldenFixtures:
    """Test with golden fixtures from real LLM responses."""

    def test_groq_llama_response_format(self):
        """Test actual Groq/Llama response format."""
        # Real-world example from Groq API
        real_response = json.dumps({
            "sentiment": "positive",
            "sentiment_score": 0.82,
            "emergent_themes": [
                "Institutional adoption",
                "Layer 2 scaling",
                "DeFi integration"
            ],
            "memetic_hooks": ["#Ethereum", "#L2"],
            "fake_or_buzz_warning": False,
            "rationale": "Strong technical fundamentals with increasing institutional "
                        "interest. Layer 2 scaling solutions showing significant TVL growth. "
                        "No red flags in recent news cycle."
        })
        
        result = validate_llm_response(
            real_response,
            NarrativeAnalysisResponse,
            context="test_golden_groq"
        )
        
        assert result is not None
        assert result.sentiment_score == 0.82
        assert len(result.emergent_themes) == 3

    def test_markdown_wrapped_json(self):
        """Test handling of markdown-wrapped JSON from LLM."""
        # Some LLMs wrap JSON in markdown code blocks
        markdown_response = """```json
{
    "sentiment": "neutral",
    "sentiment_score": 0.5,
    "emergent_themes": ["Waiting", "Sideways"],
    "rationale": "Market consolidation with no clear directional bias."
}
```"""
        
        # Clean the response (using _clean_json_response helper)
        from src.core.narrative import _clean_json_response
        cleaned = _clean_json_response(markdown_response)
        
        result = validate_llm_response(
            cleaned,
            NarrativeAnalysisResponse,
            context="test_markdown"
        )
        
        assert result is not None
        assert result.sentiment == "neutral"
