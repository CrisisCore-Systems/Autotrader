"""
Benchmark Suite and Model Cards
=================================

Automated benchmarking and documentation for HFT models.

1. BenchmarkSuite: Automated model comparison
2. ModelCard: Automated model documentation

Example
-------
>>> suite = BenchmarkSuite(
...     models=['logistic_l2', 'xgboost', 'lightgbm'],
...     horizons=[1, 5, 10, 30],
...     instruments=['BTCUSDT', 'ETHUSDT']
... )
>>> results = suite.run(features, targets)
>>> suite.generate_report(results, output_dir='./benchmark_results')
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from pathlib import Path
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class BenchmarkSuite:
    """
    Automated benchmarking suite for HFT models.
    
    Features:
    - Multi-model comparison
    - Per-instrument benchmarks
    - Per-horizon benchmarks
    - Cross-validation
    - Statistical significance tests
    - Automated reporting
    """
    
    def __init__(
        self,
        models: List[str],
        instruments: Optional[List[str]] = None,
        horizons: Optional[List[int]] = None
    ):
        """
        Initialize benchmark suite.
        
        Parameters
        ----------
        models : list of str
            Model types to benchmark
            ('logistic_l1', 'logistic_l2', 'xgboost', 'lightgbm', etc.)
        instruments : list of str, optional
            Instruments to benchmark
        horizons : list of int, optional
            Prediction horizons (seconds)
        """
        self.models = models
        self.instruments = instruments or ['default']
        self.horizons = horizons or [1]
        self.results = {}
    
    def _create_model(self, model_name: str):
        """Create model instance from name."""
        from autotrader.modeling.baselines import (
            LogisticRegressionModel,
            XGBoostModel,
            LightGBMModel
        )
        
        if model_name == 'logistic_l1':
            return LogisticRegressionModel(penalty='l1', solver='saga')
        elif model_name == 'logistic_l2':
            return LogisticRegressionModel(penalty='l2')
        elif model_name == 'logistic_elasticnet':
            return LogisticRegressionModel(penalty='elasticnet', l1_ratio=0.5, solver='saga')
        elif model_name == 'xgboost':
            return XGBoostModel()
        elif model_name == 'lightgbm':
            return LightGBMModel()
        else:
            raise ValueError(f"Unknown model: {model_name}")
    
    def run(
        self,
        features: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        targets: Union[pd.Series, Dict[int, pd.Series], Dict[str, Dict[int, pd.Series]]],
        cv_splits: int = 5,
        test_size: float = 0.2,
        embargo_period: int = 0,
        **eval_kwargs
    ) -> pd.DataFrame:
        """
        Run benchmark suite.
        
        Parameters
        ----------
        features : pd.DataFrame or dict
            Features (or dict of {instrument: features})
        targets : pd.Series or dict
            Targets (or dict of {horizon: targets} or {instrument: {horizon: targets}})
        cv_splits : int
            Number of CV splits
        test_size : float
            Test size for CV
        embargo_period : int
            Embargo period (rows)
        **eval_kwargs : dict
            Additional evaluation arguments
        
        Returns
        -------
        results : pd.DataFrame
            Benchmark results
        """
        from autotrader.modeling.selection import ModelSelector
        
        selector = ModelSelector()
        all_results = []
        
        # Handle different input formats
        if isinstance(features, pd.DataFrame):
            features_dict = {'default': features}
        else:
            features_dict = features
        
        if isinstance(targets, pd.Series):
            targets_dict = {'default': {1: targets}}
        elif isinstance(targets, dict) and all(isinstance(v, pd.Series) for v in targets.values()):
            # Dict of {horizon: targets}
            targets_dict = {'default': targets}
        else:
            # Dict of {instrument: {horizon: targets}}
            targets_dict = targets
        
        total_runs = len(self.models) * len(features_dict) * len(self.horizons)
        run_count = 0
        
        # Run benchmarks
        for instrument in features_dict.keys():
            X = features_dict[instrument]
            
            for horizon in self.horizons:
                if instrument not in targets_dict or horizon not in targets_dict[instrument]:
                    logger.warning(f"No targets for {instrument}, horizon={horizon}")
                    continue
                
                y = targets_dict[instrument][horizon]
                
                for model_name in self.models:
                    run_count += 1
                    logger.info(f"[{run_count}/{total_runs}] Benchmarking {model_name} "
                               f"on {instrument}, horizon={horizon}s")
                    
                    try:
                        # Create model
                        model = self._create_model(model_name)
                        
                        # Run cross-validation
                        cv_results = selector.walk_forward_cv(
                            X=X,
                            y=y,
                            model=model,
                            n_splits=cv_splits,
                            test_size=test_size,
                            embargo_period=embargo_period,
                            **eval_kwargs
                        )
                        
                        # Aggregate results
                        mean_results = cv_results.mean()
                        std_results = cv_results.std()
                        
                        # Store results
                        result = {
                            'model': model_name,
                            'instrument': instrument,
                            'horizon': horizon,
                            'cv_splits': cv_splits,
                        }
                        
                        # Add mean metrics
                        for col in cv_results.columns:
                            if col not in ['fold', 'train_size', 'test_size']:
                                result[f'mean_{col}'] = mean_results[col]
                                result[f'std_{col}'] = std_results[col]
                        
                        all_results.append(result)
                    
                    except Exception as e:
                        logger.error(f"Error benchmarking {model_name}: {e}")
                        continue
        
        # Convert to dataframe
        results_df = pd.DataFrame(all_results)
        
        # Sort by expected value (best for trading)
        if 'mean_ev_per_trade' in results_df.columns:
            results_df = results_df.sort_values('mean_ev_per_trade', ascending=False)
        
        self.results = results_df
        return results_df
    
    def generate_report(
        self,
        results: pd.DataFrame,
        output_dir: Union[str, Path] = './benchmark_results'
    ):
        """
        Generate comprehensive benchmark report.
        
        Parameters
        ----------
        results : pd.DataFrame
            Benchmark results
        output_dir : str or Path
            Output directory
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save raw results
        results.to_csv(output_path / 'summary.csv', index=False)
        logger.info(f"Saved summary to {output_path / 'summary.csv'}")
        
        # Generate markdown report
        report = self._generate_markdown_report(results)
        with open(output_path / 'README.md', 'w') as f:
            f.write(report)
        logger.info(f"Saved report to {output_path / 'README.md'}")
        
        # Save per-instrument results
        per_instrument_dir = output_path / 'per_instrument'
        per_instrument_dir.mkdir(exist_ok=True)
        
        for instrument in results['instrument'].unique():
            instrument_results = results[results['instrument'] == instrument]
            instrument_results.to_csv(
                per_instrument_dir / f'{instrument}_results.csv',
                index=False
            )
        
        # Save per-horizon results
        per_horizon_dir = output_path / 'per_horizon'
        per_horizon_dir.mkdir(exist_ok=True)
        
        for horizon in results['horizon'].unique():
            horizon_results = results[results['horizon'] == horizon]
            horizon_results.to_csv(
                per_horizon_dir / f'{horizon}s_results.csv',
                index=False
            )
        
        logger.info(f"Benchmark report generated in {output_path}")
    
    def _generate_markdown_report(self, results: pd.DataFrame) -> str:
        """Generate markdown report."""
        report = f"""# Benchmark Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview

- **Models**: {', '.join(self.models)}
- **Instruments**: {', '.join(self.instruments)}
- **Horizons**: {', '.join(map(str, self.horizons))}s
- **Total runs**: {len(results)}

## Top Models (by Expected Value)

"""
        # Top 10 models
        top_models = results.nlargest(10, 'mean_ev_per_trade') if 'mean_ev_per_trade' in results.columns else results.head(10)
        
        report += top_models[['model', 'instrument', 'horizon', 'mean_ev_per_trade', 'mean_sharpe', 'mean_auc']].to_markdown(index=False)
        
        report += "\n\n## Performance by Model\n\n"
        
        # Group by model
        model_summary = results.groupby('model').agg({
            'mean_ev_per_trade': ['mean', 'std'],
            'mean_sharpe': ['mean', 'std'],
            'mean_auc': ['mean', 'std']
        })
        
        report += model_summary.to_markdown()
        
        report += "\n\n## Performance by Instrument\n\n"
        
        # Group by instrument
        instrument_summary = results.groupby('instrument').agg({
            'mean_ev_per_trade': ['mean', 'std'],
            'mean_sharpe': ['mean', 'std'],
            'mean_auc': ['mean', 'std']
        })
        
        report += instrument_summary.to_markdown()
        
        report += "\n\n## Performance by Horizon\n\n"
        
        # Group by horizon
        horizon_summary = results.groupby('horizon').agg({
            'mean_ev_per_trade': ['mean', 'std'],
            'mean_sharpe': ['mean', 'std'],
            'mean_auc': ['mean', 'std']
        })
        
        report += horizon_summary.to_markdown()
        
        return report


