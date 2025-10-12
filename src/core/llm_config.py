"""Complete LLM configuration with multi-provider fallback, quotas, and cost tracking.

Features:
- Per-provider fallback chains with automatic retry
- Token-per-minute rate limiting
- Cost accounting with per-request tracking
- JSON schema enforcement guardrails
- Provider-specific configuration
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

from pydantic import BaseModel


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    
    GROQ = "groq"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class SchemaEnforcementMode(str, Enum):
    """JSON schema enforcement modes."""
    
    STRICT = "strict"  # Fail on validation errors
    WARN = "warn"  # Log warnings but continue
    DISABLED = "disabled"  # No schema validation


@dataclass
class ProviderQuota:
    """Rate limiting and quota configuration for a provider."""
    
    tokens_per_minute: int
    tokens_per_day: int
    requests_per_minute: int
    max_cost_per_day_usd: float
    
    # Runtime tracking
    tokens_used_minute: int = 0
    tokens_used_day: int = 0
    requests_used_minute: int = 0
    cost_used_day_usd: float = 0.0
    
    # Window tracking
    minute_window_start: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    day_window_start: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    
    def check_and_reserve(
        self,
        tokens: int,
        estimated_cost: float,
    ) -> tuple[bool, str]:
        """Check if request is within quota and reserve capacity.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        now = datetime.now(tz=timezone.utc)
        
        # Reset windows if needed
        self._maybe_reset_windows(now)
        
        # Check tokens per minute
        if self.tokens_used_minute + tokens > self.tokens_per_minute:
            return False, f"Tokens per minute quota exceeded ({self.tokens_per_minute})"
        
        # Check tokens per day
        if self.tokens_used_day + tokens > self.tokens_per_day:
            return False, f"Tokens per day quota exceeded ({self.tokens_per_day})"
        
        # Check requests per minute
        if self.requests_used_minute + 1 > self.requests_per_minute:
            return False, f"Requests per minute quota exceeded ({self.requests_per_minute})"
        
        # Check cost per day
        if self.cost_used_day_usd + estimated_cost > self.max_cost_per_day_usd:
            return False, f"Daily cost quota exceeded (${self.max_cost_per_day_usd})"
        
        # Reserve capacity
        self.tokens_used_minute += tokens
        self.tokens_used_day += tokens
        self.requests_used_minute += 1
        self.cost_used_day_usd += estimated_cost
        
        return True, "OK"
    
    def _maybe_reset_windows(self, now: datetime) -> None:
        """Reset tracking windows if expired."""
        # Reset minute window (60 seconds)
        if (now - self.minute_window_start).total_seconds() >= 60:
            self.tokens_used_minute = 0
            self.requests_used_minute = 0
            self.minute_window_start = now
        
        # Reset day window (24 hours)
        if (now - self.day_window_start).total_seconds() >= 86400:
            self.tokens_used_day = 0
            self.cost_used_day_usd = 0.0
            self.day_window_start = now


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""
    
    provider: LLMProvider
    model: str
    api_key_env_var: str
    
    # Pricing (per 1K tokens)
    input_cost_per_1k: float
    output_cost_per_1k: float
    
    # Quotas
    quota: ProviderQuota
    
    # Model parameters
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 1.0
    
    # Retry configuration
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    
    # Provider-specific settings
    extra_params: Dict[str, Any] = field(default_factory=dict)
    
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for a request."""
        input_cost = (input_tokens / 1000.0) * self.input_cost_per_1k
        output_cost = (output_tokens / 1000.0) * self.output_cost_per_1k
        return input_cost + output_cost


@dataclass
class LLMConfig:
    """Complete LLM configuration with fallback chains."""
    
    # Primary provider
    primary_provider: ProviderConfig
    
    # Fallback chain (in order of preference)
    fallback_providers: List[ProviderConfig] = field(default_factory=list)
    
    # Guardrails
    schema_enforcement_mode: SchemaEnforcementMode = SchemaEnforcementMode.STRICT
    max_total_cost_per_day_usd: float = 100.0
    enable_caching: bool = True
    cache_ttl_seconds: int = 3600
    
    # Cost tracking
    total_cost_today_usd: float = 0.0
    total_requests_today: int = 0
    last_reset: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    
    def get_provider_chain(self) -> List[ProviderConfig]:
        """Get ordered list of providers (primary + fallbacks)."""
        return [self.primary_provider] + self.fallback_providers
    
    def record_request(self, cost: float) -> None:
        """Record a successful request for cost tracking."""
        self._maybe_reset_daily_tracking()
        self.total_cost_today_usd += cost
        self.total_requests_today += 1
    
    def _maybe_reset_daily_tracking(self) -> None:
        """Reset daily tracking if 24 hours elapsed."""
        now = datetime.now(tz=timezone.utc)
        if (now - self.last_reset).total_seconds() >= 86400:
            self.total_cost_today_usd = 0.0
            self.total_requests_today = 0
            self.last_reset = now
    
    def check_global_quota(self, estimated_cost: float) -> tuple[bool, str]:
        """Check global daily cost quota."""
        self._maybe_reset_daily_tracking()
        
        if self.total_cost_today_usd + estimated_cost > self.max_total_cost_per_day_usd:
            return False, f"Global daily cost quota exceeded (${self.max_total_cost_per_day_usd})"
        
        return True, "OK"


class LLMClient(Protocol):
    """Protocol for LLM client implementations."""
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Execute chat completion request."""
        ...


