"""
Anomaly Detection System
Phase 12: Statistical and ML-based anomaly detection with alerting
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import logging

import pandas as pd


logger = logging.getLogger(__name__)


class AnomalySeverity(str, Enum):
    """Anomaly severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AnomalyType(str, Enum):
    """Types of anomalies detected"""
    PNL_SPIKE = "pnl_spike"
    LOSS_STREAK = "loss_streak"
    SLIPPAGE_SPIKE = "slippage_spike"
    LATENCY_SPIKE = "latency_spike"
    ERROR_RATE_SPIKE = "error_rate_spike"
    VOLUME_ANOMALY = "volume_anomaly"
    POSITION_DRIFT = "position_drift"
    RISK_BREACH = "risk_breach"
    CORRELATION_BREAK = "correlation_break"
    REGIME_SHIFT = "regime_shift"


@dataclass
class Anomaly:
    """Detected anomaly"""
    anomaly_id: str
    timestamp: datetime
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    metric_name: str
    metric_value: float
    expected_value: float
    deviation_score: float  # Standard deviations or percentile
    description: str
    context: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'anomaly_id': self.anomaly_id,
            'timestamp': self.timestamp.isoformat(),
            'anomaly_type': self.anomaly_type.value,
            'severity': self.severity.value,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'expected_value': self.expected_value,
            'deviation_score': self.deviation_score,
            'description': self.description,
            'context': self.context
        }


