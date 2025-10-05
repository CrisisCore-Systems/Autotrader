from __future__ import annotations

import time
from typing import Any

from src.services.llm_guardrails import PromptCache, SemanticCache


def _fake_embed(text: str) -> list[float]:
    return [float(len(text)), float(sum(ord(ch) for ch in text) % 100) / 100]


def test_prompt_cache_expires_entries() -> None:
    cache = PromptCache(ttl_seconds=0.01)
    cache.set("foo", {"value": 1})
    assert cache.get("foo") == {"value": 1}
    time.sleep(0.02)
    assert cache.get("foo") is None


def test_semantic_cache_returns_payload_for_same_prompt() -> None:
    cache = SemanticCache(embedder=_fake_embed, default_ttl_seconds=10)
    payload: dict[str, Any] = {"result": "ok"}
    cache.set("analyse this", payload, task_type="narrative_summary")
    assert cache.get("analyse this", task_type="narrative_summary") == payload


def test_semantic_cache_distinguishes_task_types() -> None:
    cache = SemanticCache(embedder=_fake_embed, default_ttl_seconds=10)
    payload = {"result": "ok"}
    cache.set("prompt", payload, task_type="summary")
    assert cache.get("prompt", task_type="other") is None


def test_semantic_cache_honours_task_specific_ttl() -> None:
    cache = SemanticCache(embedder=_fake_embed, default_ttl_seconds=10, per_task_ttl={"headlines": 0.01})
    cache.set("prompt", {"value": 1}, task_type="headlines")
    assert cache.get("prompt", task_type="headlines") == {"value": 1}
    time.sleep(0.02)
    assert cache.get("prompt", task_type="headlines") is None


