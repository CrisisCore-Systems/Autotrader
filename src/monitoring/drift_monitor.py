"""Model Drift Monitor MVP.

Detects and alerts on model performance drift using statistical tests.

Features:
- Statistical drift detection (KS test, PSI, chi-square)
- Feature distribution monitoring
- Performance metric tracking
- Automatic alerting on drift
- Baseline comparison
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from src.core.logging_config import get_logger
from src.core.metrics import Counter, Gauge, Histogram

logger = get_logger(__name__)

# Metrics
DRIFT_DETECTIONS = Counter(
    'drift_detections_total',
    'Total drift detections',
    ['metric_type', 'severity']
)

DRIFT_SCORE = Gauge(
    'drift_score',
    'Current drift score',
    ['metric_name']
)

PREDICTION_DISTRIBUTION = Histogram(
    'prediction_distribution',
    'Distribution of model predictions',
    buckets=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)


class DriftSeverity(Enum):
    """Drift severity levels."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DriftMetric(Enum):
    """Types of drift metrics."""
    FEATURE_DISTRIBUTION = "feature_distribution"
    PREDICTION_DISTRIBUTION = "prediction_distribution"
    PERFORMANCE = "performance"
    DATA_QUALITY = "data_quality"


@dataclass
class DriftStatistics:
    """Statistical drift test results."""
    test_name: str
    statistic: float
    p_value: float
    threshold: float
    is_drifted: bool
    severity: DriftSeverity
    description: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "test_name": self.test_name,
            "statistic": float(self.statistic),
            "p_value": float(self.p_value),
            "threshold": float(self.threshold),
            "is_drifted": bool(self.is_drifted),
            "severity": self.severity.value,
            "description": self.description,
        }


@dataclass
class DriftReport:
    """Comprehensive drift report."""
    timestamp: datetime
    metric_type: DriftMetric
    metric_name: str
    drift_detected: bool
    severity: DriftSeverity
    statistics: List[DriftStatistics]
    baseline_stats: Dict[str, float]
    current_stats: Dict[str, float]
    recommendations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric_type": self.metric_type.value,
            "metric_name": self.metric_name,
            "drift_detected": self.drift_detected,
            "severity": self.severity.value,
            "statistics": [s.to_dict() for s in self.statistics],
            "baseline_stats": self.baseline_stats,
            "current_stats": self.current_stats,
            "recommendations": self.recommendations,
        }


