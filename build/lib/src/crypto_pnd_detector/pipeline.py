"""Convenience builders exposing high-level APIs."""

from __future__ import annotations

from typing import Sequence

from .data.collectors.base import BaseCollector
from .inference.realtime_pipeline import RealtimePumpDetector, build_realtime_detector as _build_rt
from .models.ensemble import ExplainablePumpDetector


def build_realtime_detector(*, collectors: Sequence[BaseCollector], detector: ExplainablePumpDetector) -> RealtimePumpDetector:
    return _build_rt(collectors=collectors, detector=detector)
