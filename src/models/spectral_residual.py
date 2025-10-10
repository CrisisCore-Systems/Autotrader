"""Spectral Residual anomaly detection for burst confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from scipy import fft, signal

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SpectralAnomalyScore:
    """Score from Spectral Residual analysis."""

    timestamp: float
    anomaly_score: float
    is_anomaly: bool
    threshold: float
    saliency_map: Optional[np.ndarray] = None


class SpectralResidualDetector:
    """
    Spectral Residual anomaly detection for time series.
    
    Based on the paper "Time-Series Anomaly Detection Service at Microsoft"
    by Ren et al. (KDD 2019).
    
    The algorithm detects anomalies by:
    1. Computing the spectral residual in frequency domain
    2. Converting back to time domain as saliency map
    3. Identifying points with high saliency as anomalies
    
    Excellent for detecting bursts, spikes, and sudden changes in patterns.
    """

    def __init__(
        self,
        window_size: int = 20,
        threshold_multiplier: float = 3.0,
        mag_window: int = 3,
        score_window: int = 40,
    ) -> None:
        """
        Initialize Spectral Residual detector.

        Args:
            window_size: Size of moving average window for spectral residual
            threshold_multiplier: Multiplier for threshold (higher = fewer detections)
            mag_window: Window size for magnitude spectrum smoothing
            score_window: Window size for anomaly score smoothing
        """
        self.window_size = window_size
        self.threshold_multiplier = threshold_multiplier
        self.mag_window = mag_window
        self.score_window = score_window

    def detect(
        self,
        series: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
    ) -> List[SpectralAnomalyScore]:
        """
        Detect anomalies in time series.

        Args:
            series: Time series data
            timestamps: Optional timestamps for each point

        Returns:
            List of SpectralAnomalyScore objects
        """
        if len(series) < self.window_size:
            logger.warning(
                "insufficient_data_for_sr",
                series_length=len(series),
                required=self.window_size,
            )
            return []

        if timestamps is None:
            timestamps = np.arange(len(series))

        # Compute spectral residual
        saliency_map = self._spectral_residual(series)

        # Compute anomaly scores
        scores = self._compute_anomaly_scores(saliency_map)

        # Determine threshold
        threshold = self._compute_threshold(scores)

        # Create results
        results = []
        for i, (ts, score) in enumerate(zip(timestamps, scores)):
            is_anomaly = score > threshold
            results.append(
                SpectralAnomalyScore(
                    timestamp=float(ts),
                    anomaly_score=float(score),
                    is_anomaly=bool(is_anomaly),
                    threshold=float(threshold),
                    saliency_map=saliency_map if i == len(timestamps) - 1 else None,
                )
            )

        n_anomalies = sum(1 for r in results if r.is_anomaly)
        logger.info(
            "spectral_residual_detection",
            series_length=len(series),
            n_anomalies=n_anomalies,
            threshold=threshold,
        )

        return results

    def _spectral_residual(self, series: np.ndarray) -> np.ndarray:
        """
        Compute spectral residual of time series.

        Args:
            series: Input time series

        Returns:
            Saliency map in time domain
        """
        # Pad series to power of 2 for efficient FFT
        n = len(series)
        pad_size = 2 ** int(np.ceil(np.log2(n)))
        padded_series = np.pad(series, (0, pad_size - n), mode="edge")

        # Compute FFT
        freq_spectrum = fft.fft(padded_series)

        # Compute amplitude and phase
        amplitude = np.abs(freq_spectrum)
        phase = np.angle(freq_spectrum)

        # Log amplitude
        log_amplitude = np.log(amplitude + 1e-10)

        # Compute spectral residual (difference from moving average)
        avg_filter = np.ones(self.mag_window) / self.mag_window
        averaged_amplitude = np.convolve(log_amplitude, avg_filter, mode="same")
        spectral_residual = log_amplitude - averaged_amplitude

        # Reconstruct in frequency domain
        reconstructed = np.exp(spectral_residual + 1j * phase)

        # Inverse FFT to get saliency map
        saliency_map = np.abs(fft.ifft(reconstructed))

        # Trim to original length
        saliency_map = saliency_map[:n]

        return saliency_map

    def _compute_anomaly_scores(self, saliency_map: np.ndarray) -> np.ndarray:
        """
        Compute anomaly scores from saliency map.

        Args:
            saliency_map: Saliency map from spectral residual

        Returns:
            Anomaly scores
        """
        # Smooth saliency map
        if self.score_window > 1:
            kernel = np.ones(self.score_window) / self.score_window
            smoothed = np.convolve(saliency_map, kernel, mode="same")
        else:
            smoothed = saliency_map

        return smoothed

    def _compute_threshold(self, scores: np.ndarray) -> float:
        """
        Compute adaptive threshold for anomaly detection.

        Args:
            scores: Anomaly scores

        Returns:
            Threshold value
        """
        # Use median + k*MAD (Median Absolute Deviation)
        median = np.median(scores)
        mad = np.median(np.abs(scores - median))

        # Threshold = median + k * MAD
        threshold = median + self.threshold_multiplier * mad

        return float(threshold)

    def detect_bursts(
        self,
        series: np.ndarray,
        timestamps: Optional[np.ndarray] = None,
        min_duration: int = 1,
        max_gap: int = 2,
    ) -> List[Dict]:
        """
        Detect burst periods (consecutive anomalies).

        Args:
            series: Time series data
            timestamps: Optional timestamps
            min_duration: Minimum burst duration (points)
            max_gap: Maximum gap between anomalies to merge into burst

        Returns:
            List of burst dictionaries with start/end times and scores
        """
        # Get anomaly detections
        detections = self.detect(series, timestamps)

        # Find consecutive anomalies
        bursts = []
        current_burst = None

        for i, detection in enumerate(detections):
            if detection.is_anomaly:
                if current_burst is None:
                    # Start new burst
                    current_burst = {
                        "start_idx": i,
                        "end_idx": i,
                        "start_time": detection.timestamp,
                        "end_time": detection.timestamp,
                        "max_score": detection.anomaly_score,
                        "mean_score": detection.anomaly_score,
                        "scores": [detection.anomaly_score],
                    }
                else:
                    # Extend current burst
                    gap = i - current_burst["end_idx"]
                    if gap <= max_gap:
                        current_burst["end_idx"] = i
                        current_burst["end_time"] = detection.timestamp
                        current_burst["scores"].append(detection.anomaly_score)
                        current_burst["max_score"] = max(
                            current_burst["max_score"], detection.anomaly_score
                        )
                        current_burst["mean_score"] = np.mean(current_burst["scores"])
                    else:
                        # Gap too large, save current and start new
                        if (
                            current_burst["end_idx"] - current_burst["start_idx"] + 1
                            >= min_duration
                        ):
                            bursts.append(current_burst)

                        current_burst = {
                            "start_idx": i,
                            "end_idx": i,
                            "start_time": detection.timestamp,
                            "end_time": detection.timestamp,
                            "max_score": detection.anomaly_score,
                            "mean_score": detection.anomaly_score,
                            "scores": [detection.anomaly_score],
                        }
            else:
                # No anomaly, might end current burst
                if current_burst is not None:
                    gap = i - current_burst["end_idx"]
                    if gap > max_gap:
                        # Save burst if long enough
                        if (
                            current_burst["end_idx"] - current_burst["start_idx"] + 1
                            >= min_duration
                        ):
                            bursts.append(current_burst)
                        current_burst = None

        # Save final burst
        if current_burst is not None:
            if current_burst["end_idx"] - current_burst["start_idx"] + 1 >= min_duration:
                bursts.append(current_burst)

        # Add duration to each burst
        for burst in bursts:
            burst["duration_points"] = burst["end_idx"] - burst["start_idx"] + 1
            burst["duration_time"] = burst["end_time"] - burst["start_time"]
            del burst["scores"]  # Remove detailed scores to save space

        logger.info(
            "burst_detection",
            n_bursts=len(bursts),
            total_points=len(series),
        )

        return bursts


class BurstConfirmationFilter:
    """
    Filter trading signals using burst confirmation.
    
    Only confirms signals that align with detected bursts in volume or price.
    """

    def __init__(
        self,
        sr_detector: Optional[SpectralResidualDetector] = None,
        lookback_window: int = 100,
        min_burst_score: float = 3.0,
    ) -> None:
        """
        Initialize burst confirmation filter.

        Args:
            sr_detector: SpectralResidualDetector instance
            lookback_window: Window size for burst detection
            min_burst_score: Minimum anomaly score to confirm burst
        """
        self.sr_detector = sr_detector or SpectralResidualDetector()
        self.lookback_window = lookback_window
        self.min_burst_score = min_burst_score

        # History buffers
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.timestamp_history: List[float] = []

    def update(self, price: float, volume: float, timestamp: float) -> None:
        """
        Update history with new data point.

        Args:
            price: Current price
            volume: Current volume
            timestamp: Current timestamp
        """
        self.price_history.append(price)
        self.volume_history.append(volume)
        self.timestamp_history.append(timestamp)

        # Trim to window size
        if len(self.price_history) > self.lookback_window:
            self.price_history = self.price_history[-self.lookback_window :]
            self.volume_history = self.volume_history[-self.lookback_window :]
            self.timestamp_history = self.timestamp_history[-self.lookback_window :]

    def confirm_burst(self) -> Tuple[bool, float]:
        """
        Check if current conditions indicate a burst.

        Returns:
            Tuple of (is_burst, burst_score)
        """
        if len(self.price_history) < self.sr_detector.window_size:
            return False, 0.0

        # Detect bursts in volume
        volume_detections = self.sr_detector.detect(
            np.array(self.volume_history), np.array(self.timestamp_history)
        )

        # Check if latest point is anomalous
        if volume_detections:
            latest = volume_detections[-1]
            if latest.is_anomaly and latest.anomaly_score >= self.min_burst_score:
                logger.info(
                    "burst_confirmed",
                    anomaly_score=latest.anomaly_score,
                    threshold=latest.threshold,
                )
                return True, latest.anomaly_score

        return False, 0.0

    def filter_signal(self, signal_confidence: float) -> Tuple[bool, float]:
        """
        Filter a trading signal with burst confirmation.

        Args:
            signal_confidence: Confidence score of the signal

        Returns:
            Tuple of (should_take_signal, adjusted_confidence)
        """
        is_burst, burst_score = self.confirm_burst()

        if is_burst:
            # Boost confidence with burst confirmation
            adjusted_confidence = min(1.0, signal_confidence * (1 + burst_score / 10))
            logger.debug(
                "signal_boosted",
                original=signal_confidence,
                adjusted=adjusted_confidence,
                burst_score=burst_score,
            )
            return True, adjusted_confidence
        else:
            # No burst, reduce confidence
            adjusted_confidence = signal_confidence * 0.7
            return adjusted_confidence > 0.5, adjusted_confidence
