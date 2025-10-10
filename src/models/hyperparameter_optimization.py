"""Hyperparameter optimization using Optuna."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import optuna
import pandas as pd
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

from src.core.logging_config import get_logger
from src.models.lightgbm_pipeline import LightGBMPipeline

logger = get_logger(__name__)


class HyperparameterOptimizer:
    """
    Hyperparameter optimization for LightGBM models using Optuna.
    
    Features:
    - Bayesian optimization with TPE sampler
    - Early stopping via median pruning
    - Multi-objective optimization support
    - Detailed logging and visualization
    """

    def __init__(
        self,
        study_name: str,
        storage_dir: Path,
        direction: str = "maximize",
        n_trials: int = 100,
        n_jobs: int = 1,
        timeout: Optional[int] = None,
    ) -> None:
        """
        Initialize hyperparameter optimizer.

        Args:
            study_name: Name of the optimization study
            storage_dir: Directory to store study results
            direction: Optimization direction ('maximize' or 'minimize')
            n_trials: Number of optimization trials
            n_jobs: Number of parallel jobs
            timeout: Timeout in seconds (None for no timeout)
        """
        self.study_name = study_name
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.direction = direction
        self.n_trials = n_trials
        self.n_jobs = n_jobs
        self.timeout = timeout

        # Create storage path
        storage_path = self.storage_dir / "optuna_study.db"
        storage_url = f"sqlite:///{storage_path}"

        # Create study
        self.study = optuna.create_study(
            study_name=study_name,
            storage=storage_url,
            direction=direction,
            load_if_exists=True,
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=10, n_warmup_steps=5),
        )

        self.best_params: Optional[Dict] = None
        self.best_score: Optional[float] = None

    def optimize_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        metric: str = "f1",
        fixed_params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Optimize LightGBM hyperparameters.

        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features
            y_val: Validation target
            metric: Metric to optimize ('f1', 'precision', 'recall', 'roc_auc')
            fixed_params: Parameters to keep fixed

        Returns:
            Dict of best hyperparameters
        """
        fixed_params = fixed_params or {}

        def objective(trial: optuna.Trial) -> float:
            """Optuna objective function."""
            # Sample hyperparameters
            params = {
                "objective": "binary",
                "metric": "auc",
                "boosting_type": trial.suggest_categorical(
                    "boosting_type", ["gbdt", "dart", "goss"]
                ),
                "num_leaves": trial.suggest_int("num_leaves", 15, 127),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
                "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
                "bagging_freq": trial.suggest_int("bagging_freq", 1, 10),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
                "min_child_weight": trial.suggest_float("min_child_weight", 1e-3, 10.0, log=True),
                "subsample": trial.suggest_float("subsample", 0.5, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
                "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 20.0),
                "verbosity": -1,
                "seed": 42,
            }

            # Override with fixed params
            params.update(fixed_params)

            # Create pipeline
            temp_dir = self.storage_dir / f"trial_{trial.number}"
            temp_dir.mkdir(exist_ok=True)

            pipeline = LightGBMPipeline(model_dir=temp_dir, params=params)

            # Train model
            try:
                import lightgbm as lgb

                train_data = lgb.Dataset(X_train, label=y_train)
                val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

                # Train with pruning callback
                pruning_callback = optuna.integration.LightGBMPruningCallback(trial, metric)

                model = lgb.train(
                    params,
                    train_data,
                    num_boost_round=1000,
                    valid_sets=[val_data],
                    valid_names=["val"],
                    callbacks=[
                        lgb.early_stopping(stopping_rounds=50),
                        pruning_callback,
                    ],
                )

                # Get predictions
                y_pred_proba = model.predict(X_val)
                y_pred = (y_pred_proba > 0.5).astype(int)

                # Calculate metric
                from sklearn.metrics import (
                    f1_score,
                    precision_score,
                    recall_score,
                    roc_auc_score,
                )

                if metric == "f1":
                    score = f1_score(y_val, y_pred, zero_division=0)
                elif metric == "precision":
                    score = precision_score(y_val, y_pred, zero_division=0)
                elif metric == "recall":
                    score = recall_score(y_val, y_pred, zero_division=0)
                elif metric == "roc_auc":
                    score = roc_auc_score(y_val, y_pred_proba)
                else:
                    raise ValueError(f"Unknown metric: {metric}")

                return float(score)

            except optuna.TrialPruned:
                raise
            except Exception as exc:
                logger.error("optuna_trial_failed", trial_number=trial.number, error=str(exc))
                return 0.0

        # Run optimization
        logger.info(
            "optuna_optimization_start",
            study_name=self.study_name,
            n_trials=self.n_trials,
            metric=metric,
        )

        self.study.optimize(
            objective,
            n_trials=self.n_trials,
            n_jobs=self.n_jobs,
            timeout=self.timeout,
            show_progress_bar=True,
        )

        # Get best results
        self.best_params = self.study.best_params
        self.best_score = self.study.best_value

        logger.info(
            "optuna_optimization_complete",
            best_score=self.best_score,
            n_trials=len(self.study.trials),
            best_params=self.best_params,
        )

        # Save results
        self._save_results(metric)

        return self.best_params

    def optimize_meta_labeling(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
    ) -> Dict[str, Any]:
        """
        Optimize meta-labeling thresholds.

        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features
            y_val: Validation target

        Returns:
            Dict of best thresholds
        """

        def objective(trial: optuna.Trial) -> float:
            """Objective for meta-labeling thresholds."""
            primary_threshold = trial.suggest_float("primary_threshold", 0.3, 0.7)
            meta_threshold = trial.suggest_float("meta_threshold", 0.5, 0.9)

            # This would integrate with actual meta-labeling pipeline
            # For now, return a placeholder
            return 0.0

        logger.info("meta_labeling_optimization_start", n_trials=self.n_trials)

        self.study.optimize(objective, n_trials=self.n_trials, n_jobs=self.n_jobs)

        self.best_params = self.study.best_params
        self.best_score = self.study.best_value

        self._save_results("meta_labeling")

        return self.best_params

    def get_best_params(self) -> Dict[str, Any]:
        """Get best parameters from study."""
        if self.best_params is None:
            return self.study.best_params
        return self.best_params

    def get_study_summary(self) -> pd.DataFrame:
        """Get summary of all trials."""
        trials = self.study.trials
        summary_data = []

        for trial in trials:
            summary_data.append({
                "trial_number": trial.number,
                "value": trial.value,
                "state": trial.state.name,
                **trial.params,
            })

        return pd.DataFrame(summary_data)

    def plot_optimization_history(self, save_path: Optional[Path] = None) -> None:
        """
        Plot optimization history.

        Args:
            save_path: Optional path to save plot
        """
        try:
            from optuna.visualization import (
                plot_optimization_history,
                plot_param_importances,
                plot_slice,
            )
            import plotly.io as pio

            # Optimization history
            fig = plot_optimization_history(self.study)
            save_file = save_path or (self.storage_dir / "optimization_history.html")
            pio.write_html(fig, str(save_file))

            # Parameter importances
            fig = plot_param_importances(self.study)
            save_file = save_path or (self.storage_dir / "param_importances.html")
            pio.write_html(fig, str(save_file))

            # Slice plot
            fig = plot_slice(self.study)
            save_file = save_path or (self.storage_dir / "param_slice.html")
            pio.write_html(fig, str(save_file))

            logger.info("optuna_plots_saved", storage_dir=str(self.storage_dir))

        except ImportError:
            logger.warning("plotly_not_available", message="Cannot create visualization")

    def _save_results(self, metric: str) -> None:
        """Save optimization results."""
        # Save best params
        best_params_file = self.storage_dir / "best_params.json"
        with open(best_params_file, "w") as f:
            json.dump({
                "best_params": self.best_params,
                "best_score": self.best_score,
                "metric": metric,
                "n_trials": len(self.study.trials),
            }, f, indent=2)

        # Save trial summary
        summary_df = self.get_study_summary()
        summary_file = self.storage_dir / "trials_summary.csv"
        summary_df.to_csv(summary_file, index=False)

        # Create plots
        self.plot_optimization_history()

        logger.info("optuna_results_saved", storage_dir=str(self.storage_dir))


class MultiObjectiveOptimizer(HyperparameterOptimizer):
    """
    Multi-objective hyperparameter optimization.
    
    Optimizes multiple metrics simultaneously (e.g., precision and recall).
    """

    def __init__(
        self,
        study_name: str,
        storage_dir: Path,
        directions: List[str],
        n_trials: int = 100,
        n_jobs: int = 1,
    ) -> None:
        """
        Initialize multi-objective optimizer.

        Args:
            study_name: Name of study
            storage_dir: Storage directory
            directions: List of directions for each objective
            n_trials: Number of trials
            n_jobs: Number of parallel jobs
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.n_trials = n_trials
        self.n_jobs = n_jobs

        storage_path = self.storage_dir / "optuna_multi_study.db"
        storage_url = f"sqlite:///{storage_path}"

        # Create multi-objective study
        self.study = optuna.create_study(
            study_name=study_name,
            storage=storage_url,
            directions=directions,
            load_if_exists=True,
            sampler=TPESampler(seed=42),
        )

        self.study_name = study_name

    def optimize_precision_recall(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame,
        y_val: pd.Series,
        fixed_params: Optional[Dict] = None,
    ) -> List[Dict[str, Any]]:
        """
        Optimize for both precision and recall.

        Args:
            X_train: Training features
            y_train: Training target
            X_val: Validation features
            y_val: Validation target
            fixed_params: Fixed parameters

        Returns:
            List of Pareto-optimal parameter sets
        """
        fixed_params = fixed_params or {}

        def objective(trial: optuna.Trial) -> tuple:
            """Multi-objective function."""
            # Sample hyperparameters (similar to single-objective)
            params = {
                "objective": "binary",
                "metric": "auc",
                "boosting_type": "gbdt",
                "num_leaves": trial.suggest_int("num_leaves", 15, 127),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "scale_pos_weight": trial.suggest_float("scale_pos_weight", 1.0, 20.0),
                "verbosity": -1,
                "seed": 42,
            }
            params.update(fixed_params)

            # Train model
            try:
                import lightgbm as lgb
                from sklearn.metrics import precision_score, recall_score

                train_data = lgb.Dataset(X_train, label=y_train)
                val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

                model = lgb.train(
                    params,
                    train_data,
                    num_boost_round=1000,
                    valid_sets=[val_data],
                    callbacks=[lgb.early_stopping(stopping_rounds=50)],
                )

                y_pred_proba = model.predict(X_val)
                y_pred = (y_pred_proba > 0.5).astype(int)

                precision = precision_score(y_val, y_pred, zero_division=0)
                recall = recall_score(y_val, y_pred, zero_division=0)

                return float(precision), float(recall)

            except Exception as exc:
                logger.error("multi_objective_trial_failed", error=str(exc))
                return 0.0, 0.0

        logger.info("multi_objective_optimization_start", n_trials=self.n_trials)

        self.study.optimize(objective, n_trials=self.n_trials, n_jobs=self.n_jobs)

        # Get Pareto front
        pareto_trials = [t for t in self.study.best_trials]
        pareto_params = [t.params for t in pareto_trials]

        logger.info(
            "multi_objective_complete",
            n_pareto_solutions=len(pareto_trials),
        )

        return pareto_params
