"""Utilities for caching and budgeting GPT usage."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Dict, Optional

from collections.abc import Callable, Mapping, Sequence


class BudgetExceeded(RuntimeError):
    """Raised when an LLM request would exceed the configured spend ceiling."""


def _month_start(now: datetime | None = None) -> datetime:
    current = now or datetime.now(tz=timezone.utc)
    return current.replace(day=1, hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)


def _estimate_tokens(text: str) -> int:
    # Cheap approximation: assume 4 characters per token.
    return max(1, math.ceil(len(text) / 4))


@dataclass
class LLMBudgetGuardrail:
    """Tracks and enforces a monthly USD budget for GPT usage."""

    monthly_limit_usd: float
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
    expected_output_tokens: int = 600
    usage_usd: float = 0.0
    window_start: datetime = field(default_factory=_month_start)

    def reserve(self, prompt: str, *, expected_output_tokens: Optional[int] = None) -> float:
        self._maybe_rollover()
        tokens_in = _estimate_tokens(prompt)
        tokens_out = expected_output_tokens or self.expected_output_tokens
        cost = (tokens_in / 1000.0) * self.input_cost_per_1k_tokens
        cost += (tokens_out / 1000.0) * self.output_cost_per_1k_tokens
        if self.usage_usd + cost > self.monthly_limit_usd:
            raise BudgetExceeded(
                f"LLM budget exceeded: {self.usage_usd + cost:.2f} > {self.monthly_limit_usd:.2f} USD"
            )
        self.usage_usd += cost
        return cost

    def remaining_budget(self) -> float:
        self._maybe_rollover()
        return max(self.monthly_limit_usd - self.usage_usd, 0.0)

    def _maybe_rollover(self) -> None:
        now = datetime.now(tz=timezone.utc)
        current_window = _month_start(now)
        if current_window > self.window_start:
            self.window_start = current_window
            self.usage_usd = 0.0


class PromptCache:
    """In-memory TTL cache for prompt/response payloads."""

    def __init__(self, ttl_seconds: float = 86400.0) -> None:
        self._ttl = ttl_seconds
        self._entries: Dict[str, tuple[float, Dict[str, Any]]] = {}

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        entry = self._entries.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at < time.time():
            self._entries.pop(key, None)
            return None
        return dict(payload)

    def set(
        self,
        key: str,
        payload: Mapping[str, Any],
        *,
        ttl: Optional[float] = None,
    ) -> None:
        expiry = time.time() + (ttl if ttl is not None else self._ttl)
        self._entries[key] = (expiry, dict(payload))

    @staticmethod
    def hash_prompt(prompt: str, *, model: str) -> str:
        digest = sha256()
        digest.update(model.encode("utf-8"))
        digest.update(b"|")
        digest.update(prompt.encode("utf-8"))
        return digest.hexdigest()


class SemanticCache:
    """Embedding-aware cache used to short-circuit expensive LLM calls."""

    def __init__(
        self,
        *,
        embedder: Callable[[str], Sequence[float]],
        default_ttl_seconds: float = 43200.0,
        per_task_ttl: Mapping[str, float] | None = None,
        version: str = "v1",
        round_digits: int = 3,
    ) -> None:
        self._embedder = embedder
        self._default_ttl = default_ttl_seconds
        self._per_task_ttl = dict(per_task_ttl or {})
        self._version = version
        self._round_digits = round_digits
        self._entries: Dict[str, tuple[float, tuple[float, ...], Dict[str, Any]]] = {}

    def get(self, prompt: str, *, task_type: str) -> Optional[Dict[str, Any]]:
        key, embedding = self._make_key(prompt, task_type=task_type)
        entry = self._entries.get(key)
        if entry is None:
            return None

        expires_at, cached_embedding, payload = entry
        if expires_at < time.time():
            self._entries.pop(key, None)
            return None

        if not self._is_same_embedding(embedding, cached_embedding):
            return None

        return dict(payload)

    def set(
        self,
        prompt: str,
        payload: Mapping[str, Any],
        *,
        task_type: str,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        key, embedding = self._make_key(prompt, task_type=task_type)
        ttl = ttl_seconds if ttl_seconds is not None else self._per_task_ttl.get(task_type, self._default_ttl)
        expires_at = time.time() + ttl
        self._entries[key] = (expires_at, embedding, dict(payload))

    def purge_expired(self) -> None:
        now = time.time()
        expired = [key for key, (expires_at, _, _) in self._entries.items() if expires_at < now]
        for key in expired:
            self._entries.pop(key, None)

    def _make_key(self, prompt: str, *, task_type: str) -> tuple[str, tuple[float, ...]]:
        embedding = self._rounded_embedding(self._embedder(prompt))
        digest = sha256()
        digest.update("|".join(f"{value:.{self._round_digits}f}" for value in embedding).encode("utf-8"))
        digest.update(b"|")
        digest.update(task_type.encode("utf-8"))
        digest.update(b"|")
        digest.update(self._version.encode("utf-8"))
        return digest.hexdigest(), embedding

    def _rounded_embedding(self, values: Sequence[float]) -> tuple[float, ...]:
        return tuple(round(float(value), self._round_digits) for value in values)

    def _is_same_embedding(self, a: Sequence[float], b: Sequence[float]) -> bool:
        if len(a) != len(b):
            return False
        return all(abs(x - y) <= 10 ** (-self._round_digits) for x, y in zip(a, b))


__all__ = ["BudgetExceeded", "LLMBudgetGuardrail", "PromptCache", "SemanticCache"]
