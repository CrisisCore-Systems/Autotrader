"""Regime detection utilities for BounceHunter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd
import yfinance as yf


@dataclass(slots=True)
class RegimeState:
    """Current market regime assessment."""

    is_high_vix: bool
    is_spy_stressed: bool
    vix_percentile: float
    spy_dist_200dma: float
    effective_bcs_threshold: float
    effective_size_pct: float

    @property
    def is_risk_off(self) -> bool:
        """True if either high-VIX or SPY stress detected."""
        return self.is_high_vix or self.is_spy_stressed

    def description(self) -> str:
        """Human-readable regime summary."""
        if self.is_spy_stressed:
            return "SPY stress (< 90% of 200DMA)"
        if self.is_high_vix:
            return f"High VIX ({self.vix_percentile:.0%} percentile)"
        return "Normal regime"


class RegimeDetector:
    """Assess market conditions and adjust thresholds."""

    def __init__(
        self,
        vix_lookback_days: int = 252,
        highvix_percentile: float = 0.80,
        spy_stress_multiplier: float = 0.90,
    ) -> None:
        self.vix_lookback = vix_lookback_days
        self.highvix_pctile = highvix_percentile
        self.spy_stress_mult = spy_stress_multiplier
        self._vix_cache: Optional[pd.DataFrame] = None
        self._spy_cache: Optional[pd.DataFrame] = None

    def detect(
        self,
        as_of: pd.Timestamp,
        bcs_base: float,
        bcs_highvix: float,
        size_base: float,
        size_highvix: float,
    ) -> RegimeState:
        """Compute regime state and return adjusted thresholds."""
        vix_pctile = self._compute_vix_percentile(as_of)
        is_high_vix = vix_pctile >= self.highvix_pctile

        spy_dist = self._compute_spy_distance_200dma(as_of)
        # SPY stressed if trading below 90% of its 200DMA
        is_spy_stressed = spy_dist < (self.spy_stress_mult - 1.0)

        # Use high-VIX settings if either condition triggers
        risk_off = is_high_vix or is_spy_stressed
        effective_bcs = bcs_highvix if risk_off else bcs_base
        effective_size = size_highvix if risk_off else size_base

        return RegimeState(
            is_high_vix=is_high_vix,
            is_spy_stressed=is_spy_stressed,
            vix_percentile=vix_pctile,
            spy_dist_200dma=spy_dist,
            effective_bcs_threshold=effective_bcs,
            effective_size_pct=effective_size,
        )

    def _compute_vix_percentile(self, as_of: pd.Timestamp) -> float:
        """Fetch VIX and compute percentile rank over lookback window."""
        if self._vix_cache is None or as_of not in self._vix_cache.index:
            # Fetch more history than needed to ensure we have enough data
            start = as_of - pd.Timedelta(days=self.vix_lookback + 100)
            vix_ticker = yf.Ticker("^VIX")
            hist = vix_ticker.history(start=start, end=as_of + pd.Timedelta(days=1))
            if hist.empty:
                return 0.5  # fallback to neutral
            self._vix_cache = hist[["Close"]].rename(columns={"Close": "vix"})

        # Get most recent lookback_days of VIX
        recent = self._vix_cache[self._vix_cache.index <= as_of].tail(self.vix_lookback)
        if len(recent) < 50:
            return 0.5  # insufficient data

        current_vix = recent["vix"].iloc[-1]
        percentile = (recent["vix"] < current_vix).sum() / len(recent)
        return float(percentile)

    def _compute_spy_distance_200dma(self, as_of: pd.Timestamp) -> float:
        """Compute SPY's distance from its 200-day moving average."""
        if self._spy_cache is None or as_of not in self._spy_cache.index:
            start = as_of - pd.Timedelta(days=300)
            spy_ticker = yf.Ticker("SPY")
            hist = spy_ticker.history(start=start, end=as_of + pd.Timedelta(days=1))
            if hist.empty:
                return 0.0  # fallback
            self._spy_cache = hist[["Close"]]

        recent = self._spy_cache[self._spy_cache.index <= as_of].tail(210)
        if len(recent) < 200:
            return 0.0

        current_price = recent["Close"].iloc[-1]
        ma200 = recent["Close"].rolling(200).mean().iloc[-1]
        return float((current_price / ma200) - 1.0)
