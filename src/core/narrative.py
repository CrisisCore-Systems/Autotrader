"""Narrative analysis utilities with optional Groq LLM integration."""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

import numpy as np
from pydantic import ValidationError

from src.core.llm_schemas import NarrativeAnalysisResponse, validate_llm_response
from src.services.llm_guardrails import (
    BudgetExceeded,
    LLMBudgetGuardrail,
    PromptCache,
    SemanticCache,
)

logger = logging.getLogger(__name__)

try:  # pragma: no cover - optional dependency import
    from groq import Groq

    _GROQ_AVAILABLE = True
except ImportError:  # pragma: no cover - handled gracefully at runtime
    Groq = None  # type: ignore[assignment]
    _GROQ_AVAILABLE = False


@dataclass
class NarrativeInsight:
    sentiment_score: float
    momentum: float
    themes: List[str]
    volatility: float
    meme_momentum: float


_SYSTEM_PROMPT = "You are a crypto narrative analyst. Always respond with valid JSON only."

_DEFAULT_PROMPT = """You are Narrative GPT, a crypto narrative analyst.

Respond with JSON only:
{
  "sentiment": "positive|neutral|negative",
  "sentiment_score": 0.0-1.0,
  "emergent_themes": ["theme1", "theme2"],
  "memetic_hooks": ["hook1", "hook2"],
  "fake_or_buzz_warning": false,
  "rationale": "brief explanation"
}"""

_POSITIVE_WORDS = {
    "growth",
    "partnership",
    "expansion",
    "bullish",
    "upgrade",
    "mainnet",
    "integration",
    "surge",
    "milestone",
    "launch",
}
_NEGATIVE_WORDS = {
    "hack",
    "exploit",
    "down",
    "selloff",
    "delay",
    "halt",
    "bug",
    "reorg",
    "bankrupt",
}


_RISK_WORDS = {"hack", "exploit", "rug", "scam", "phishing", "breach"}
_STOPWORDS = {
    "the",
    "with",
    "from",
    "into",
    "that",
    "this",
    "have",
    "about",
    "into",
    "over",
    "their",
    "there",
    "https",
    "http",
    "www",
}


