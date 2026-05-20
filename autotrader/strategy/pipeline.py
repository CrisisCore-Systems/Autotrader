import json
import logging
import os
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List, Any, Optional

from autotrader.execution.adapters import Fill, Order, OrderStatus

logger = logging.getLogger("AutoTrader.StrategyPipeline")


class LiveStrategyPipeline:
    DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "live_alpha_weights.json"

    def __init__(
        self,
        router: Any,
        target_accounts: List[str],
        policy: str = "DYNAMIC_NLV",
        *,
        spread_mode: Optional[str] = None,
        spread_threshold: Optional[float] = None,
        max_spread_bps: Optional[float] = None,
        imbalance_cutoff: Optional[float] = None,
        imbalance_velocity_lookback: Optional[int] = None,
        imbalance_velocity_threshold: Optional[float] = None,
        latency_window: Optional[int] = None,
        spread_window: Optional[int] = None,
        signal_quantity: Optional[int] = None,
        config_path: Optional[str] = None,
    ):
        self.router = router
        self.target_accounts = target_accounts
        self.policy = policy
        self.active_signals: Dict[str, Any] = {}
        self._order_to_symbol: Dict[str, str] = {}
        self._spread_history: Dict[str, Deque[float]] = defaultdict(deque)
        self._mid_history: Dict[str, Deque[float]] = defaultdict(deque)
        self._imbalance_history: Dict[str, Deque[float]] = defaultdict(deque)

        config_values = self._load_alpha_config(config_path)
        self.spread_mode = self._normalize_spread_mode(
            spread_mode if spread_mode is not None else config_values.get("spread_mode", "relative")
        )
        self.spread_threshold = float(
            spread_threshold if spread_threshold is not None else config_values.get("spread_threshold", -0.5)
        )
        configured_max_spread_bps = config_values.get("max_spread_bps")
        self.max_spread_bps = (
            float(max_spread_bps)
            if max_spread_bps is not None
            else (float(configured_max_spread_bps) if configured_max_spread_bps is not None else None)
        )
        if self.spread_mode == "absolute" and self.max_spread_bps is None:
            raise ValueError("max_spread_bps is required when spread_mode is absolute")
        self.imbalance_cutoff = float(
            imbalance_cutoff if imbalance_cutoff is not None else config_values.get("imbalance_cutoff", 0.55)
        )
        self.imbalance_velocity_lookback = max(
            1,
            int(
                imbalance_velocity_lookback
                if imbalance_velocity_lookback is not None
                else config_values.get("imbalance_velocity_lookback", 5)
            ),
        )
        self.imbalance_velocity_threshold = float(
            imbalance_velocity_threshold
            if imbalance_velocity_threshold is not None
            else config_values.get("imbalance_velocity_threshold", 0.0)
        )
        self.latency_window = max(
            2,
            int(latency_window if latency_window is not None else config_values.get("latency_window", 5)),
        )
        self.spread_window = max(
            5,
            int(spread_window if spread_window is not None else config_values.get("spread_window", 32)),
        )
        self.signal_quantity = max(
            1,
            int(signal_quantity if signal_quantity is not None else config_values.get("signal_quantity", 100)),
        )
        self._register_lifecycle_callbacks()

    @staticmethod
    def _normalize_spread_mode(raw: Any) -> str:
        normalized = str(raw).strip().lower()
        if normalized not in {"relative", "absolute"}:
            raise ValueError("spread_mode must be one of: relative, absolute")
        return normalized

    def _load_alpha_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        explicit_path = config_path or os.getenv("LIVE_ALPHA_WEIGHTS_PATH")
        resolved_path = Path(explicit_path) if explicit_path else self.DEFAULT_CONFIG_PATH
        if not resolved_path.exists():
            return {}
        try:
            with resolved_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.warning(f"Failed to load alpha config from {resolved_path}: {exc}")
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _compute_zscore(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean_value = sum(values) / len(values)
        variance = sum((value - mean_value) ** 2 for value in values) / max(len(values) - 1, 1)
        std_dev = variance ** 0.5
        if std_dev <= 1e-12:
            return 0.0
        return (values[-1] - mean_value) / std_dev

    @staticmethod
    def _imbalance_velocity(imbalance_history: Deque[float], lookback: int) -> float:
        history_values = list(imbalance_history)
        if len(history_values) <= int(lookback):
            return 0.0
        return float(history_values[-1] - history_values[-1 - int(lookback)])

    @staticmethod
    def _passes_imbalance_velocity(side: str, imbalance_velocity: float, threshold: float) -> bool:
        normalized_side = str(side).upper().strip()
        threshold_value = float(threshold)
        if threshold_value <= 0.0:
            return True
        if normalized_side == "BUY":
            return float(imbalance_velocity) >= threshold_value
        if normalized_side == "SELL":
            return float(imbalance_velocity) <= -threshold_value
        return False

    def evaluate_quote_features(
        self,
        symbol: str,
        bid: float,
        ask: float,
        bid_size: Optional[float],
        ask_size: Optional[float],
    ) -> Optional[Dict[str, float]]:
        if bid <= 0 or ask <= 0:
            return None

        normalized_symbol = str(symbol).upper().strip()
        mid = (bid + ask) / 2.0
        spread_pct = ((ask - bid) / mid) if mid > 0 else 0.0
        spread_bps = spread_pct * 10_000.0

        spread_history = self._spread_history[normalized_symbol]
        spread_history.append(float(spread_pct))
        while len(spread_history) > self.spread_window:
            spread_history.popleft()

        mid_history = self._mid_history[normalized_symbol]
        mid_history.append(float(mid))
        while len(mid_history) > self.latency_window:
            mid_history.popleft()

        spread_zscore = self._compute_zscore(list(spread_history))
        total_book = float((bid_size or 0.0) + (ask_size or 0.0))
        imbalance = (float(bid_size or 0.0) / total_book) if total_book > 0 else 0.5
        imbalance_history = self._imbalance_history[normalized_symbol]
        imbalance_history.append(float(imbalance))
        while len(imbalance_history) > self.imbalance_velocity_lookback + 1:
            imbalance_history.popleft()
        imbalance_velocity = self._imbalance_velocity(imbalance_history, self.imbalance_velocity_lookback)

        mid_values = list(mid_history)
        if len(mid_values) <= 1:
            latency_attenuated_mid = float(mid)
        else:
            latency_attenuated_mid = sum(mid_values[:-1]) / len(mid_values[:-1])

        return {
            "mid": float(mid),
            "spread_pct": float(spread_pct),
            "spread_bps": float(spread_bps),
            "spread_zscore": float(spread_zscore),
            "imbalance_ratio": float(imbalance),
            "imbalance_velocity": float(imbalance_velocity),
            "latency_attenuated_mid": float(latency_attenuated_mid),
            "bid_size": float(bid_size or 0.0),
            "ask_size": float(ask_size or 0.0),
        }

    def passes_spread_gate(self, features: Dict[str, float]) -> bool:
        if self.spread_mode == "absolute":
            assert self.max_spread_bps is not None
            return float(features["spread_bps"]) <= float(self.max_spread_bps)
        return float(features["spread_zscore"]) <= float(self.spread_threshold)

    def generate_signal_from_quote(
        self,
        symbol: str,
        bid: float,
        ask: float,
        bid_size: Optional[float],
        ask_size: Optional[float],
        *,
        total_qty: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        features = self.evaluate_quote_features(symbol, bid, ask, bid_size, ask_size)
        if features is None:
            return None

        if symbol in self.active_signals:
            return None

        imbalance_ratio = float(features["imbalance_ratio"])
        imbalance_velocity = float(features["imbalance_velocity"])
        mid = float(features["mid"])
        latency_mid = float(features["latency_attenuated_mid"])

        if not self.passes_spread_gate(features):
            return None

        side: Optional[str] = None
        if imbalance_ratio >= self.imbalance_cutoff and mid >= latency_mid:
            side = "BUY"
        elif imbalance_ratio <= (1.0 - self.imbalance_cutoff) and mid <= latency_mid:
            side = "SELL"

        if side is None:
            return None
        if not self._passes_imbalance_velocity(side, imbalance_velocity, self.imbalance_velocity_threshold):
            return None

        return {
            "symbol": symbol,
            "side": side,
            "total_qty": int(total_qty or self.signal_quantity),
            "features": features,
        }

    def _register_lifecycle_callbacks(self) -> None:
        adapter = getattr(self.router, "adapter", None)
        if adapter is None:
            return
        if hasattr(adapter, "subscribe_fills"):
            adapter.subscribe_fills(self.on_fill)
        if hasattr(adapter, "subscribe_order_updates"):
            adapter.subscribe_order_updates(self.on_order_update)

    def _recompute_signal_status(self, state: Dict[str, Any]) -> str:
        filled_quantity = float(state.get("filled_quantity", 0.0))
        target_quantity = float(state.get("target_quantity", 0.0))
        order_statuses = list((state.get("order_statuses") or {}).values())

        if target_quantity > 0 and filled_quantity >= target_quantity - 1e-9:
            return "FILLED"
        if filled_quantity > 0:
            return "PARTIAL_FILL"
        if order_statuses and all(status == OrderStatus.CANCELLED.value for status in order_statuses):
            return "CANCELLED"
        if order_statuses and all(status in {OrderStatus.CANCELLED.value, OrderStatus.REJECTED.value} for status in order_statuses):
            return "REJECTED" if any(status == OrderStatus.REJECTED.value for status in order_statuses) else "CANCELLED"
        return "ROUTED"

    def on_fill(self, fill: Fill) -> None:
        symbol = self._order_to_symbol.get(str(fill.order_id), fill.symbol)
        signal_state = self.active_signals.get(symbol)
        if signal_state is None:
            return

        fills = signal_state.setdefault("fills", [])
        fills.append(
            {
                "order_id": str(fill.order_id),
                "execution_id": str(fill.execution_id),
                "quantity": float(fill.quantity),
                "price": float(fill.price),
                "side": fill.side.value,
            }
        )
        signal_state["filled_quantity"] = float(signal_state.get("filled_quantity", 0.0)) + float(fill.quantity)
        signal_state["status"] = self._recompute_signal_status(signal_state)

    def on_order_update(self, order: Order) -> None:
        symbol = self._order_to_symbol.get(str(order.order_id), order.symbol)
        signal_state = self.active_signals.get(symbol)
        if signal_state is None:
            return

        order_statuses = signal_state.setdefault("order_statuses", {})
        order_statuses[str(order.order_id)] = order.status.value
        signal_state["last_order_status"] = order.status.value
        signal_state["status"] = self._recompute_signal_status(signal_state)

    def on_quote_update(self, symbol: str, bid: float, ask: float, bid_size: int, ask_size: int):
        """
        Hot-path callback triggered on every incoming market data tick.
        Place your primary alpha generating logic inside this execution block.
        """
        generated_signal = self.generate_signal_from_quote(
            symbol=symbol,
            bid=bid,
            ask=ask,
            bid_size=bid_size,
            ask_size=ask_size,
        )
        if generated_signal is None:
            return

        features = generated_signal["features"]
        logger.info(
            f"Alpha condition met for {symbol}. z_spread={features['spread_zscore']:.4f}, "
            f"imbalance={features['imbalance_ratio']:.4f}, latency_mid={features['latency_attenuated_mid']:.4f}. Dispatching..."
        )
        import asyncio
        asyncio.create_task(
            self.execute_strategy_signal(
                symbol=symbol,
                total_qty=int(generated_signal["total_qty"]),
                side=str(generated_signal["side"]),
            )
        )

    async def execute_strategy_signal(self, symbol: str, total_qty: int, side: str):
        """Dispatches the raw strategy signal down through the secure allocation perimeters."""
        if symbol in self.active_signals:
            return  # Concurrency guard: avoid double-entry execution race conditions
        self.active_signals[symbol] = {"status": "PENDING", "side": side}
        try:
            logger.info(f"Initiating multi-account order routing for {total_qty} shares of {symbol} via {self.policy}")
            order_ids = await self.router.route_order(
                symbol=symbol,
                total_qty=total_qty,
                side=side,
                policy=self.policy,
                target_accounts=self.target_accounts,
                orderType="MKT" # Market order envelope to guarantee immediate execution fill
            )
            order_statuses = {str(order_id): OrderStatus.SUBMITTED.value for order_id in order_ids}
            for order_id in order_ids:
                self._order_to_symbol[str(order_id)] = symbol
            self.active_signals[symbol] = {
                "status": "ROUTED",
                "side": side,
                "order_ids": [str(order_id) for order_id in order_ids],
                "order_statuses": order_statuses,
                "target_quantity": float(total_qty),
                "filled_quantity": 0.0,
                "fills": [],
            }
            logger.info(f"Successfully deployed trade block to market wire. Order Identifiers: {order_ids}")
        except Exception as e:
            logger.error(f"Strategy allocation rejected on risk perimeter: {str(e)}")
            del self.active_signals[symbol]
