"""
Baseline Models: Linear and Tree Ensembles
===========================================

Implements classical ML baselines for HFT:
1. Logistic/Linear Regression (L1/L2/ElasticNet)
2. XGBoost (gradient boosting)
3. LightGBM (fast gradient boosting)

Academic References:
- Hastie et al. (2009): "The Elements of Statistical Learning"
- Chen & Guestrin (2016): "XGBoost: A Scalable Tree Boosting System"
- Ke et al. (2017): "LightGBM: A Highly Efficient Gradient Boosting Decision Tree"
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union, Tuple
from sklearn.linear_model import LogisticRegression, Ridge, Lasso, ElasticNet
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import lightgbm as lgb
import logging

logger = logging.getLogger(__name__)


class LogisticRegressionModel:
    """
    Logistic regression with L1/L2/ElasticNet regularization.
    
    Pros:
    - Fast training and inference
    - Interpretable coefficients
    - Probabilistic outputs (well-calibrated)
    - Regularization prevents overfitting
    
    Cons:
    - Linear only (no interactions)
    - Requires feature engineering
    - Assumes independent features
    
    References:
    - Cox (1958): "The Regression Analysis of Binary Sequences"
    - Hastie et al. (2009): "The Elements of Statistical Learning"
    """
    
    def __init__(
        self,
        penalty: str = 'l2',
        C: float = 1.0,
        solver: str = 'lbfgs',
        max_iter: int = 1000,
        class_weight: Optional[Union[str, Dict]] = 'balanced',
        l1_ratio: Optional[float] = None,
        calibrate: bool = True,
        calibration_method: str = 'isotonic',
        random_state: int = 42
    ):
        """
        Initialize logistic regression model.
        
        Parameters
        ----------
        penalty : str
            Regularization penalty ('l1', 'l2', 'elasticnet', 'none')
        C : float
            Inverse regularization strength (smaller = more regularization)
        solver : str
            Optimization algorithm ('lbfgs', 'saga', 'liblinear')
        max_iter : int
            Maximum iterations
        class_weight : str or dict
            Weights for imbalanced classes ('balanced' recommended)
        l1_ratio : float, optional
            ElasticNet mixing (0 = L2, 1 = L1)
        calibrate : bool
            Whether to calibrate probabilities
        calibration_method : str
            Calibration method ('isotonic' or 'sigmoid')
        random_state : int
            Random seed
        """
        self.penalty = penalty
        self.C = C
        self.solver = solver
        self.max_iter = max_iter
        self.class_weight = class_weight
        self.l1_ratio = l1_ratio
        self.calibrate = calibrate
        self.calibration_method = calibration_method
        self.random_state = random_state
        
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = None
        self.is_fitted = False
    
    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        X_val: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y_val: Optional[Union[np.ndarray, pd.Series]] = None
    ) -> 'LogisticRegressionModel':
        """
        Train logistic regression model.
        
        Parameters
        ----------
        X : array-like
            Training features
        y : array-like
            Training labels
        X_val : array-like, optional
            Validation features (for calibration)
        y_val : array-like, optional
            Validation labels (for calibration)
        
        Returns
        -------
        self : LogisticRegressionModel
            Fitted model
        """
        # Store feature names
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
            X = X.values
        else:
            self.feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        
        # Convert labels to numpy
        if isinstance(y, pd.Series):
            y = y.values
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Create base model
        base_model = LogisticRegression(
            penalty=self.penalty,
            C=self.C,
            solver=self.solver,
            max_iter=self.max_iter,
            class_weight=self.class_weight,
            l1_ratio=self.l1_ratio if self.penalty == 'elasticnet' else None,
            random_state=self.random_state,
            n_jobs=-1
        )
        
        # Fit model
        logger.info(f"Training logistic regression (penalty={self.penalty}, C={self.C})")
        base_model.fit(X_scaled, y)
        
        # Calibrate probabilities if requested
        if self.calibrate and X_val is not None and y_val is not None:
            logger.info(f"Calibrating probabilities ({self.calibration_method})")
            if isinstance(X_val, pd.DataFrame):
                X_val = X_val.values
            if isinstance(y_val, pd.Series):
                y_val = y_val.values
            
            X_val_scaled = self.scaler.transform(X_val)
            self.model = CalibratedClassifierCV(
                base_model,
                method=self.calibration_method,
                cv='prefit'
            )
            self.model.fit(X_val_scaled, y_val)
        else:
            self.model = base_model
        
        self.is_fitted = True
        logger.info("Logistic regression training complete")
        
        return self
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class labels."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class probabilities."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        X_scaled = self.scaler.transform(X)
        return self.model.predict_proba(X_scaled)
    
    def get_feature_importance(self) -> pd.DataFrame:
        """
        Get feature importance (absolute coefficients).
        
        Returns
        -------
        importance : pd.DataFrame
            Feature importance with columns ['feature', 'importance', 'coefficient']
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Get base estimator coefficients
        if hasattr(self.model, 'coef_'):
            coef = self.model.coef_[0]
        elif hasattr(self.model, 'base_estimator'):
            coef = self.model.base_estimator.coef_[0]
        else:
            raise ValueError("Could not extract coefficients from model")
        
        # Create importance dataframe
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'coefficient': coef,
            'importance': np.abs(coef)
        })
        
        # Sort by importance
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        return importance_df
    
    def get_params(self) -> Dict:
        """Get model hyperparameters."""
        return {
            'penalty': self.penalty,
            'C': self.C,
            'solver': self.solver,
            'max_iter': self.max_iter,
            'class_weight': self.class_weight,
            'l1_ratio': self.l1_ratio,
            'calibrate': self.calibrate,
            'calibration_method': self.calibration_method
        }