class NarrativeAnalyzer:
    """Narrative analyzer powered by Groq's LLM with deterministic fallbacks."""

    def __init__(
        self,
        *,
        client: Optional[Any] = None,
        use_llm: bool = True,
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.3,
        max_tokens: int = 600,
        prompt_cache: PromptCache | None = None,
        cost_guardrail: LLMBudgetGuardrail | None = None,
        cache_ttl_seconds: float = 86400.0,
        semantic_task_type: str = "narrative_summary",
        semantic_cache_ttl: float | None = None,
        semantic_cache: SemanticCache | None = None,
    ) -> None:
        self._provided_client = client
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._prompt_cache = prompt_cache if prompt_cache is not None else PromptCache(ttl_seconds=cache_ttl_seconds)
        self._cache_ttl = cache_ttl_seconds
        self._cost_guardrail = cost_guardrail
        self._semantic_cache = semantic_cache
        self._semantic_task_type = semantic_task_type
        self._semantic_cache_ttl = semantic_cache_ttl
        self._prompt_template = self._load_prompt_template()

        self._llm_client = self._resolve_client(use_llm)
        self._use_llm = use_llm and self._llm_client is not None

    def analyze(self, narratives: Iterable[str]) -> NarrativeInsight:
        texts = [text.strip() for text in narratives if text and text.strip()]
        if not texts:
            return NarrativeInsight(
                sentiment_score=0.5,
                momentum=0.5,
                themes=[],
                volatility=0.0,
                meme_momentum=0.0,
            )

        prompt = self._build_user_prompt(texts)
        payload: dict[str, Any]
        if self._use_llm:
            payload = self._request_analysis(prompt, texts)
        else:
            payload = {}

        if not payload:
            payload = self._fallback_payload(texts)

        sentiment_score = float(np.clip(_as_float(payload.get("sentiment_score"), default=0.5), 0.0, 1.0))
        themes = _as_str_list(payload.get("emergent_themes"))
        meme_hooks = _as_str_list(payload.get("memetic_hooks"))
        fake_warning = bool(payload.get("fake_or_buzz_warning", False))

        if sentiment_score > 0.6:
            momentum = 0.6
        elif sentiment_score < 0.4:
            momentum = 0.4
        else:
            momentum = 0.5
        volatility = 0.7 if fake_warning else 0.3
        meme_momentum = float(np.clip(len(meme_hooks) / 5.0, 0.0, 1.0))

        return NarrativeInsight(
            sentiment_score=sentiment_score,
            momentum=momentum,
            themes=themes,
            volatility=volatility,
            meme_momentum=meme_momentum,
        )

    def _check_semantic_cache(self, prompt: str) -> Optional[dict]:
        """Check semantic cache for cached response."""
        if self._semantic_cache is None:
            return None
        payload = self._semantic_cache.get(prompt, task_type=self._semantic_task_type)
        return dict(payload) if payload is not None else None

    def _check_prompt_cache(self, cache_key: Optional[str]) -> Optional[dict]:
        """Check prompt cache for cached response."""
        if not (cache_key and self._prompt_cache):
            return None
        cached = self._prompt_cache.get(cache_key)
        return dict(cached) if cached is not None else None

    def _handle_llm_invocation(self, prompt: str, texts: Sequence[str]) -> Optional[str]:
        """Invoke LLM with error handling."""
        try:
            return self._invoke_completion(prompt)
        except BudgetExceeded:
            logger.warning("llm_budget_exceeded", extra={"context": "narrative_analysis", "fallback": "heuristics"})
            return None
        except Exception as e:
            logger.error("llm_invocation_error", extra={"context": "narrative_analysis", "error": str(e)})
            return None

    def _validate_and_cache_response(
        self, response_content: str, cache_key: Optional[str], prompt: str
    ) -> Optional[dict]:
        """Validate LLM response and cache if valid."""
        cleaned = _clean_json_response(response_content)
        validated_response = validate_llm_response(cleaned, NarrativeAnalysisResponse, context="narrative_analysis")

        if validated_response is None:
            logger.warning(
                "llm_validation_failed_using_fallback",
                extra={"context": "narrative_analysis", "response_preview": cleaned[:200]},
            )
            return None

        data = validated_response.model_dump()

        # Cache the validated data
        if cache_key and self._prompt_cache:
            self._prompt_cache.set(cache_key, data, ttl=self._cache_ttl)
        if self._semantic_cache is not None:
            self._semantic_cache.set(
                prompt, data, task_type=self._semantic_task_type, ttl_seconds=self._semantic_cache_ttl
            )

        logger.info(
            "llm_response_validated",
            extra={
                "context": "narrative_analysis",
                "sentiment": data.get("sentiment"),
                "sentiment_score": data.get("sentiment_score"),
                "themes_count": len(data.get("emergent_themes", [])),
            },
        )
        return data

    def _request_analysis(self, prompt: str, texts: Sequence[str]) -> dict[str, Any]:
        """Invoke the LLM and parse the JSON payload with strict Pydantic validation.

        This method enforces JSON schema validation using Pydantic models.
        Invalid payloads trigger fail-fast behavior with structured logging.
        """
        if not self._use_llm or self._llm_client is None:
            return {}

        cache_key = self._prompt_cache.hash_prompt(prompt, model=self._model) if self._prompt_cache else None

        # Check caches
        semantic_result = self._check_semantic_cache(prompt)
        if semantic_result is not None:
            return semantic_result

        prompt_result = self._check_prompt_cache(cache_key)
        if prompt_result is not None:
            return prompt_result

        # Invoke LLM
        response_content = self._handle_llm_invocation(prompt, texts)
        if response_content is None:
            return self._fallback_payload(texts)

        # Validate and cache
        validated_data = self._validate_and_cache_response(response_content, cache_key, prompt)
        if validated_data is None:
            return self._fallback_payload(texts)

        return validated_data

    def _invoke_completion(self, prompt: str) -> str:
        """Call the Groq client (or injected stub) to score the provided narratives."""

        if self._llm_client is None:
            return ""
        if self._cost_guardrail is not None:
            self._cost_guardrail.reserve(prompt)

        try:
            completion = self._llm_client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            # Try to get more details from the error
            error_details = str(e)
            if hasattr(e, "response") and e.response:
                try:
                    error_details = f"{error_details} - Response: {e.response.text}"
                except:
                    pass

            logger.error(
                "groq_api_error",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": error_details,
                    "model": self._model,
                    "prompt_length": len(prompt),
                    "prompt_preview": prompt[:200] + "..." if len(prompt) > 200 else prompt,
                },
            )
            raise

    def _build_user_prompt(self, texts: Sequence[str]) -> str:
        joined = "\n".join(f"- {text}" for text in texts[:10])
        return (
            f"{self._prompt_template}\n\n"
            "Narratives to analyze:\n"
            f"{joined}\n\n"
            "Respond with ONLY valid JSON, no markdown formatting."
        )

    @staticmethod
    def _fallback_payload(texts: Sequence[str]) -> dict[str, Any]:
        combined = " ".join(texts)
        tokens = [token.lower() for token in re.findall(r"[#@]?[A-Za-z0-9_]{3,}", combined)]
        counts = Counter(tokens)
        positive_hits = sum(counts[token] for token in _POSITIVE_WORDS if token in counts)
        negative_hits = sum(counts[token] for token in _NEGATIVE_WORDS if token in counts)
        total = positive_hits + negative_hits
        if total == 0:
            score = 0.5
        else:
            score = 0.5 + 0.4 * (positive_hits - negative_hits) / max(total, 1)
        score = float(np.clip(score, 0.0, 1.0))

        hooks = [token for token in tokens if token.startswith("#")][:5]
        themes = [token for token, _ in counts.most_common() if token not in _STOPWORDS and not token.startswith("#")]
        themes = [theme for theme in themes if len(theme) > 3][:5]
        warning = any(token in _RISK_WORDS for token in tokens)

        return {
            "sentiment": "positive" if score > 0.55 else "negative" if score < 0.45 else "neutral",
            "sentiment_score": score,
            "emergent_themes": themes,
            "memetic_hooks": hooks,
            "fake_or_buzz_warning": warning,
            "rationale": "Heuristic fallback generated when Groq analysis is unavailable.",
        }

    def _resolve_client(self, use_llm: bool) -> Any | None:
        if not use_llm:
            return None
        if self._provided_client is not None:
            return self._provided_client
        if not _GROQ_AVAILABLE:
            return None
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        try:
            client = Groq(api_key=api_key)
        except Exception:  # pragma: no cover - runtime configuration errors
            return None
        else:
            print("✓ Groq LLM enabled for narrative analysis")
            return client

    def _load_prompt_template(self) -> str:
        prompt_path = Path("prompts/narrative_analyzer.md")
        if prompt_path.exists():
            try:
                return prompt_path.read_text()
            except OSError:  # pragma: no cover - filesystem edge case
                return _DEFAULT_PROMPT
        return _DEFAULT_PROMPT


def _as_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_str_list(value: Any) -> List[str]:
    if not isinstance(value, (list, tuple)):
        return []
    results: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            results.append(item.strip())
    return results


def _clean_json_response(content: str) -> str:
    content = content.strip()
    if not content:
        return "{}"
    if content.startswith("```"):
        parts = content.split("```")
        if len(parts) >= 2:
            candidate = parts[1]
            if candidate.startswith("json"):
                candidate = candidate[4:]
            content = candidate.strip()
    return content
