"""
Online learning models using River.

This module implements incremental learning models that update
continuously as new data arrives, without retraining from scratch.

Key Classes
-----------
OnlineLogisticRegression : Incremental logistic regression
OnlineGradientBooster : Incremental gradient boosting
OnlineEnsemble : Ensemble of online models
DriftDetector : Concept drift detection

Requirements
------------
pip install river scikit-learn

References
----------
- Montiel et al. (2021): "River: Machine Learning for Streaming Data in Python"
"""

from typing import Optional, Dict, List, Literal
import numpy as np
import pandas as pd
from dataclasses import dataclass, field

try:
    from river import (
        linear_model,
        ensemble,
        tree,
        preprocessing,
        drift,
        metrics
    )
    RIVER_AVAILABLE = True
except ImportError:
    RIVER_AVAILABLE = False
    print("Warning: River not available. Install with: pip install river")


@dataclass
class OnlineConfig:
    """Configuration for online learning models."""
    learning_rate: float = 0.01
    l2_penalty: float = 0.0
    drift_detection: bool = True
    drift_threshold: float = 0.05
    window_size: int = 1000
    ensemble_size: int = 5


class OnlineModel:
    """
    Base class for online learning models.
    
    Provides common functionality for incremental learning.
    """
    
    def __init__(self, config: Optional[OnlineConfig] = None):
        if not RIVER_AVAILABLE:
            raise ImportError("River is required. Install with: pip install river")
        
        self.config = config or OnlineConfig()
        self.model = None
        self.scaler = None
        self.drift_detector = None
        self.is_fitted = False
        self.n_samples_seen = 0
        self.drift_detected = []
        
        if self.config.drift_detection:
            self.drift_detector = drift.ADWIN(delta=self.config.drift_threshold)
    
    def partial_fit(self, X: np.ndarray, y: np.ndarray):
        """
        Incrementally fit the model.
        
        Parameters
        ----------
        X : np.ndarray
            Features (n_samples, n_features)
        y : np.ndarray
            Targets (n_samples,)
        """
        if self.model is None:
            raise ValueError("Model not initialized")
        
        # Initialize scaler on first call
        if self.scaler is None:
            self.scaler = preprocessing.StandardScaler()
        
        # Process each sample
        for i in range(len(X)):
            x_dict = {f"f{j}": float(X[i, j]) for j in range(X.shape[1])}
            y_val = float(y[i])
            
            # Scale features
            x_scaled = self.scaler.learn_one(x_dict).transform_one(x_dict)
            
            # Predict (for drift detection)
            if self.is_fitted and self.drift_detector is not None:
                y_pred = self.model.predict_one(x_scaled)
                error = abs(y_val - y_pred)
                
                # Update drift detector
                self.drift_detector.update(error)
                
                if self.drift_detector.drift_detected:
                    self.drift_detected.append(self.n_samples_seen)
            
            # Update model
            self.model.learn_one(x_scaled, y_val)
            
            self.n_samples_seen += 1
        
        self.is_fitted = True
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict on new data.
        
        Parameters
        ----------
        X : np.ndarray
            Features (n_samples, n_features)
        
        Returns
        -------
        predictions : np.ndarray
            Predicted values
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        predictions = []
        
        for i in range(len(X)):
            x_dict = {f"f{j}": float(X[i, j]) for j in range(X.shape[1])}
            x_scaled = self.scaler.transform_one(x_dict)
            y_pred = self.model.predict_one(x_scaled)
            predictions.append(y_pred)
        
        return np.array(predictions)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probabilities.
        
        Parameters
        ----------
        X : np.ndarray
            Features (n_samples, n_features)
        
        Returns
        -------
        probabilities : np.ndarray
            Shape (n_samples, 2) for binary classification
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction")
        
        probabilities = []
        
        for i in range(len(X)):
            x_dict = {f"f{j}": float(X[i, j]) for j in range(X.shape[1])}
            x_scaled = self.scaler.transform_one(x_dict)
            
            proba_dict = self.model.predict_proba_one(x_scaled)
            
            # Get probability for class 1
            prob_1 = proba_dict.get(1, proba_dict.get(True, 0.5))
            probabilities.append([1 - prob_1, prob_1])
        
        return np.array(probabilities)


class OnlineLogisticRegression(OnlineModel):
    """
    Online logistic regression model.
    
    Uses stochastic gradient descent for incremental updates.
    
    Parameters
    ----------
    config : OnlineConfig, optional
        Model configuration
    
    Examples
    --------
    >>> model = OnlineLogisticRegression()
    >>> model.partial_fit(X_batch1, y_batch1)
    >>> model.partial_fit(X_batch2, y_batch2)
    >>> predictions = model.predict(X_test)
    
    References
    ----------
    - River documentation: river.linear_model.LogisticRegression
    """
    
    def __init__(self, config: Optional[OnlineConfig] = None):
        super().__init__(config)
        
        self.model = linear_model.LogisticRegression(
            optimizer=preprocessing.StandardScaler() | linear_model.LogisticRegression.optimizer,
            l2=self.config.l2_penalty
        )


