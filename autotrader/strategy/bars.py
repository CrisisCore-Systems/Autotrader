from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd


class TickToBarAggregator:
    def __init__(self, bar_frequency: str = "1m", *, emit_empty_bars: bool = True):
        self.bar_frequency = self._normalize_bar_frequency(bar_frequency)
        self.emit_empty_bars = bool(emit_empty_bars)
        self._bar_delta = pd.Timedelta(self.bar_frequency)
        self._active_bars: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _normalize_bar_frequency(raw: str) -> str:
        normalized = str(raw).strip().lower()
        mapping = {"1m": "1min", "5m": "5min", "15m": "15min"}
        if normalized not in mapping:
            raise ValueError("bar_frequency must be one of: 1m, 5m, 15m")
        return mapping[normalized]

    @staticmethod
    def _normalize_timestamp(value: Any) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")

    def _bar_start(self, timestamp: pd.Timestamp) -> pd.Timestamp:
        return timestamp.floor(self.bar_frequency)

    def _bar_end(self, bar_start: pd.Timestamp) -> pd.Timestamp:
        return bar_start + self._bar_delta

    @staticmethod
    def _symbol_key(symbol: str) -> str:
        return str(symbol).upper().strip()

    def _start_bar(
        self,
        *,
        symbol: str,
        bar_start: pd.Timestamp,
        bid: float,
        ask: float,
        bid_size: Optional[float],
        ask_size: Optional[float],
    ) -> Dict[str, Any]:
        normalized_bid_size = float(bid_size or 0.0)
        normalized_ask_size = float(ask_size or 0.0)
        mid = (float(bid) + float(ask)) / 2.0
        spread_bps = ((float(ask) - float(bid)) / mid) * 10_000.0 if mid > 0 else 0.0
        return {
            "symbol": symbol,
            "bar_start_ts": bar_start,
            "bar_end_ts": self._bar_end(bar_start),
            "open_bid": float(bid),
            "open_ask": float(ask),
            "high_bid": float(bid),
            "high_ask": float(ask),
            "low_bid": float(bid),
            "low_ask": float(ask),
            "close_bid": float(bid),
            "close_ask": float(ask),
            "mid_open": float(mid),
            "mid_high": float(mid),
            "mid_low": float(mid),
            "mid_close": float(mid),
            "tick_count": 1,
            "volume_proxy": float(normalized_bid_size + normalized_ask_size),
            "ofi_bar": float(normalized_bid_size - normalized_ask_size),
            "spread_bps_open": float(spread_bps),
            "spread_bps_close": float(spread_bps),
            "spread_bps_mean": float(spread_bps),
            "spread_bps_max": float(spread_bps),
            "empty_bar": False,
        }

    def _start_empty_bar(self, *, symbol: str, bar_start: pd.Timestamp, prior_bar: Dict[str, Any]) -> Dict[str, Any]:
        close_bid = float(prior_bar["close_bid"])
        close_ask = float(prior_bar["close_ask"])
        mid_close = float(prior_bar["mid_close"])
        spread_bps_close = float(prior_bar["spread_bps_close"])
        return {
            "symbol": symbol,
            "bar_start_ts": bar_start,
            "bar_end_ts": self._bar_end(bar_start),
            "open_bid": close_bid,
            "open_ask": close_ask,
            "high_bid": close_bid,
            "high_ask": close_ask,
            "low_bid": close_bid,
            "low_ask": close_ask,
            "close_bid": close_bid,
            "close_ask": close_ask,
            "mid_open": mid_close,
            "mid_high": mid_close,
            "mid_low": mid_close,
            "mid_close": mid_close,
            "tick_count": 0,
            "volume_proxy": 0.0,
            "ofi_bar": 0.0,
            "spread_bps_open": spread_bps_close,
            "spread_bps_close": spread_bps_close,
            "spread_bps_mean": spread_bps_close,
            "spread_bps_max": spread_bps_close,
            "empty_bar": True,
        }

    @staticmethod
    def _copy_bar(bar: Dict[str, Any]) -> Dict[str, Any]:
        return dict(bar)

    @staticmethod
    def _update_running_mean(current_mean: float, current_count: int, new_value: float) -> float:
        if current_count <= 0:
            return float(new_value)
        return float(((current_mean * current_count) + new_value) / float(current_count + 1))

    def _update_bar(
        self,
        bar: Dict[str, Any],
        *,
        bid: float,
        ask: float,
        bid_size: Optional[float],
        ask_size: Optional[float],
    ) -> None:
        normalized_bid_size = float(bid_size or 0.0)
        normalized_ask_size = float(ask_size or 0.0)
        mid = (float(bid) + float(ask)) / 2.0
        spread_bps = ((float(ask) - float(bid)) / mid) * 10_000.0 if mid > 0 else 0.0
        current_tick_count = int(bar["tick_count"])

        bar["high_bid"] = max(float(bar["high_bid"]), float(bid))
        bar["high_ask"] = max(float(bar["high_ask"]), float(ask))
        bar["low_bid"] = min(float(bar["low_bid"]), float(bid))
        bar["low_ask"] = min(float(bar["low_ask"]), float(ask))
        bar["close_bid"] = float(bid)
        bar["close_ask"] = float(ask)
        bar["mid_high"] = max(float(bar["mid_high"]), float(mid))
        bar["mid_low"] = min(float(bar["mid_low"]), float(mid))
        bar["mid_close"] = float(mid)
        bar["tick_count"] = current_tick_count + 1
        bar["volume_proxy"] = float(bar["volume_proxy"]) + float(normalized_bid_size + normalized_ask_size)
        bar["ofi_bar"] = float(bar["ofi_bar"]) + float(normalized_bid_size - normalized_ask_size)
        bar["spread_bps_close"] = float(spread_bps)
        bar["spread_bps_mean"] = self._update_running_mean(float(bar["spread_bps_mean"]), current_tick_count, spread_bps)
        bar["spread_bps_max"] = max(float(bar["spread_bps_max"]), float(spread_bps))

    def update(
        self,
        *,
        symbol: str,
        timestamp: Any,
        bid: float,
        ask: float,
        bid_size: Optional[float],
        ask_size: Optional[float],
    ) -> List[Dict[str, Any]]:
        normalized_symbol = self._symbol_key(symbol)
        normalized_ts = self._normalize_timestamp(timestamp)
        current_bar_start = self._bar_start(normalized_ts)
        active_bar = self._active_bars.get(normalized_symbol)

        if active_bar is None:
            self._active_bars[normalized_symbol] = self._start_bar(
                symbol=normalized_symbol,
                bar_start=current_bar_start,
                bid=bid,
                ask=ask,
                bid_size=bid_size,
                ask_size=ask_size,
            )
            return []

        if current_bar_start == active_bar["bar_start_ts"]:
            self._update_bar(active_bar, bid=bid, ask=ask, bid_size=bid_size, ask_size=ask_size)
            return []

        emitted: List[Dict[str, Any]] = [self._copy_bar(active_bar)]
        prior_bar = active_bar
        next_bar_start = self._bar_end(pd.Timestamp(active_bar["bar_start_ts"]))
        while self.emit_empty_bars and next_bar_start < current_bar_start:
            empty_bar = self._start_empty_bar(symbol=normalized_symbol, bar_start=next_bar_start, prior_bar=prior_bar)
            emitted.append(empty_bar)
            prior_bar = empty_bar
            next_bar_start = self._bar_end(next_bar_start)

        self._active_bars[normalized_symbol] = self._start_bar(
            symbol=normalized_symbol,
            bar_start=current_bar_start,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
        )
        return emitted

    def flush(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        if symbol is None:
            symbols = list(self._active_bars.keys())
        else:
            symbols = [self._symbol_key(symbol)]

        emitted: List[Dict[str, Any]] = []
        for normalized_symbol in symbols:
            active_bar = self._active_bars.pop(normalized_symbol, None)
            if active_bar is not None:
                emitted.append(self._copy_bar(active_bar))
        return emitted