class DriftDetector:
    """Base drift detector with statistical tests."""
    
    def __init__(
        self,
        name: str,
        p_value_threshold: float = 0.05,
        psi_threshold: float = 0.2,
    ):
        """Initialize drift detector.
        
        Args:
            name: Detector name
            p_value_threshold: P-value threshold for statistical tests
            psi_threshold: PSI threshold for distribution drift
        """
        self.name = name
        self.p_value_threshold = p_value_threshold
        self.psi_threshold = psi_threshold
        
        logger.info(
            "drift_detector_initialized",
            name=name,
            p_value_threshold=p_value_threshold,
            psi_threshold=psi_threshold,
        )
    
    def kolmogorov_smirnov_test(
        self,
        baseline: np.ndarray,
        current: np.ndarray,
    ) -> DriftStatistics:
        """Perform Kolmogorov-Smirnov test for distribution drift.
        
        Args:
            baseline: Baseline distribution
            current: Current distribution
            
        Returns:
            Drift statistics
        """
        statistic, p_value = stats.ks_2samp(baseline, current)
        is_drifted = p_value < self.p_value_threshold
        
        # Determine severity based on KS statistic
        if statistic > 0.5:
            severity = DriftSeverity.CRITICAL
        elif statistic > 0.3:
            severity = DriftSeverity.HIGH
        elif statistic > 0.2:
            severity = DriftSeverity.MEDIUM
        elif statistic > 0.1:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE
        
        return DriftStatistics(
            test_name="Kolmogorov-Smirnov",
            statistic=statistic,
            p_value=p_value,
            threshold=self.p_value_threshold,
            is_drifted=is_drifted,
            severity=severity,
            description=f"KS statistic: {statistic:.4f}, p-value: {p_value:.4f}",
        )
    
    def population_stability_index(
        self,
        baseline: np.ndarray,
        current: np.ndarray,
        bins: int = 10,
    ) -> DriftStatistics:
        """Calculate Population Stability Index (PSI).
        
        Args:
            baseline: Baseline distribution
            current: Current distribution
            bins: Number of bins for discretization
            
        Returns:
            Drift statistics
        """
        # Create bins based on baseline
        bin_edges = np.percentile(
            baseline,
            np.linspace(0, 100, bins + 1)
        )
        
        # Ensure unique edges
        bin_edges = np.unique(bin_edges)
        if len(bin_edges) < 2:
            bin_edges = np.array([baseline.min(), baseline.max()])
        
        # Calculate distributions
        baseline_dist, _ = np.histogram(baseline, bins=bin_edges)
        current_dist, _ = np.histogram(current, bins=bin_edges)
        
        # Normalize
        baseline_dist = baseline_dist / len(baseline) + 1e-10
        current_dist = current_dist / len(current) + 1e-10
        
        # Calculate PSI
        psi = np.sum((current_dist - baseline_dist) * np.log(current_dist / baseline_dist))
        
        is_drifted = psi > self.psi_threshold
        
        # Determine severity
        if psi > 0.25:
            severity = DriftSeverity.CRITICAL
        elif psi > 0.2:
            severity = DriftSeverity.HIGH
        elif psi > 0.1:
            severity = DriftSeverity.MEDIUM
        elif psi > 0.05:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE
        
        return DriftStatistics(
            test_name="Population Stability Index",
            statistic=psi,
            p_value=0.0,  # PSI doesn't have p-value
            threshold=self.psi_threshold,
            is_drifted=is_drifted,
            severity=severity,
            description=f"PSI: {psi:.4f}",
        )
    
    def chi_square_test(
        self,
        baseline: np.ndarray,
        current: np.ndarray,
        bins: int = 10,
    ) -> DriftStatistics:
        """Perform chi-square test for categorical drift.
        
        Args:
            baseline: Baseline distribution
            current: Current distribution
            bins: Number of bins
            
        Returns:
            Drift statistics
        """
        # Create bins
        bin_edges = np.linspace(
            min(baseline.min(), current.min()),
            max(baseline.max(), current.max()),
            bins + 1
        )
        
        # Calculate distributions
        baseline_dist, _ = np.histogram(baseline, bins=bin_edges)
        current_dist, _ = np.histogram(current, bins=bin_edges)
        
        # Normalize to same total count to make them comparable
        baseline_normalized = (baseline_dist + 1) / (baseline_dist.sum() + len(baseline_dist))
        current_normalized = (current_dist + 1) / (current_dist.sum() + len(current_dist))
        
        # Scale to same size for chi-square test
        scale_factor = 1000
        baseline_scaled = baseline_normalized * scale_factor
        current_scaled = current_normalized * scale_factor
        
        # Perform chi-square test
        statistic, p_value = stats.chisquare(
            current_scaled,
            baseline_scaled
        )
        
        is_drifted = p_value < self.p_value_threshold
        
        severity = DriftSeverity.HIGH if is_drifted else DriftSeverity.NONE
        
        return DriftStatistics(
            test_name="Chi-Square",
            statistic=statistic,
            p_value=p_value,
            threshold=self.p_value_threshold,
            is_drifted=is_drifted,
            severity=severity,
            description=f"Chi-square: {statistic:.4f}, p-value: {p_value:.4f}",
        )
    
    def kullback_leibler_divergence(
        self,
        baseline: np.ndarray,
        current: np.ndarray,
        bins: int = 10,
    ) -> DriftStatistics:
        """Calculate Kullback-Leibler (KL) divergence for distribution drift.
        
        KL divergence measures how one probability distribution diverges from a 
        reference distribution. Higher values indicate greater drift.
        
        Args:
            baseline: Baseline distribution
            current: Current distribution
            bins: Number of bins for discretization
            
        Returns:
            Drift statistics
        """
        # Create bins based on combined range
        bin_edges = np.linspace(
            min(baseline.min(), current.min()),
            max(baseline.max(), current.max()),
            bins + 1
        )
        
        # Calculate distributions
        baseline_dist, _ = np.histogram(baseline, bins=bin_edges)
        current_dist, _ = np.histogram(current, bins=bin_edges)
        
        # Normalize to probabilities (add small epsilon to avoid log(0))
        epsilon = 1e-10
        baseline_prob = (baseline_dist + epsilon) / (baseline_dist.sum() + epsilon * bins)
        current_prob = (current_dist + epsilon) / (current_dist.sum() + epsilon * bins)
        
        # Calculate KL divergence: sum(P * log(P/Q))
        kl_divergence = np.sum(current_prob * np.log(current_prob / baseline_prob))
        
        # KL divergence thresholds (empirical)
        # 0-0.1: minimal drift
        # 0.1-0.3: moderate drift
        # 0.3-0.5: significant drift
        # >0.5: severe drift
        kl_threshold = 0.3
        is_drifted = kl_divergence > kl_threshold
        
        # Determine severity
        if kl_divergence > 0.5:
            severity = DriftSeverity.CRITICAL
        elif kl_divergence > 0.3:
            severity = DriftSeverity.HIGH
        elif kl_divergence > 0.1:
            severity = DriftSeverity.MEDIUM
        elif kl_divergence > 0.05:
            severity = DriftSeverity.LOW
        else:
            severity = DriftSeverity.NONE
        
        return DriftStatistics(
            test_name="KL Divergence",
            statistic=kl_divergence,
            p_value=0.0,  # KL divergence doesn't have p-value
            threshold=kl_threshold,
            is_drifted=is_drifted,
            severity=severity,
            description=f"KL divergence: {kl_divergence:.4f}",
        )


