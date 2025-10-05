"""Tests for the lightweight narrative analyzer."""

from __future__ import annotations

from src.core.narrative import NarrativeAnalyzer


def test_narrative_analyzer_scores_sentiment() -> None:
    analyzer = NarrativeAnalyzer()
    insight = analyzer.analyze(["Bullish growth and partnership expansion", "Minor delay but launch remains on track"])
    assert 0.0 <= insight.sentiment_score <= 1.0
    assert 0.0 <= insight.momentum <= 1.0
    assert isinstance(insight.themes, list)
    assert 0.0 <= insight.volatility <= 1.0
    assert 0.0 <= insight.meme_momentum <= 1.0


def test_narrative_analyzer_defaults_without_text() -> None:
    analyzer = NarrativeAnalyzer()
    insight = analyzer.analyze([])
    assert insight.sentiment_score == 0.5
    assert insight.momentum == 0.5
    assert insight.themes == []
    assert insight.volatility == 0.0
    assert insight.meme_momentum == 0.0
