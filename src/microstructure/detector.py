"""Microstructure drift detection using CUSUM and ensemble methods."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional

import numpy as np

from src.core.logging_config import get_logger
from src.microstructure.features import MicrostructureFeatures

logger = get_logger(__name__)


@dataclass
class DetectionSignal:
    """Microstructure detection signal."""

    timestamp: float
    signal_type: str  # 'drift', 'burst', 'regime_change'
    score: float  # 0-1, confidence of signal
    features: Dict[str, float]  # Contributing features
    cooldown_until: float  # When this signal type can fire again
    metadata: Dict[str, object] = field(default_factory=dict)


@dataclass
class CUSUMState:
    """State for CUSUM drift detector."""

    cumsum_pos: float = 0.0
    cumsum_neg: float = 0.0
    mean: float = 0.0
    std: float = 1.0
    sample_count: int = 0


class CUSUMDetector:
    """
    CUSUM (Cumulative Sum) drift detector.
    
    Detects persistent shifts in a signal by accumulating deviations
    from the mean and firing when cumulative sum exceeds thresholds.
    """

    def __init__(
        self,
        threshold: float = 3.0,
        drift: float = 0.5,
        warmup_samples: int = 100,
    ):
        """
        Initialize CUSUM detector.
        
        Args:
            threshold: Detection threshold (in std devs)
            drift: Minimum shift to detect (in std devs)
            warmup_samples: Samples needed before detection starts
        """
        self.threshold = threshold
        self.drift = drift
        self.warmup_samples = warmup_samples
        self.state = CUSUMState()
        self.history: Deque[float] = deque(maxlen=1000)

    def update(self, value: float) -> tuple[bool, float]:
        """
        Update CUSUM with new value.
        
        Returns:
            (detected, score): Whether drift detected and detection score
        """
        self.history.append(value)
        self.state.sample_count += 1

        # Warmup phase - just collect stats
        if self.state.sample_count < self.warmup_samples:
            self._update_stats()
            return False, 0.0

        # Standardize value
        if self.state.std > 0:
            z = (value - self.state.mean) / self.state.std
        else:
            z = 0.0

        # Update CUSUM
        self.state.cumsum_pos = max(0, self.state.cumsum_pos + z - self.drift)
        self.state.cumsum_neg = max(0, self.state.cumsum_neg - z - self.drift)

        # Check for detection
        detected = False
        score = 0.0

        if self.state.cumsum_pos > self.threshold:
            detected = True
            score = min(1.0, self.state.cumsum_pos / (self.threshold * 2))
            self.state.cumsum_pos = 0.0  # Reset after detection

        elif self.state.cumsum_neg > self.threshold:
            detected = True
            score = min(1.0, self.state.cumsum_neg / (self.threshold * 2))
            self.state.cumsum_neg = 0.0  # Reset after detection

        # Periodically update stats
        if self.state.sample_count % 50 == 0:
            self._update_stats()

        return detected, score

    def _update_stats(self) -> None:
        """Update running mean and std from history."""
        if len(self.history) < 2:
            return

        self.state.mean = float(np.mean(self.history))
        self.state.std = float(np.std(self.history))

    def reset(self) -> None:
        """Reset CUSUM state."""
        self.state = CUSUMState()


class MicrostructureDetector:
    """
    Ensemble microstructure detector combining multiple signals.
    
    Detects:
    - Drift: Persistent shifts in orderbook/trade flow
    - Bursts: Sudden volume/volatility spikes
    - Regime changes: Transitions in market microstructure
    """

    def __init__(
        self,
        *,
        drift_threshold: float = 3.0,
        burst_threshold: float = 2.5,
        regime_threshold: float = 0.7,
        cooldown_seconds: float = 30.0,
        dynamic_threshold_window: int = 500,
    ):
        """
        Initialize microstructure detector.
        
        Args:
            drift_threshold: CUSUM threshold for drift detection
            burst_threshold: Z-score threshold for burst detection
            regime_threshold: Probability threshold for regime change
            cooldown_seconds: Cooldown period between signals of same type
            dynamic_threshold_window: Window for adaptive thresholds
        """
        self.drift_threshold = drift_threshold
        self.burst_threshold = burst_threshold
        self.regime_threshold = regime_threshold
        self.cooldown_seconds = cooldown_seconds
        self.dynamic_threshold_window = dynamic_threshold_window

        # CUSUM detectors for key signals
        self.cusum_imbalance = CUSUMDetector(threshold=drift_threshold)
        self.cusum_microprice = CUSUMDetector(threshold=drift_threshold)
        self.cusum_spread = CUSUMDetector(threshold=drift_threshold)
        self.cusum_trade_imbalance = CUSUMDetector(threshold=drift_threshold)

        # Signal history for ensemble scoring
        self.recent_signals: Deque[DetectionSignal] = deque(maxlen=1000)
        self.last_signal_time: Dict[str, float] = {}

        # Feature history for adaptive thresholds
        self.feature_history: Deque[Dict[str, float]] = deque(maxlen=dynamic_threshold_window)

        # Metrics
        self.detection_count = 0

        logger.info(
            "detector_initialized",
            drift_threshold=drift_threshold,
            burst_threshold=burst_threshold,
            regime_threshold=regime_threshold,
        )

    def process(self, features: MicrostructureFeatures) -> Optional[DetectionSignal]:
        """
        Process features and detect signals.
        
        Returns:
            DetectionSignal if detected, None otherwise
        """
        current_time = features.timestamp
        self.feature_history.append(self._extract_feature_dict(features))

        # Run individual detectors
        drift_signal = self._detect_drift(features, current_time)
        burst_signal = self._detect_burst(features, current_time)
        regime_signal = self._detect_regime_change(features, current_time)

        # Ensemble scoring - combine signals
        candidates = [s for s in [drift_signal, burst_signal, regime_signal] if s is not None]

        if not candidates:
            return None

        # Pick highest confidence signal (could also combine scores)
        best_signal = max(candidates, key=lambda s: s.score)

        # Apply cooldown
        if self._in_cooldown(best_signal.signal_type, current_time):
            return None

        # Update cooldown
        self.last_signal_time[best_signal.signal_type] = current_time
        best_signal.cooldown_until = current_time + self.cooldown_seconds

        self.recent_signals.append(best_signal)
        self.detection_count += 1

        logger.info(
            "detection_signal",
            signal_type=best_signal.signal_type,
            score=best_signal.score,
            timestamp=best_signal.timestamp,
        )

        return best_signal

    def _detect_drift(
        self,
        features: MicrostructureFeatures,
        current_time: float,
    ) -> Optional[DetectionSignal]:
        """Detect persistent drift in orderbook/trade flow."""
        # Check multiple CUSUM detectors
        imbalance_detected, imbalance_score = self.cusum_imbalance.update(
            features.orderbook.imbalance_top5
        )
        microprice_detected, microprice_score = self.cusum_microprice.update(
            features.orderbook.microprice_drift
        )
        spread_detected, spread_score = self.cusum_spread.update(
            features.orderbook.spread_compression
        )
        trade_detected, trade_score = self.cusum_trade_imbalance.update(
            features.trades.trade_imbalance_5s
        )

        # Ensemble score - average of triggered detectors
        triggered = []
        if imbalance_detected:
            triggered.append(("imbalance", imbalance_score))
        if microprice_detected:
            triggered.append(("microprice", microprice_score))
        if spread_detected:
            triggered.append(("spread", spread_score))
        if trade_detected:
            triggered.append(("trade_imbalance", trade_score))

        if not triggered:
            return None

        # Compute ensemble score
        ensemble_score = np.mean([score for _, score in triggered])

        return DetectionSignal(
            timestamp=current_time,
            signal_type="drift",
            score=float(ensemble_score),
            features={
                "imbalance_top5": features.orderbook.imbalance_top5,
                "microprice_drift": features.orderbook.microprice_drift,
                "spread_compression": features.orderbook.spread_compression,
                "trade_imbalance_5s": features.trades.trade_imbalance_5s,
            },
            cooldown_until=current_time + self.cooldown_seconds,
            metadata={"triggered_detectors": [name for name, _ in triggered]},
        )

    def _detect_burst(
        self,
        features: MicrostructureFeatures,
        current_time: float,
    ) -> Optional[DetectionSignal]:
        """Detect sudden volume/volatility bursts."""
        # Check volume z-scores across windows
        vol_zscore_1s = features.trades.volume_zscore_1s
        vol_zscore_5s = features.trades.volume_zscore_5s
        vol_zscore_30s = features.trades.volume_zscore_30s

        # Check realized volatility
        rvol_1s = features.trades.realized_vol_1s
        rvol_5s = features.trades.realized_vol_5s

        # Detect if any z-score exceeds threshold
        max_vol_zscore = max(abs(vol_zscore_1s), abs(vol_zscore_5s), abs(vol_zscore_30s))

        if max_vol_zscore < self.burst_threshold:
            return None

        # Score based on magnitude and consistency across windows
        score = min(1.0, max_vol_zscore / (self.burst_threshold * 2))

        return DetectionSignal(
            timestamp=current_time,
            signal_type="burst",
            score=float(score),
            features={
                "volume_zscore_1s": vol_zscore_1s,
                "volume_zscore_5s": vol_zscore_5s,
                "volume_zscore_30s": vol_zscore_30s,
                "realized_vol_1s": rvol_1s,
                "realized_vol_5s": rvol_5s,
            },
            cooldown_until=current_time + self.cooldown_seconds,
            metadata={"max_zscore": float(max_vol_zscore)},
        )

    def _detect_regime_change(
        self,
        features: MicrostructureFeatures,
        current_time: float,
    ) -> Optional[DetectionSignal]:
        """Detect regime changes (if BOCPD is available)."""
        if features.changepoint_prob is None:
            return None

        if features.changepoint_prob < self.regime_threshold:
            return None

        return DetectionSignal(
            timestamp=current_time,
            signal_type="regime_change",
            score=float(features.changepoint_prob),
            features={
                "changepoint_prob": features.changepoint_prob,
                "regime_id": float(features.regime_id or 0),
            },
            cooldown_until=current_time + self.cooldown_seconds,
            metadata={"regime_id": features.regime_id},
        )

    def _in_cooldown(self, signal_type: str, current_time: float) -> bool:
        """Check if signal type is in cooldown period."""
        last_time = self.last_signal_time.get(signal_type)
        if last_time is None:
            return False
        return (current_time - last_time) < self.cooldown_seconds

    @staticmethod
    def _extract_feature_dict(features: MicrostructureFeatures) -> Dict[str, float]:
        """Extract flat feature dictionary for history tracking."""
        return {
            "imbalance_top5": features.orderbook.imbalance_top5,
            "imbalance_top10": features.orderbook.imbalance_top10,
            "microprice_drift": features.orderbook.microprice_drift,
            "spread_bps": features.orderbook.spread_bps,
            "spread_compression": features.orderbook.spread_compression,
            "trade_imbalance_1s": features.trades.trade_imbalance_1s,
            "trade_imbalance_5s": features.trades.trade_imbalance_5s,
            "volume_zscore_1s": features.trades.volume_zscore_1s,
            "volume_zscore_5s": features.trades.volume_zscore_5s,
            "realized_vol_1s": features.trades.realized_vol_1s,
            "realized_vol_5s": features.trades.realized_vol_5s,
        }

    def get_stats(self) -> Dict[str, object]:
        """Get detector statistics."""
        signal_counts = {}
        for signal in self.recent_signals:
            signal_counts[signal.signal_type] = signal_counts.get(signal.signal_type, 0) + 1

        return {
            "total_detections": self.detection_count,
            "recent_signals": len(self.recent_signals),
            "signal_counts": signal_counts,
            "cooldowns": {
                k: v for k, v in self.last_signal_time.items()
            },
        }
