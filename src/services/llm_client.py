"""LLM client with fallback, retry, and cost tracking."""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError

from src.core.llm_config import (
    LLMConfig,
    LLMProvider,
    LLMRequestResult,
    ProviderConfig,
    SchemaEnforcementMode,
)
from src.services.llm_guardrails import PromptCache, _estimate_tokens

logger = logging.getLogger(__name__)


class LLMClientError(Exception):
    """Raised when all LLM providers fail."""
    pass


class QuotaExceededError(Exception):
    """Raised when quota limits are exceeded."""
    pass


class ManagedLLMClient:
    """LLM client with automatic fallback, retry, and cost tracking.
    
    Features:
    - Automatic provider fallback on failure
    - Per-provider quota enforcement
    - Cost tracking and reporting
    - Optional response caching
    - JSON schema validation
    """
    
    def __init__(
        self,
        config: LLMConfig,
        cache: Optional[PromptCache] = None,
    ):
        self.config = config
        self.cache = cache or PromptCache(ttl_seconds=config.cache_ttl_seconds)
        self._clients: Dict[LLMProvider, Any] = {}
    
    def _get_client(self, provider: LLMProvider) -> Any:
        """Get or create client for provider."""
        if provider in self._clients:
            return self._clients[provider]
        
        # Lazy initialization of provider clients
        if provider == LLMProvider.GROQ:
            try:
                from groq import Groq
                api_key = os.environ.get("GROQ_API_KEY")
                if not api_key:
                    raise ValueError("GROQ_API_KEY not set")
                client = Groq(api_key=api_key)
                self._clients[provider] = client
                return client
            except ImportError:
                logger.error("groq package not installed")
                raise
        
        elif provider == LLMProvider.OPENAI:
            try:
                from openai import OpenAI
                api_key = os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not set")
                client = OpenAI(api_key=api_key)
                self._clients[provider] = client
                return client
            except ImportError:
                logger.error("openai package not installed")
                raise
        
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        response_schema: Optional[type[BaseModel]] = None,
        use_cache: bool = True,
    ) -> LLMRequestResult:
        """Execute chat completion with fallback and tracking.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            response_schema: Optional Pydantic model for response validation
            use_cache: Whether to use response cache
            
        Returns:
            LLMRequestResult with response and cost tracking
            
        Raises:
            LLMClientError: If all providers fail
            QuotaExceededError: If quotas exceeded
        """
        # Check cache first
        if use_cache and self.config.enable_caching:
            cache_key = self._make_cache_key(messages)
            cached = self.cache.get(cache_key)
            if cached:
                logger.info("llm_cache_hit", extra={"cache_key": cache_key[:16]})
                return self._result_from_cache(cached)
        
        # Try providers in order (primary + fallbacks)
        provider_chain = self.config.get_provider_chain()
        last_error: Optional[Exception] = None
        
        for provider_config in provider_chain:
            try:
                result = self._try_provider(
                    provider_config,
                    messages,
                    response_schema,
                )
                
                # Cache successful response
                if use_cache and self.config.enable_caching and result.success:
                    cache_key = self._make_cache_key(messages)
                    self.cache.set(cache_key, result.to_dict())
                
                return result
                
            except QuotaExceededError as e:
                logger.warning(
                    "llm_quota_exceeded",
                    extra={
                        "provider": provider_config.provider.value,
                        "reason": str(e),
                    }
                )
                last_error = e
                continue
            
            except Exception as e:
                logger.warning(
                    "llm_provider_failed",
                    extra={
                        "provider": provider_config.provider.value,
                        "error": str(e),
                    }
                )
                last_error = e
                continue
        
        # All providers failed
        raise LLMClientError(f"All LLM providers failed. Last error: {last_error}")
    
    def _try_provider(
        self,
        provider_config: ProviderConfig,
        messages: List[Dict[str, str]],
        response_schema: Optional[type[BaseModel]],
    ) -> LLMRequestResult:
        """Try a single provider with retries."""
        # Estimate tokens and cost
        prompt_text = " ".join(m["content"] for m in messages)
        input_tokens = _estimate_tokens(prompt_text)
        output_tokens = provider_config.max_tokens
        estimated_cost = provider_config.estimate_cost(input_tokens, output_tokens)
        
        # Check global quota
        allowed, reason = self.config.check_global_quota(estimated_cost)
        if not allowed:
            raise QuotaExceededError(f"Global quota: {reason}")
        
        # Check provider quota
        allowed, reason = provider_config.quota.check_and_reserve(
            input_tokens + output_tokens,
            estimated_cost,
        )
        if not allowed:
            raise QuotaExceededError(f"Provider quota: {reason}")
        
        # Get client
        client = self._get_client(provider_config.provider)
        
        # Retry loop
        last_error: Optional[Exception] = None
        for attempt in range(provider_config.max_retries):
            try:
                start_time = time.time()
                
                # Execute request
                response = client.chat.completions.create(
                    model=provider_config.model,
                    messages=messages,
                    temperature=provider_config.temperature,
                    max_tokens=provider_config.max_tokens,
                    top_p=provider_config.top_p,
                    **provider_config.extra_params,
                )
                
                latency = time.time() - start_time
                
                # Extract response
                response_text = response.choices[0].message.content
                actual_input_tokens = response.usage.prompt_tokens
                actual_output_tokens = response.usage.completion_tokens
                actual_cost = provider_config.estimate_cost(
                    actual_input_tokens,
                    actual_output_tokens,
                )
                
                # Validate schema if provided
                if response_schema:
                    self._validate_response_schema(
                        response_text,
                        response_schema,
                        provider_config.provider,
                    )
                
                # Record cost
                self.config.record_request(actual_cost)
                
                # Build result
                return LLMRequestResult(
                    success=True,
                    response={"content": response_text, "raw": response},
                    provider_used=provider_config.provider,
                    model_used=provider_config.model,
                    input_tokens=actual_input_tokens,
                    output_tokens=actual_output_tokens,
                    total_tokens=actual_input_tokens + actual_output_tokens,
                    estimated_cost_usd=estimated_cost,
                    actual_cost_usd=actual_cost,
                    latency_seconds=latency,
                    retry_count=attempt,
                )
                
            except Exception as e:
                last_error = e
                if attempt < provider_config.max_retries - 1:
                    time.sleep(provider_config.retry_delay_seconds * (attempt + 1))
                    continue
                else:
                    raise
        
        raise last_error or Exception("Unknown error in LLM request")
    
    def _validate_response_schema(
        self,
        response_text: str,
        schema: type[BaseModel],
        provider: LLMProvider,
    ) -> None:
        """Validate response against Pydantic schema."""
        if self.config.schema_enforcement_mode == SchemaEnforcementMode.DISABLED:
            return
        
        try:
            data = json.loads(response_text)
            schema.model_validate(data)
            
        except json.JSONDecodeError as e:
            msg = f"LLM response is not valid JSON: {e}"
            logger.error("llm_invalid_json", extra={"provider": provider.value})
            
            if self.config.schema_enforcement_mode == SchemaEnforcementMode.STRICT:
                raise ValueError(msg)
        
        except ValidationError as e:
            msg = f"LLM response failed schema validation: {e}"
            logger.error(
                "llm_schema_validation_failed",
                extra={
                    "provider": provider.value,
                    "errors": e.errors(),
                }
            )
            
            if self.config.schema_enforcement_mode == SchemaEnforcementMode.STRICT:
                raise ValueError(msg)
    
    def _make_cache_key(self, messages: List[Dict[str, str]]) -> str:
        """Create cache key from messages."""
        return PromptCache.hash_prompt(
            json.dumps(messages, sort_keys=True),
            model=self.config.primary_provider.model,
        )
    
    def _result_from_cache(self, cached: Dict[str, Any]) -> LLMRequestResult:
        """Reconstruct result from cached data."""
        return LLMRequestResult(
            success=cached["success"],
            response={"content": cached.get("content", "")},
            provider_used=LLMProvider(cached["provider"]),
            model_used=cached["model"],
            input_tokens=cached["tokens"]["input"],
            output_tokens=cached["tokens"]["output"],
            total_tokens=cached["tokens"]["total"],
            estimated_cost_usd=cached["cost_usd"]["estimated"],
            actual_cost_usd=cached["cost_usd"]["actual"],
            latency_seconds=0.0,  # Cache hit has no latency
            cache_hit=True,
        )
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost tracking summary."""
        return {
            "total_cost_today_usd": round(self.config.total_cost_today_usd, 4),
            "total_requests_today": self.config.total_requests_today,
            "quota_remaining_usd": round(
                self.config.max_total_cost_per_day_usd - self.config.total_cost_today_usd,
                4
            ),
            "quota_utilization_pct": round(
                100.0 * self.config.total_cost_today_usd / self.config.max_total_cost_per_day_usd,
                2
            ),
        }


__all__ = ["ManagedLLMClient", "LLMClientError", "QuotaExceededError"]