class XGBoostModel:
    """
    XGBoost gradient boosting classifier.
    
    Pros:
    - Captures non-linear patterns
    - Automatic feature interactions
    - Robust to outliers and missing data
    - Built-in regularization
    - GPU acceleration
    
    Cons:
    - Slow training (vs LightGBM)
    - Less interpretable
    - Hyperparameter-sensitive
    - Risk of overfitting
    
    References:
    - Chen & Guestrin (2016): "XGBoost: A Scalable Tree Boosting System"
    - Friedman (2001): "Greedy Function Approximation: A Gradient Boosting Machine"
    """
    
    def __init__(
        self,
        objective: str = 'binary:logistic',
        max_depth: int = 6,
        learning_rate: float = 0.1,
        n_estimators: int = 100,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        scale_pos_weight: float = 1.0,
        tree_method: str = 'hist',
        eval_metric: str = 'auc',
        early_stopping_rounds: int = 10,
        random_state: int = 42
    ):
        """
        Initialize XGBoost model.
        
        Parameters
        ----------
        objective : str
            Learning objective ('binary:logistic', 'reg:squarederror')
        max_depth : int
            Maximum tree depth
        learning_rate : float
            Step size shrinkage (eta)
        n_estimators : int
            Number of boosting rounds
        subsample : float
            Row sampling ratio
        colsample_bytree : float
            Column sampling ratio
        reg_alpha : float
            L1 regularization
        reg_lambda : float
            L2 regularization
        scale_pos_weight : float
            Balance of positive/negative weights
        tree_method : str
            Tree construction algorithm ('hist', 'gpu_hist', 'exact')
        eval_metric : str
            Evaluation metric ('auc', 'logloss', 'rmse')
        early_stopping_rounds : int
            Early stopping patience
        random_state : int
            Random seed
        """
        self.params = {
            'objective': objective,
            'max_depth': max_depth,
            'learning_rate': learning_rate,
            'n_estimators': n_estimators,
            'subsample': subsample,
            'colsample_bytree': colsample_bytree,
            'reg_alpha': reg_alpha,
            'reg_lambda': reg_lambda,
            'scale_pos_weight': scale_pos_weight,
            'tree_method': tree_method,
            'eval_metric': eval_metric,
            'random_state': random_state,
            'n_jobs': -1
        }
        self.early_stopping_rounds = early_stopping_rounds
        
        self.model = None
        self.feature_names = None
        self.is_fitted = False
        self.best_iteration = None
    
    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        X_val: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y_val: Optional[Union[np.ndarray, pd.Series]] = None,
        verbose: bool = False
    ) -> 'XGBoostModel':
        """
        Train XGBoost model.
        
        Parameters
        ----------
        X : array-like
            Training features
        y : array-like
            Training labels
        X_val : array-like, optional
            Validation features (for early stopping)
        y_val : array-like, optional
            Validation labels (for early stopping)
        verbose : bool
            Print training progress
        
        Returns
        -------
        self : XGBoostModel
            Fitted model
        """
        # Store feature names
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
            X = X.values
        else:
            self.feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        
        # Convert labels to numpy
        if isinstance(y, pd.Series):
            y = y.values
        
        # Prepare eval set
        eval_set = []
        if X_val is not None and y_val is not None:
            if isinstance(X_val, pd.DataFrame):
                X_val = X_val.values
            if isinstance(y_val, pd.Series):
                y_val = y_val.values
            eval_set = [(X_val, y_val)]
        
        # Create model
        self.model = xgb.XGBClassifier(**self.params)
        
        # Fit model
        logger.info(f"Training XGBoost (max_depth={self.params['max_depth']}, "
                   f"n_estimators={self.params['n_estimators']})")
        
        fit_params = {}
        if eval_set:
            fit_params['eval_set'] = eval_set
            fit_params['early_stopping_rounds'] = self.early_stopping_rounds
            fit_params['verbose'] = verbose
        
        self.model.fit(X, y, **fit_params)
        
        # Store best iteration
        if hasattr(self.model, 'best_iteration'):
            self.best_iteration = self.model.best_iteration
            logger.info(f"Best iteration: {self.best_iteration}")
        
        self.is_fitted = True
        logger.info("XGBoost training complete")
        
        return self
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class labels."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        return self.model.predict(X)
    
    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class probabilities."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        if isinstance(X, pd.DataFrame):
            X = X.values
        
        return self.model.predict_proba(X)
    
    def get_feature_importance(
        self,
        importance_type: str = 'gain'
    ) -> pd.DataFrame:
        """
        Get feature importance.
        
        Parameters
        ----------
        importance_type : str
            Type of importance ('gain', 'weight', 'cover')
            - gain: Average gain across splits
            - weight: Number of times feature used
            - cover: Average coverage across splits
        
        Returns
        -------
        importance : pd.DataFrame
            Feature importance with columns ['feature', 'importance']
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Get importance scores
        importance_dict = self.model.get_booster().get_score(
            importance_type=importance_type
        )
        
        # Convert to dataframe
        importance_df = pd.DataFrame([
            {'feature': feat, 'importance': score}
            for feat, score in importance_dict.items()
        ])
        
        # Sort by importance
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        return importance_df
    
    def get_params(self) -> Dict:
        """Get model hyperparameters."""
        return self.params.copy()


class LightGBMModel:
    """
    LightGBM gradient boosting classifier.
    
    Pros:
    - Fastest gradient boosting (leaf-wise growth)
    - Low memory usage
    - Native categorical support
    - GPU acceleration
    - Built-in early stopping
    
    Cons:
    - Prone to overfitting (small datasets)
    - Requires tuning (max_depth, num_leaves)
    
    References:
    - Ke et al. (2017): "LightGBM: A Highly Efficient Gradient Boosting Decision Tree"
    """
    
    def __init__(
        self,
        objective: str = 'binary',
        metric: str = 'auc',
        num_leaves: int = 31,
        max_depth: int = -1,
        learning_rate: float = 0.1,
        n_estimators: int = 100,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 0.1,
        reg_lambda: float = 1.0,
        min_child_samples: int = 20,
        device: str = 'cpu',
        early_stopping_rounds: int = 10,
        random_state: int = 42
    ):
        """
        Initialize LightGBM model.
        
        Parameters
        ----------
        objective : str
            Learning objective ('binary', 'regression')
        metric : str
            Evaluation metric ('auc', 'binary_logloss', 'rmse')
        num_leaves : int
            Maximum number of leaves
        max_depth : int
            Maximum tree depth (-1 = no limit)
        learning_rate : float
            Step size shrinkage
        n_estimators : int
            Number of boosting rounds
        subsample : float
            Row sampling ratio
        colsample_bytree : float
            Column sampling ratio
        reg_alpha : float
            L1 regularization
        reg_lambda : float
            L2 regularization
        min_child_samples : int
            Minimum samples per leaf (prevents overfitting)
        device : str
            Device type ('cpu' or 'gpu')
        early_stopping_rounds : int
            Early stopping patience
        random_state : int
            Random seed
        """
        self.params = {
            'objective': objective,
            'metric': metric,
            'num_leaves': num_leaves,
            'max_depth': max_depth,
            'learning_rate': learning_rate,
            'n_estimators': n_estimators,
            'subsample': subsample,
            'colsample_bytree': colsample_bytree,
            'reg_alpha': reg_alpha,
            'reg_lambda': reg_lambda,
            'min_child_samples': min_child_samples,
            'device': device,
            'random_state': random_state,
            'n_jobs': -1,
            'verbose': -1
        }
        self.early_stopping_rounds = early_stopping_rounds
        
        self.model = None
        self.feature_names = None
        self.is_fitted = False
        self.best_iteration = None
    
    def fit(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        y: Union[np.ndarray, pd.Series],
        X_val: Optional[Union[np.ndarray, pd.DataFrame]] = None,
        y_val: Optional[Union[np.ndarray, pd.Series]] = None,
        categorical_features: Optional[List[str]] = None,
        verbose: bool = False
    ) -> 'LightGBMModel':
        """
        Train LightGBM model.
        
        Parameters
        ----------
        X : array-like
            Training features
        y : array-like
            Training labels
        X_val : array-like, optional
            Validation features (for early stopping)
        y_val : array-like, optional
            Validation labels (for early stopping)
        categorical_features : list of str, optional
            Categorical feature names
        verbose : bool
            Print training progress
        
        Returns
        -------
        self : LightGBMModel
            Fitted model
        """
        # Store feature names
        if isinstance(X, pd.DataFrame):
            self.feature_names = X.columns.tolist()
        else:
            self.feature_names = [f'feature_{i}' for i in range(X.shape[1])]
        
        # Prepare eval set
        eval_set = []
        if X_val is not None and y_val is not None:
            eval_set = [(X_val, y_val)]
        
        # Create model
        self.model = lgb.LGBMClassifier(**self.params)
        
        # Fit model
        logger.info(f"Training LightGBM (num_leaves={self.params['num_leaves']}, "
                   f"n_estimators={self.params['n_estimators']})")
        
        fit_params = {}
        if eval_set:
            fit_params['eval_set'] = eval_set
            fit_params['callbacks'] = [
                lgb.early_stopping(self.early_stopping_rounds, verbose=verbose)
            ]
        if categorical_features:
            fit_params['categorical_feature'] = categorical_features
        
        self.model.fit(X, y, **fit_params)
        
        # Store best iteration
        if hasattr(self.model, 'best_iteration_'):
            self.best_iteration = self.model.best_iteration_
            logger.info(f"Best iteration: {self.best_iteration}")
        
        self.is_fitted = True
        logger.info("LightGBM training complete")
        
        return self
    
    def predict(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class labels."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        return self.model.predict(X)
    
    def predict_proba(self, X: Union[np.ndarray, pd.DataFrame]) -> np.ndarray:
        """Predict class probabilities."""
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        return self.model.predict_proba(X)
    
    def get_feature_importance(
        self,
        importance_type: str = 'gain'
    ) -> pd.DataFrame:
        """
        Get feature importance.
        
        Parameters
        ----------
        importance_type : str
            Type of importance ('gain' or 'split')
            - gain: Total gain from splits
            - split: Number of times feature used
        
        Returns
        -------
        importance : pd.DataFrame
            Feature importance with columns ['feature', 'importance']
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Get importance scores
        importance_scores = self.model.feature_importances_
        
        # Create dataframe
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance_scores
        })
        
        # Sort by importance
        importance_df = importance_df.sort_values('importance', ascending=False)
        
        return importance_df
    
    def get_params(self) -> Dict:
        """Get model hyperparameters."""
        return self.params.copy()
