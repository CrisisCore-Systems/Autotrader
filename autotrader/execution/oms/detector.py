from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from autotrader.execution.adapters import OrderSide
from autotrader.execution.oms.stop_run import StructuralTrapSignal


class StructuralTrapDetector(ABC):
    """Producer-side interface for detectors that emit structural trap intents."""

    @abstractmethod
    def detect(self, finalized_bars: Sequence[Dict[str, Any]]) -> List[StructuralTrapSignal]:
        """Return zero or more structural trap signals from finalized bars."""


@dataclass(frozen=True)
class VolumeProfileNode:
    price_bin: float
    volume: float
    prominence: float
    node_kind: str


@dataclass(frozen=True)
class VolumeProfileValueArea:
    point_of_control: float
    point_of_control_volume: float
    value_area_low: float
    value_area_high: float
    total_volume: float
    target_volume: float
    covered_volume: float


@dataclass(frozen=True)
class VolumeProfileZone:
    symbol: str
    zone_id: str
    zone_kind: str
    directional_bias: str
    lower_bound: float
    upper_bound: float
    reference_price: float
    source_levels: Dict[str, float]
    metadata: Dict[str, Any]


class MockStructuralTrapDetector(StructuralTrapDetector):
    """Deterministic swing-failure mock over finalized bars.

    This detector is intentionally simple and stable: it only looks at the latest
    finalized bar against a rolling lookback window of prior bars.
    """

    def __init__(
        self,
        *,
        lookback_bars: int = 3,
        min_breach_bps: float = 5.0,
        total_size: float = 1.0,
        layer_offsets_bps: Sequence[float] = (5.0, 10.0, 15.0),
        layer_weights: Sequence[float] = (0.5, 0.3, 0.2),
        ttl_seconds: float = 30.0,
        invalidation_buffer_bps: float = 10.0,
    ):
        if lookback_bars < 2:
            raise ValueError("lookback_bars must be at least 2")
        if total_size <= 0:
            raise ValueError("total_size must be positive")
        if len(layer_offsets_bps) != len(layer_weights):
            raise ValueError("layer_weights must match layer_offsets_bps length")

        self.lookback_bars = int(lookback_bars)
        self.min_breach_bps = float(min_breach_bps)
        self.total_size = float(total_size)
        self.layer_offsets_bps = tuple(float(value) for value in layer_offsets_bps)
        self.layer_weights = tuple(float(value) for value in layer_weights)
        self.ttl_seconds = float(ttl_seconds)
        self.invalidation_buffer_bps = float(invalidation_buffer_bps)
        self._emitted_trap_ids: set[str] = set()

    def detect(self, finalized_bars: Sequence[Dict[str, Any]]) -> List[StructuralTrapSignal]:
        if len(finalized_bars) < self.lookback_bars + 1:
            return []

        window = list(finalized_bars[-(self.lookback_bars + 1) :])
        prior_bars = window[:-1]
        latest_bar = window[-1]
        symbol = str(latest_bar["symbol"])

        buy_signal = self._build_buy_trap(symbol=symbol, latest_bar=latest_bar, prior_bars=prior_bars)
        sell_signal = self._build_sell_trap(symbol=symbol, latest_bar=latest_bar, prior_bars=prior_bars)

        if buy_signal is not None and sell_signal is not None:
            stronger_signal = max(
                [buy_signal, sell_signal],
                key=self._signal_breach_bps,
            )
            return [stronger_signal]

        if buy_signal is not None:
            return [buy_signal]

        if sell_signal is not None:
            return [sell_signal]

        return []

    def _build_buy_trap(
        self,
        *,
        symbol: str,
        latest_bar: Dict[str, Any],
        prior_bars: Sequence[Dict[str, Any]],
    ) -> Optional[StructuralTrapSignal]:
        structural_price = min(float(bar["mid_low"]) for bar in prior_bars)
        breach_price = float(latest_bar["mid_low"])
        latest_close = float(latest_bar["mid_close"])
        if breach_price >= structural_price or latest_close <= structural_price:
            return None

        breach_bps = ((structural_price - breach_price) / structural_price) * 10_000.0 if structural_price > 0 else 0.0
        if breach_bps < self.min_breach_bps:
            return None

        trap_id = self._trap_id(symbol=symbol, bar=latest_bar, side=OrderSide.BUY)
        if trap_id in self._emitted_trap_ids:
            return None

        self._emitted_trap_ids.add(trap_id)
        return StructuralTrapSignal(
            symbol=symbol,
            trap_id=trap_id,
            structural_price=structural_price,
            breach_price=breach_price,
            side=OrderSide.BUY,
            total_size=self.total_size,
            layer_offsets_bps=self.layer_offsets_bps,
            layer_weights=self.layer_weights,
            ttl_seconds=self.ttl_seconds,
            invalidation_price=breach_price * (1.0 - (self.invalidation_buffer_bps / 10_000.0)),
            liquidity_score=self._liquidity_score(prior_bars, latest_bar),
            node_density=self._node_density(prior_bars, structural_price),
        )

    def _build_sell_trap(
        self,
        *,
        symbol: str,
        latest_bar: Dict[str, Any],
        prior_bars: Sequence[Dict[str, Any]],
    ) -> Optional[StructuralTrapSignal]:
        structural_price = max(float(bar["mid_high"]) for bar in prior_bars)
        breach_price = float(latest_bar["mid_high"])
        latest_close = float(latest_bar["mid_close"])
        if breach_price <= structural_price or latest_close >= structural_price:
            return None

        breach_bps = ((breach_price - structural_price) / structural_price) * 10_000.0 if structural_price > 0 else 0.0
        if breach_bps < self.min_breach_bps:
            return None

        trap_id = self._trap_id(symbol=symbol, bar=latest_bar, side=OrderSide.SELL)
        if trap_id in self._emitted_trap_ids:
            return None

        self._emitted_trap_ids.add(trap_id)
        return StructuralTrapSignal(
            symbol=symbol,
            trap_id=trap_id,
            structural_price=structural_price,
            breach_price=breach_price,
            side=OrderSide.SELL,
            total_size=self.total_size,
            layer_offsets_bps=self.layer_offsets_bps,
            layer_weights=self.layer_weights,
            ttl_seconds=self.ttl_seconds,
            invalidation_price=breach_price * (1.0 + (self.invalidation_buffer_bps / 10_000.0)),
            liquidity_score=self._liquidity_score(prior_bars, latest_bar),
            node_density=self._node_density(prior_bars, structural_price),
        )

    @staticmethod
    def _trap_id(*, symbol: str, bar: Dict[str, Any], side: OrderSide) -> str:
        bar_end = pd.Timestamp(bar["bar_end_ts"]).isoformat()
        compact_symbol = str(symbol).replace("/", "").replace("-", "")
        return f"mock_{compact_symbol}_{side.value}_{bar_end}"

    @staticmethod
    def _liquidity_score(prior_bars: Sequence[Dict[str, Any]], latest_bar: Dict[str, Any]) -> float:
        prior_volume = [float(bar.get("volume_proxy", 0.0) or 0.0) for bar in prior_bars]
        avg_prior_volume = sum(prior_volume) / len(prior_volume) if prior_volume else 0.0
        latest_volume = float(latest_bar.get("volume_proxy", 0.0) or 0.0)
        if avg_prior_volume <= 1e-12:
            return 0.0
        return float(latest_volume / avg_prior_volume)

    @staticmethod
    def _node_density(prior_bars: Sequence[Dict[str, Any]], structural_price: float) -> float:
        if not prior_bars:
            return 0.0
        touch_count = 0
        for bar in prior_bars:
            low = float(bar["mid_low"])
            high = float(bar["mid_high"])
            if low <= structural_price <= high:
                touch_count += 1
        return float(touch_count / len(prior_bars))

    @staticmethod
    def _signal_breach_bps(signal: StructuralTrapSignal) -> float:
        if signal.side == OrderSide.BUY:
            return float(((signal.structural_price - signal.breach_price) / signal.structural_price) * 10_000.0)
        return float(((signal.breach_price - signal.structural_price) / signal.structural_price) * 10_000.0)


