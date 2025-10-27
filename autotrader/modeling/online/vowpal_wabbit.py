"""
Vowpal Wabbit integration for large-scale online learning.

This module provides a wrapper for Vowpal Wabbit (VW), enabling
extremely fast online learning on large datasets.

Key Classes
-----------
VowpalWabbitModel : VW wrapper for classification/regression
VWConfig : Configuration for VW models

Requirements
------------
pip install vowpalwabbit scikit-learn

References
----------
- Langford et al. (2007): "Vowpal Wabbit"
- https://vowpalwabbit.org/
"""

from typing import Optional, Dict, List, Literal
import numpy as np
import tempfile
import os
from dataclasses import dataclass

try:
    from vowpalwabbit import pyvw
    VW_AVAILABLE = True
except ImportError:
    VW_AVAILABLE = False
    print("Warning: Vowpal Wabbit not available. Install with: pip install vowpalwabbit")


@dataclass
class VWConfig:
    """Configuration for Vowpal Wabbit models."""
    learning_rate: float = 0.5
    l1_penalty: float = 0.0
    l2_penalty: float = 0.0
    passes: int = 1
    bits: int = 18
    loss_function: Literal['squared', 'logistic', 'hinge'] = 'logistic'
    quadratic: Optional[str] = None
    cubic: Optional[str] = None
    interactions: Optional[List[str]] = None