@dataclass
class Baseline:
    """Baseline data for drift comparison."""
    name: str
    created_at: datetime
    feature_distributions: Dict[str, np.ndarray]
    prediction_distribution: np.ndarray
    performance_metrics: Dict[str, float]
    statistics: Dict[str, Dict[str, float]]  # feature -> {mean, std, min, max, etc}
    
    def save(self, path: Path) -> None:
        """Save baseline to disk.
        
        Args:
            path: Save path
        """
        data = {
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "feature_distributions": {
                k: v.tolist() for k, v in self.feature_distributions.items()
            },
            "prediction_distribution": self.prediction_distribution.tolist(),
            "performance_metrics": self.performance_metrics,
            "statistics": self.statistics,
        }
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info("baseline_saved", path=str(path))
    
    @classmethod
    def load(cls, path: Path) -> Baseline:
        """Load baseline from disk.
        
        Args:
            path: Load path
            
        Returns:
            Baseline instance
        """
        with open(path, 'r') as f:
            data = json.load(f)
        
        return cls(
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            feature_distributions={
                k: np.array(v) for k, v in data["feature_distributions"].items()
            },
            prediction_distribution=np.array(data["prediction_distribution"]),
            performance_metrics=data["performance_metrics"],
            statistics=data["statistics"],
        )


