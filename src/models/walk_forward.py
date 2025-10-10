"""Walk-forward optimization framework for model validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score

from src.core.logging_config import get_logger
from src.models.lightgbm_pipeline import LightGBMPipeline

logger = get_logger(__name__)


@dataclass
class WalkForwardWindow:
    """Single walk-forward validation window."""

    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_size: int
    test_size: int


@dataclass
class WalkForwardResults:
    """Results from walk-forward validation."""

    window_id: int
    train_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    feature_importance: Dict[str, float]
    predictions: pd.DataFrame
    best_iteration: int


class WalkForwardOptimizer:
    """
    Walk-forward optimization for time series models.
    
    Performs rolling window backtesting with:
    - Expanding or sliding training windows
    - Out-of-sample testing
    - Performance tracking across time periods
    - Feature stability analysis
    """

    def __init__(
        self,
        train_window_size: timedelta,
        test_window_size: timedelta,
        step_size: timedelta,
        min_train_size: int = 1000,
        expanding_window: bool = False,
        results_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize walk-forward optimizer.

        Args:
            train_window_size: Size of training window
            test_window_size: Size of test window
            step_size: Step size between windows
            min_train_size: Minimum samples required for training
            expanding_window: If True, use expanding window; else sliding
            results_dir: Directory to save results
        """
        self.train_window_size = train_window_size
        self.test_window_size = test_window_size
        self.step_size = step_size
        self.min_train_size = min_train_size
        self.expanding_window = expanding_window
        self.results_dir = Path(results_dir) if results_dir else Path("walk_forward_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.windows: List[WalkForwardWindow] = []
        self.results: List[WalkForwardResults] = []

    def create_windows(
        self,
        df: pd.DataFrame,
        time_column: str = "timestamp",
    ) -> List[WalkForwardWindow]:
        """
        Create walk-forward windows.

        Args:
            df: Dataframe with time column
            time_column: Name of timestamp column

        Returns:
            List of WalkForwardWindow objects
        """
        # Ensure time column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            df[time_column] = pd.to_datetime(df[time_column])

        df = df.sort_values(time_column)

        start_time = df[time_column].min()
        end_time = df[time_column].max()

        windows = []
        window_id = 0

        # First training window
        train_end = start_time + self.train_window_size
        test_start = train_end
        test_end = test_start + self.test_window_size

        while test_end <= end_time:
            # Determine train start
            if self.expanding_window:
                train_start = start_time
            else:
                train_start = train_end - self.train_window_size

            # Count samples
            train_mask = (df[time_column] >= train_start) & (df[time_column] < train_end)
            test_mask = (df[time_column] >= test_start) & (df[time_column] < test_end)

            train_size = train_mask.sum()
            test_size = test_mask.sum()

            if train_size >= self.min_train_size and test_size > 0:
                window = WalkForwardWindow(
                    window_id=window_id,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_size=train_size,
                    test_size=test_size,
                )
                windows.append(window)
                window_id += 1

            # Move to next window
            train_end += self.step_size
            test_start = train_end
            test_end = test_start + self.test_window_size

        self.windows = windows

        logger.info(
            "walk_forward_windows_created",
            n_windows=len(windows),
            expanding=self.expanding_window,
            total_days=(end_time - start_time).days,
        )

        return windows

    def run_optimization(
        self,
        df: pd.DataFrame,
        feature_columns: List[str],
        target_column: str = "is_gem",
        time_column: str = "timestamp",
        model_params: Optional[Dict] = None,
        num_boost_round: int = 1000,
        early_stopping_rounds: int = 50,
    ) -> List[WalkForwardResults]:
        """
        Run walk-forward optimization.

        Args:
            df: Training data
            feature_columns: List of feature columns
            target_column: Target column name
            time_column: Time column name
            model_params: LightGBM parameters
            num_boost_round: Max boosting rounds
            early_stopping_rounds: Early stopping patience

        Returns:
            List of WalkForwardResults
        """
        if not self.windows:
            self.create_windows(df, time_column)

        # Ensure time column is datetime
        if not pd.api.types.is_datetime64_any_dtype(df[time_column]):
            df[time_column] = pd.to_datetime(df[time_column])

        results = []

        for window in self.windows:
            logger.info(
                "walk_forward_window_start",
                window_id=window.window_id,
                train_start=window.train_start,
                test_end=window.test_end,
            )

            # Split data
            train_mask = (df[time_column] >= window.train_start) & (df[time_column] < window.train_end)
            test_mask = (df[time_column] >= window.test_start) & (df[time_column] < window.test_end)

            train_df = df[train_mask].copy()
            test_df = df[test_mask].copy()

            if len(train_df) < self.min_train_size or len(test_df) == 0:
                logger.warning(
                    "insufficient_data",
                    window_id=window.window_id,
                    train_size=len(train_df),
                    test_size=len(test_df),
                )
                continue

            # Create model for this window
            model_dir = self.results_dir / f"window_{window.window_id}"
            model_dir.mkdir(exist_ok=True)

            pipeline = LightGBMPipeline(model_dir=model_dir, params=model_params)

            # Prepare features
            X_train, y_train = pipeline.prepare_features(
                train_df, feature_columns, target_column
            )
            X_test, y_test = pipeline.prepare_features(test_df, feature_columns, target_column)

            # Train model
            train_metrics = pipeline.train(
                X_train,
                y_train,
                num_boost_round=num_boost_round,
                early_stopping_rounds=early_stopping_rounds,
                val_size=0.0,  # No validation split, using test as OOS
            )

            # Get test predictions
            y_pred_proba = pipeline.predict(X_test)
            y_pred = (y_pred_proba > 0.5).astype(int)

            # Calculate test metrics
            test_metrics = {
                "precision": float(precision_score(y_test, y_pred, zero_division=0)),
                "recall": float(recall_score(y_test, y_pred, zero_division=0)),
                "f1": float(f1_score(y_test, y_pred, zero_division=0)),
                "roc_auc": float(roc_auc_score(y_test, y_pred_proba)),
                "n_samples": len(y_test),
                "n_positives": int(y_test.sum()),
                "n_predicted_positives": int(y_pred.sum()),
            }

            # Get feature importance
            feature_importance = pipeline.get_feature_importance()

            # Store predictions
            predictions_df = pd.DataFrame({
                "timestamp": test_df[time_column].values,
                "y_true": y_test.values,
                "y_pred": y_pred,
                "y_pred_proba": y_pred_proba,
            })

            # Create result
            result = WalkForwardResults(
                window_id=window.window_id,
                train_metrics={
                    "precision": train_metrics.precision,
                    "recall": train_metrics.recall,
                    "f1": train_metrics.f1_score,
                    "roc_auc": train_metrics.roc_auc,
                },
                test_metrics=test_metrics,
                feature_importance=feature_importance,
                predictions=predictions_df,
                best_iteration=pipeline.model.best_iteration if pipeline.model else 0,
            )

            results.append(result)

            logger.info(
                "walk_forward_window_complete",
                window_id=window.window_id,
                test_precision=test_metrics["precision"],
                test_recall=test_metrics["recall"],
                test_f1=test_metrics["f1"],
            )

        self.results = results
        self._save_results()

        return results

    def get_aggregate_metrics(self) -> Dict[str, float]:
        """
        Get aggregate metrics across all windows.

        Returns:
            Dict of aggregated metrics
        """
        if not self.results:
            return {}

        # Aggregate test metrics
        test_precisions = [r.test_metrics["precision"] for r in self.results]
        test_recalls = [r.test_metrics["recall"] for r in self.results]
        test_f1s = [r.test_metrics["f1"] for r in self.results]
        test_aucs = [r.test_metrics["roc_auc"] for r in self.results]

        return {
            "mean_precision": float(np.mean(test_precisions)),
            "std_precision": float(np.std(test_precisions)),
            "mean_recall": float(np.mean(test_recalls)),
            "std_recall": float(np.std(test_recalls)),
            "mean_f1": float(np.mean(test_f1s)),
            "std_f1": float(np.std(test_f1s)),
            "mean_roc_auc": float(np.mean(test_aucs)),
            "std_roc_auc": float(np.std(test_aucs)),
            "n_windows": len(self.results),
        }

    def get_feature_stability(self) -> pd.DataFrame:
        """
        Analyze feature importance stability across windows.

        Returns:
            DataFrame with feature stability metrics
        """
        if not self.results:
            return pd.DataFrame()

        # Collect feature importance across windows
        all_features = set()
        for result in self.results:
            all_features.update(result.feature_importance.keys())

        feature_data = {feat: [] for feat in all_features}

        for result in self.results:
            for feat in all_features:
                importance = result.feature_importance.get(feat, 0.0)
                feature_data[feat].append(importance)

        # Calculate stability metrics
        stability_df = pd.DataFrame({
            "feature": list(all_features),
            "mean_importance": [np.mean(feature_data[f]) for f in all_features],
            "std_importance": [np.std(feature_data[f]) for f in all_features],
            "cv_importance": [
                np.std(feature_data[f]) / (np.mean(feature_data[f]) + 1e-10)
                for f in all_features
            ],
        })

        stability_df = stability_df.sort_values("mean_importance", ascending=False)

        return stability_df

    def _save_results(self) -> None:
        """Save walk-forward results to disk."""
        # Save aggregate metrics
        aggregate_metrics = self.get_aggregate_metrics()
        metrics_file = self.results_dir / "aggregate_metrics.json"

        import json

        with open(metrics_file, "w") as f:
            json.dump(aggregate_metrics, f, indent=2)

        # Save feature stability
        stability_df = self.get_feature_stability()
        stability_file = self.results_dir / "feature_stability.csv"
        stability_df.to_csv(stability_file, index=False)

        # Save window-by-window results
        results_summary = []
        for result in self.results:
            results_summary.append({
                "window_id": result.window_id,
                **result.test_metrics,
            })

        summary_df = pd.DataFrame(results_summary)
        summary_file = self.results_dir / "window_results.csv"
        summary_df.to_csv(summary_file, index=False)

        # Save detailed predictions
        all_predictions = pd.concat([r.predictions for r in self.results], ignore_index=True)
        predictions_file = self.results_dir / "all_predictions.csv"
        all_predictions.to_csv(predictions_file, index=False)

        logger.info("walk_forward_results_saved", results_dir=str(self.results_dir))

    def plot_results(self, save_path: Optional[Path] = None) -> None:
        """
        Plot walk-forward results.

        Args:
            save_path: Optional path to save plot
        """
        try:
            import matplotlib.pyplot as plt

            fig, axes = plt.subplots(2, 2, figsize=(15, 10))

            # Extract metrics
            window_ids = [r.window_id for r in self.results]
            precisions = [r.test_metrics["precision"] for r in self.results]
            recalls = [r.test_metrics["recall"] for r in self.results]
            f1s = [r.test_metrics["f1"] for r in self.results]
            aucs = [r.test_metrics["roc_auc"] for r in self.results]

            # Plot precision
            axes[0, 0].plot(window_ids, precisions, marker="o")
            axes[0, 0].set_title("Precision Over Time")
            axes[0, 0].set_xlabel("Window ID")
            axes[0, 0].set_ylabel("Precision")
            axes[0, 0].grid(True)

            # Plot recall
            axes[0, 1].plot(window_ids, recalls, marker="o", color="orange")
            axes[0, 1].set_title("Recall Over Time")
            axes[0, 1].set_xlabel("Window ID")
            axes[0, 1].set_ylabel("Recall")
            axes[0, 1].grid(True)

            # Plot F1
            axes[1, 0].plot(window_ids, f1s, marker="o", color="green")
            axes[1, 0].set_title("F1 Score Over Time")
            axes[1, 0].set_xlabel("Window ID")
            axes[1, 0].set_ylabel("F1 Score")
            axes[1, 0].grid(True)

            # Plot ROC AUC
            axes[1, 1].plot(window_ids, aucs, marker="o", color="red")
            axes[1, 1].set_title("ROC AUC Over Time")
            axes[1, 1].set_xlabel("Window ID")
            axes[1, 1].set_ylabel("ROC AUC")
            axes[1, 1].grid(True)

            plt.tight_layout()

            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches="tight")
                logger.info("walk_forward_plot_saved", path=str(save_path))
            else:
                plt.savefig(self.results_dir / "walk_forward_results.png", dpi=300)
                logger.info("walk_forward_plot_saved", path=str(self.results_dir))

            plt.close()

        except ImportError:
            logger.warning("matplotlib_not_available", message="Cannot plot results")