class VowpalWabbitModel:
    """
    Vowpal Wabbit model for large-scale learning.
    
    Provides a scikit-learn compatible interface to VW for
    efficient online learning with feature hashing.
    
    Parameters
    ----------
    config : VWConfig, optional
        Model configuration
    task : str, optional
        Task type: 'classification' or 'regression'
    
    Examples
    --------
    >>> model = VowpalWabbitModel(task='classification')
    >>> model.fit(X_train, y_train)
    >>> predictions = model.predict(X_test)
    
    >>> # Online learning
    >>> model = VowpalWabbitModel()
    >>> for X_batch, y_batch in data_stream:
    ...     model.partial_fit(X_batch, y_batch)
    
    References
    ----------
    - Vowpal Wabbit documentation: https://vowpalwabbit.org/
    """
    
    def __init__(
        self,
        config: Optional[VWConfig] = None,
        task: Literal['classification', 'regression'] = 'classification'
    ):
        if not VW_AVAILABLE:
            raise ImportError(
                "Vowpal Wabbit is required. Install with: pip install vowpalwabbit"
            )
        
        self.config = config or VWConfig()
        self.task = task
        self.model = None
        self.is_fitted = False
        self.n_features = None
        self.temp_file = None
    
    def _build_vw_string(self) -> str:
        """Build VW command string from config."""
        parts = []
        
        # Learning rate
        parts.append(f"--learning_rate {self.config.learning_rate}")
        
        # Regularization
        if self.config.l1_penalty > 0:
            parts.append(f"--l1 {self.config.l1_penalty}")
        if self.config.l2_penalty > 0:
            parts.append(f"--l2 {self.config.l2_penalty}")
        
        # Hash bits
        parts.append(f"--bit_precision {self.config.bits}")
        
        # Loss function
        if self.task == 'classification':
            parts.append("--loss_function logistic")
        else:
            parts.append(f"--loss_function {self.config.loss_function}")
        
        # Interactions
        if self.config.quadratic:
            parts.append(f"--quadratic {self.config.quadratic}")
        if self.config.cubic:
            parts.append(f"--cubic {self.config.cubic}")
        if self.config.interactions:
            for interaction in self.config.interactions:
                parts.append(f"--interactions {interaction}")
        
        return " ".join(parts)
    
    def _convert_to_vw_format(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None
    ) -> List[str]:
        """
        Convert numpy arrays to VW format.
        
        VW format: [label] [importance] [tag]|namespace feature:value ...
        """
        examples = []
        
        for i in range(len(X)):
            parts = []
            
            # Label
            if y is not None:
                label = float(y[i])
                if self.task == 'classification':
                    # Convert 0/1 to -1/1 for VW
                    label = 1 if label > 0.5 else -1
                parts.append(str(label))
            
            # Features (namespace 'f')
            features = []
            for j in range(X.shape[1]):
                val = float(X[i, j])
                if val != 0:  # Sparse format
                    features.append(f"f{j}:{val}")
            
            parts.append(f"|f {' '.join(features)}")
            examples.append(" ".join(parts))
        
        return examples
    
    def fit(self, X: np.ndarray, y: np.ndarray):
        """
        Fit the model.
        
        Parameters
        ----------
        X : np.ndarray
            Training features (n_samples, n_features)
        y : np.ndarray
            Training targets (n_samples,)
        """
        self.n_features = X.shape[1]
        
        # Initialize VW
        vw_string = self._build_vw_string()
        self.model = pyvw.Workspace(vw_string)
        
        # Convert to VW format
        examples = self._convert_to_vw_format(X, y)
        
        # Train
        for _ in range(self.config.passes):
            for example in examples:
                self.model.learn(example)
        
        self.is_fitted = True
    
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
            self.n_features = X.shape[1]
            vw_string = self._build_vw_string()
            self.model = pyvw.Workspace(vw_string)
        
        # Convert to VW format
        examples = self._convert_to_vw_format(X, y)
        
        # Update
        for example in examples:
            self.model.learn(example)
        
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
        
        # Convert to VW format (no labels)
        examples = self._convert_to_vw_format(X)
        
        # Predict
        predictions = []
        for example in examples:
            pred = self.model.predict(example)
            
            if self.task == 'classification':
                # Convert VW output to probability
                # VW returns raw prediction, apply sigmoid
                prob = 1 / (1 + np.exp(-pred))
                predictions.append(1 if prob > 0.5 else 0)
            else:
                predictions.append(pred)
        
        return np.array(predictions)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probabilities (for classification).
        
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
        
        if self.task != 'classification':
            raise ValueError("predict_proba only available for classification")
        
        # Convert to VW format
        examples = self._convert_to_vw_format(X)
        
        # Predict
        probabilities = []
        for example in examples:
            pred = self.model.predict(example)
            
            # Apply sigmoid to get probability
            prob_1 = 1 / (1 + np.exp(-pred))
            probabilities.append([1 - prob_1, prob_1])
        
        return np.array(probabilities)
    
    def save(self, filepath: str):
        """
        Save model to file.
        
        Parameters
        ----------
        filepath : str
            Path to save the model
        """
        if not self.is_fitted:
            raise ValueError("Cannot save unfitted model")
        
        self.model.save(filepath)
    
    def load(self, filepath: str):
        """
        Load model from file.
        
        Parameters
        ----------
        filepath : str
            Path to load the model from
        """
        # Build VW string with model file
        vw_string = self._build_vw_string()
        vw_string += f" --initial_regressor {filepath}"
        
        self.model = pyvw.Workspace(vw_string)
        self.is_fitted = True
    
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance (weights).
        
        Returns
        -------
        importance : Dict[str, float]
            Feature names to weights
        """
        if not self.is_fitted:
            raise ValueError("Model must be fitted first")
        
        # Save weights to temp file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            temp_path = f.name
        
        try:
            self.model.save(temp_path + '.model')
            
            # Read weights (this is a simplified version)
            # In practice, you'd need to parse VW's weight dump
            return {}
        finally:
            # Clean up
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            if os.path.exists(temp_path + '.model'):
                os.unlink(temp_path + '.model')
    
    def __del__(self):
        """Cleanup VW workspace."""
        if self.model is not None:
            self.model.finish()


class VWHashingWrapper:
    """
    Wrapper for VW with feature hashing.
    
    Automatically handles feature hashing and namespace management.
    
    Parameters
    ----------
    config : VWConfig, optional
        Model configuration
    namespaces : List[str], optional
        Namespace names for feature groups
    
    Examples
    --------
    >>> model = VWHashingWrapper(namespaces=['price', 'volume', 'technical'])
    >>> model.fit(X_train, y_train, feature_names=feature_names)
    >>> predictions = model.predict(X_test)
    """
    
    def __init__(
        self,
        config: Optional[VWConfig] = None,
        namespaces: Optional[List[str]] = None
    ):
        if not VW_AVAILABLE:
            raise ImportError("Vowpal Wabbit is required")
        
        self.config = config or VWConfig()
        self.namespaces = namespaces or ['default']
        self.feature_to_namespace = {}
        self.vw_model = VowpalWabbitModel(config=config)
    
    def _assign_features_to_namespaces(self, feature_names: List[str]):
        """Assign features to namespaces based on names."""
        # Simple heuristic: assign based on name prefixes
        for feature in feature_names:
            assigned = False
            for namespace in self.namespaces:
                if namespace.lower() in feature.lower():
                    self.feature_to_namespace[feature] = namespace
                    assigned = True
                    break
            
            if not assigned:
                self.feature_to_namespace[feature] = self.namespaces[0]
    
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None
    ):
        """
        Fit with automatic namespace assignment.
        
        Parameters
        ----------
        X : np.ndarray
            Training features
        y : np.ndarray
            Training targets
        feature_names : List[str], optional
            Feature names for namespace assignment
        """
        if feature_names:
            self._assign_features_to_namespaces(feature_names)
        
        self.vw_model.fit(X, y)
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict on new data."""
        return self.vw_model.predict(X)
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities."""
        return self.vw_model.predict_proba(X)


# Export public API
__all__ = [
    'VowpalWabbitModel',
    'VWHashingWrapper',
    'VWConfig',
]
