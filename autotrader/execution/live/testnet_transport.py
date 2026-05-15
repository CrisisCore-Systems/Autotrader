"""
Testnet transport adapters for Phase 5 live staging.

This module provides a minimal live WebSocket ingestion adapter that can be
plugged directly into LiveMarketDataAdapter via transport_stream_provider.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterable, Dict, List, Optional

logger = logging.getLogger("autotrader.execution.live.testnet_transport")


class BinanceTestnetTransportAdapter:
    """Binance testnet trade stream adapter.

    The adapter yields dict payloads in the format expected by
    LiveMarketDataAdapter.parse_websocket_message.
    """

    def __init__(
        self,
        websocket_url: str = "wss://stream.testnet.binance.vision/ws",
        reconnect_delay_seconds: float = 2.0,
        quote_asset: str = "USDT",
    ):
        self.websocket_url = websocket_url
        self.reconnect_delay_seconds = max(0.5, float(reconnect_delay_seconds))
        self.quote_asset = str(quote_asset).upper()
        self._running = False
        self._sequence: Dict[str, int] = {}

    def _to_exchange_symbol(self, symbol: str) -> str:
        raw = str(symbol).strip().upper().replace("-", "/")
        if "/" in raw:
            base, quote = raw.split("/", 1)
            if quote == "USD":
                quote = self.quote_asset
            return f"{base}{quote}"

        # Already exchange-style or compact symbol.
        if raw.endswith("USD") and not raw.endswith(self.quote_asset):
            return raw[:-3] + self.quote_asset
        return raw

    def _to_canonical_symbol(self, exchange_symbol: str) -> str:
        s = exchange_symbol.upper()
        known_quotes = ["USDT", "USD", "BUSD", "USDC", "BTC", "ETH"]
        for quote in known_quotes:
            if s.endswith(quote) and len(s) > len(quote):
                base = s[: -len(quote)]
                canonical_quote = "USD" if quote in {"USDT", "USDC", "BUSD"} else quote
                return f"{base}/{canonical_quote}"
        return s

    def _next_sequence(self, canonical_symbol: str) -> int:
        current = self._sequence.get(canonical_symbol, 0) + 1
        self._sequence[canonical_symbol] = current
        return current

    def _trade_payload_to_tick(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        event_type = payload.get("e")
        if event_type != "trade":
            return None

        exchange_symbol = str(payload.get("s") or "").upper()
        if not exchange_symbol:
            return None

        canonical_symbol = self._to_canonical_symbol(exchange_symbol)

        event_ms = payload.get("E")
        trade_ms = payload.get("T")
        event_time_us = int(float(event_ms) * 1_000) if event_ms is not None else int(float(trade_ms) * 1_000)
        exchange_time_us = int(float(trade_ms) * 1_000) if trade_ms is not None else event_time_us

        side = "SELL" if bool(payload.get("m", False)) else "BUY"

        tick = {
            "symbol": canonical_symbol,
            "venue": "BINANCE_TESTNET",
            "event_time_us": event_time_us,
            "exchange_time_us": exchange_time_us,
            "price": float(payload.get("p", 0.0)),
            "quantity": float(payload.get("q", 0.0)),
            "side": side,
            "sequence_id": self._next_sequence(canonical_symbol),
            "flags": "testnet_trade",
        }
        return tick

    async def stream(self, symbols: List[str]) -> AsyncIterable[Dict[str, Any]]:
        """Yield normalized trade ticks from Binance testnet stream."""
        try:
            import websockets
        except Exception as exc:  # pragma: no cover - dependency gating
            raise RuntimeError(
                "Binance testnet transport requires the 'websockets' package to be installed"
            ) from exc

        exchange_symbols = [self._to_exchange_symbol(symbol).lower() for symbol in symbols]
        if not exchange_symbols:
            raise ValueError("At least one symbol is required for testnet streaming")

        subscribe_msg = {
            "method": "SUBSCRIBE",
            "params": [f"{symbol}@trade" for symbol in exchange_symbols],
            "id": 1,
        }

        self._running = True

        while self._running:
            try:
                logger.info(
                    "Connecting to Binance testnet websocket: %s (symbols=%s)",
                    self.websocket_url,
                    ",".join(exchange_symbols),
                )
                async with websockets.connect(self.websocket_url, ping_interval=20, ping_timeout=10) as ws:
                    await ws.send(json.dumps(subscribe_msg))

                    async for message in ws:
                        if not self._running:
                            return

                        raw = json.loads(message)
                        if isinstance(raw, dict) and "data" in raw and isinstance(raw["data"], dict):
                            payload = raw["data"]
                        else:
                            payload = raw

                        tick = self._trade_payload_to_tick(payload)
                        if tick is None:
                            continue

                        yield tick

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Binance testnet stream error: %s", exc)
                await asyncio.sleep(self.reconnect_delay_seconds)

    def stop(self) -> None:
        self._running = False


__all__ = ["BinanceTestnetTransportAdapter"]
