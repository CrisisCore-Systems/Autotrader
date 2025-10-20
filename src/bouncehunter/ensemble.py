"""
Ensemble Forecasting with Uncertainty Quantification

Multi-model approach combining:
- Logistic Regression (linear baseline)
- XGBoost (gradient boosting)
- Random Forest (ensemble trees)
- Neural Network (non-linear patterns)

Provides uncertainty estimates and model agreement metrics.

Author: BounceHunter Agentic V2
Date: October 2025
"""

from dataclasses import dataclass
from typing import Dict

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier

try:
    import xgboost as xgb

    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================


@dataclass
class EnsemblePrediction:
    """Result from ensemble forecaster."""

    probability: float  # Ensemble weighted probability
    confidence: float  # Adjusted for uncertainty
    uncertainty: float  # Prediction uncertainty (0-1)
    agreement: float  # Model agreement score (0-1)
    model_predictions: Dict[str, float]  # Individual model outputs
    model_uncertainties: Dict[str, float]  # Individual uncertainties


# ==============================================================================
# ENSEMBLE FORECASTER
# ==============================================================================


class EnsembleForecaster:
    """
    Multi-model forecaster with uncertainty quantification.

    Key improvements over single model:
    1. Model diversity reduces overfitting
    2. Uncertainty estimates flag low-confidence predictions
    3. Agreement metrics detect regime shifts
    4. Dynamic weighting adapts to recent performance
    """

    def __init__(self, memory=None):
        self.memory = memory

        # Initialize models
        self.models = {}
        self._init_models()

        # Model weights (updated based on performance)
        self.model_weights = {name: 1.0 / len(self.models) for name in self.models}

        # Performance tracking
        self.model_performance = {name: [] for name in self.models}

    def _init_models(self):
        """Initialize all ensemble models."""
        # Logistic Regression (linear baseline)
        self.models["logistic"] = LogisticRegression(
            C=1.0, max_iter=1000, random_state=42, class_weight="balanced"
        )

        # Random Forest (ensemble trees)
        self.models["random_forest"] = RandomForestClassifier(
            n_estimators=100,
            max_depth=8,
            min_samples_leaf=10,
            random_state=42,
            class_weight="balanced",
        )

        # XGBoost (if available)
        if XGB_AVAILABLE:
            self.models["xgboost"] = xgb.XGBClassifier(
                n_estimators=100,
                max_depth=6,
                learning_rate=0.05,
                random_state=42,
                scale_pos_weight=1.0,
                use_label_encoder=False,
                eval_metric="logloss",
            )

        # Neural Network (non-linear patterns)
        self.models["neural_net"] = MLPClassifier(
            hidden_layer_sizes=(64, 32),
            activation="relu",
            max_iter=500,
            alpha=0.01,
            random_state=42,
            early_stopping=True,
            validation_fraction=0.15,
        )

    def fit(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """
        Train all ensemble models.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Target labels (n_samples,)

        Returns:
            Dictionary of model accuracies
        """
        accuracies = {}

        for name, model in self.models.items():
            try:
                model.fit(X, y)

                # Calculate training accuracy
                y_pred = model.predict(X)
                accuracy = np.mean(y_pred == y)
                accuracies[name] = accuracy

                print(f"✓ {name}: {accuracy:.1%} accuracy")
            except Exception as e:
                print(f"✗ {name}: Failed to train - {e}")
                accuracies[name] = 0.5

        return accuracies

    def predict_with_uncertainty(
        self, X: np.ndarray
    ) -> EnsemblePrediction:
        """
        Predict with uncertainty quantification.

        Args:
            X: Feature vector (1, n_features) or (n_features,)

        Returns:
            EnsemblePrediction with probability, confidence, uncertainty
        """
        # Ensure 2D array
        if X.ndim == 1:
            X = X.reshape(1, -1)

        predictions = {}
        uncertainties = {}

        for name, model in self.models.items():
            try:
                # Get probability prediction
                proba = model.predict_proba(X)[0][1]
                predictions[name] = proba

                # Estimate uncertainty
                uncertainty = self._estimate_uncertainty(model, X, proba)
                uncertainties[name] = uncertainty

            except Exception:
                # Fallback to neutral if model fails
                predictions[name] = 0.5
                uncertainties[name] = 0.5

        # Weighted ensemble prediction
        ensemble_pred = sum(
            predictions[name] * self.model_weights[name] for name in predictions
        )

        # Weighted ensemble uncertainty
        ensemble_uncertainty = sum(
            uncertainties[name] * self.model_weights[name] for name in uncertainties
        )

        # Model agreement (inverse of std dev)
        pred_values = list(predictions.values())
        if len(pred_values) > 1:
            agreement = 1.0 - min(1.0, np.std(pred_values) * 2)  # Normalize to 0-1
        else:
            agreement = 1.0

        # Adjust confidence based on uncertainty and agreement
        confidence = ensemble_pred * (1.0 - ensemble_uncertainty * 0.4) * (0.7 + agreement * 0.3)
        confidence = max(0.0, min(1.0, confidence))

        return EnsemblePrediction(
            probability=ensemble_pred,
            confidence=confidence,
            uncertainty=ensemble_uncertainty,
            agreement=agreement,
            model_predictions=predictions,
            model_uncertainties=uncertainties,
        )

    def _estimate_uncertainty(
        self, model, X: np.ndarray, proba: float
    ) -> float:
        """
        Estimate prediction uncertainty for a model.

        Methods:
        - Tree models: Use prediction variance across trees
        - Neural nets: Use distance from decision boundary
        - Logistic: Use distance from 0.5 threshold
        """
        if hasattr(model, "estimators_"):
            # Random Forest or similar: variance across trees
            try:
                tree_preds = np.array(
                    [tree.predict_proba(X)[0][1] for tree in model.estimators_]
                )
                uncertainty = np.std(tree_preds)
                return min(1.0, uncertainty * 2)  # Scale to 0-1
            except Exception:
                # Fallback if tree extraction fails
                pass

        # Fallback: Distance from decision boundary
        # Further from 0.5 = more certain
        distance_from_boundary = abs(proba - 0.5)
        uncertainty = 1.0 - (distance_from_boundary * 2)  # Convert to 0-1
        return max(0.0, min(1.0, uncertainty))

    def update_model_weights(self, recent_performance: Dict[str, float]):
        """
        Update model weights based on recent performance.

        Args:
            recent_performance: Dict of {model_name: accuracy}
        """
        if not recent_performance:
            return

        # Normalize weights based on performance
        total_performance = sum(recent_performance.values())
        if total_performance > 0:
            self.model_weights = {
                name: perf / total_performance
                for name, perf in recent_performance.items()
            }

        # Ensure weights sum to 1
        weight_sum = sum(self.model_weights.values())
        if weight_sum > 0:
            self.model_weights = {
                name: w / weight_sum for name, w in self.model_weights.items()
            }

    def get_feature_importance(self) -> Dict[str, np.ndarray]:
        """Get feature importance from tree-based models."""
        importance = {}

        for name, model in self.models.items():
            if hasattr(model, "feature_importances_"):
                importance[name] = model.feature_importances_
            elif hasattr(model, "coef_"):
                # For logistic regression, use absolute coefficients
                importance[name] = np.abs(model.coef_[0])

        return importance

    def get_model_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for each model."""
        stats = {}

        for name in self.models:
            stats[name] = {
                "weight": self.model_weights.get(name, 0),
                "recent_accuracy": (
                    np.mean(self.model_performance[name][-20:])
                    if self.model_performance[name]
                    else 0.5
                ),
            }

        return stats


# ==============================================================================
# ENSEMBLE MANAGER
# ==============================================================================


class EnsembleManager:
    """
    Manages ensemble forecaster lifecycle:
    - Training on new data
    - Performance monitoring
    - Weight updates
    - Model versioning
    """

    def __init__(self, memory=None):
        self.memory = memory
        self.forecaster = EnsembleForecaster(memory)
        self.training_history = []

    def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, float]:
        """Train ensemble on labeled data."""
        accuracies = self.forecaster.fit(X, y)

        # Record training event
        self.training_history.append(
            {
                "timestamp": np.datetime64("now"),
                "n_samples": len(y),
                "accuracies": accuracies,
            }
        )

        return accuracies

    def evaluate_and_update(self, X_test: np.ndarray, y_test: np.ndarray):
        """
        Evaluate models on test set and update weights.

        Args:
            X_test: Test features
            y_test: Test labels
        """
        model_accuracies = {}

        for name, model in self.forecaster.models.items():
            try:
                y_pred = model.predict(X_test)
                accuracy = np.mean(y_pred == y_test)
                model_accuracies[name] = accuracy

                # Track performance
                self.forecaster.model_performance[name].append(accuracy)

            except Exception:
                model_accuracies[name] = 0.5

        # Update weights based on recent performance
        self.forecaster.update_model_weights(model_accuracies)

        return model_accuracies

    def predict(self, X: np.ndarray) -> EnsemblePrediction:
        """Make prediction with current ensemble."""
        return self.forecaster.predict_with_uncertainty(X)

    def get_diagnostics(self) -> Dict:
        """Get ensemble diagnostics and health metrics."""
        return {
            "model_weights": self.forecaster.model_weights,
            "model_stats": self.forecaster.get_model_stats(),
            "training_count": len(self.training_history),
            "last_training": (
                self.training_history[-1] if self.training_history else None
            ),
        }
