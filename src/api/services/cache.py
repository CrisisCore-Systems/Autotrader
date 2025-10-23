"""Caching helpers for token scan responses."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, Optional

from ..schemas.token import TokenCacheEntry, TokenSummary


LOGGER = logging.getLogger(__name__)


def _parse_iso_timestamp(value: str) -> datetime:
    """Parse ISO timestamps including ``Z`` suffix to naive UTC datetimes."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        # Parse as timezone-aware and convert to naive UTC
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except ValueError:
        return datetime.utcnow()


def _build_summary(detail: Dict[str, object]) -> TokenSummary:
    """Build a cached summary payload from a full token detail response."""
    return TokenSummary(
        symbol=str(detail["symbol"]),
        price=float(detail["price"]),
        liquidity_usd=float(detail["liquidity_usd"]),
        gem_score=float(detail["gem_score"]),
        final_score=float(detail["final_score"]),
        confidence=float(detail["confidence"]),
        flagged=bool(detail["flagged"]),
        narrative_momentum=float(detail["narrative_momentum"]),
        sentiment_score=float(detail["sentiment_score"]),
        holders=int(detail["holders"]),
        updated_at=str(detail["updated_at"]),
    )


class TokenCache:
    """In-memory cache for token scan results."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._entries: Dict[str, TokenCacheEntry] = {}
        self._ttl_seconds = ttl_seconds

    def put(self, symbol: str, detail: Dict[str, object]) -> TokenCacheEntry:
        """Store a token detail payload and derived summary in the cache."""
        timestamp = datetime.utcnow()
        updated_at_iso = detail.get("updated_at")
        if isinstance(updated_at_iso, str):
            timestamp = _parse_iso_timestamp(updated_at_iso)

        entry: TokenCacheEntry = {
            "detail": detail,
            "summary": _build_summary(detail),
            "timestamp": timestamp,
        }
        normalized_symbol = symbol.upper()
        LOGGER.debug(
            "cache_store symbol=%s detail_symbol=%s",
            normalized_symbol,
            detail.get("symbol"),
        )
        self._entries[normalized_symbol] = entry
        return entry

    def get(self, symbol: str) -> Optional[TokenCacheEntry]:
        """Return a cache entry for ``symbol`` if still valid."""
        normalized_symbol = symbol.upper()
        entry = self._entries.get(normalized_symbol)
        LOGGER.debug(
            "cache_lookup symbol=%s hit=%s keys=%s",
            normalized_symbol,
            entry is not None,
            list(self._entries.keys()),
        )
        if not entry:
            return None

        age_seconds = (datetime.utcnow() - entry["timestamp"]).total_seconds()
        if age_seconds > self._ttl_seconds:
            return None

        return entry

    def clear(self) -> None:
        """Remove all cached entries."""
        self._entries.clear()

    def set_ttl(self, ttl_seconds: int) -> None:
        """Update the cache TTL at runtime."""
        self._ttl_seconds = ttl_seconds