class OnlineGradientBooster(OnlineModel):
    """
    Online gradient boosting model.
    
    Uses adaptive boosting on decision trees for incremental learning.
    
    Parameters
    ----------
    config : OnlineConfig, optional
        Model configuration
    
    Examples
    --------
    >>> model = OnlineGradientBooster()
    >>> for X_batch, y_batch in data_stream:
    ...     model.partial_fit(X_batch, y_batch)
    >>> predictions = model.predict(X_new)
    
    References
    ----------
    - River documentation: river.ensemble
    """
    
    def __init__(self, config: Optional[OnlineConfig] = None):
        super().__init__(config)
        
        self.model = ensemble.AdaptiveRandomForestClassifier(
            n_models=self.config.ensemble_size,
            drift_detector=drift.ADWIN(delta=self.config.drift_threshold),
            warning_detector=drift.ADWIN(delta=self.config.drift_threshold * 2)
        )


class OnlineEnsemble(OnlineModel):
    """
    Ensemble of online models with voting.
    
    Combines multiple online learners for improved robustness.
    
    Parameters
    ----------
    config : OnlineConfig, optional
        Model configuration
    models : List[str], optional
        List of model types: ['logistic', 'tree', 'naive_bayes']
    
    Examples
    --------
    >>> model = OnlineEnsemble(models=['logistic', 'tree'])
    >>> model.partial_fit(X_train, y_train)
    >>> predictions = model.predict(X_test)
    
    References
    ----------
    - River documentation: river.ensemble
    """
    
    def __init__(
        self,
        config: Optional[OnlineConfig] = None,
        models: Optional[List[str]] = None
    ):
        super().__init__(config)
        
        if models is None:
            models = ['logistic', 'tree']
        
        # Create ensemble
        model_list = []
        
        for model_type in models:
            if model_type == 'logistic':
                model_list.append(linear_model.LogisticRegression())
            elif model_type == 'tree':
                model_list.append(tree.HoeffdingTreeClassifier())
            elif model_type == 'naive_bayes':
                from river import naive_bayes
                model_list.append(naive_bayes.GaussianNB())
        
        self.model = ensemble.VotingClassifier(model_list)


class DriftDetector:
    """
    Concept drift detector.
    
    Monitors model performance and detects when the data
    distribution changes significantly.
    
    Parameters
    ----------
    method : str, optional
        Drift detection method: 'adwin', 'ddm', 'eddm'
    threshold : float, optional
        Sensitivity threshold
    
    Examples
    --------
    >>> detector = DriftDetector(method='adwin')
    >>> for y_true, y_pred in predictions:
    ...     error = abs(y_true - y_pred)
    ...     detector.update(error)
    ...     if detector.drift_detected:
    ...         print("Drift detected!")
    
    References
    ----------
    - Bifet & Gavalda (2007): "Learning from Time-Changing Data with Adaptive Windowing"
    """
    
    def __init__(
        self,
        method: Literal['adwin', 'ddm', 'eddm'] = 'adwin',
        threshold: float = 0.05
    ):
        if not RIVER_AVAILABLE:
            raise ImportError("River is required. Install with: pip install river")
        
        if method == 'adwin':
            self.detector = drift.ADWIN(delta=threshold)
        elif method == 'ddm':
            self.detector = drift.binary.DDM()
        elif method == 'eddm':
            self.detector = drift.binary.EDDM()
        else:
            raise ValueError(f"Unknown method: {method}")
        
        self.drift_points = []
        self.n_updates = 0
    
    def update(self, value: float):
        """
        Update detector with new value.
        
        Parameters
        ----------
        value : float
            Prediction error or other metric
        """
        self.detector.update(value)
        self.n_updates += 1
        
        if self.detector.drift_detected:
            self.drift_points.append(self.n_updates)
    
    @property
    def drift_detected(self) -> bool:
        """Check if drift was detected on last update."""
        return self.detector.drift_detected
    
    def reset(self):
        """Reset the detector."""
        self.detector = type(self.detector)()
        self.n_updates = 0


class StreamingMetrics:
    """
    Compute metrics on streaming data.
    
    Tracks performance over time without storing all predictions.
    
    Examples
    --------
    >>> metrics_tracker = StreamingMetrics()
    >>> for y_true, y_pred in predictions:
    ...     metrics_tracker.update(y_true, y_pred)
    >>> print(metrics_tracker.get_metrics())
    """
    
    def __init__(self):
        if not RIVER_AVAILABLE:
            raise ImportError("River is required. Install with: pip install river")
        
        self.accuracy = metrics.Accuracy()
        self.precision = metrics.Precision()
        self.recall = metrics.Recall()
        self.f1 = metrics.F1()
    
    def update(self, y_true, y_pred):
        """Update metrics with new prediction."""
        self.accuracy.update(y_true, y_pred)
        self.precision.update(y_true, y_pred)
        self.recall.update(y_true, y_pred)
        self.f1.update(y_true, y_pred)
    
    def get_metrics(self) -> Dict[str, float]:
        """Get current metric values."""
        return {
            'accuracy': self.accuracy.get(),
            'precision': self.precision.get(),
            'recall': self.recall.get(),
            'f1': self.f1.get()
        }


# Export public API
__all__ = [
    'OnlineLogisticRegression',
    'OnlineGradientBooster',
    'OnlineEnsemble',
    'DriftDetector',
    'StreamingMetrics',
    'OnlineConfig',
]