class StatisticalDetector:
    """
    Statistical anomaly detection using Z-score, IQR, and rolling windows
    """
    
    def __init__(
        self,
        z_threshold: float = 3.0,
        iqr_multiplier: float = 1.5,
        window_size: int = 100
    ):
        """
        Initialize statistical detector
        
        Args:
            z_threshold: Z-score threshold for anomalies
            iqr_multiplier: IQR multiplier for outlier detection
            window_size: Rolling window size for baseline
        """
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier
        self.window_size = window_size
        logger.info("Statistical Detector initialized")
    
    def detect_zscore_anomaly(
        self,
        values: pd.Series,
        metric_name: str
    ) -> List[Anomaly]:
        """
        Detect anomalies using Z-score method
        
        Args:
            values: Time series of metric values
            metric_name: Name of the metric
        
        Returns:
            List of detected anomalies
        """
        if len(values) < 2:
            return []
        
        # Calculate rolling mean and std
        rolling_mean = values.rolling(window=self.window_size, min_periods=10).mean()
        rolling_std = values.rolling(window=self.window_size, min_periods=10).std()
        
        # Calculate Z-scores
        z_scores = (values - rolling_mean) / rolling_std
        
        # Detect anomalies
        anomalies = []
        for idx, z_score in z_scores.items():
            if abs(z_score) > self.z_threshold:
                severity = self._classify_severity(abs(z_score), self.z_threshold)
                
                anomaly = Anomaly(
                    anomaly_id=f"zscore_{metric_name}_{idx}",
                    timestamp=idx if isinstance(idx, datetime) else datetime.now(),
                    anomaly_type=self._infer_anomaly_type(metric_name),
                    severity=severity,
                    metric_name=metric_name,
                    metric_value=values[idx],
                    expected_value=rolling_mean[idx],
                    deviation_score=z_score,
                    description=f"{metric_name} deviated {z_score:.2f} std from baseline",
                    context={
                        'method': 'z-score',
                        'threshold': self.z_threshold,
                        'window_size': self.window_size
                    }
                )
                anomalies.append(anomaly)
        
        logger.info(f"Z-score detection: {len(anomalies)} anomalies in {metric_name}")
        return anomalies
    
    def detect_iqr_anomaly(
        self,
        values: pd.Series,
        metric_name: str
    ) -> List[Anomaly]:
        """
        Detect anomalies using Interquartile Range (IQR) method
        
        Args:
            values: Time series of metric values
            metric_name: Name of the metric
        
        Returns:
            List of detected anomalies
        """
        if len(values) < 4:
            return []
        
        # Calculate rolling IQR
        rolling_q25 = values.rolling(window=self.window_size, min_periods=10).quantile(0.25)
        rolling_q75 = values.rolling(window=self.window_size, min_periods=10).quantile(0.75)
        rolling_iqr = rolling_q75 - rolling_q25
        
        # Define bounds
        lower_bound = rolling_q25 - self.iqr_multiplier * rolling_iqr
        upper_bound = rolling_q75 + self.iqr_multiplier * rolling_iqr
        
        # Detect anomalies
        anomalies = []
        for idx, value in values.items():
            if value < lower_bound[idx] or value > upper_bound[idx]:
                # Calculate deviation score (how many IQRs away)
                deviation = max(
                    (rolling_q25[idx] - value) / rolling_iqr[idx],
                    (value - rolling_q75[idx]) / rolling_iqr[idx]
                ) if rolling_iqr[idx] > 0 else 0
                
                severity = self._classify_severity(abs(deviation), self.iqr_multiplier)
                
                anomaly = Anomaly(
                    anomaly_id=f"iqr_{metric_name}_{idx}",
                    timestamp=idx if isinstance(idx, datetime) else datetime.now(),
                    anomaly_type=self._infer_anomaly_type(metric_name),
                    severity=severity,
                    metric_name=metric_name,
                    metric_value=value,
                    expected_value=(rolling_q25[idx] + rolling_q75[idx]) / 2,
                    deviation_score=deviation,
                    description=f"{metric_name} outside IQR bounds by {deviation:.2f}x",
                    context={
                        'method': 'iqr',
                        'multiplier': self.iqr_multiplier,
                        'lower_bound': lower_bound[idx],
                        'upper_bound': upper_bound[idx]
                    }
                )
                anomalies.append(anomaly)
        
        logger.info(f"IQR detection: {len(anomalies)} anomalies in {metric_name}")
        return anomalies
    
    def detect_rate_change_anomaly(
        self,
        values: pd.Series,
        metric_name: str,
        threshold_pct: float = 50.0
    ) -> List[Anomaly]:
        """
        Detect sudden rate of change anomalies
        
        Args:
            values: Time series of metric values
            metric_name: Name of the metric
            threshold_pct: Percentage change threshold
        
        Returns:
            List of detected anomalies
        """
        if len(values) < 2:
            return []
        
        # Calculate percentage change
        pct_change = values.pct_change() * 100
        
        # Detect anomalies
        anomalies = []
        for idx, change in pct_change.items():
            if abs(change) > threshold_pct:
                severity = AnomalySeverity.CRITICAL if abs(change) > threshold_pct * 2 else AnomalySeverity.WARNING
                
                anomaly = Anomaly(
                    anomaly_id=f"rate_{metric_name}_{idx}",
                    timestamp=idx if isinstance(idx, datetime) else datetime.now(),
                    anomaly_type=self._infer_anomaly_type(metric_name),
                    severity=severity,
                    metric_name=metric_name,
                    metric_value=values[idx],
                    expected_value=values.shift(1)[idx],
                    deviation_score=change / threshold_pct,
                    description=f"{metric_name} changed {change:.1f}% suddenly",
                    context={
                        'method': 'rate_change',
                        'threshold_pct': threshold_pct,
                        'change_pct': change
                    }
                )
                anomalies.append(anomaly)
        
        logger.info(f"Rate change detection: {len(anomalies)} anomalies in {metric_name}")
        return anomalies
    
    def _classify_severity(self, deviation: float, threshold: float) -> AnomalySeverity:
        """Classify severity based on deviation magnitude"""
        if deviation > threshold * 2:
            return AnomalySeverity.CRITICAL
        elif deviation > threshold * 1.5:
            return AnomalySeverity.WARNING
        else:
            return AnomalySeverity.INFO
    
    def _infer_anomaly_type(self, metric_name: str) -> AnomalyType:
        """Infer anomaly type from metric name"""
        metric_lower = metric_name.lower()
        
        if 'pnl' in metric_lower or 'profit' in metric_lower:
            return AnomalyType.PNL_SPIKE
        elif 'slippage' in metric_lower:
            return AnomalyType.SLIPPAGE_SPIKE
        elif 'latency' in metric_lower or 'delay' in metric_lower:
            return AnomalyType.LATENCY_SPIKE
        elif 'error' in metric_lower or 'failure' in metric_lower:
            return AnomalyType.ERROR_RATE_SPIKE
        elif 'volume' in metric_lower:
            return AnomalyType.VOLUME_ANOMALY
        elif 'position' in metric_lower:
            return AnomalyType.POSITION_DRIFT
        elif 'risk' in metric_lower:
            return AnomalyType.RISK_BREACH
        else:
            return AnomalyType.PNL_SPIKE  # Default


