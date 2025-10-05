"""LLM-backed narrative analysis utilities for scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence

import numpy as np


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


class NarrativeAnalyzer:
    """Narrative analyzer powered by GPT-4 style sentiment synthesis."""

    def __init__(
        self,
        *,
        client: Optional[Any] = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.2,
    ) -> None:
        self._client = client
        self._model = model
        self._temperature = temperature

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

        payload = self._request_analysis(texts)
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

    def _request_analysis(self, texts: Sequence[str]) -> dict[str, Any]:
        """Invoke the LLM and parse the JSON payload it returns."""

        try:
            response_content = self._invoke_completion(texts)
        except Exception:
            return {}

        try:
            data = json.loads(response_content)
        except json.JSONDecodeError:
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _invoke_completion(self, texts: Sequence[str]) -> str:
        """Call the OpenAI client to score the provided narratives."""

        client = self._client or _create_default_openai_client()
        prompt = self._build_user_prompt(texts)
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
