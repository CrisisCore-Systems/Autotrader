"""Tests for the GPT-backed narrative analyzer."""

from __future__ import annotations

from src.core.narrative import NarrativeAnalyzer
from src.services.llm_guardrails import LLMBudgetGuardrail, PromptCache
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


def test_narrative_analyzer_caches_prompt_responses() -> None:
    stub = StubOpenAIClient(
        payload={
            "sentiment": "positive",
            "sentiment_score": 0.72,
            "emergent_themes": ["layer2"],
            "memetic_hooks": ["#airdrop"],
            "fake_or_buzz_warning": False,
            "rationale": "Momentum from scaling news.",
        }
    )
    cache = PromptCache(ttl_seconds=3600)
    analyzer = NarrativeAnalyzer(client=stub, prompt_cache=cache)

    analyzer.analyze(["Layer2 mainnet growth", "TVL pumping across chains"])
    analyzer.analyze(["Layer2 mainnet growth", "TVL pumping across chains"])

    assert len(stub.invocations) == 1


def test_narrative_analyzer_falls_back_when_budget_hit() -> None:
    guardrail = LLMBudgetGuardrail(
        monthly_limit_usd=0.0001,
        input_cost_per_1k_tokens=0.1,
        output_cost_per_1k_tokens=0.2,
    )
    stub = StubOpenAIClient()
    analyzer = NarrativeAnalyzer(client=stub, cost_guardrail=guardrail)

    insight = analyzer.analyze(["Exploit on bridge raises community concern"])

    # Guardrail should prevent the remote call so the stub is never invoked.
    assert len(stub.invocations) == 0
    assert 0.0 <= insight.sentiment_score <= 1.0
    assert isinstance(insight.themes, list)