class MLDetector:
    """
    Machine Learning-based anomaly detection using Isolation Forest
    """
    
    def __init__(
        self,
        contamination: float = 0.05,
        n_estimators: int = 100
    ):
        """
        Initialize ML detector
        
        Args:
            contamination: Expected proportion of outliers
            n_estimators: Number of trees in Isolation Forest
        """
        self.contamination = contamination
        self.n_estimators = n_estimators
        self.models = {}  # Store trained models per metric
        logger.info("ML Detector initialized")
    
    def detect_isolation_forest(
        self,
        features: pd.DataFrame,
        metric_name: str,
        retrain: bool = False
    ) -> List[Anomaly]:
        """
        Detect anomalies using Isolation Forest
        
        Args:
            features: DataFrame with feature columns
            metric_name: Name of the metric being monitored
            retrain: Whether to retrain the model
        
        Returns:
            List of detected anomalies
        """
        try:
            from sklearn.ensemble import IsolationForest
        except ImportError:
            logger.error("scikit-learn not installed - ML detection unavailable")
            return []
        
        if len(features) < 10:
            return []
        
        # Train or load model
        model_key = f"iso_forest_{metric_name}"
        if model_key not in self.models or retrain:
            model = IsolationForest(
                contamination=self.contamination,
                n_estimators=self.n_estimators,
                random_state=42
            )
            model.fit(features)
            self.models[model_key] = model
        else:
            model = self.models[model_key]
        
        # Predict anomalies
        predictions = model.predict(features)
        anomaly_scores = model.decision_function(features)
        
        # Create anomaly objects
        anomalies = []
        for idx, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
            if pred == -1:  # Anomaly detected
                timestamp = features.index[idx] if hasattr(features, 'index') else datetime.now()
                
                severity = AnomalySeverity.CRITICAL if score < -0.5 else AnomalySeverity.WARNING
                
                anomaly = Anomaly(
                    anomaly_id=f"ml_{metric_name}_{timestamp}",
                    timestamp=timestamp if isinstance(timestamp, datetime) else datetime.now(),
                    anomaly_type=AnomalyType.CORRELATION_BREAK,
                    severity=severity,
                    metric_name=metric_name,
                    metric_value=features.iloc[idx].mean(),
                    expected_value=features.mean().mean(),
                    deviation_score=score,
                    description=f"ML detected anomaly in {metric_name} (score: {score:.3f})",
                    context={
                        'method': 'isolation_forest',
                        'contamination': self.contamination,
                        'anomaly_score': score,
                        'features': features.columns.tolist()
                    }
                )
                anomalies.append(anomaly)
        
        logger.info(f"Isolation Forest: {len(anomalies)} anomalies in {metric_name}")
        return anomalies
    
    def detect_one_class_svm(
        self,
        features: pd.DataFrame,
        metric_name: str,
        retrain: bool = False
    ) -> List[Anomaly]:
        """
        Detect anomalies using One-Class SVM
        
        Args:
            features: DataFrame with feature columns
            metric_name: Name of the metric being monitored
            retrain: Whether to retrain the model
        
        Returns:
            List of detected anomalies
        """
        try:
            from sklearn.svm import OneClassSVM
        except ImportError:
            logger.error("scikit-learn not installed - ML detection unavailable")
            return []
        
        if len(features) < 10:
            return []
        
        # Train or load model
        model_key = f"one_class_svm_{metric_name}"
        if model_key not in self.models or retrain:
            model = OneClassSVM(nu=self.contamination, kernel='rbf', gamma='auto')
            model.fit(features)
            self.models[model_key] = model
        else:
            model = self.models[model_key]
        
        # Predict anomalies
        predictions = model.predict(features)
        anomaly_scores = model.decision_function(features)
        
        # Create anomaly objects
        anomalies = []
        for idx, (pred, score) in enumerate(zip(predictions, anomaly_scores)):
            if pred == -1:  # Anomaly detected
                timestamp = features.index[idx] if hasattr(features, 'index') else datetime.now()
                
                severity = AnomalySeverity.CRITICAL if score < -1.0 else AnomalySeverity.WARNING
                
                anomaly = Anomaly(
                    anomaly_id=f"svm_{metric_name}_{timestamp}",
                    timestamp=timestamp if isinstance(timestamp, datetime) else datetime.now(),
                    anomaly_type=AnomalyType.CORRELATION_BREAK,
                    severity=severity,
                    metric_name=metric_name,
                    metric_value=features.iloc[idx].mean(),
                    expected_value=features.mean().mean(),
                    deviation_score=score,
                    description=f"SVM detected anomaly in {metric_name} (score: {score:.3f})",
                    context={
                        'method': 'one_class_svm',
                        'nu': self.contamination,
                        'anomaly_score': score,
                        'features': features.columns.tolist()
                    }
                )
                anomalies.append(anomaly)
        
        logger.info(f"One-Class SVM: {len(anomalies)} anomalies in {metric_name}")
        return anomalies


