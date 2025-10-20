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

    tickers: Sequence[str] = field(default_factory=lambda: list(DEFAULT_TICKERS))
    start: str = "2018-01-01"
    rebound_pct: float = 0.03
    horizon_days: int = 5
    stop_pct: float = 0.03
    bcs_threshold: float = 0.62
    z_score_drop: float = -1.5
    rsi2_max: float = 10.0
    max_dist_200dma: float = -0.12
    min_event_samples: int = 40
    min_adv_usd: float = 5_000_000.0
    trailing_trend_window: int = 252
    trend_floor: float = 0.0
    falling_knife_tolerance: float = -0.2
    falling_knife_lookback: int = 63

    def with_tickers(self, tickers: Iterable[str]) -> "BounceHunterConfig":
        tickers_list: List[str] = list(tickers)
        if not tickers_list:
            raise ValueError("Ticker universe cannot be empty.")
        return BounceHunterConfig(
            tickers=tickers_list,
            start=self.start,
            rebound_pct=self.rebound_pct,
            horizon_days=self.horizon_days,
            stop_pct=self.stop_pct,
            bcs_threshold=self.bcs_threshold,
            z_score_drop=self.z_score_drop,
            rsi2_max=self.rsi2_max,
            max_dist_200dma=self.max_dist_200dma,
            min_event_samples=self.min_event_samples,
            min_adv_usd=self.min_adv_usd,
            trailing_trend_window=self.trailing_trend_window,
            trend_floor=self.trend_floor,
            falling_knife_tolerance=self.falling_knife_tolerance,
            falling_knife_lookback=self.falling_knife_lookback,
        )
