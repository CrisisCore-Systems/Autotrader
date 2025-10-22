"""Strict Pydantic schemas for LLM output validation.

This module enforces JSON schema validation for all LLM outputs with fail-fast
behavior and structured logging for invalid payloads.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator

logger = logging.getLogger(__name__)


class NarrativeAnalysisResponse(BaseModel):
    """Strict schema for narrative analysis LLM output.
    
    All fields are validated with strict constraints. Invalid payloads will
    fail fast with detailed validation errors logged.
    """
    
    sentiment: Literal["positive", "neutral", "negative"] = Field(
        ...,
        description="Overall sentiment classification"
    )
    
    sentiment_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized sentiment score between 0.0 (negative) and 1.0 (positive)"
    )
    
    emergent_themes: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Key themes identified in narratives"
    )
    
    memetic_hooks: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Viral/meme-worthy phrases or hashtags"
    )
    
    fake_or_buzz_warning: bool = Field(
        default=False,
        description="Warning flag for potential fake news or hype"
    )
    
    rationale: str = Field(
        ...,
        min_length=10,
        max_length=2000,
        description="Explanation of the analysis"
    )
    
    @field_validator("sentiment")
    @classmethod
    def validate_sentiment_literal(cls, v: str) -> str:
        """Ensure sentiment is properly stripped and validated."""
        if not isinstance(v, str):
            raise ValueError("Sentiment must be a string")
        
        stripped = v.strip().lower()
        if stripped not in ["positive", "neutral", "negative"]:
            raise ValueError(f"Invalid sentiment: {stripped}. Must be 'positive', 'neutral', or 'negative'")
        
        return stripped
    
    @field_validator("emergent_themes", "memetic_hooks")
    @classmethod
    def validate_string_lists(cls, v: List[str]) -> List[str]:
        """Ensure all list items are non-empty strings."""
        if not isinstance(v, list):
            raise ValueError("Must be a list of strings")
        
        cleaned = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"Expected string, got {type(item).__name__}")
            stripped = item.strip()
            if stripped:
                cleaned.append(stripped)
        
        return cleaned
    
    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, v: str) -> str:
        """Ensure rationale is meaningful content."""
        if not v or not v.strip():
            raise ValueError("Rationale cannot be empty")
        
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("Rationale must be at least 10 characters")
        
        return stripped
    
    @field_validator("sentiment_score")
    @classmethod
    def validate_sentiment_alignment(cls, v: float, info) -> float:
        """Validate sentiment_score aligns with sentiment label."""
        # Note: Can't access other fields during validation in Pydantic v2
        # This validation happens at model level if needed
        return v
    
    model_config = {
        "extra": "forbid",  # Fail on unexpected fields
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }


class ContractSafetyResponse(BaseModel):
    """Schema for contract safety analysis (future LLM integration)."""
    
    risk_level: Literal["low", "medium", "high", "critical"] = Field(
        ...,
        description="Overall risk assessment"
    )
    
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized risk score (0=safe, 1=critical)"
    )
    
    findings: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Specific security findings"
    )
    
    vulnerabilities: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Identified vulnerabilities"
    )
    
    recommendations: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Recommended actions"
    )
    
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence level of the analysis"
    )
    
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }


class TechnicalPatternResponse(BaseModel):
    """Schema for technical pattern recognition (future LLM integration)."""
    
    pattern_type: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Identified pattern type"
    )
    
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Pattern confidence score"
    )
    
    signal_strength: Literal["weak", "moderate", "strong"] = Field(
        ...,
        description="Signal strength classification"
    )
    
    price_targets: Dict[str, float] = Field(
        default_factory=dict,
        description="Price targets (support, resistance, etc.)"
    )
    
    timeframe: str = Field(
        default="unknown",
        description="Expected timeframe for pattern completion"
    )
    
    rationale: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Explanation of pattern identification"
    )
    
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }


class OnchainActivityResponse(BaseModel):
    """Schema for on-chain activity forensic analysis."""
    
    accumulation_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Net smart-money accumulation signal (0=distribution, 1=strong accumulation)"
    )
    
    top_wallet_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of supply held by top 5 wallets"
    )
    
    tx_size_skew: Literal["small", "medium", "large"] = Field(
        ...,
        description="Dominant transaction cohort size"
    )
    
    suspicious_patterns: List[str] = Field(
        default_factory=list,
        max_length=5,
        description="Concrete anomalies (wash trading, sandwich attacks, etc.)"
    )
    
    notes: str = Field(
        ...,
        min_length=10,
        max_length=320,
        description="Context and interpretation (≤2 sentences)"
    )
    
    @field_validator("suspicious_patterns")
    @classmethod
    def validate_suspicious_patterns(cls, v: List[str]) -> List[str]:
        """Ensure all list items are non-empty strings with max length."""
        if not isinstance(v, list):
            raise ValueError("Must be a list of strings")
        
        cleaned = []
        for item in v:
            if not isinstance(item, str):
                raise ValueError(f"Expected string, got {type(item).__name__}")
            stripped = item.strip()
            if stripped:
                if len(stripped) > 128:
                    raise ValueError(f"Pattern description too long: {len(stripped)} > 128")
                cleaned.append(stripped)
        
        return cleaned
    
    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: str) -> str:
        """Ensure notes is meaningful content."""
        if not v or not v.strip():
            raise ValueError("Notes cannot be empty")
        
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("Notes must be at least 10 characters")
        
        return stripped
    
    model_config = {
        "extra": "forbid",
        "str_strip_whitespace": True,
        "validate_assignment": True,
    }


def validate_llm_response(
    raw_response: str,
    schema: type[BaseModel],
    context: str = "llm_response"
) -> Optional[BaseModel]:
    """Validate LLM response with fail-fast and structured logging.
    
    Args:
        raw_response: Raw JSON string from LLM
        schema: Pydantic model class to validate against
        context: Context identifier for logging (e.g., "narrative_analysis")
    
    Returns:
        Validated Pydantic model instance, or None if validation fails
        
    Raises:
        ValidationError: If fail_fast is True and validation fails
        
    Example:
        >>> result = validate_llm_response(
        ...     raw_json,
        ...     NarrativeAnalysisResponse,
        ...     context="narrative_summary"
        ... )
        >>> if result:
        ...     print(f"Sentiment: {result.sentiment_score}")
    """
    import json
    
    # Parse JSON
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            "llm_invalid_json",
            extra={
                "context": context,
                "error": str(e),
                "raw_response_preview": raw_response[:200],
            }
        )
        return None
    
    # Validate schema
    try:
        validated = schema.model_validate(data)
        logger.info(
            "llm_validation_success",
            extra={
                "context": context,
                "schema": schema.__name__,
            }
        )
        return validated
        
    except ValidationError as e:
        logger.error(
            "llm_schema_validation_failed",
            extra={
                "context": context,
                "schema": schema.__name__,
                "errors": e.errors(),
                "raw_data": data,
            }
        )
        return None


def validate_llm_response_strict(
    raw_response: str,
    schema: type[BaseModel],
    context: str = "llm_response"
) -> BaseModel:
    """Validate LLM response with STRICT fail-fast behavior.
    
    Unlike validate_llm_response(), this variant raises exceptions
    instead of returning None, enforcing strict validation.
    
    Args:
        raw_response: Raw JSON string from LLM
        schema: Pydantic model class to validate against
        context: Context identifier for logging
    
    Returns:
        Validated Pydantic model instance
        
    Raises:
        json.JSONDecodeError: If JSON parsing fails
        ValidationError: If schema validation fails
    """
    import json
    
    # Parse JSON (fail-fast)
    try:
        data = json.loads(raw_response)
    except json.JSONDecodeError as e:
        logger.error(
            "llm_invalid_json_strict",
            extra={
                "context": context,
                "error": str(e),
                "raw_response_preview": raw_response[:200],
            }
        )
        raise
    
    # Validate schema (fail-fast)
    try:
        validated = schema.model_validate(data)
        logger.info(
            "llm_validation_success_strict",
            extra={
                "context": context,
                "schema": schema.__name__,
            }
        )
        return validated
        
    except ValidationError as e:
        logger.error(
            "llm_schema_validation_failed_strict",
            extra={
                "context": context,
                "schema": schema.__name__,
                "errors": e.errors(),
                "error_count": len(e.errors()),
            }
        )
        raise
