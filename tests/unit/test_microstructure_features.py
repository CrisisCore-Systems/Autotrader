import math
import numpy as np
from types import SimpleNamespace

from src.intraday.data_pipeline import TickData
from src.intraday.microstructure import (
    MicrostructureFeatures,
    RobustMicrostructureFeatures,
    LegacyMicrostructureAdapter,
)


class _FakeOrderBook:
    def __init__(self):
        level = SimpleNamespace(size=1_000)
        self.bids = [level for _ in range(5)]
        self.asks = [level for _ in range(5)]

    def get_depth_imbalance(self, levels: int = 5) -> float:
        return 0.0


class _FakePipeline:
    def __init__(self, ticks):
        self._ticks = ticks
        self.order_book = _FakeOrderBook()

    def get_latest_ticks(self, lookback: int):
        if not self._ticks:
            return []
        if lookback >= len(self._ticks):
            return list(self._ticks)
        return self._ticks[-lookback:]

    def get_latest_bars(self, count: int):  # pragma: no cover - not used but required interface
        return []


def _make_ticks(count: int = 60):
    base_ts = 1_700_000_000
    ticks = []
    for i in range(count):
        price = 400.0 + 0.5 * math.sin(i / 5.0)
        bid = price - 0.01
        ask = price + 0.01
        ticks.append(
            TickData(
                timestamp=base_ts + i,
                price=price,
                size=100 + (i % 10),
                bid=bid,
                ask=ask,
                bid_size=500 + i,
                ask_size=520 + i,
            )
        )
    return ticks


def test_robust_microstructure_extended_dimension():
    ticks = _make_ticks()
    pipeline = _FakePipeline(ticks)

    engine = RobustMicrostructureFeatures(
        pipeline,
        include_order_flow=True,
        include_regimes=True,
        include_liquidity_metrics=True,
        normalized=False,
    )

    features = engine.compute()

    assert isinstance(features, np.ndarray)
    assert features.shape[0] > len(MicrostructureFeatures.BASE_FEATURE_NAMES)
    assert np.all(np.isfinite(features))


def test_legacy_adapter_restores_dimension():
    ticks = _make_ticks()
    pipeline = _FakePipeline(ticks)

    engine = RobustMicrostructureFeatures(
        pipeline,
        include_order_flow=True,
        include_regimes=True,
        include_liquidity_metrics=True,
        normalized=False,
    )

    adapter = LegacyMicrostructureAdapter(engine)
    legacy_features = adapter.compute()

    assert legacy_features.shape[0] == len(MicrostructureFeatures.BASE_FEATURE_NAMES)
    assert list(adapter.get_feature_names()) == MicrostructureFeatures.BASE_FEATURE_NAMES

    legacy_dict = adapter.compute_dict()
    assert list(legacy_dict.keys()) == MicrostructureFeatures.BASE_FEATURE_NAMES
    assert np.all(np.isfinite(list(legacy_dict.values())))