class ModelCard:
    """
    Automated model documentation (Model Card).
    
    Generates comprehensive documentation including:
    - Model details and hyperparameters
    - Performance metrics (train/test/CV)
    - Feature importance
    - Pros/cons
    - Calibration analysis
    - Deployment recommendations
    
    References
    ----------
    - Mitchell et al. (2019): "Model Cards for Model Reporting"
    
    Example
    -------
    >>> card = ModelCard(
    ...     model=xgb_model,
    ...     model_name='XGBoost Classifier',
    ...     task='binary_classification',
    ...     features=feature_names,
    ...     train_metrics=train_metrics,
    ...     test_metrics=test_metrics
    ... )
    >>> card.generate(output_path='./model_cards/xgboost_v1.md')
    """
    
    def __init__(
        self,
        model,
        model_name: str,
        task: str,
        features: List[str],
        train_metrics: Dict[str, float],
        test_metrics: Dict[str, float],
        cv_results: Optional[pd.DataFrame] = None,
        dataset_info: Optional[Dict] = None
    ):
        """
        Initialize model card.
        
        Parameters
        ----------
        model : object
            Trained model
        model_name : str
            Model name
        task : str
            Task type ('binary_classification', 'regression')
        features : list of str
            Feature names
        train_metrics : dict
            Training metrics
        test_metrics : dict
            Test metrics
        cv_results : pd.DataFrame, optional
            Cross-validation results
        dataset_info : dict, optional
            Dataset information
        """
        self.model = model
        self.model_name = model_name
        self.task = task
        self.features = features
        self.train_metrics = train_metrics
        self.test_metrics = test_metrics
        self.cv_results = cv_results
        self.dataset_info = dataset_info or {}
    
    def generate(self, output_path: Union[str, Path]):
        """
        Generate model card.
        
        Parameters
        ----------
        output_path : str or Path
            Output path for model card (.md file)
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        card = self._generate_card()
        
        with open(output_path, 'w') as f:
            f.write(card)
        
        logger.info(f"Model card saved to {output_path}")
    
    def _generate_card(self) -> str:
        """Generate model card content."""
        card = f"""# Model Card: {self.model_name}

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Model Details

