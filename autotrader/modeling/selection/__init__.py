"""
Model Selection and Cross-Validation
======================================

Time-series aware model selection with:
1. Walk-forward cross-validation
2. Purged K-fold (prevents leakage)
3. Hyperparameter optimization (Optuna)
4. Model comparison and ranking

Academic References:
- Lopez de Prado (2018): "Advances in Financial Machine Learning"
- Harvey & Liu (2015): "Backtesting"
- Bergmeir & Benítez (2012): "Time Series Cross-Validation"
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Callable, Tuple
from sklearn.model_selection import TimeSeriesSplit
import optuna
import logging

logger = logging.getLogger(__name__)


class WalkForwardCV:
    """
    Walk-forward cross-validation for time-series.
    
    Respects temporal ordering (no lookahead bias).
    Includes embargo period to prevent leakage from overlapping labels.
    
    Example
    -------
    >>> cv = WalkForwardCV(n_splits=5, test_size=0.2, embargo_period=10)
    >>> for train_idx, test_idx in cv.split(X):
    ...     X_train, X_test = X[train_idx], X[test_idx]
    ...     # Train and evaluate
    
    References
    ----------
    - Lopez de Prado (2018): "Advances in Financial Machine Learning", Chapter 7
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        test_size: float = 0.2,
        embargo_period: int = 0,
        purge_period: int = 0
    ):
        """
        Initialize walk-forward cross-validator.
        
        Parameters
        ----------
        n_splits : int
            Number of splits
        test_size : float
            Proportion of data for testing
        embargo_period : int
            Gap between train and test (rows) to prevent leakage
        purge_period : int
            Number of rows to remove from train set (overlapping labels)
        """
        self.n_splits = n_splits
        self.test_size = test_size
        self.embargo_period = embargo_period
        self.purge_period = purge_period
    
    def split(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Optional[Union[np.ndarray, pd.Series]] = None,
        groups: Optional[np.ndarray] = None
    ):
        """
        Generate train/test splits.
        
        Parameters
        ----------
        X : array-like
            Features
        y : array-like, optional
            Labels (not used, for sklearn compatibility)
        groups : array-like, optional
            Group labels (not used)
        
        Yields
        ------
        train_idx : np.ndarray
            Training indices
        test_idx : np.ndarray
            Testing indices
        """
        n_samples = len(X)
        test_size_samples = int(n_samples * self.test_size)
        
        # Calculate split points
        splits = []
        for i in range(self.n_splits):
            # Test set end
            test_end = n_samples - i * test_size_samples
            if test_end < test_size_samples:
                break
            
            # Test set start
            test_start = test_end - test_size_samples
            
            # Train set end (with embargo)
            train_end = test_start - self.embargo_period
            
            # Train set start
            train_start = max(0, test_start - int((n_samples - test_size_samples) * (i + 1) / self.n_splits))
            
            # Purge overlapping labels from train set
            if self.purge_period > 0:
                train_end = max(train_start, train_end - self.purge_period)
            
            if train_end > train_start:
                splits.append((
                    np.arange(train_start, train_end),
                    np.arange(test_start, test_end)
                ))
        
        # Reverse to go forward in time
        for train_idx, test_idx in reversed(splits):
            yield train_idx, test_idx
    
    def get_n_splits(self, X=None, y=None, groups=None):
        """Return number of splits."""
        return self.n_splits


