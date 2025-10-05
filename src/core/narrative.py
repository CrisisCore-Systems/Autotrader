"""Simple narrative analysis utilities for scoring."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List

import numpy as np

_POSITIVE_TOKENS = {
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
_NEGATIVE_TOKENS = {
    "hack",
    "rug",
    "exploit",
    "down",
    "selloff",
    "delay",
    "halt",
    "bug",
    "reorg",
    "bankrupt",
}


@dataclass
class NarrativeInsight:
    sentiment_score: float
    momentum: float
    themes: List[str]
    volatility: float
    meme_momentum: float


class NarrativeAnalyzer:
    """Lightweight sentiment estimator built for deterministic tests."""

    def analyze(self, narratives: Iterable[str]) -> NarrativeInsight:
        texts = [text.strip().lower() for text in narratives if text.strip()]
        if not texts:
            return NarrativeInsight(
                sentiment_score=0.5,
                momentum=0.5,
                themes=[],
                volatility=0.0,
                meme_momentum=0.0,
            )

        scores: List[float] = []
        token_counter: Counter[str] = Counter()
        meme_hits = 0
        token_count = 0
        for text in texts:
            tokens = [token.strip(".,!?") for token in text.split()]
            token_counter.update(tokens)
            positive_hits = sum(1 for token in tokens if token in _POSITIVE_TOKENS)
            negative_hits = sum(1 for token in tokens if token in _NEGATIVE_TOKENS)
            meme_hits += sum(1 for token in tokens if token in _POSITIVE_TOKENS)
            token_count += len(tokens)
            magnitude = positive_hits + negative_hits
            if magnitude == 0:
                sentiment = 0.5
            else:
                sentiment = (positive_hits - negative_hits) / max(magnitude, 1)
                sentiment = 0.5 + 0.5 * np.clip(sentiment, -1.0, 1.0)
            scores.append(float(sentiment))

        sentiment_score = float(np.clip(np.mean(scores), 0.0, 1.0))
        momentum = float(np.clip((scores[-1] - scores[0]) * 0.5 + 0.5 if len(scores) > 1 else sentiment_score, 0.0, 1.0))
        themes = [token for token, _ in token_counter.most_common(5) if len(token) >= 5]

        volatility = float(np.clip(np.std(scores) * 2.0, 0.0, 1.0))
        if token_count == 0:
            meme_momentum = 0.0
        else:
            meme_ratio = meme_hits / token_count
            meme_momentum = float(np.clip(0.5 + meme_ratio, 0.0, 1.0))

        return NarrativeInsight(
            sentiment_score=sentiment_score,
            momentum=momentum,
            themes=themes,
            volatility=volatility,
            meme_momentum=meme_momentum,
        )
