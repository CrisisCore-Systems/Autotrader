"""Bayesian Online Changepoint Detection (BOCPD) for regime identification."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque

import numpy as np
from scipy import stats

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class RegimeInfo:
    """Information about current regime."""

    regime_id: int
    run_length: int  # Time steps since last changepoint
    changepoint_prob: float  # Probability of changepoint NOW
    regime_mean: float
    regime_std: float


class BOCPDDetector:
    """
    Bayesian Online Changepoint Detection.
    
    Detects regime changes in time series by maintaining a distribution
    over run lengths (time since last changepoint) and updating beliefs
    with each new observation using Bayesian inference.
    
    Based on:
    Adams & MacKay (2007). "Bayesian Online Changepoint Detection"
    """

    def __init__(
        self,
        hazard_rate: float = 0.01,
        alpha: float = 0.1,
        beta: float = 1.0,
        kappa: float = 1.0,
        mu: float = 0.0,
        threshold: float = 0.5,
    ):
        """
        Initialize BOCPD detector.
        
        Args:
            hazard_rate: Prior probability of changepoint at each time step
            alpha: Prior shape parameter for precision (inverse variance)
            beta: Prior rate parameter for precision
            kappa: Prior pseudo-observations
            mu: Prior mean
            threshold: Changepoint probability threshold for detection
        """
        self.hazard_rate = hazard_rate
        self.alpha0 = alpha
        self.beta0 = beta
        self.kappa0 = kappa
        self.mu0 = mu
        self.threshold = threshold

        # State
        self.t = 0  # Current time step
        self.run_length_dist = np.array([1.0])  # P(r_t | x_1:t)
        self.current_regime = 0
        self.regime_history: Deque[int] = deque(maxlen=1000)

        # Sufficient statistics for each run length
        self.alpha = np.array([alpha])
        self.beta = np.array([beta])
        self.kappa = np.array([kappa])
        self.mu = np.array([mu])

        # History
        self.changepoint_probs: Deque[float] = deque(maxlen=1000)
        self.observations: Deque[float] = deque(maxlen=1000)

        logger.info(
            "bocpd_initialized",
            hazard_rate=hazard_rate,
            threshold=threshold,
        )

    def update(self, observation: float) -> RegimeInfo:
        """
        Update BOCPD with new observation.
        
        Args:
            observation: New data point
            
        Returns:
            RegimeInfo with current regime and changepoint probability
        """
        self.t += 1
        self.observations.append(observation)

        # Evaluate predictive probability
        predictive_probs = self._predictive_probability(observation)

        # Calculate growth probabilities (no changepoint)
        growth_probs = self.run_length_dist * predictive_probs * (1 - self.hazard_rate)

        # Calculate changepoint probability (changepoint at t)
        cp_prob = (self.run_length_dist * predictive_probs * self.hazard_rate).sum()

        # Update run length distribution
        new_run_length_dist = np.zeros(self.t + 1)
        new_run_length_dist[0] = cp_prob
        new_run_length_dist[1 : self.t + 1] = growth_probs

        # Normalize
        normalization = new_run_length_dist.sum()
        if normalization > 0:
            new_run_length_dist /= normalization

        self.run_length_dist = new_run_length_dist
        self.changepoint_probs.append(float(cp_prob))

        # Update sufficient statistics
        self._update_statistics(observation)

        # Detect regime change
        if cp_prob > self.threshold:
            self.current_regime += 1
            logger.info(
                "regime_change_detected",
                regime=self.current_regime,
                changepoint_prob=cp_prob,
                time_step=self.t,
            )

        self.regime_history.append(self.current_regime)

        # Get current regime statistics
        run_length = int(np.argmax(self.run_length_dist))
        regime_mean = float(self.mu[run_length])
        
        # Estimate std from precision parameters
        if self.alpha[run_length] > 1:
            regime_var = self.beta[run_length] / (self.alpha[run_length] - 1)
            regime_std = float(np.sqrt(regime_var))
        else:
            regime_std = 1.0

        return RegimeInfo(
            regime_id=self.current_regime,
            run_length=run_length,
            changepoint_prob=float(cp_prob),
            regime_mean=regime_mean,
            regime_std=regime_std,
        )

    def _predictive_probability(self, observation: float) -> np.ndarray:
        """
        Compute predictive probability p(x_t | r_t-1, x_1:t-1) for each run length.
        
        Uses Student's t-distribution as the predictive distribution.
        """
        # Degrees of freedom
        df = 2 * self.alpha

        # Location (mean)
        loc = self.mu

        # Scale
        scale = np.sqrt(self.beta * (self.kappa + 1) / (self.alpha * self.kappa))

        # Evaluate Student's t pdf
        probs = stats.t.pdf(observation, df, loc=loc, scale=scale)

        # Clip to avoid numerical issues
        probs = np.clip(probs, 1e-10, None)

        return probs

    def _update_statistics(self, observation: float) -> None:
        """Update sufficient statistics for each run length."""
        # Initialize new run length (r=0)
        new_alpha = np.zeros(self.t + 1)
        new_beta = np.zeros(self.t + 1)
        new_kappa = np.zeros(self.t + 1)
        new_mu = np.zeros(self.t + 1)

        # r = 0: new regime starts with prior
        new_alpha[0] = self.alpha0
        new_beta[0] = self.beta0
        new_kappa[0] = self.kappa0
        new_mu[0] = self.mu0

        # r > 0: update existing regimes
        for r in range(1, self.t + 1):
            if r <= len(self.alpha):
                # Get previous statistics
                alpha_prev = self.alpha[r - 1]
                beta_prev = self.beta[r - 1]
                kappa_prev = self.kappa[r - 1]
                mu_prev = self.mu[r - 1]

                # Update with new observation (Bayesian update for Normal-Gamma conjugate prior)
                new_kappa[r] = kappa_prev + 1
                new_mu[r] = (kappa_prev * mu_prev + observation) / new_kappa[r]
                new_alpha[r] = alpha_prev + 0.5
                new_beta[r] = (
                    beta_prev
                    + (kappa_prev * (observation - mu_prev) ** 2) / (2 * new_kappa[r])
                )

        self.alpha = new_alpha
        self.beta = new_beta
        self.kappa = new_kappa
        self.mu = new_mu

    def get_regime_stats(self) -> dict:
        """Get statistics about detected regimes."""
        if not self.regime_history:
            return {
                "current_regime": self.current_regime,
                "num_regimes": 0,
                "avg_regime_length": 0.0,
                "changepoints": 0,
            }

        # Count regime changes
        regimes = list(self.regime_history)
        changepoints = sum(1 for i in range(1, len(regimes)) if regimes[i] != regimes[i - 1])

        # Average regime length
        if changepoints > 0:
            avg_length = len(regimes) / (changepoints + 1)
        else:
            avg_length = len(regimes)

        return {
            "current_regime": self.current_regime,
            "num_regimes": self.current_regime + 1,
            "avg_regime_length": float(avg_length),
            "changepoints": changepoints,
            "total_observations": self.t,
        }

    def reset(self) -> None:
        """Reset detector state."""
        self.t = 0
        self.run_length_dist = np.array([1.0])
        self.current_regime = 0
        self.regime_history.clear()
        self.changepoint_probs.clear()
        self.observations.clear()

        self.alpha = np.array([self.alpha0])
        self.beta = np.array([self.beta0])
        self.kappa = np.array([self.kappa0])
        self.mu = np.array([self.mu0])

        logger.info("bocpd_reset")


class MultivariateBOCPD:
    """
    Multivariate BOCPD for detecting regime changes across multiple signals.
    
    Maintains separate BOCPD detectors for each feature and combines
    their changepoint probabilities.
    """

    def __init__(
        self,
        feature_names: list[str],
        hazard_rate: float = 0.01,
        threshold: float = 0.5,
        aggregation: str = "max",  # 'max', 'mean', or 'vote'
    ):
        """
        Initialize multivariate BOCPD.
        
        Args:
            feature_names: Names of features to track
            hazard_rate: Prior hazard rate
            threshold: Changepoint threshold
            aggregation: How to combine probabilities ('max', 'mean', 'vote')
        """
        self.feature_names = feature_names
        self.aggregation = aggregation
        self.detectors = {
            name: BOCPDDetector(hazard_rate=hazard_rate, threshold=threshold)
            for name in feature_names
        }

        logger.info(
            "multivariate_bocpd_initialized",
            num_features=len(feature_names),
            aggregation=aggregation,
        )

    def update(self, observations: dict[str, float]) -> RegimeInfo:
        """
        Update all detectors with new observations.
        
        Args:
            observations: Dict mapping feature name -> value
            
        Returns:
            Combined RegimeInfo
        """
        regime_infos = {}
        for name, value in observations.items():
            if name in self.detectors:
                regime_infos[name] = self.detectors[name].update(value)

        # Aggregate changepoint probabilities
        cp_probs = [info.changepoint_prob for info in regime_infos.values()]

        if self.aggregation == "max":
            combined_cp_prob = max(cp_probs) if cp_probs else 0.0
        elif self.aggregation == "mean":
            combined_cp_prob = np.mean(cp_probs) if cp_probs else 0.0
        elif self.aggregation == "vote":
            # Vote: % of detectors above threshold
            votes = sum(1 for p in cp_probs if p > 0.5)
            combined_cp_prob = votes / len(cp_probs) if cp_probs else 0.0
        else:
            combined_cp_prob = max(cp_probs) if cp_probs else 0.0

        # Use first detector's regime info as base
        if regime_infos:
            base_info = list(regime_infos.values())[0]
            return RegimeInfo(
                regime_id=base_info.regime_id,
                run_length=base_info.run_length,
                changepoint_prob=float(combined_cp_prob),
                regime_mean=base_info.regime_mean,
                regime_std=base_info.regime_std,
            )

        return RegimeInfo(
            regime_id=0,
            run_length=0,
            changepoint_prob=0.0,
            regime_mean=0.0,
            regime_std=1.0,
        )

    def get_stats(self) -> dict:
        """Get statistics for all detectors."""
        stats = {}
        for name, detector in self.detectors.items():
            stats[name] = detector.get_regime_stats()
        return stats
