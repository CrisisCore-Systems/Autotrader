"""Test utilities for stubbing external services."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any, Dict, Optional


class StubGroqClient:
    """Minimal stub that mimics the Groq chat completion interface."""

    def __init__(self, payload: Optional[Dict[str, Any]] = None) -> None:
        if payload is None:
            payload = {
                "sentiment": "neutral",
                "sentiment_score": 0.5,
                "emergent_themes": ["baseline"],
                "memetic_hooks": [],
                "fake_or_buzz_warning": False,
                "rationale": "Default stub response.",
            }
        self.payload = payload
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))
        self.invocations: list[Dict[str, Any]] = []

    def _create(self, **kwargs: Any) -> Any:  # noqa: D401 - mimic Groq signature
        self.invocations.append(kwargs)
        message = SimpleNamespace(content=json.dumps(self.payload))
        choice = SimpleNamespace(message=message)
        return SimpleNamespace(choices=[choice])


# Backwards compatibility for older tests/imports
StubOpenAIClient = StubGroqClient
