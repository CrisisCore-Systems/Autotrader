"""Pydantic schemas and lightweight types for token API responses."""

from datetime import datetime
from typing import Any, Dict, TypedDict

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Summary of a scanned token."""

    symbol: str
    price: float
    liquidity_usd: float
    gem_score: float
    final_score: float
    confidence: float
    flagged: bool
    narrative_momentum: float
    sentiment_score: float
    holders: int
    updated_at: str


class TokenSummary(TypedDict):
    """Cached summary payload for a token."""

    symbol: str
    price: float
    liquidity_usd: float
    gem_score: float
    final_score: float
    confidence: float
    flagged: bool
    narrative_momentum: float
    sentiment_score: float
    holders: int
    updated_at: str


class TokenCacheEntry(TypedDict):
    """Internal representation of cached token results."""

    detail: Dict[str, Any]
    summary: TokenSummary
    timestamp: datetime
