"""LLM-backed narrative analysis utilities for scoring."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence

import numpy as np

from src.services.llm_guardrails import BudgetExceeded, LLMBudgetGuardrail, PromptCache

@dataclass
class NarrativeInsight:
    sentiment_score: float
    momentum: float
    themes: List[str]
    volatility: float
    meme_momentum: float


_SYSTEM_PROMPT = (
    "You are Narrative GPT, an analyst focused on cryptocurrency discourse. "
    "Always respond with a single JSON object containing the keys "
    "'sentiment', 'sentiment_score', 'emergent_themes', 'memetic_hooks', "
    "'fake_or_buzz_warning', and 'rationale'."
)

_POSITIVE_WORDS = {
    "bullish",
    "growth",
    "surge",
    "pump",
    "partnership",
    "upgrade",
    "launch",
    "mainnet",
    "win",
    "support",
}
_NEGATIVE_WORDS = {
    "bearish",
    "dump",
    "hack",
    "exploit",
    "delay",
    "rug",
    "lawsuit",
    "selloff",
    "liquidation",
    "risk",
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
    """Narrative analyzer powered by GPT-4 style sentiment synthesis."""

    def __init__(
        self,
        *,
        client: Optional[Any] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
        prompt_cache: PromptCache | None = None,
        cost_guardrail: LLMBudgetGuardrail | None = None,
        cache_ttl_seconds: float = 86400.0,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature
        self._prompt_cache = prompt_cache if prompt_cache is not None else PromptCache(ttl_seconds=cache_ttl_seconds)
        self._cache_ttl = cache_ttl_seconds
        self._cost_guardrail = cost_guardrail

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
        payload = self._request_analysis(prompt, texts)
        sentiment_score = float(np.clip(_as_float(payload.get("sentiment_score"), default=0.5), 0.0, 1.0))
        themes = _as_str_list(payload.get("emergent_themes"))
        meme_hooks = _as_str_list(payload.get("memetic_hooks"))
        fake_warning = bool(payload.get("fake_or_buzz_warning", False))

        momentum = float(
            np.clip(
                sentiment_score
                + 0.15 * (1 if meme_hooks else 0)
                - 0.2 * (1 if fake_warning else 0),
                0.0,
                1.0,
            )
        )
        volatility = float(
            np.clip(
                0.25
                + 0.35 * (1 if fake_warning else 0)
                + 0.1 * min(len(meme_hooks), 3)
                + 0.2 * (1 - abs(sentiment_score - 0.5) * 2),
                0.0,
                1.0,
            )
        )
        meme_momentum = float(np.clip(0.35 + 0.18 * len(meme_hooks), 0.0, 1.0))

        return NarrativeInsight(
            sentiment_score=sentiment_score,
            momentum=momentum,
            themes=themes,
            volatility=volatility,
            meme_momentum=meme_momentum,
        )

    def _request_analysis(self, prompt: str, texts: Sequence[str]) -> dict[str, Any]:
        """Invoke the LLM and parse the JSON payload it returns."""

        cache_key = self._prompt_cache.hash_prompt(prompt, model=self._model) if self._prompt_cache else None
        if cache_key and self._prompt_cache:
            cached = self._prompt_cache.get(cache_key)
            if cached is not None:
                return dict(cached)

        try:
            response_content = self._invoke_completion(prompt)
        except BudgetExceeded:
            payload = self._fallback_payload(texts)
            if cache_key and self._prompt_cache:
                self._prompt_cache.set(cache_key, payload, ttl=self._cache_ttl)
            return payload
        except Exception:
            return {}

        try:
            data = json.loads(response_content)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        if cache_key and self._prompt_cache:
            self._prompt_cache.set(cache_key, data, ttl=self._cache_ttl)
        return data

    def _invoke_completion(self, prompt: str) -> str:
        """Call the OpenAI client to score the provided narratives."""

        client = self._client or _create_default_openai_client()
        if self._cost_guardrail is not None:
            self._cost_guardrail.reserve(prompt)
        completion = client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        )
        return completion.choices[0].message.content or ""

    @staticmethod
    def _build_user_prompt(texts: Sequence[str]) -> str:
        joined = "\n".join(f"- {text}" for text in texts)
        return (
            "Evaluate the following crypto narratives. "
            "Return the JSON object described by the system instructions with fields populated from your analysis.\n"
            f"Narratives:\n{joined}"
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

        hooks = [token for token in tokens if token.startswith("#")][:3]
        themes = [token for token, _ in counts.most_common() if token not in _STOPWORDS and not token.startswith("#")]
        themes = [theme for theme in themes if len(theme) > 3][:5]
        warning = any(token in _RISK_WORDS for token in tokens)

        return {
            "sentiment": "positive" if score > 0.55 else "negative" if score < 0.45 else "neutral",
            "sentiment_score": score,
            "emergent_themes": themes,
            "memetic_hooks": hooks,
            "fake_or_buzz_warning": warning,
            "rationale": "Heuristic fallback generated when GPT budget guardrail is hit.",
        }


def _create_default_openai_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - triggered only when dependency missing
        raise RuntimeError("openai package is required for NarrativeAnalyzer") from exc
    return OpenAI()


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
