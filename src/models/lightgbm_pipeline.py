"""LightGBM training pipeline for hidden gem detection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import (
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
)

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ModelMetrics:
    """Metrics for model evaluation."""

    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    avg_precision: float
    feature_importance: Dict[str, float]


class LightGBMPipeline:
    """
    Training pipeline for LightGBM gem detection model.
    
    Features:
    - Time-series aware cross-validation
    - Feature importance tracking
    - Model checkpointing
    - Hyperparameter tracking
    """

    def __init__(
        self,
        model_dir: Path,
        params: Optional[Dict] = None,
    ) -> None:
        """
        Initialize LightGBM pipeline.

        Args:
            model_dir: Directory to save models and metrics
            params: LightGBM hyperparameters
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Default LightGBM parameters optimized for imbalanced classification
        self.params = params or {
            "objective": "binary",
            "metric": "auc",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "max_depth": -1,
            "min_child_samples": 20,
            "scale_pos_weight": 10.0,  # Handle imbalanced data
            "is_unbalance": True,
            "verbosity": -1,
            "seed": 42,
        }

        self.model: Optional[lgb.Booster] = None
        self.feature_names: List[str] = []
        self.training_history: List[Dict] = []

    def prepare_features(
        self,
        df: pd.DataFrame,
        feature_columns: List[str],
        target_column: str = "is_gem",
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare features and target for training.

        Args:
            df: Input dataframe with features and target
            feature_columns: List of feature column names
            target_column: Name of target column

        Returns:
            Tuple of (features_df, target_series)
        """
        # Handle missing values
        df = df.copy()
        df[feature_columns] = df[feature_columns].fillna(0)

        # Remove infinite values
        df[feature_columns] = df[feature_columns].replace([np.inf, -np.inf], 0)

        X = df[feature_columns]
        y = df[target_column]

        self.feature_names = feature_columns

        logger.info(
            "features_prepared",
            n_samples=len(X),
            n_features=len(feature_columns),
            positive_rate=float(y.mean()),
        )

        return X, y

    def train(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
        val_size: float = 0.2,
    ) -> ModelMetrics:
        """
        Train LightGBM model with validation.

        Args:
            X: Feature dataframe
            y: Target series
            num_boost_round: Maximum number of boosting rounds
            early_stopping_rounds: Early stopping patience
            val_size: Validation set size (fraction)

        Returns:
            ModelMetrics with training results
        """
        # Split into train/val preserving temporal order
        split_idx = int(len(X) * (1 - val_size))
        X_train, X_val = X.iloc[:split_idx], X.iloc[split_idx:]
        y_train, y_val = y.iloc[:split_idx], y.iloc[split_idx:]

        logger.info(
            "train_val_split",
            train_size=len(X_train),
            val_size=len(X_val),
            train_positive_rate=float(y_train.mean()),
            val_positive_rate=float(y_val.mean()),
        )

        # Create LightGBM datasets
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        # Train model
        callbacks = [
            lgb.log_evaluation(period=50),
            lgb.early_stopping(stopping_rounds=early_stopping_rounds),
        ]

        self.model = lgb.train(
            self.params,
            train_data,
            num_boost_round=num_boost_round,
            valid_sets=[train_data, val_data],
            valid_names=["train", "val"],
            callbacks=callbacks,
        )

        # Get predictions
        y_pred_proba = self.model.predict(X_val)
        y_pred = (y_pred_proba > 0.5).astype(int)

        # Calculate metrics
        metrics = self._calculate_metrics(y_val, y_pred, y_pred_proba)

        # Log metrics
        logger.info(
            "training_complete",
            precision=metrics.precision,
            recall=metrics.recall,
            f1=metrics.f1_score,
            roc_auc=metrics.roc_auc,
            avg_precision=metrics.avg_precision,
            num_iterations=self.model.best_iteration,
        )

        # Save model
        self._save_model(metrics)

        return metrics

    def cross_validate(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_splits: int = 5,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
    ) -> List[ModelMetrics]:
        """
        Perform time-series cross-validation.

        Args:
            X: Feature dataframe
            y: Target series
            n_splits: Number of CV splits
            num_boost_round: Maximum boosting rounds
            early_stopping_rounds: Early stopping patience

        Returns:
            List of ModelMetrics for each fold
        """
        tscv = TimeSeriesSplit(n_splits=n_splits)
        cv_metrics = []

        for fold_idx, (train_idx, val_idx) in enumerate(tscv.split(X)):
            logger.info("cv_fold_start", fold=fold_idx + 1, total_folds=n_splits)

            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            # Create LightGBM datasets
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

            # Train fold model
            callbacks = [
                lgb.log_evaluation(period=100),
                lgb.early_stopping(stopping_rounds=early_stopping_rounds),
            ]

            fold_model = lgb.train(
                self.params,
                train_data,
                num_boost_round=num_boost_round,
                valid_sets=[train_data, val_data],
                valid_names=["train", "val"],
                callbacks=callbacks,
            )

            # Get predictions
            y_pred_proba = fold_model.predict(X_val)
            y_pred = (y_pred_proba > 0.5).astype(int)

            # Calculate metrics
            metrics = self._calculate_metrics(y_val, y_pred, y_pred_proba)
            cv_metrics.append(metrics)

            logger.info(
                "cv_fold_complete",
                fold=fold_idx + 1,
                precision=metrics.precision,
                recall=metrics.recall,
                f1=metrics.f1_score,
                roc_auc=metrics.roc_auc,
            )

        # Calculate average metrics
        avg_metrics = self._average_metrics(cv_metrics)
        logger.info(
            "cv_complete",
            avg_precision=avg_metrics.precision,
            avg_recall=avg_metrics.recall,
            avg_f1=avg_metrics.f1_score,
            avg_roc_auc=avg_metrics.roc_auc,
        )

        return cv_metrics

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get predictions from trained model.

        Args:
            X: Feature dataframe

        Returns:
            Array of predicted probabilities
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        return self.model.predict(X)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Get prediction probabilities.

        Args:
            X: Feature dataframe

        Returns:
            Array of predicted probabilities
        """
        return self.predict(X)

    def get_feature_importance(self, importance_type: str = "gain") -> Dict[str, float]:
        """
        Get feature importance from trained model.

        Args:
            importance_type: Type of importance ('split', 'gain')

        Returns:
            Dict mapping feature names to importance scores
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        importance = self.model.feature_importance(importance_type=importance_type)
        return dict(zip(self.feature_names, importance))

    def _calculate_metrics(
        self,
        y_true: pd.Series,
        y_pred: np.ndarray,
        y_pred_proba: np.ndarray,
    ) -> ModelMetrics:
        """Calculate evaluation metrics."""
        feature_importance = self.get_feature_importance() if self.model else {}

        return ModelMetrics(
            precision=float(precision_score(y_true, y_pred, zero_division=0)),
            recall=float(recall_score(y_true, y_pred, zero_division=0)),
            f1_score=float(f1_score(y_true, y_pred, zero_division=0)),
            roc_auc=float(roc_auc_score(y_true, y_pred_proba)),
            avg_precision=float(average_precision_score(y_true, y_pred_proba)),
            feature_importance=feature_importance,
        )

    def _average_metrics(self, metrics_list: List[ModelMetrics]) -> ModelMetrics:
        """Average metrics across CV folds."""
        return ModelMetrics(
            precision=float(np.mean([m.precision for m in metrics_list])),
            recall=float(np.mean([m.recall for m in metrics_list])),
            f1_score=float(np.mean([m.f1_score for m in metrics_list])),
            roc_auc=float(np.mean([m.roc_auc for m in metrics_list])),
            avg_precision=float(np.mean([m.avg_precision for m in metrics_list])),
            feature_importance={},  # Would need to aggregate feature importance
        )

    def _save_model(self, metrics: ModelMetrics) -> None:
        """Save model and metrics to disk."""
        if self.model is None:
            return

        # Save model
        model_path = self.model_dir / "model.txt"
        self.model.save_model(str(model_path))

        # Save metrics
        metrics_path = self.model_dir / "metrics.json"
        metrics_dict = {
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "roc_auc": metrics.roc_auc,
            "avg_precision": metrics.avg_precision,
            "feature_importance": metrics.feature_importance,
        }
        with open(metrics_path, "w") as f:
            json.dump(metrics_dict, f, indent=2)

        # Save feature names
        features_path = self.model_dir / "features.json"
        with open(features_path, "w") as f:
            json.dump({"features": self.feature_names}, f, indent=2)

        # Save hyperparameters
        params_path = self.model_dir / "params.json"
        with open(params_path, "w") as f:
            json.dump(self.params, f, indent=2)

        logger.info("model_saved", model_dir=str(self.model_dir))

    def load_model(self, model_path: Optional[Path] = None) -> None:
        """
        Load model from disk.

        Args:
            model_path: Path to model file (default: model_dir/model.txt)
        """
        if model_path is None:
            model_path = self.model_dir / "model.txt"

        self.model = lgb.Booster(model_file=str(model_path))

        # Load feature names
        features_path = self.model_dir / "features.json"
        if features_path.exists():
            with open(features_path, "r") as f:
                data = json.load(f)
                self.feature_names = data["features"]

        logger.info("model_loaded", model_path=str(model_path))