class ModelSelector:
    """
    Model selection framework with hyperparameter optimization.
    
    Features:
    - Walk-forward cross-validation
    - Optuna hyperparameter optimization
    - Multi-objective optimization
    - Model comparison and ranking
    
    Example
    -------
    >>> selector = ModelSelector()
    >>> best_params = selector.optimize_hyperparameters(
    ...     model_type='xgboost',
    ...     X_train=X_train,
    ...     y_train=y_train,
    ...     X_val=X_val,
    ...     y_val=y_val,
    ...     metric='ev_per_trade',
    ...     n_trials=100
    ... )
    """
    
    def __init__(self):
        self.results = {}
    
    def walk_forward_cv(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        model,
        n_splits: int = 5,
        test_size: float = 0.2,
        embargo_period: int = 0,
        purge_period: int = 0,
        metric: str = 'auc',
        **eval_kwargs
    ) -> pd.DataFrame:
        """
        Perform walk-forward cross-validation.
        
        Parameters
        ----------
        X : array-like
            Features
        y : array-like
            Labels
        model : object
            Model to evaluate (must have fit, predict_proba methods)
        n_splits : int
            Number of CV splits
        test_size : float
            Proportion for testing
        embargo_period : int
            Embargo period (rows)
        purge_period : int
            Purge period (rows)
        metric : str
            Primary metric to track
        **eval_kwargs : dict
            Additional arguments for ModelEvaluator.evaluate()
        
        Returns
        -------
        results : pd.DataFrame
            CV results with metrics per fold
        """
        from autotrader.modeling.evaluation import ModelEvaluator
        
        cv = WalkForwardCV(
            n_splits=n_splits,
            test_size=test_size,
            embargo_period=embargo_period,
            purge_period=purge_period
        )
        
        evaluator = ModelEvaluator()
        results = []
        
        for fold, (train_idx, test_idx) in enumerate(cv.split(X)):
            logger.info(f"Fold {fold + 1}/{n_splits}")
            
            # Split data
            if isinstance(X, pd.DataFrame):
                X_train_fold = X.iloc[train_idx]
                X_test_fold = X.iloc[test_idx]
            else:
                X_train_fold = X[train_idx]
                X_test_fold = X[test_idx]
            
            if isinstance(y, pd.Series):
                y_train_fold = y.iloc[train_idx]
                y_test_fold = y.iloc[test_idx]
            else:
                y_train_fold = y[train_idx]
                y_test_fold = y[test_idx]
            
            # Train model
            model.fit(X_train_fold, y_train_fold)
            
            # Evaluate
            metrics = evaluator.evaluate(
                model=model,
                X_test=X_test_fold,
                y_test=y_test_fold,
                **eval_kwargs
            )
            
            metrics['fold'] = fold
            metrics['train_size'] = len(train_idx)
            metrics['test_size'] = len(test_idx)
            results.append(metrics)
        
        # Convert to dataframe
        results_df = pd.DataFrame(results)
        
        # Log summary
        logger.info(f"CV Summary ({metric}):")
        logger.info(f"  Mean: {results_df[metric].mean():.4f}")
        logger.info(f"  Std: {results_df[metric].std():.4f}")
        logger.info(f"  Min: {results_df[metric].min():.4f}")
        logger.info(f"  Max: {results_df[metric].max():.4f}")
        
        return results_df
    
    def optimize_hyperparameters(
        self,
        model_type: str,
        X_train: Union[np.ndarray, pd.DataFrame],
        y_train: Union[np.ndarray, pd.Series],
        X_val: Union[np.ndarray, pd.DataFrame],
        y_val: Union[np.ndarray, pd.Series],
        metric: str = 'auc',
        n_trials: int = 100,
        timeout: Optional[int] = None,
        **eval_kwargs
    ) -> Dict:
        """
        Optimize hyperparameters using Optuna.
        
        Parameters
        ----------
        model_type : str
            Model type: 'logistic', 'xgboost', 'lightgbm',
            'lstm', 'gru', 'tcn', 'transformer',
            'online_logistic', 'online_gb', 'vowpal_wabbit'
        X_train : array-like
            Training features
        y_train : array-like
            Training labels
        X_val : array-like
            Validation features
        y_val : array-like
            Validation labels
        metric : str
            Metric to optimize ('auc', 'ev_per_trade', 'sharpe')
        n_trials : int
            Number of optimization trials
        timeout : int, optional
            Timeout in seconds
        **eval_kwargs : dict
            Additional arguments for ModelEvaluator.evaluate()
        
        Returns
        -------
        best_params : dict
            Best hyperparameters
        
        Example
        -------
        >>> best_params = selector.optimize_hyperparameters(
        ...     model_type='lstm',
        ...     X_train=X_train,
        ...     y_train=y_train,
        ...     X_val=X_val,
        ...     y_val=y_val,
        ...     metric='ev_per_trade',
        ...     n_trials=50
        ... )
        """
        from autotrader.modeling.evaluation import ModelEvaluator
        
        evaluator = ModelEvaluator()
        
        def objective(trial):
            # Suggest hyperparameters based on model type
            if model_type == 'logistic':
                from autotrader.modeling.baselines import LogisticRegressionModel
                
                params = {
                    'penalty': trial.suggest_categorical('penalty', ['l1', 'l2', 'elasticnet']),
                    'C': trial.suggest_loguniform('C', 1e-3, 1e2),
                    'solver': 'saga',
                    'max_iter': 1000
                }
                
                if params['penalty'] == 'elasticnet':
                    params['l1_ratio'] = trial.suggest_uniform('l1_ratio', 0.0, 1.0)
                
                model = LogisticRegressionModel(**params)
            
            elif model_type == 'xgboost':
                from autotrader.modeling.baselines import XGBoostModel
                
                params = {
                    'max_depth': trial.suggest_int('max_depth', 3, 10),
                    'learning_rate': trial.suggest_loguniform('learning_rate', 1e-3, 1e-1),
                    'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                    'subsample': trial.suggest_uniform('subsample', 0.6, 1.0),
                    'colsample_bytree': trial.suggest_uniform('colsample_bytree', 0.6, 1.0),
                    'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-3, 10.0),
                    'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-3, 10.0)
                }
                
                model = XGBoostModel(**params)
            
            elif model_type == 'lightgbm':
                from autotrader.modeling.baselines import LightGBMModel
                
                params = {
                    'num_leaves': trial.suggest_int('num_leaves', 15, 63),
                    'max_depth': trial.suggest_int('max_depth', 3, 10),
                    'learning_rate': trial.suggest_loguniform('learning_rate', 1e-3, 1e-1),
                    'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                    'subsample': trial.suggest_uniform('subsample', 0.6, 1.0),
                    'colsample_bytree': trial.suggest_uniform('colsample_bytree', 0.6, 1.0),
                    'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-3, 10.0),
                    'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-3, 10.0),
                    'min_child_samples': trial.suggest_int('min_child_samples', 10, 50)
                }
                
                model = LightGBMModel(**params)
            
            elif model_type in ['lstm', 'gru', 'tcn']:
                from autotrader.modeling.sequential import LSTMModel, GRUModel, TCNModel, SequenceConfig
                
                config = SequenceConfig(
                    sequence_length=trial.suggest_int('sequence_length', 20, 100),
                    hidden_size=trial.suggest_int('hidden_size', 32, 128),
                    num_layers=trial.suggest_int('num_layers', 1, 3),
                    dropout=trial.suggest_uniform('dropout', 0.1, 0.5),
                    learning_rate=trial.suggest_loguniform('learning_rate', 1e-4, 1e-2),
                    batch_size=trial.suggest_categorical('batch_size', [16, 32, 64])
                )
                
                if model_type == 'lstm':
                    model = LSTMModel(config=config)
                elif model_type == 'gru':
                    model = GRUModel(config=config)
                else:  # tcn
                    model = TCNModel(config=config)
            
            elif model_type == 'transformer':
                from autotrader.modeling.transformers import TransformerModel, TransformerConfig
                
                config = TransformerConfig(
                    sequence_length=trial.suggest_int('sequence_length', 20, 100),
                    d_model=trial.suggest_categorical('d_model', [32, 64, 128]),
                    nhead=trial.suggest_categorical('nhead', [2, 4, 8]),
                    num_encoder_layers=trial.suggest_int('num_encoder_layers', 1, 4),
                    dim_feedforward=trial.suggest_categorical('dim_feedforward', [128, 256, 512]),
                    dropout=trial.suggest_uniform('dropout', 0.1, 0.3),
                    learning_rate=trial.suggest_loguniform('learning_rate', 1e-4, 1e-2),
                    batch_size=trial.suggest_categorical('batch_size', [16, 32, 64])
                )
                
                model = TransformerModel(config=config)
            
            elif model_type == 'online_logistic':
                from autotrader.modeling.online import OnlineLogisticRegression, OnlineConfig
                
                config = OnlineConfig(
                    learning_rate=trial.suggest_loguniform('learning_rate', 1e-3, 1e-1),
                    l2_penalty=trial.suggest_loguniform('l2_penalty', 1e-5, 1e-1)
                )
                
                model = OnlineLogisticRegression(config=config)
            
            elif model_type == 'online_gb':
                from autotrader.modeling.online import OnlineGradientBooster, OnlineConfig
                
                config = OnlineConfig(
                    ensemble_size=trial.suggest_int('ensemble_size', 3, 10),
                    drift_threshold=trial.suggest_uniform('drift_threshold', 0.01, 0.1)
                )
                
                model = OnlineGradientBooster(config=config)
            
            elif model_type == 'vowpal_wabbit':
                from autotrader.modeling.online.vowpal_wabbit import VowpalWabbitModel, VWConfig
                
                config = VWConfig(
                    learning_rate=trial.suggest_loguniform('learning_rate', 0.1, 2.0),
                    l1_penalty=trial.suggest_loguniform('l1_penalty', 1e-6, 1e-2),
                    l2_penalty=trial.suggest_loguniform('l2_penalty', 1e-6, 1e-2),
                    bits=trial.suggest_int('bits', 16, 20)
                )
                
                model = VowpalWabbitModel(config=config)
            
            else:
                raise ValueError(f"Unknown model type: {model_type}")
            
            # Train model
            if hasattr(model, 'partial_fit'):
                # Online model
                model.partial_fit(X_train, y_train)
            else:
                model.fit(X_train, y_train, X_val=X_val, y_val=y_val)
            
            # Evaluate
            metrics = evaluator.evaluate(
                model=model,
                X_test=X_val,
                y_test=y_val,
                **eval_kwargs
            )
            
            # Return metric to optimize
            return metrics[metric]
        
        # Run optimization
        direction = 'maximize' if metric in ['auc', 'ev_per_trade', 'sharpe', 'precision', 'recall'] else 'minimize'
        
        study = optuna.create_study(direction=direction)
        study.optimize(
            objective,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True
        )
        
        logger.info(f"Best {metric}: {study.best_value:.4f}")
        logger.info(f"Best params: {study.best_params}")
        
        return study.best_params
    
    def multi_objective_optimization(
        self,
        model_type: str,
        X_train: Union[np.ndarray, pd.DataFrame],
        y_train: Union[np.ndarray, pd.Series],
        X_val: Union[np.ndarray, pd.DataFrame],
        y_val: Union[np.ndarray, pd.Series],
        metrics: List[str] = ['ev_per_trade', 'turnover_rate'],
        directions: List[str] = ['maximize', 'minimize'],
        n_trials: int = 100,
        **eval_kwargs
    ) -> List[Dict]:
        """
        Multi-objective hyperparameter optimization.
        
        Finds Pareto-optimal solutions trading off multiple objectives.
        
        Parameters
        ----------
        model_type : str
            Model type
        X_train, y_train : array-like
            Training data
        X_val, y_val : array-like
            Validation data
        metrics : list of str
            Metrics to optimize
        directions : list of str
            Optimization directions ('maximize' or 'minimize')
        n_trials : int
            Number of trials
        **eval_kwargs : dict
            Additional evaluation arguments
        
        Returns
        -------
        pareto_solutions : list of dict
            Pareto-optimal hyperparameters
        
        Example
        -------
        >>> # Maximize EV, minimize turnover
        >>> solutions = selector.multi_objective_optimization(
        ...     model_type='xgboost',
        ...     X_train=X_train,
        ...     y_train=y_train,
        ...     X_val=X_val,
        ...     y_val=y_val,
        ...     metrics=['ev_per_trade', 'turnover_rate'],
        ...     directions=['maximize', 'minimize'],
        ...     n_trials=100
        ... )
        """
        from autotrader.modeling.evaluation import ModelEvaluator
        
        evaluator = ModelEvaluator()
        
        def objective(trial):
            # Get hyperparameters (same as single-objective)
            if model_type == 'xgboost':
                from autotrader.modeling.baselines import XGBoostModel
                
                params = {
                    'max_depth': trial.suggest_int('max_depth', 3, 10),
                    'learning_rate': trial.suggest_loguniform('learning_rate', 1e-3, 1e-1),
                    'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                    'subsample': trial.suggest_uniform('subsample', 0.6, 1.0),
                    'colsample_bytree': trial.suggest_uniform('colsample_bytree', 0.6, 1.0),
                    'reg_alpha': trial.suggest_loguniform('reg_alpha', 1e-3, 10.0),
                    'reg_lambda': trial.suggest_loguniform('reg_lambda', 1e-3, 10.0)
                }
                
                model = XGBoostModel(**params)
            else:
                raise NotImplementedError(f"Multi-objective not implemented for {model_type}")
            
            # Train
            model.fit(X_train, y_train, X_val=X_val, y_val=y_val)
            
            # Evaluate
            eval_metrics = evaluator.evaluate(
                model=model,
                X_test=X_val,
                y_test=y_val,
                **eval_kwargs
            )
            
            # Return multiple objectives
            return tuple(eval_metrics[m] for m in metrics)
        
        # Create study
        study = optuna.create_study(directions=directions)
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
        
        # Get Pareto-optimal solutions
        pareto_trials = study.best_trials
        pareto_solutions = [trial.params for trial in pareto_trials]
        
        logger.info(f"Found {len(pareto_solutions)} Pareto-optimal solutions")
        
        return pareto_solutions


def optimize_hyperparameters(model_type, X_train, y_train, X_val, y_val, **kwargs):
    """Convenience function for hyperparameter optimization."""
    selector = ModelSelector()
    return selector.optimize_hyperparameters(
        model_type, X_train, y_train, X_val, y_val, **kwargs
    )
