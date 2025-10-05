"""Tests for the GPT-backed narrative analyzer."""

from __future__ import annotations

from src.core.narrative import NarrativeAnalyzer
from tests.stubs import StubOpenAIClient


def test_narrative_analyzer_scores_sentiment() -> None:
    stub = StubOpenAIClient(
        payload={
            "sentiment": "positive",
            "sentiment_score": 0.82,
            "emergent_themes": ["growth", "partnership"],
            "memetic_hooks": ["mainnet hype"],
            "fake_or_buzz_warning": False,
            "rationale": "Strong roadmap execution.",
        }
    )
    analyzer = NarrativeAnalyzer(client=stub)
    insight = analyzer.analyze(["Bullish growth and partnership expansion", "Minor delay but launch remains on track"])
    assert insight.sentiment_score == 0.82
    assert 0.0 <= insight.momentum <= 1.0
    assert insight.themes == ["growth", "partnership"]
    assert 0.0 <= insight.volatility <= 1.0
    assert insight.meme_momentum > 0.4


def test_narrative_analyzer_defaults_without_text() -> None:
    analyzer = NarrativeAnalyzer()
    insight = analyzer.analyze([])
    assert insight.sentiment_score == 0.5
    assert insight.momentum == 0.5
    assert insight.themes == []
    assert insight.volatility == 0.0
    assert insight.meme_momentum == 0.0
