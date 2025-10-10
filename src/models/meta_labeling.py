"""Meta-labeling system for reducing false positives in predictions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

from src.core.logging_config import get_logger
from src.models.lightgbm_pipeline import LightGBMPipeline, ModelMetrics

logger = get_logger(__name__)


@dataclass
class MetaLabelingConfig:
    """Configuration for meta-labeling system."""

    primary_threshold: float = 0.5  # Threshold for primary model
    meta_threshold: float = 0.7  # Threshold for meta model (higher = more conservative)
    min_confidence_gap: float = 0.2  # Minimum gap between positive/negative confidence


class MetaLabeler:
    """
    Meta-labeling system to filter primary model predictions.
    
    The meta model learns to predict whether the primary model's
    positive predictions are actually correct, reducing false positives.
    
    Pipeline:
    1. Primary model makes predictions
    2. Meta model evaluates confidence of positive predictions
    3. Only high-confidence predictions are kept
    """

    def __init__(
        self,
        primary_model: LightGBMPipeline,
        meta_model_dir: Path,
        config: Optional[MetaLabelingConfig] = None,
    ) -> None:
        """
        Initialize meta-labeling system.

        Args:
            primary_model: Trained primary LightGBM model
            meta_model_dir: Directory to save meta model
            config: Meta-labeling configuration
        """
        self.primary_model = primary_model
        self.meta_model_dir = Path(meta_model_dir)
        self.meta_model_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or MetaLabelingConfig()

        # Meta model parameters (simpler than primary)
        meta_params = {
            "objective": "binary",
            "metric": "auc",
            "boosting_type": "gbdt",
            "num_leaves": 15,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "max_depth": 5,
            "min_child_samples": 20,
            "scale_pos_weight": 1.0,  # Balanced for meta-labeling
            "verbosity": -1,
            "seed": 42,
        }

        self.meta_pipeline = LightGBMPipeline(
            model_dir=self.meta_model_dir,
            params=meta_params,
        )

    def create_meta_features(
        self,
        X: pd.DataFrame,
        primary_predictions: np.ndarray,
    ) -> pd.DataFrame:
        """
        Create features for meta model.

        Meta features include:
        - Primary model probability
        - Confidence metrics (probability - 0.5)
        - Original feature statistics
        - Feature crosses indicating uncertainty

        Args:
            X: Original features
            primary_predictions: Primary model probabilities

        Returns:
            DataFrame with meta features
        """
        meta_df = pd.DataFrame()

        # Primary model outputs
        meta_df["primary_proba"] = primary_predictions
        meta_df["primary_confidence"] = np.abs(primary_predictions - 0.5)
        meta_df["primary_logit"] = np.log(
            (primary_predictions + 1e-10) / (1 - primary_predictions + 1e-10)
        )

        # Prediction bins
        meta_df["pred_bin_low"] = (primary_predictions < 0.3).astype(float)
        meta_df["pred_bin_mid"] = ((primary_predictions >= 0.3) & (primary_predictions < 0.7)).astype(
            float
        )
        meta_df["pred_bin_high"] = (primary_predictions >= 0.7).astype(float)

        # Feature statistics (summary of input uncertainty)
        if len(X.columns) > 0:
            # Mean and std of original features
            meta_df["feature_mean"] = X.mean(axis=1)
            meta_df["feature_std"] = X.std(axis=1)
            meta_df["feature_min"] = X.min(axis=1)
            meta_df["feature_max"] = X.max(axis=1)
            meta_df["feature_range"] = meta_df["feature_max"] - meta_df["feature_min"]

            # Feature crosses with prediction
            meta_df["pred_x_mean"] = primary_predictions * meta_df["feature_mean"]
            meta_df["pred_x_std"] = primary_predictions * meta_df["feature_std"]

            # Select top important features from primary model
            feature_importance = self.primary_model.get_feature_importance()
            top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]

            for feat_name, _ in top_features:
                if feat_name in X.columns:
                    meta_df[f"top_feat_{feat_name}"] = X[feat_name].values

        return meta_df

    def create_meta_labels(
        self,
        y_true: pd.Series,
        primary_predictions: np.ndarray,
    ) -> pd.Series:
        """
        Create labels for meta model.

        Meta label is 1 if:
        - Primary model predicted positive (>= threshold)
        - True label is actually positive
        
        Meta label is 0 if:
        - Primary model predicted positive
        - True label is actually negative (false positive)

        We only train on samples where primary predicted positive.

        Args:
            y_true: True labels
            primary_predictions: Primary model probabilities

        Returns:
            Series of meta labels
        """
        # Meta label = (primary predicted positive) AND (actually positive)
        primary_positive = (primary_predictions >= self.config.primary_threshold).astype(int)
        meta_labels = (primary_positive & y_true.values).astype(int)

        return pd.Series(meta_labels, index=y_true.index)

    def train_meta_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        num_boost_round: int = 500,
        early_stopping_rounds: int = 30,
    ) -> ModelMetrics:
        """
        Train meta model on primary model predictions.

        Args:
            X: Original features
            y: True labels
            num_boost_round: Maximum boosting rounds
            early_stopping_rounds: Early stopping patience

        Returns:
            ModelMetrics from meta model training
        """
        # Get primary predictions
        primary_probs = self.primary_model.predict(X)

        # Create meta features
        X_meta = self.create_meta_features(X, primary_probs)

        # Create meta labels
        y_meta = self.create_meta_labels(y, primary_probs)

        # Filter to only samples where primary predicted positive
        positive_mask = primary_probs >= self.config.primary_threshold
        X_meta_filtered = X_meta[positive_mask]
        y_meta_filtered = y_meta[positive_mask]

        logger.info(
            "meta_training_data",
            total_samples=len(X),
            primary_positives=int(positive_mask.sum()),
            meta_positive_rate=float(y_meta_filtered.mean()),
        )

        if len(X_meta_filtered) < 10:
            logger.warning("insufficient_meta_samples", n_samples=len(X_meta_filtered))
            raise ValueError("Insufficient samples for meta-labeling training")

        # Prepare and train meta model
        feature_cols = list(X_meta_filtered.columns)
        X_meta_prepared, y_meta_prepared = self.meta_pipeline.prepare_features(
            pd.concat([X_meta_filtered, y_meta_filtered.rename("target")], axis=1),
            feature_columns=feature_cols,
            target_column="target",
        )

        metrics = self.meta_pipeline.train(
            X_meta_prepared,
            y_meta_prepared,
            num_boost_round=num_boost_round,
            early_stopping_rounds=early_stopping_rounds,
        )

        logger.info(
            "meta_model_trained",
            precision=metrics.precision,
            recall=metrics.recall,
            f1=metrics.f1_score,
        )

        return metrics

    def predict_with_meta(
        self,
        X: pd.DataFrame,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Make predictions using both primary and meta models.

        Args:
            X: Features

        Returns:
            Tuple of (primary_probs, meta_probs, final_predictions)
        """
        # Primary predictions
        primary_probs = self.primary_model.predict(X)

        # Create meta features
        X_meta = self.create_meta_features(X, primary_probs)

        # Meta predictions (only for primary positives)
        meta_probs = self.meta_pipeline.predict(X_meta)

        # Final prediction: primary positive AND meta confirms
        final_predictions = (
            (primary_probs >= self.config.primary_threshold)
            & (meta_probs >= self.config.meta_threshold)
        ).astype(int)

        logger.debug(
            "meta_prediction_summary",
            primary_positives=int((primary_probs >= self.config.primary_threshold).sum()),
            meta_filtered=int(final_predictions.sum()),
            filter_rate=1.0
            - (final_predictions.sum() / max((primary_probs >= self.config.primary_threshold).sum(), 1)),
        )

        return primary_probs, meta_probs, final_predictions

    def evaluate_meta_system(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> Dict[str, Dict[str, float]]:
        """
        Evaluate both primary and meta-filtered predictions.

        Args:
            X: Features
            y: True labels

        Returns:
            Dict with metrics for primary and meta-filtered predictions
        """
        primary_probs, meta_probs, final_preds = self.predict_with_meta(X)
        primary_preds = (primary_probs >= self.config.primary_threshold).astype(int)

        # Primary metrics
        primary_metrics = {
            "precision": float(precision_score(y, primary_preds, zero_division=0)),
            "recall": float(recall_score(y, primary_preds, zero_division=0)),
            "f1": float(f1_score(y, primary_preds, zero_division=0)),
            "n_predictions": int(primary_preds.sum()),
        }

        # Meta-filtered metrics
        meta_metrics = {
            "precision": float(precision_score(y, final_preds, zero_division=0)),
            "recall": float(recall_score(y, final_preds, zero_division=0)),
            "f1": float(f1_score(y, final_preds, zero_division=0)),
            "n_predictions": int(final_preds.sum()),
        }

        # Calculate improvement
        precision_improvement = meta_metrics["precision"] - primary_metrics["precision"]
        recall_tradeoff = meta_metrics["recall"] - primary_metrics["recall"]

        logger.info(
            "meta_evaluation",
            primary_precision=primary_metrics["precision"],
            meta_precision=meta_metrics["precision"],
            precision_improvement=precision_improvement,
            recall_tradeoff=recall_tradeoff,
        )

        return {
            "primary": primary_metrics,
            "meta_filtered": meta_metrics,
            "improvement": {
                "precision_gain": precision_improvement,
                "recall_loss": recall_tradeoff,
            },
        }

    def save_meta_model(self) -> None:
        """Save meta model to disk."""
        # Meta pipeline handles its own saving
        logger.info("meta_model_saved", path=str(self.meta_model_dir))

    def load_meta_model(self) -> None:
        """Load meta model from disk."""
        self.meta_pipeline.load_model()
        logger.info("meta_model_loaded", path=str(self.meta_model_dir))
