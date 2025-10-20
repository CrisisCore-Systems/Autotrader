"""Configuration primitives for the BounceHunter scanner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Sequence


DEFAULT_TICKERS: Sequence[str] = (
    "AAPL",
    "MSFT",
    "NVDA",
    "META",
    "AMZN",
    "GOOGL",
    "AMD",
    "AVGO",
    "COST",
    "PEP",
    "KO",
    "MCD",
    "UNH",
    "XOM",
    "JNJ",
    "PG",
    "V",
    "MA",
    "NFLX",
    "TSLA",
    "SPY",
    "QQQ",
)


@dataclass(slots=True)
class BounceHunterConfig:
    """Tunable hyperparameters for mean-reversion scouting.

    All thresholds are expressed as decimals (e.g., 0.03 == 3%).
    """

    # Universe
    tickers: Sequence[str] = field(default_factory=lambda: list(DEFAULT_TICKERS))
    start: str = "2018-01-01"
    min_adv_usd: float = 5_000_000.0

    # Entry filters
    z_score_drop: float = -1.5
    rsi2_max: float = 10.0
    max_dist_200dma: float = -0.12
    bcs_threshold: float = 0.62
    bcs_threshold_highvix: float = 0.68

    # Exit rules
    rebound_pct: float = 0.03
    stop_pct: float = 0.03
    horizon_days: int = 5

    # Earnings protection
    skip_earnings: bool = True
    earnings_window_days: int = 5
    earnings_fetch_limit: int = 24
    skip_earnings_for_etfs: bool = True

    # Falling knife filter
    falling_knife_tolerance: float = -0.2
    falling_knife_lookback: int = 63

    # Training requirements
    min_event_samples: int = 40
    trailing_trend_window: int = 252
    trend_floor: float = 0.0

    # Regime detection
    vix_lookback_days: int = 252
    highvix_percentile: float = 0.80
    spy_stress_multiplier: float = 0.90

    # Position sizing
    size_pct_base: float = 0.012
    size_pct_highvix: float = 0.006

    # Portfolio limits
    max_concurrent: int = 8
    max_per_sector: int = 3

    # Portfolio limits
    max_concurrent: int = 8
    max_per_sector: int = 3

    def with_tickers(self, tickers: Iterable[str]) -> "BounceHunterConfig":
        tickers_list: List[str] = list(tickers)
        if not tickers_list:
            raise ValueError("Ticker universe cannot be empty.")
        # Return new instance with updated tickers but same other params
        return BounceHunterConfig(
            tickers=tickers_list,
            start=self.start,
            min_adv_usd=self.min_adv_usd,
            z_score_drop=self.z_score_drop,
            rsi2_max=self.rsi2_max,
            max_dist_200dma=self.max_dist_200dma,
            bcs_threshold=self.bcs_threshold,
            bcs_threshold_highvix=self.bcs_threshold_highvix,
            rebound_pct=self.rebound_pct,
            stop_pct=self.stop_pct,
            horizon_days=self.horizon_days,
            skip_earnings=self.skip_earnings,
            earnings_window_days=self.earnings_window_days,
            earnings_fetch_limit=self.earnings_fetch_limit,
            skip_earnings_for_etfs=self.skip_earnings_for_etfs,
            falling_knife_tolerance=self.falling_knife_tolerance,
            falling_knife_lookback=self.falling_knife_lookback,
            min_event_samples=self.min_event_samples,
            trailing_trend_window=self.trailing_trend_window,
            trend_floor=self.trend_floor,
            vix_lookback_days=self.vix_lookback_days,
            highvix_percentile=self.highvix_percentile,
            spy_stress_multiplier=self.spy_stress_multiplier,
            size_pct_base=self.size_pct_base,
            size_pct_highvix=self.size_pct_highvix,
            max_concurrent=self.max_concurrent,
            max_per_sector=self.max_per_sector,
        )