class AnomalyDetector:
    """
    Unified anomaly detection system combining statistical and ML methods
    """
    
    def __init__(self):
        """Initialize anomaly detector"""
        self.statistical = StatisticalDetector()
        self.ml = MLDetector()
        self.detected_anomalies: List[Anomaly] = []
        logger.info("Anomaly Detector initialized")
    
    def detect_all(
        self,
        metrics: Dict[str, pd.Series],
        features: Optional[Dict[str, pd.DataFrame]] = None
    ) -> List[Anomaly]:
        """
        Run all detection methods on metrics
        
        Args:
            metrics: Dictionary of metric name -> time series
            features: Optional dictionary of metric name -> feature DataFrame for ML
        
        Returns:
            List of all detected anomalies
        """
        all_anomalies = []
        
        # Statistical detection on each metric
        for metric_name, values in metrics.items():
            # Z-score detection
            anomalies = self.statistical.detect_zscore_anomaly(values, metric_name)
            all_anomalies.extend(anomalies)
            
            # IQR detection
            anomalies = self.statistical.detect_iqr_anomaly(values, metric_name)
            all_anomalies.extend(anomalies)
            
            # Rate change detection
            anomalies = self.statistical.detect_rate_change_anomaly(values, metric_name)
            all_anomalies.extend(anomalies)
        
        # ML detection on features
        if features:
            for metric_name, feature_df in features.items():
                # Isolation Forest
                anomalies = self.ml.detect_isolation_forest(feature_df, metric_name)
                all_anomalies.extend(anomalies)
        
        # Deduplicate and sort by severity
        all_anomalies = self._deduplicate_anomalies(all_anomalies)
        all_anomalies.sort(key=lambda x: (x.severity.value, x.timestamp), reverse=True)
        
        self.detected_anomalies = all_anomalies
        
        logger.info(f"Total anomalies detected: {len(all_anomalies)}")
        return all_anomalies
    
    def get_critical_anomalies(self) -> List[Anomaly]:
        """Get only critical anomalies"""
        return [a for a in self.detected_anomalies if a.severity == AnomalySeverity.CRITICAL]
    
    def get_recent_anomalies(self, hours: int = 24) -> List[Anomaly]:
        """Get anomalies from the last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [a for a in self.detected_anomalies if a.timestamp >= cutoff]
    
    def _deduplicate_anomalies(self, anomalies: List[Anomaly]) -> List[Anomaly]:
        """Remove duplicate anomalies (same metric, time, type)"""
        seen = set()
        unique = []
        
        for anomaly in anomalies:
            key = (
                anomaly.metric_name,
                anomaly.timestamp.replace(second=0, microsecond=0),  # Round to minute
                anomaly.anomaly_type
            )
            
            if key not in seen:
                seen.add(key)
                unique.append(anomaly)
        
        return unique
