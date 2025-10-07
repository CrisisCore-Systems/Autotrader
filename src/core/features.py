"""Feature extraction utilities for the Hidden-Gem Scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd


@dataclass
class MarketSnapshot:
    """Represents normalized market data for a token."""

    symbol: str
    timestamp: datetime
    price: float
    volume_24h: float
    liquidity_usd: float
    holders: int
    onchain_metrics: Dict[str, float]
    narratives: List[str]


def compute_time_series_features(price_series: pd.Series) -> Dict[str, float]:
    """Compute basic technical indicators on closing price data.

    The helper intentionally prefers robustness over precision. Many of the
    pipelines that will call this function operate on sparse or short time
    series windows, so we guard against division-by-zero, `NaN`, or
    insufficient sample sizes when deriving indicators.

    Parameters
    ----------
    price_series:
        Pandas Series indexed by datetime with price values.
    """

    if price_series is None or price_series.empty:
        return {"rsi": 0.5, "macd": 0.0, "volatility": 0.0}

    clean_series = price_series.dropna()
    if clean_series.empty:
        return {"rsi": 0.5, "macd": 0.0, "volatility": 0.0}

    returns = clean_series.pct_change().dropna()
    if returns.empty:
        volatility = 0.0
    else:
        volatility = float(returns.std() * np.sqrt(min(len(returns), 24)))

    delta = clean_series.diff().dropna()
    if delta.empty:
        rsi = 0.5
    else:
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        window = 14
        avg_gain = gain.rolling(window=window, min_periods=window).mean()
        avg_loss = loss.rolling(window=window, min_periods=window).mean()
        last_gain = avg_gain.dropna().iloc[-1] if not avg_gain.dropna().empty else gain.mean()
        last_loss = avg_loss.dropna().iloc[-1] if not avg_loss.dropna().empty else loss.mean()
        if last_loss == 0:
            rsi = 1.0
        else:
            rs = last_gain / last_loss
            rsi = 1 - (1 / (1 + rs))

    ema12 = clean_series.ewm(span=12, adjust=False).mean()
    ema26 = clean_series.ewm(span=26, adjust=False).mean()
    macd = float((ema12 - ema26).iloc[-1]) if not ema12.empty and not ema26.empty else 0.0

    return {
        "rsi": float(np.clip(rsi, 0, 1)),
        "macd": macd,
        "volatility": float(volatility),
    }


def normalize_feature(
    value: Optional[float], *, default: float = 0.0, max_value: float = 1.0
) -> float:
    """Clamp feature values into 0-1 range with graceful fallback.

    Parameters
    ----------
    value:
        The raw feature value to normalise.
    default:
        Value returned when ``value`` is missing or invalid.
    max_value:
        Denominator used for scaling. Must be positive to avoid division
        errors.
    """

    if max_value <= 0:
        raise ValueError("max_value must be positive")

    if value is None:
        return default
    if not np.isfinite(value):
        return default
    return float(np.clip(value / max_value, 0.0, 1.0))


def build_feature_vector(
    market_snapshot: MarketSnapshot,
    price_features: Dict[str, float],
    narrative_embedding_score: float,
    contract_metrics: Dict[str, float],
    *,
    narrative_momentum: float,
) -> Dict[str, float]:
    """Combine heterogeneous features into the GemScore feature vector."""

    liquidity_depth = normalize_feature(market_snapshot.liquidity_usd, max_value=5_000_000)
    onchain_activity = normalize_feature(
        market_snapshot.onchain_metrics.get("active_wallets"),
        max_value=10_000,
    )
    accumulation_score = normalize_feature(
        market_snapshot.onchain_metrics.get("net_inflows"),
        max_value=1_000_000,
    )

    tokenomics_risk = 1 - normalize_feature(
        market_snapshot.onchain_metrics.get("unlock_pressure"),
        max_value=1.0,
    )
    upcoming_unlock_risk = float(
        np.clip(market_snapshot.onchain_metrics.get("upcoming_unlock_risk", 0.0), 0.0, 1.0)
    )
    if upcoming_unlock_risk >= 0.5:
        tokenomics_risk = min(tokenomics_risk, 0.4)

    vector = {
        "SentimentScore": float(np.clip(narrative_embedding_score, 0.0, 1.0)),
        "AccumulationScore": accumulation_score,
        "OnchainActivity": onchain_activity,
        "LiquidityDepth": liquidity_depth,
        "TokenomicsRisk": tokenomics_risk,
        "ContractSafety": contract_metrics.get("score", 0.0),
        "NarrativeMomentum": float(np.clip(narrative_momentum, 0.0, 1.0)),
        "CommunityGrowth": normalize_feature(market_snapshot.holders, max_value=500_000),
        "UpcomingUnlockRisk": upcoming_unlock_risk,
        "RSI": price_features.get("rsi", 0.5),
        "MACD": price_features.get("macd", 0.0),
        "Volatility": price_features.get("volatility", 0.0),
    }

    return vector


def merge_feature_vectors(vectors: Iterable[Dict[str, float]]) -> Dict[str, float]:
    """Average multiple feature vectors (e.g., across time windows)."""

    vectors = list(vectors)
    if not vectors:
        return {}

    keys = {k for vector in vectors for k in vector}
    aggregated = {}
    for key in keys:
        aggregated[key] = float(np.mean([vector.get(key, 0.0) for vector in vectors]))
    return aggregated