class DriftMonitor:
    """Monitor for model drift detection."""
    
    def __init__(
        self,
        name: str,
        baseline: Optional[Baseline] = None,
        p_value_threshold: float = 0.05,
        psi_threshold: float = 0.2,
    ):
        """Initialize drift monitor.
        
        Args:
            name: Monitor name
            baseline: Baseline for comparison
            p_value_threshold: P-value threshold
            psi_threshold: PSI threshold
        """
        self.name = name
        self.baseline = baseline
        self.detector = DriftDetector(
            name=f"{name}_detector",
            p_value_threshold=p_value_threshold,
            psi_threshold=psi_threshold,
        )
        self.drift_reports: List[DriftReport] = []
        
        logger.info(
            "drift_monitor_initialized",
            name=name,
            has_baseline=baseline is not None,
        )
    
    def set_baseline(self, baseline: Baseline) -> None:
        """Set baseline for comparison.
        
        Args:
            baseline: Baseline data
        """
        self.baseline = baseline
        logger.info("baseline_set", name=baseline.name)
    
    def create_baseline(
        self,
        name: str,
        features: Dict[str, np.ndarray],
        predictions: np.ndarray,
        performance_metrics: Dict[str, float],
    ) -> Baseline:
        """Create baseline from current data.
        
        Args:
            name: Baseline name
            features: Feature distributions
            predictions: Prediction distribution
            performance_metrics: Performance metrics
            
        Returns:
            Baseline instance
        """
        # Calculate statistics for each feature
        statistics = {}
        for feature_name, values in features.items():
            statistics[feature_name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
                "median": float(np.median(values)),
                "q25": float(np.percentile(values, 25)),
                "q75": float(np.percentile(values, 75)),
            }
        
        baseline = Baseline(
            name=name,
            created_at=datetime.now(timezone.utc),
            feature_distributions=features,
            prediction_distribution=predictions,
            performance_metrics=performance_metrics,
            statistics=statistics,
        )
        
        self.baseline = baseline
        
        logger.info(
            "baseline_created",
            name=name,
            num_features=len(features),
            num_predictions=len(predictions),
        )
        
        return baseline
    
    def detect_feature_drift(
        self,
        feature_name: str,
        current_distribution: np.ndarray,
    ) -> DriftReport:
        """Detect drift in a single feature.
        
        Args:
            feature_name: Feature name
            current_distribution: Current feature values
            
        Returns:
            Drift report
        """
        if self.baseline is None:
            raise ValueError("No baseline set for drift detection")
        
        if feature_name not in self.baseline.feature_distributions:
            raise ValueError(f"Feature {feature_name} not in baseline")
        
        baseline_dist = self.baseline.feature_distributions[feature_name]
        
        # Run statistical tests
        ks_stats = self.detector.kolmogorov_smirnov_test(baseline_dist, current_distribution)
        psi_stats = self.detector.population_stability_index(baseline_dist, current_distribution)
        chi_stats = self.detector.chi_square_test(baseline_dist, current_distribution)
        kl_stats = self.detector.kullback_leibler_divergence(baseline_dist, current_distribution)
        
        statistics = [ks_stats, psi_stats, chi_stats, kl_stats]
        
        # Determine overall drift
        drift_detected = any(s.is_drifted for s in statistics)
        severity = max([s.severity for s in statistics], key=lambda x: list(DriftSeverity).index(x))
        
        # Calculate current stats
        current_stats = {
            "mean": float(np.mean(current_distribution)),
            "std": float(np.std(current_distribution)),
            "min": float(np.min(current_distribution)),
            "max": float(np.max(current_distribution)),
            "median": float(np.median(current_distribution)),
        }
        
        # Generate recommendations
        recommendations = []
        if drift_detected:
            recommendations.append(f"Feature '{feature_name}' shows significant drift")
            recommendations.append("Consider retraining the model with recent data")
            
            if severity in [DriftSeverity.HIGH, DriftSeverity.CRITICAL]:
                recommendations.append("URGENT: Drift severity is high - immediate action required")
        
        report = DriftReport(
            timestamp=datetime.now(timezone.utc),
            metric_type=DriftMetric.FEATURE_DISTRIBUTION,
            metric_name=feature_name,
            drift_detected=drift_detected,
            severity=severity,
            statistics=statistics,
            baseline_stats=self.baseline.statistics[feature_name],
            current_stats=current_stats,
            recommendations=recommendations,
        )
        
        self.drift_reports.append(report)
        
        # Record metrics
        if drift_detected:
            DRIFT_DETECTIONS.labels(
                metric_type=DriftMetric.FEATURE_DISTRIBUTION.value,
                severity=severity.value,
            ).inc()
        
        DRIFT_SCORE.labels(metric_name=feature_name).set(psi_stats.statistic)
        
        logger.info(
            "feature_drift_detected" if drift_detected else "feature_drift_checked",
            feature=feature_name,
            drift_detected=drift_detected,
            severity=severity.value,
            ks_pvalue=ks_stats.p_value,
            psi=psi_stats.statistic,
        )
        
        return report
    
    def detect_prediction_drift(
        self,
        current_predictions: np.ndarray,
    ) -> DriftReport:
        """Detect drift in model predictions.
        
        Args:
            current_predictions: Current prediction distribution
            
        Returns:
            Drift report
        """
        if self.baseline is None:
            raise ValueError("No baseline set for drift detection")
        
        baseline_preds = self.baseline.prediction_distribution
        
        # Run statistical tests
        ks_stats = self.detector.kolmogorov_smirnov_test(baseline_preds, current_predictions)
        psi_stats = self.detector.population_stability_index(baseline_preds, current_predictions)
        
        statistics = [ks_stats, psi_stats]
        
        drift_detected = any(s.is_drifted for s in statistics)
        severity = max([s.severity for s in statistics], key=lambda x: list(DriftSeverity).index(x))
        
        # Record prediction distribution
        for pred in current_predictions:
            PREDICTION_DISTRIBUTION.observe(pred)
        
        current_stats = {
            "mean": float(np.mean(current_predictions)),
            "std": float(np.std(current_predictions)),
            "min": float(np.min(current_predictions)),
            "max": float(np.max(current_predictions)),
        }
        
        baseline_stats = {
            "mean": float(np.mean(baseline_preds)),
            "std": float(np.std(baseline_preds)),
            "min": float(np.min(baseline_preds)),
            "max": float(np.max(baseline_preds)),
        }
        
        recommendations = []
        if drift_detected:
            recommendations.append("Model predictions show significant drift")
            recommendations.append("Review model performance metrics")
            recommendations.append("Consider model retraining or recalibration")
        
        report = DriftReport(
            timestamp=datetime.now(timezone.utc),
            metric_type=DriftMetric.PREDICTION_DISTRIBUTION,
            metric_name="predictions",
            drift_detected=drift_detected,
            severity=severity,
            statistics=statistics,
            baseline_stats=baseline_stats,
            current_stats=current_stats,
            recommendations=recommendations,
        )
        
        self.drift_reports.append(report)
        
        if drift_detected:
            DRIFT_DETECTIONS.labels(
                metric_type=DriftMetric.PREDICTION_DISTRIBUTION.value,
                severity=severity.value,
            ).inc()
        
        logger.info(
            "prediction_drift_detected" if drift_detected else "prediction_drift_checked",
            drift_detected=drift_detected,
            severity=severity.value,
        )
        
        return report
    
    def detect_performance_drift(
        self,
        current_metrics: Dict[str, float],
        threshold_pct: float = 10.0,
    ) -> DriftReport:
        """Detect drift in performance metrics.
        
        Args:
            current_metrics: Current performance metrics
            threshold_pct: Percentage threshold for drift
            
        Returns:
            Drift report
        """
        if self.baseline is None:
            raise ValueError("No baseline set for drift detection")
        
        drift_detected = False
        statistics = []
        max_severity = DriftSeverity.NONE
        
        for metric_name, current_value in current_metrics.items():
            if metric_name in self.baseline.performance_metrics:
                baseline_value = self.baseline.performance_metrics[metric_name]
                
                if baseline_value != 0:
                    pct_change = abs((current_value - baseline_value) / baseline_value * 100)
                    
                    is_drifted = pct_change > threshold_pct
                    
                    if pct_change > 50:
                        severity = DriftSeverity.CRITICAL
                    elif pct_change > 30:
                        severity = DriftSeverity.HIGH
                    elif pct_change > 20:
                        severity = DriftSeverity.MEDIUM
                    elif pct_change > 10:
                        severity = DriftSeverity.LOW
                    else:
                        severity = DriftSeverity.NONE
                    
                    statistics.append(DriftStatistics(
                        test_name=f"{metric_name}_change",
                        statistic=pct_change,
                        p_value=0.0,
                        threshold=threshold_pct,
                        is_drifted=is_drifted,
                        severity=severity,
                        description=f"{metric_name}: {pct_change:.2f}% change",
                    ))
                    
                    if is_drifted:
                        drift_detected = True
                        if list(DriftSeverity).index(severity) > list(DriftSeverity).index(max_severity):
                            max_severity = severity
        
        recommendations = []
        if drift_detected:
            recommendations.append("Performance metrics show significant degradation")
            recommendations.append("Investigate root cause of performance change")
            recommendations.append("Consider model refresh or feature engineering")
        
        report = DriftReport(
            timestamp=datetime.now(timezone.utc),
            metric_type=DriftMetric.PERFORMANCE,
            metric_name="performance",
            drift_detected=drift_detected,
            severity=max_severity,
            statistics=statistics,
            baseline_stats=self.baseline.performance_metrics,
            current_stats=current_metrics,
            recommendations=recommendations,
        )
        
        self.drift_reports.append(report)
        
        if drift_detected:
            DRIFT_DETECTIONS.labels(
                metric_type=DriftMetric.PERFORMANCE.value,
                severity=max_severity.value,
            ).inc()
        
        logger.info(
            "performance_drift_detected" if drift_detected else "performance_drift_checked",
            drift_detected=drift_detected,
            severity=max_severity.value,
        )
        
        return report
    
    def get_drift_summary(self) -> Dict[str, Any]:
        """Get summary of all drift reports.
        
        Returns:
            Summary dictionary
        """
        if not self.drift_reports:
            return {
                "total_reports": 0,
                "drift_detected": False,
            }
        
        return {
            "total_reports": len(self.drift_reports),
            "drift_detected": any(r.drift_detected for r in self.drift_reports),
            "by_severity": {
                severity.value: len([r for r in self.drift_reports if r.severity == severity])
                for severity in DriftSeverity
            },
            "by_type": {
                metric_type.value: len([r for r in self.drift_reports if r.metric_type == metric_type])
                for metric_type in DriftMetric
            },
            "latest_report": self.drift_reports[-1].to_dict() if self.drift_reports else None,
        }