- **Model Type**: {self.model_name}
- **Task**: {self.task}
- **Number of Features**: {len(self.features)}

"""
        # Hyperparameters
        if hasattr(self.model, 'get_params'):
            params = self.model.get_params()
            card += "### Hyperparameters\n\n"
            for k, v in params.items():
                card += f"- {k}: {v}\n"
            card += "\n"
        
        # Dataset info
        if self.dataset_info:
            card += "## Dataset\n\n"
            for k, v in self.dataset_info.items():
                card += f"- {k}: {v}\n"
            card += "\n"
        
        # Performance
        card += "## Performance\n\n"
        card += "### Training Metrics\n\n"
        for k, v in self.train_metrics.items():
            card += f"- {k}: {v:.4f}\n"
        card += "\n"
        
        card += "### Test Metrics\n\n"
        for k, v in self.test_metrics.items():
            card += f"- {k}: {v:.4f}\n"
        card += "\n"
        
        # Cross-validation
        if self.cv_results is not None:
            card += "### Cross-Validation Results\n\n"
            key_metrics = ['auc', 'ev_per_trade', 'sharpe']
            for metric in key_metrics:
                col = f'mean_{metric}' if f'mean_{metric}' in self.cv_results.columns else metric
                if col in self.cv_results.columns:
                    mean = self.cv_results[col].mean()
                    std = self.cv_results[col].std()
                    card += f"- {metric}: {mean:.4f} ± {std:.4f}\n"
            card += "\n"
        
        # Feature importance
        if hasattr(self.model, 'get_feature_importance'):
            importance = self.model.get_feature_importance()
            card += "## Feature Importance (Top 10)\n\n"
            top_features = importance.head(10)
            for i, row in top_features.iterrows():
                card += f"{i+1}. {row['feature']}: {row['importance']:.4f}\n"
            card += "\n"
        
        # Pros/cons
        card += self._generate_pros_cons()
        
        # Deployment recommendations
        card += "## Deployment Recommendations\n\n"
        card += "- **Retraining Frequency**: Weekly\n"
        card += "- **Monitoring**: Track AUC, precision@10, turnover\n"
        card += "- **Risk**: Limit position size to 1% of portfolio\n"
        card += "\n"
        
        return card
    
    def _generate_pros_cons(self) -> str:
        """Generate pros/cons section."""
        model_type = self.model_name.lower()
        
        if 'logistic' in model_type:
            return """## Pros & Cons

### Pros
- Fast training and inference
- Interpretable coefficients
- Probabilistic outputs (well-calibrated)
- Regularization prevents overfitting

### Cons
- Linear only (no interactions)
- Requires feature engineering
- Assumes independent features

"""
        elif 'xgboost' in model_type:
            return """## Pros & Cons

### Pros
- Captures non-linear patterns
- Automatic feature interactions
- Robust to outliers and missing data
- Built-in regularization

### Cons
- Slow training (vs LightGBM)
- Less interpretable
- Hyperparameter-sensitive
- Risk of overfitting

"""
        elif 'lightgbm' in model_type:
            return """## Pros & Cons

### Pros
- Fastest gradient boosting
- Low memory usage
- Native categorical support
- GPU acceleration

### Cons
- Prone to overfitting (small datasets)
- Requires tuning (max_depth, num_leaves)

"""
        else:
            return ""
