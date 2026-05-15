"""
Live market data adapter.

Keeps asynchronous transport I/O isolated from the synchronous execution core,
while feeding heartbeat pulses into the live reconciler and aggregating ticks
into deterministic 15-minute bars.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterable, Awaitable, Callable, Deque, Dict, Iterable, List, Optional

from autotrader.schemas.market_data import AssetClass, OHLCV, Side, Tick


logger = logging.getLogger("autotrader.execution.live.market_data")


@dataclass
class _BarState:
    """Internal mutable bar accumulator."""

    symbol: str
    venue: str
    asset_class: AssetClass
    open_time_us: Optional[int] = None
    close_time_us: Optional[int] = None
    open: Optional[float] = None
    high: float = float("-inf")
    low: float = float("inf")
    close: Optional[float] = None
    volume: float = 0.0
    trade_count: int = 0
    vwap_notional: float = 0.0
    last_event_time_us: Optional[int] = None
    last_exchange_time_us: Optional[int] = None

    def is_empty(self) -> bool:
        return self.trade_count == 0

    def to_completed_bar(self) -> OHLCV:
        if self.open_time_us is None or self.open is None or self.close is None:
            raise ValueError("Cannot finalize empty bar")

        vwap = self.vwap_notional / self.volume if self.volume > 0 else self.close
        return OHLCV(
            timestamp=datetime.fromtimestamp(self.open_time_us / 1_000_000, tz=timezone.utc),
            symbol=self.symbol,
            venue=self.venue,
            asset_class=self.asset_class,
            open=self.open,
            high=self.high if self.high != float("-inf") else self.open,
            low=self.low if self.low != float("inf") else self.open,
            close=self.close,
            volume=self.volume,
            vwap=vwap,
            trade_count=self.trade_count,
        )

    def snapshot(self) -> Dict[str, Any]:
        """Return a JSON-friendly view for callers that prefer dict access."""
        return {
            "symbol": self.symbol,
            "venue": self.venue,
            "asset_class": self.asset_class.value,
            "timestamp_utc": (
                datetime.fromtimestamp(self.open_time_us / 1_000_000, tz=timezone.utc).isoformat()
                if self.open_time_us is not None
                else None
            ),
            "bar_open_time_us": self.open_time_us,
            "bar_close_time_us": self.close_time_us,
            "open": self.open,
            "high": None if self.high == float("-inf") else self.high,
            "low": None if self.low == float("inf") else self.low,
            "close": self.close,
            "volume": self.volume,
            "trade_count": self.trade_count,
            "vwap": self.vwap_notional / self.volume if self.volume > 0 else self.close,
            "last_event_time_us": self.last_event_time_us,
            "last_exchange_time_us": self.last_exchange_time_us,
            "completed": False,
        }


class LiveMarketDataAdapter:
    """Phase 5 live ingestion wrapper.

    Parameters
    ----------
    symbols:
        Symbols to subscribe to.
    reconciler:
        Live reconciler instance or any object exposing ``mark_heartbeat``.
    bar_interval_minutes:
        Aggregation window size.
    rest_fallback_seconds:
        Poll cadence for optional REST fallback provider.
    transport_stream_provider:
        Optional async iterable factory for websocket payloads.
    rest_snapshot_provider:
        Optional provider returning historical/live fallback ticks or bar-like dicts.
    on_completed_bar:
        Optional callback invoked when a bar closes.
    """

    def __init__(
        self,
        symbols: List[str],
        reconciler: Any,
        bar_interval_minutes: int = 15,
        rest_fallback_seconds: int = 5,
        venue: str = "LIVE",
        asset_class: AssetClass = AssetClass.CRYPTO,
        transport_stream_provider: Optional[Callable[[List[str]], AsyncIterable[Dict[str, Any]]]] = None,
        rest_snapshot_provider: Optional[Callable[[List[str]], Any]] = None,
        on_completed_bar: Optional[Callable[[OHLCV], Any]] = None,
        max_completed_bars: int = 5_000,
    ):
        self.symbols = list(dict.fromkeys(symbols))
        self.reconciler = reconciler
        self.bar_interval_minutes = int(bar_interval_minutes)
        self.interval_seconds = max(1, self.bar_interval_minutes * 60)
        self.interval_us = self.interval_seconds * 1_000_000
        self.rest_fallback_seconds = int(rest_fallback_seconds)
        self.venue = venue
        self.asset_class = asset_class
        self.transport_stream_provider = transport_stream_provider
        self.rest_snapshot_provider = rest_snapshot_provider
        self.on_completed_bar = on_completed_bar
        self.max_completed_bars = int(max_completed_bars)

        self.logger = logger
        self.is_running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: list[asyncio.Task] = []
        self._sequence_counters: Dict[str, int] = {symbol: 0 for symbol in self.symbols}

        self.current_bars: Dict[str, _BarState] = {
            symbol: self._init_empty_bar(symbol) for symbol in self.symbols
        }
        self.completed_bars: Dict[str, Deque[OHLCV]] = {
            symbol: deque(maxlen=self.max_completed_bars) for symbol in self.symbols
        }

    def _init_empty_bar(self, symbol: str) -> _BarState:
        return _BarState(symbol=symbol, venue=self.venue, asset_class=self.asset_class)

    def connect_streams(self, symbols: List[str]) -> None:
        """Register one or more symbols for live ingestion."""
        for symbol in symbols:
            if symbol not in self.current_bars:
                self.current_bars[symbol] = self._init_empty_bar(symbol)
                self.completed_bars[symbol] = deque(maxlen=self.max_completed_bars)
                self._sequence_counters[symbol] = 0
            if symbol not in self.symbols:
                self.symbols.append(symbol)

    async def start(self) -> None:
        """Launch websocket and fallback monitors."""
        if self.is_running:
            return

        self.is_running = True
        self._loop = asyncio.get_running_loop()
        self._tasks = [
            asyncio.create_task(self._websocket_listener_loop()),
            asyncio.create_task(self._rest_fallback_loop()),
        ]

    async def stop(self) -> None:
        """Stop all background loops and flush active bars."""
        if not self.is_running:
            return

        self.is_running = False
        for task in self._tasks:
            task.cancel()

        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # pragma: no cover - best effort shutdown
                self.logger.warning("Error stopping live market data task: %s", exc)

        self._tasks.clear()
        self._loop = None

        for symbol, bar in list(self.current_bars.items()):
            if not bar.is_empty():
                await self._emit_completed_bar(symbol, bar)
                self.current_bars[symbol] = self._init_empty_bar(symbol)

    def parse_websocket_message(self, msg: Any) -> None:
        """Normalize an incoming transport payload and update the bar state."""
        tick = self._coerce_tick(msg)
        self._touch_heartbeat()
        self._process_market_tick(tick)

    def get_latest_bar(self, symbol: str) -> Dict[str, Any]:
        """Return the most recent completed bar or current in-progress bar."""
        if symbol in self.completed_bars and self.completed_bars[symbol]:
            latest = self.completed_bars[symbol][-1]
            return self._bar_to_dict(latest, completed=True)
        if symbol in self.current_bars:
            return self.current_bars[symbol].snapshot()
        return self._init_empty_bar(symbol).snapshot()

    def get_latest_bars(self, symbol: str, n: int = 100) -> List[Dict[str, Any]]:
        """Return recent completed bars for a symbol."""
        bars = list(self.completed_bars.get(symbol, deque()))[-n:]
        return [self._bar_to_dict(bar, completed=True) for bar in bars]

    def get_current_bar(self, symbol: str) -> Dict[str, Any]:
        """Alias for the in-progress bar snapshot."""
        return self.current_bars.get(symbol, self._init_empty_bar(symbol)).snapshot()

    async def _websocket_listener_loop(self) -> None:
        """Consume transport payloads from the injected async stream provider."""
        while self.is_running:
            if self.transport_stream_provider is None:
                self.logger.warning("No transport_stream_provider configured; websocket loop idle")
                await asyncio.sleep(self.rest_fallback_seconds)
                continue

            try:
                stream = self.transport_stream_provider(self.symbols)
                async for raw_msg in stream:
                    if not self.is_running:
                        break
                    self.parse_websocket_message(raw_msg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.exception("WebSocket transport exception: %s", exc)
                await asyncio.sleep(2)

    async def _rest_fallback_loop(self) -> None:
        """Poll the fallback provider when live transport is absent or stale."""
        while self.is_running:
            await asyncio.sleep(self.rest_fallback_seconds)

            if self.rest_snapshot_provider is None:
                continue

            try:
                snapshot = self.rest_snapshot_provider(self.symbols)
                if inspect.isawaitable(snapshot):
                    snapshot = await snapshot

                if snapshot is None:
                    continue

                if isinstance(snapshot, dict):
                    payloads: Iterable[Any] = snapshot.get("ticks", []) or snapshot.get("bars", []) or []
                else:
                    payloads = snapshot

                processed_any = False
                for payload in payloads:
                    self.parse_websocket_message(payload)
                    processed_any = True

                if processed_any:
                    self._touch_heartbeat()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.warning("REST fallback poll failed: %s", exc)

    def _coerce_tick(self, msg: Any) -> Tick:
        """Normalize dict-like payloads into the shared Tick schema."""
        if isinstance(msg, Tick):
            return msg

        if not isinstance(msg, dict):
            raise TypeError(f"Unsupported market payload type: {type(msg)!r}")

        symbol = str(msg.get("symbol") or msg.get("s") or "").strip()
        if not symbol:
            raise ValueError("Market payload is missing symbol")

        price = self._coerce_float(msg, ["price", "last", "close", "mid", "mark_price"])
        quantity = self._coerce_float(msg, ["quantity", "qty", "size", "volume"], default=0.0)
        event_time_us = self._coerce_event_time_us(msg)
        exchange_time_us = self._coerce_event_time_us(msg, keys=["exchange_time_us", "exchange_timestamp_us", "E"], required=False)

        side_value = str(msg.get("side") or msg.get("S") or "UNKNOWN").upper()
        side = Side.__members__.get(side_value, Side.UNKNOWN)

        venue = str(msg.get("venue") or msg.get("exchange") or self.venue)
        sequence_id = int(msg.get("sequence_id", self._sequence_counters.get(symbol, 0) + 1))
        self._sequence_counters[symbol] = sequence_id

        tick = Tick(
            event_time_us=event_time_us,
            exchange_time_us=exchange_time_us,
            symbol=symbol,
            venue=venue,
            asset_class=self.asset_class,
            price=price,
            quantity=quantity,
            side=side,
            bid=self._coerce_optional_float(msg, ["bid", "best_bid", "B"]),
            ask=self._coerce_optional_float(msg, ["ask", "best_ask", "A"]),
            bid_size=self._coerce_optional_float(msg, ["bid_size", "best_bid_size", "bidQty"]),
            ask_size=self._coerce_optional_float(msg, ["ask_size", "best_ask_size", "askQty"]),
            sequence_id=sequence_id,
            flags=str(msg.get("flags", "")),
        )
        return tick

    def _process_market_tick(self, tick: Tick) -> None:
        symbol = tick.symbol
        if symbol not in self.current_bars:
            self.connect_streams([symbol])

        bar_open_us = (tick.event_time_us // self.interval_us) * self.interval_us
        bar_close_us = bar_open_us + self.interval_us
        current = self.current_bars[symbol]

        if current.open_time_us is not None and bar_open_us > current.open_time_us:
            self._finalize_current_bar(symbol)
            current = self.current_bars[symbol]

        if current.open_time_us is None:
            current.open_time_us = bar_open_us
            current.close_time_us = bar_close_us

        if current.open is None:
            current.open = tick.price
            current.high = tick.price
            current.low = tick.price
        else:
            current.high = max(current.high, tick.price)
            current.low = min(current.low, tick.price)

        current.close = tick.price
        current.volume += float(tick.quantity or 0.0)
        current.trade_count += 1
        current.vwap_notional += float(tick.price) * float(tick.quantity or 0.0)
        current.last_event_time_us = tick.event_time_us
        current.last_exchange_time_us = tick.exchange_time_us

    async def _emit_completed_bar(self, symbol: str, bar: _BarState) -> None:
        completed_bar = bar.to_completed_bar()
        self.completed_bars[symbol].append(completed_bar)

        self.logger.info(
            "Frame complete for %s @ %s O=%.4f H=%.4f L=%.4f C=%.4f V=%.4f",
            symbol,
            completed_bar.timestamp.isoformat(),
            completed_bar.open,
            completed_bar.high,
            completed_bar.low,
            completed_bar.close,
            completed_bar.volume,
        )

        if self.on_completed_bar is not None:
            result = self.on_completed_bar(completed_bar)
            if inspect.isawaitable(result):
                await result

    def _finalize_current_bar(self, symbol: str) -> None:
        bar = self.current_bars[symbol]
        if bar.is_empty():
            self.current_bars[symbol] = self._init_empty_bar(symbol)
            return

        if self._loop is not None and self._loop.is_running():
            self._loop.create_task(self._emit_completed_bar(symbol, bar))
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._emit_completed_bar(symbol, bar))
            except RuntimeError:
                # Best-effort synchronous fallback for tests / local calls.
                asyncio.run(self._emit_completed_bar(symbol, bar))

        self.current_bars[symbol] = self._init_empty_bar(symbol)

    def _bar_to_dict(self, bar: OHLCV, completed: bool = False) -> Dict[str, Any]:
        return {
            "timestamp_utc": bar.timestamp.isoformat(),
            "symbol": bar.symbol,
            "venue": bar.venue,
            "asset_class": bar.asset_class.value,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "vwap": bar.vwap,
            "trade_count": bar.trade_count,
            "completed": completed,
        }

    def _touch_heartbeat(self) -> None:
        if hasattr(self.reconciler, "mark_heartbeat"):
            self.reconciler.mark_heartbeat()

    def _coerce_float(self, msg: Dict[str, Any], keys: List[str], default: Optional[float] = None) -> float:
        for key in keys:
            if key in msg and msg[key] is not None and msg[key] != "":
                return float(msg[key])
        if default is not None:
            return float(default)
        raise ValueError(f"Market payload is missing required numeric field from {keys}")

    def _coerce_optional_float(self, msg: Dict[str, Any], keys: List[str]) -> Optional[float]:
        for key in keys:
            value = msg.get(key)
            if value is not None and value != "":
                return float(value)
        return None

    def _coerce_event_time_us(self, msg: Dict[str, Any], keys: Optional[List[str]] = None, required: bool = True) -> int:
        lookup_keys = keys or ["event_time_us", "timestamp_us", "timestamp", "ts", "E", "time"]
        for key in lookup_keys:
            value = msg.get(key)
            if value is None or value == "":
                continue
            if isinstance(value, datetime):
                dt_value = value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
                return int(dt_value.timestamp() * 1_000_000)

            numeric = float(value)
            if numeric > 1e15:
                return int(numeric)
            if numeric > 1e12:
                return int(numeric * 1_000)
            if numeric > 1e9:
                return int(numeric * 1_000_000)
            return int(numeric * 1_000_000)

        if required:
            raise ValueError(f"Market payload is missing a timestamp field from {lookup_keys}")
        return 0