class VolumeProfileDetector(StructuralTrapDetector):
    """Deterministic fixed-bin volume-at-price substrate for future structural detectors."""

    def __init__(
        self,
        *,
        bin_size: float,
        lookback_bars: int = 20,
        min_poc_reversion_distance_bps: float = 10.0,
        node_window_size: int = 3,
        min_node_prominence: float = 0.0,
    ):
        if float(bin_size) <= 0:
            raise ValueError("bin_size must be positive")
        if int(lookback_bars) < 1:
            raise ValueError("lookback_bars must be at least 1")
        if float(min_poc_reversion_distance_bps) <= 0:
            raise ValueError("min_poc_reversion_distance_bps must be positive")

        self.bin_size = float(bin_size)
        self.lookback_bars = int(lookback_bars)
        self.min_poc_reversion_distance_bps = float(min_poc_reversion_distance_bps)
        self.node_window_size = self._normalize_window_size(node_window_size)
        self.min_node_prominence = float(min_node_prominence)
        self._last_profile: Dict[float, float] = {}
        self._last_zones: List[VolumeProfileZone] = []

    def detect(self, finalized_bars: Sequence[Dict[str, Any]]) -> List[StructuralTrapSignal]:
        self._last_profile = self.build_profile(finalized_bars)
        self._last_zones = self.extract_zones(finalized_bars)
        return []

    def extract_zones(self, finalized_bars: Sequence[Dict[str, Any]]) -> List[VolumeProfileZone]:
        window = list(finalized_bars[-self.lookback_bars :])
        if len(window) < 2:
            self._last_zones = []
            return []

        profile = self.build_profile(window)
        if not profile:
            self._last_zones = []
            return []

        value_area = self.value_area(window)
        if value_area is None:
            self._last_zones = []
            return []

        nodes = self.extract_nodes(
            window,
            window_size=self.node_window_size,
            min_prominence=self.min_node_prominence,
        )
        previous_bar = window[-2]
        latest_bar = window[-1]
        symbol = str(latest_bar["symbol"])

        zones: List[VolumeProfileZone] = []

        value_edge_long = self._value_edge_rejection_zone(
            symbol=symbol,
            previous_bar=previous_bar,
            latest_bar=latest_bar,
            value_area=value_area,
            nodes=nodes,
            side="long",
        )
        if value_edge_long is not None:
            zones.append(value_edge_long)

        value_edge_short = self._value_edge_rejection_zone(
            symbol=symbol,
            previous_bar=previous_bar,
            latest_bar=latest_bar,
            value_area=value_area,
            nodes=nodes,
            side="short",
        )
        if value_edge_short is not None:
            zones.append(value_edge_short)

        poc_long = self._poc_reversion_zone(
            symbol=symbol,
            previous_bar=previous_bar,
            latest_bar=latest_bar,
            value_area=value_area,
            side="long",
        )
        if poc_long is not None:
            zones.append(poc_long)

        poc_short = self._poc_reversion_zone(
            symbol=symbol,
            previous_bar=previous_bar,
            latest_bar=latest_bar,
            value_area=value_area,
            side="short",
        )
        if poc_short is not None:
            zones.append(poc_short)

        self._last_zones = zones
        return list(zones)

    def export_zones(self, finalized_bars: Optional[Sequence[Dict[str, Any]]] = None) -> List[VolumeProfileZone]:
        if finalized_bars is not None:
            return self.extract_zones(finalized_bars)
        return list(self._last_zones)

    def build_profile(self, finalized_bars: Sequence[Dict[str, Any]]) -> Dict[float, float]:
        window = list(finalized_bars[-self.lookback_bars :])
        profile: Dict[float, float] = {}

        for bar in window:
            bin_prices = self._bins_for_bar(bar)
            if not bin_prices:
                continue
            bar_volume = float(bar.get("volume_proxy", 0.0) or 0.0)
            allocation = float(bar_volume / len(bin_prices))
            for price_bin in bin_prices:
                profile[price_bin] = float(profile.get(price_bin, 0.0) + allocation)

        self._last_profile = profile
        return dict(profile)

    def export_profile(self, finalized_bars: Optional[Sequence[Dict[str, Any]]] = None) -> List[Tuple[float, float]]:
        profile = self.build_profile(finalized_bars) if finalized_bars is not None else self._last_profile
        return sorted((float(price_bin), float(volume)) for price_bin, volume in profile.items())

    def point_of_control(
        self,
        finalized_bars: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Optional[Tuple[float, float]]:
        profile_pairs = self.export_profile(finalized_bars)
        if not profile_pairs:
            return None

        max_volume = max(float(volume) for _, volume in profile_pairs)
        candidates = [(float(price_bin), float(volume)) for price_bin, volume in profile_pairs if float(volume) == max_volume]
        return min(candidates, key=lambda item: item[0])

    def value_area(
        self,
        finalized_bars: Optional[Sequence[Dict[str, Any]]] = None,
        *,
        value_area_pct: float = 0.70,
    ) -> Optional[VolumeProfileValueArea]:
        normalized_pct = float(value_area_pct)
        if normalized_pct <= 0.0 or normalized_pct > 1.0:
            raise ValueError("value_area_pct must be in the interval (0, 1]")

        profile_pairs = self.export_profile(finalized_bars)
        if not profile_pairs:
            return None

        poc = self.point_of_control(finalized_bars)
        if poc is None:
            return None

        poc_price, poc_volume = poc
        total_volume = float(sum(float(volume) for _, volume in profile_pairs))
        target_volume = float(total_volume * normalized_pct)
        poc_index = next(idx for idx, (price_bin, _) in enumerate(profile_pairs) if float(price_bin) == float(poc_price))

        included = {poc_index}
        covered_volume = float(poc_volume)
        left_index = poc_index - 1
        right_index = poc_index + 1

        while covered_volume < target_volume and (left_index >= 0 or right_index < len(profile_pairs)):
            left_candidate = profile_pairs[left_index] if left_index >= 0 else None
            right_candidate = profile_pairs[right_index] if right_index < len(profile_pairs) else None

            if left_candidate is None:
                include_left = False
            elif right_candidate is None:
                include_left = True
            else:
                left_volume = float(left_candidate[1])
                right_volume = float(right_candidate[1])
                if left_volume == right_volume:
                    include_left = True
                else:
                    include_left = left_volume > right_volume

            if include_left:
                included.add(left_index)
                covered_volume += float(profile_pairs[left_index][1])
                left_index -= 1
            else:
                included.add(right_index)
                covered_volume += float(profile_pairs[right_index][1])
                right_index += 1

        included_prices = [float(profile_pairs[idx][0]) for idx in sorted(included)]
        return VolumeProfileValueArea(
            point_of_control=float(poc_price),
            point_of_control_volume=float(poc_volume),
            value_area_low=float(min(included_prices)),
            value_area_high=float(max(included_prices)),
            total_volume=total_volume,
            target_volume=target_volume,
            covered_volume=float(covered_volume),
        )

    def smoothed_profile(
        self,
        finalized_bars: Optional[Sequence[Dict[str, Any]]] = None,
        *,
        window_size: int = 3,
    ) -> List[Tuple[float, float]]:
        normalized_window = self._normalize_window_size(window_size)
        profile_pairs = self.export_profile(finalized_bars)
        if not profile_pairs:
            return []

        volumes = [float(volume) for _, volume in profile_pairs]
        half_window = normalized_window // 2
        smoothed: List[Tuple[float, float]] = []

        for idx, (price_bin, _) in enumerate(profile_pairs):
            left = max(0, idx - half_window)
            right = min(len(volumes), idx + half_window + 1)
            window_values = volumes[left:right]
            smoothed.append((float(price_bin), float(sum(window_values) / len(window_values))))

        return smoothed

    def extract_nodes(
        self,
        finalized_bars: Optional[Sequence[Dict[str, Any]]] = None,
        *,
        window_size: int = 3,
        min_prominence: float = 0.0,
    ) -> Dict[str, List[VolumeProfileNode]]:
        smoothed_pairs = self.smoothed_profile(finalized_bars, window_size=window_size)
        if len(smoothed_pairs) < 3:
            return {"hvns": [], "lvns": []}

        hvns: List[VolumeProfileNode] = []
        lvns: List[VolumeProfileNode] = []

        for idx in range(1, len(smoothed_pairs) - 1):
            left_bin, left_volume = smoothed_pairs[idx - 1]
            price_bin, center_volume = smoothed_pairs[idx]
            right_bin, right_volume = smoothed_pairs[idx + 1]
            _ = left_bin, right_bin

            if center_volume > left_volume and center_volume > right_volume:
                prominence = float(center_volume - max(left_volume, right_volume))
                if prominence >= float(min_prominence):
                    hvns.append(
                        VolumeProfileNode(
                            price_bin=float(price_bin),
                            volume=float(center_volume),
                            prominence=prominence,
                            node_kind="hvn",
                        )
                    )

            if center_volume < left_volume and center_volume < right_volume:
                prominence = float(min(left_volume, right_volume) - center_volume)
                if prominence >= float(min_prominence):
                    lvns.append(
                        VolumeProfileNode(
                            price_bin=float(price_bin),
                            volume=float(center_volume),
                            prominence=prominence,
                            node_kind="lvn",
                        )
                    )

        return {"hvns": hvns, "lvns": lvns}

    def top_k_bins(self, k: int, finalized_bars: Optional[Sequence[Dict[str, Any]]] = None) -> List[Tuple[float, float]]:
        profile = self.build_profile(finalized_bars) if finalized_bars is not None else self._last_profile
        return sorted(profile.items(), key=lambda item: (-float(item[1]), float(item[0])))[: max(0, int(k))]

    def bottom_k_bins(self, k: int, finalized_bars: Optional[Sequence[Dict[str, Any]]] = None) -> List[Tuple[float, float]]:
        profile = self.build_profile(finalized_bars) if finalized_bars is not None else self._last_profile
        return sorted(profile.items(), key=lambda item: (float(item[1]), float(item[0])))[: max(0, int(k))]

    def _value_edge_rejection_zone(
        self,
        *,
        symbol: str,
        previous_bar: Dict[str, Any],
        latest_bar: Dict[str, Any],
        value_area: VolumeProfileValueArea,
        nodes: Dict[str, List[VolumeProfileNode]],
        side: str,
    ) -> Optional[VolumeProfileZone]:
        latest_close = self._bar_close(latest_bar)
        inside_value = value_area.value_area_low <= latest_close <= value_area.value_area_high
        if not inside_value:
            return None

        if side == "long":
            breached = self._bar_low(previous_bar) < value_area.value_area_low
            if not breached:
                return None
            reference_price = float(value_area.value_area_low)
            lower_bound = reference_price
            upper_bound = float(reference_price + self.bin_size)
            directional_bias = "long_reversion"
        else:
            breached = self._bar_high(previous_bar) > value_area.value_area_high
            if not breached:
                return None
            reference_price = float(value_area.value_area_high)
            lower_bound = float(reference_price - self.bin_size)
            upper_bound = reference_price
            directional_bias = "short_reversion"

        nearest_node = self._nearest_node(reference_price, [*nodes.get("hvns", []), *nodes.get("lvns", [])])
        metadata: Dict[str, Any] = {
            "confirmation": "breach_then_reentry",
            "confirming_close": float(latest_close),
            "breach_bar_low": float(self._bar_low(previous_bar)),
            "breach_bar_high": float(self._bar_high(previous_bar)),
        }
        if nearest_node is not None:
            metadata["nearest_node_price"] = float(nearest_node.price_bin)
            metadata["nearest_node_kind"] = str(nearest_node.node_kind)
            metadata["nearest_node_distance"] = float(abs(nearest_node.price_bin - reference_price))

        return VolumeProfileZone(
            symbol=symbol,
            zone_id=f"{symbol.replace('/', '').replace('-', '').lower()}_value_edge_{side}_{self._zone_suffix(latest_bar)}",
            zone_kind="value_edge_rejection",
            directional_bias=directional_bias,
            lower_bound=float(min(lower_bound, upper_bound)),
            upper_bound=float(max(lower_bound, upper_bound)),
            reference_price=reference_price,
            source_levels={
                "point_of_control": float(value_area.point_of_control),
                "value_area_low": float(value_area.value_area_low),
                "value_area_high": float(value_area.value_area_high),
            },
            metadata=metadata,
        )

    def _poc_reversion_zone(
        self,
        *,
        symbol: str,
        previous_bar: Dict[str, Any],
        latest_bar: Dict[str, Any],
        value_area: VolumeProfileValueArea,
        side: str,
    ) -> Optional[VolumeProfileZone]:
        poc = float(value_area.point_of_control)
        previous_close = self._bar_close(previous_bar)
        latest_close = self._bar_close(latest_bar)
        previous_distance_bps = self._distance_bps(previous_close, poc)

        if previous_distance_bps < self.min_poc_reversion_distance_bps:
            return None

        previous_abs = abs(previous_close - poc)
        latest_abs = abs(latest_close - poc)
        if latest_abs >= previous_abs:
            return None

        if side == "long":
            if previous_close >= poc or latest_close <= previous_close:
                return None
            directional_bias = "long_reversion"
        else:
            if previous_close <= poc or latest_close >= previous_close:
                return None
            directional_bias = "short_reversion"

        return VolumeProfileZone(
            symbol=symbol,
            zone_id=f"{symbol.replace('/', '').replace('-', '').lower()}_poc_reversion_{side}_{self._zone_suffix(latest_bar)}",
            zone_kind="poc_reversion",
            directional_bias=directional_bias,
            lower_bound=float(min(previous_close, latest_close)),
            upper_bound=float(max(previous_close, latest_close)),
            reference_price=poc,
            source_levels={
                "point_of_control": poc,
                "value_area_low": float(value_area.value_area_low),
                "value_area_high": float(value_area.value_area_high),
            },
            metadata={
                "confirmation": "distance_then_rotation",
                "previous_close": float(previous_close),
                "confirming_close": float(latest_close),
                "distance_from_poc_bps": float(previous_distance_bps),
            },
        )

    @staticmethod
    def _nearest_node(reference_price: float, nodes: Sequence[VolumeProfileNode]) -> Optional[VolumeProfileNode]:
        if not nodes:
            return None
        return min(nodes, key=lambda node: (abs(float(node.price_bin) - float(reference_price)), float(node.price_bin)))

    @staticmethod
    def _distance_bps(price: float, reference_price: float) -> float:
        if float(reference_price) <= 0.0:
            return 0.0
        return float(abs(float(price) - float(reference_price)) / float(reference_price) * 10_000.0)

    @staticmethod
    def _zone_suffix(bar: Dict[str, Any]) -> str:
        if "bar_end_ts" in bar:
            return pd.Timestamp(bar["bar_end_ts"]).isoformat()
        close = VolumeProfileDetector._bar_close(bar)
        return f"close_{close:.10f}".replace(".", "p")

    def _bins_for_bar(self, bar: Dict[str, Any]) -> List[float]:
        low = self._bar_low(bar)
        high = self._bar_high(bar)
        if high < low:
            low, high = high, low

        low_index = self._bin_index(low)
        high_index = self._bin_index(high)
        return [self._bin_price(index) for index in range(low_index, high_index + 1)]

    def _bin_index(self, price: float) -> int:
        scaled = float(price) / self.bin_size
        return int(math.floor(scaled + 1e-12))

    def _bin_price(self, index: int) -> float:
        return float(round(index * self.bin_size, 10))

    @staticmethod
    def _bar_low(bar: Dict[str, Any]) -> float:
        for key in ("mid_low", "low", "low_price"):
            if key in bar:
                return float(bar[key])
        raise KeyError("bar is missing a low price field")

    @staticmethod
    def _bar_high(bar: Dict[str, Any]) -> float:
        for key in ("mid_high", "high", "high_price"):
            if key in bar:
                return float(bar[key])
        raise KeyError("bar is missing a high price field")

    @staticmethod
    def _bar_close(bar: Dict[str, Any]) -> float:
        for key in ("mid_close", "close", "close_price"):
            if key in bar:
                return float(bar[key])
        low = VolumeProfileDetector._bar_low(bar)
        high = VolumeProfileDetector._bar_high(bar)
        return float((low + high) / 2.0)

    @staticmethod
    def _normalize_window_size(window_size: int) -> int:
        normalized = int(window_size)
        if normalized < 1:
            raise ValueError("window_size must be at least 1")
        if normalized % 2 == 0:
            raise ValueError("window_size must be odd")
        return normalized


__all__ = [
    "StructuralTrapDetector",
    "VolumeProfileNode",
    "VolumeProfileValueArea",
    "VolumeProfileZone",
    "MockStructuralTrapDetector",
    "VolumeProfileDetector",
]