@dataclass
class LLMRequestResult:
    """Result of an LLM request with cost tracking."""
    
    success: bool
    response: Optional[Dict[str, Any]]
    provider_used: LLMProvider
    model_used: str
    
    # Token usage
    input_tokens: int
    output_tokens: int
    total_tokens: int
    
    # Cost tracking
    estimated_cost_usd: float
    actual_cost_usd: float
    
    # Metadata
    latency_seconds: float
    cache_hit: bool = False
    retry_count: int = 0
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/tracking."""
        return {
            "success": self.success,
            "provider": self.provider_used.value,
            "model": self.model_used,
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "total": self.total_tokens,
            },
            "cost_usd": {
                "estimated": round(self.estimated_cost_usd, 6),
                "actual": round(self.actual_cost_usd, 6),
            },
            "latency_seconds": round(self.latency_seconds, 3),
            "cache_hit": self.cache_hit,
            "retry_count": self.retry_count,
            "error": self.error_message,
        }


def create_groq_config(
    api_key_env_var: str = "GROQ_API_KEY",
    model: str = "llama-3.3-70b-versatile",
    tokens_per_minute: int = 30000,
    tokens_per_day: int = 1000000,
    max_cost_per_day: float = 10.0,
) -> ProviderConfig:
    """Create Groq provider configuration with typical defaults."""
    return ProviderConfig(
        provider=LLMProvider.GROQ,
        model=model,
        api_key_env_var=api_key_env_var,
        input_cost_per_1k=0.00059,  # $0.59 per 1M tokens
        output_cost_per_1k=0.00079,
        quota=ProviderQuota(
            tokens_per_minute=tokens_per_minute,
            tokens_per_day=tokens_per_day,
            requests_per_minute=30,
            max_cost_per_day_usd=max_cost_per_day,
        ),
        temperature=0.7,
        max_tokens=2000,
    )


def create_openai_config(
    api_key_env_var: str = "OPENAI_API_KEY",
    model: str = "gpt-4o-mini",
    tokens_per_minute: int = 10000,
    tokens_per_day: int = 500000,
    max_cost_per_day: float = 20.0,
) -> ProviderConfig:
    """Create OpenAI provider configuration with typical defaults."""
    return ProviderConfig(
        provider=LLMProvider.OPENAI,
        model=model,
        api_key_env_var=api_key_env_var,
        input_cost_per_1k=0.15 / 1000,  # $0.15 per 1M input tokens for GPT-4o-mini
        output_cost_per_1k=0.60 / 1000,  # $0.60 per 1M output tokens
        quota=ProviderQuota(
            tokens_per_minute=tokens_per_minute,
            tokens_per_day=tokens_per_day,
            requests_per_minute=10,
            max_cost_per_day_usd=max_cost_per_day,
        ),
        temperature=0.7,
        max_tokens=2000,
    )


def create_default_llm_config(
    enable_openai_fallback: bool = False,
) -> LLMConfig:
    """Create default LLM configuration with Groq primary and optional OpenAI fallback."""
    primary = create_groq_config()
    fallbacks = [create_openai_config()] if enable_openai_fallback else []
    
    return LLMConfig(
        primary_provider=primary,
        fallback_providers=fallbacks,
        schema_enforcement_mode=SchemaEnforcementMode.STRICT,
        max_total_cost_per_day_usd=50.0,
        enable_caching=True,
        cache_ttl_seconds=3600,
    )


__all__ = [
    "LLMProvider",
    "SchemaEnforcementMode",
    "ProviderQuota",
    "ProviderConfig",
    "LLMConfig",
    "LLMClient",
    "LLMRequestResult",
    "create_groq_config",
    "create_openai_config",
    "create_default_llm_config",
]
