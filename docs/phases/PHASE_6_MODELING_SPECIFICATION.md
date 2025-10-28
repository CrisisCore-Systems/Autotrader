# Phase 6: Modeling Baselines and Selection — Complete Specification

**Status**: ✅ Ready for Implementation  
**Date**: October 2025  
**Prerequisite**: Phase 5 Complete (Features + Labels ready)

---

## 📋 Overview

Phase 6 establishes a **comprehensive modeling framework** for high-frequency trading, including classical baselines, sequential models, and online learning approaches. The framework emphasizes **practical trading metrics** (cost-adjusted returns, turnover), **probability calibration**, and **rigorous cross-validation**.

**Total: 3 model families, 8+ model types, custom evaluation metrics, automated benchmarking**

**Core Principle**: Start simple, benchmark rigorously, scale intelligently, optimize for expected value (not just accuracy).

---

## 🎯 Objectives

### 1. Baseline Models (Multiple Paradigms)
- **Linear Models**: Logistic/Linear Regression with L1/L2 regularization
- **Tree Ensembles**: XGBoost, LightGBM, CatBoost
- **Sequential Models**: TCN, LSTM/GRU, Transformers
- **Online Learning**: River, Vowpal Wabbit for streaming adaptation

### 2. Model Selection Framework
- **Metrics**: Precision@k, AUC, Expected Value per Trade
- **Calibration**: Probability calibration for thresholding
- **Cost-Awareness**: Turnover penalties, transaction costs
- **Regime-Specific**: Per-instrument, per-horizon evaluation

### 3. Production Infrastructure
- **Cross-Validation**: Walk-forward, purged K-fold
- **Model Cards**: Documentation of pros/cons, use cases
- **Benchmark Suite**: Automated comparison across models
- **Versioning**: MLflow integration for experiment tracking

---

## 🏗️ Architecture

### Model Zoo Structure

```
autotrader/
├── models/
│   ├── __init__.py
│   ├── baselines/
│   │   ├── __init__.py
│   │   ├── linear_models.py       # Logistic/Linear + L1/L2
│   │   ├── tree_ensembles.py      # XGBoost/LightGBM/CatBoost
│   │   ├── sequential_models.py   # TCN/LSTM/GRU
│   │   ├── transformers.py        # Small transformers
│   │   └── online_models.py       # River/Vowpal Wabbit
│   ├── selection/
│   │   ├── __init__.py
│   │   ├── evaluator.py           # Metric computation
│   │   ├── calibrator.py          # Probability calibration
│   │   ├── cost_model.py          # Transaction cost modeling
│   │   └── selector.py            # Model selection logic
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── cross_validator.py     # Walk-forward, purged K-fold
│   │   ├── splitters.py           # Time-aware splitting
│   │   └── embargo.py             # Data leakage prevention
│   ├── benchmark/
│   │   ├── __init__.py
│   │   ├── suite.py               # Benchmark orchestration
│   │   ├── comparator.py          # Model comparison
│   │   └── reporter.py            # Results reporting
│   └── cards/
│       ├── __init__.py
│       ├── generator.py           # Model card generation
│       └── templates/             # Card templates
```

---

## 📦 Deliverables

### 1. Baseline Models (8 implementations)

#### A. Linear Models (`linear_models.py`)
```python
class LogisticRegressionBaseline:
    """Logistic regression with L1/L2/ElasticNet regularization."""
    - L1 (Lasso): Feature selection
    - L2 (Ridge): Regularization
    - ElasticNet: Combination
    - Calibrated probabilities (Platt scaling, isotonic)

class LinearRegressionBaseline:
    """Linear regression for continuous targets."""
    - L1/L2/ElasticNet regularization
    - Robust to outliers (Huber loss option)
```

#### B. Tree Ensembles (`tree_ensembles.py`)
```python
class XGBoostBaseline:
    """XGBoost with optimized hyperparameters."""
    - Classification (logistic, multi:softmax)
    - Regression (reg:squarederror, reg:gamma)
    - GPU acceleration support
    - Feature importance (gain, cover, weight)

class LightGBMBaseline:
    """LightGBM optimized for speed."""
    - Categorical feature support
    - Leaf-wise growth strategy
    - Fast training for large datasets
    - Built-in CV

class CatBoostBaseline:
    """CatBoost for categorical features."""
    - Ordered boosting
    - Symmetric trees
    - Native categorical handling
    - Less prone to overfitting
```

#### C. Sequential Models (`sequential_models.py`)
```python
class TCNBaseline:
    """Temporal Convolutional Network."""
    - Dilated convolutions for long sequences
    - Causal convolutions (no lookahead)
    - Faster than RNNs
    - Good for price time series

class LSTMBaseline:
    """LSTM for sequential data."""
    - Bidirectional option
    - Stacked layers
    - Attention mechanism
    - Dropout regularization

class GRUBaseline:
    """GRU (simpler than LSTM)."""
    - Faster training than LSTM
    - Similar performance
    - Fewer parameters
```

#### D. Transformers (`transformers.py`)
```python
class TransformerBaseline:
    """Lightweight transformer for short sequences."""
    - Multi-head attention
    - Positional encoding
    - Sequence length <= 128 (for speed)
    - Temporal masking for causality
```

#### E. Online Learning (`online_models.py`)
```python
class RiverBaseline:
    """River online learning models."""
    - Incremental learning
    - Adaptive to regime changes
    - Low memory footprint
    - Real-time updates

class VowpalWabbitBaseline:
    """Vowpal Wabbit for streaming."""
    - Extremely fast
    - Feature hashing
    - Online gradient descent
    - Production-scale streaming
```

---

### 2. Evaluation Framework (`selection/`)

#### Metrics (`evaluator.py`)
```python
class ModelEvaluator:
    """Comprehensive model evaluation."""
    
    def evaluate(self, y_true, y_pred, y_proba):
        return {
            # Classification metrics
            'precision': precision_score(...),
            'recall': recall_score(...),
            'f1': f1_score(...),
            'auc': roc_auc_score(...),
            'ap': average_precision_score(...),
            
            # Precision@k (critical for trading)
            'precision_at_10': self.precision_at_k(y_true, y_proba, k=10),
            'precision_at_50': self.precision_at_k(y_true, y_proba, k=50),
            'precision_at_100': self.precision_at_k(y_true, y_proba, k=100),
            
            # Cost-adjusted metrics
            'expected_value_per_trade': self.ev_per_trade(y_true, y_proba, costs),
            'sharpe_ratio': self.sharpe(returns, predictions),
            'information_ratio': self.information_ratio(returns, predictions),
            
            # Calibration metrics
            'brier_score': brier_score_loss(...),
            'calibration_error': self.calibration_error(y_true, y_proba),
        }
```

#### Calibration (`calibrator.py`)
```python
class ProbabilityCalibrator:
    """Calibrate predicted probabilities."""
    
    methods = ['platt', 'isotonic', 'beta']
    
    def calibrate(self, y_true, y_proba, method='isotonic'):
        """Calibrate probabilities to match empirical frequencies."""
        - Platt scaling (logistic regression)
        - Isotonic regression (non-parametric)
        - Beta calibration (three-parameter)
```

#### Cost Model (`cost_model.py`)
```python
class TransactionCostModel:
    """Model transaction costs and turnover penalties."""
    
    def compute_costs(self, trades, spread, slippage, commission):
        """
        Total cost = spread cost + slippage + commission + market impact
        
        Penalize high turnover:
        - Turnover = sum(|position_change|)
        - Penalty = turnover * turnover_penalty_bps
        """
        return total_cost
    
    def expected_value(self, y_proba, returns, costs):
        """
        EV = (probability × return) - costs
        
        Only trade when EV > threshold.
        """
        return ev_per_trade
```

---

### 3. Cross-Validation (`validation/`)

#### Walk-Forward Validation (`cross_validator.py`)
```python
class WalkForwardValidator:
    """Time-series aware cross-validation."""
    
    def __init__(
        self,
        n_splits=5,
        train_period_days=252,  # 1 year
        test_period_days=21,    # 1 month
        embargo_days=5,         # Gap to prevent leakage
    ):
        self.n_splits = n_splits
        self.train_period = train_period_days
        self.test_period = test_period_days
        self.embargo = embargo_days
    
    def split(self, X, y):
        """
        Generate walk-forward splits:
        
        Train: [0, 252), Test: [257, 278)
        Train: [21, 273), Test: [278, 299)
        Train: [42, 294), Test: [299, 320)
        ...
        
        5-day embargo between train/test to prevent lookahead.
        """
        yield from splits
```

#### Purged K-Fold (`splitters.py`)
```python
class PurgedKFold:
    """
    Purged K-fold for time series (Lopez de Prado 2018).
    
    Purges train samples whose labels overlap with test samples.
    Critical for multi-period labels (triple-barrier, fixed-time).
    """
    
    def split(self, X, y, label_times):
        """
        For each fold:
        1. Split data into train/test
        2. Purge train samples that overlap with test
        3. Add embargo period after purging
        """
        yield from purged_splits
```

---

### 4. Benchmark Suite (`benchmark/`)

#### Suite Orchestrator (`suite.py`)
```python
class BenchmarkSuite:
    """Automated model benchmarking."""
    
    def __init__(
        self,
        models: List[BaseModel],
        evaluator: ModelEvaluator,
        validator: WalkForwardValidator,
    ):
        self.models = models
        self.evaluator = evaluator
        self.validator = validator
    
    def run(
        self,
        X, y,
        instruments: List[str],
        horizons: List[int] = [1, 5, 21],  # 1d, 1w, 1m
    ):
        """
        Run full benchmark:
        1. For each instrument
        2. For each horizon
        3. For each model
        4. Run cross-validation
        5. Compute all metrics
        6. Generate reports
        
        Returns:
            DataFrame with results per model/instrument/horizon
        """
        results = []
        
        for instrument in instruments:
            for horizon in horizons:
                for model in self.models:
                    # Cross-validate
                    cv_scores = self.validator.cross_validate(
                        model, X, y, 
                        instrument=instrument,
                        horizon=horizon
                    )
                    
                    # Aggregate metrics
                    results.append({
                        'model': model.name,
                        'instrument': instrument,
                        'horizon': horizon,
                        'mean_auc': np.mean(cv_scores['auc']),
                        'std_auc': np.std(cv_scores['auc']),
                        'mean_precision_at_10': np.mean(cv_scores['precision_at_10']),
                        'mean_sharpe': np.mean(cv_scores['sharpe']),
                        'mean_turnover': np.mean(cv_scores['turnover']),
                        # ... more metrics
                    })
        
        return pd.DataFrame(results)
```

---

### 5. Model Cards (`cards/`)

#### Card Generator (`generator.py`)
```python
class ModelCardGenerator:
    """Generate comprehensive model documentation."""
    
    def generate(
        self,
        model,
        metrics,
        training_config,
        data_summary,
    ):
        """
        Generate model card with:
        - Model description
        - Intended use cases
        - Performance metrics (train/val/test)
        - Limitations and caveats
        - Computational requirements
        - Feature importance
        - Hyperparameters
        - Training details
        - Bias and fairness considerations
        """
        return model_card
```

**Example Model Card**:
```yaml
model_name: XGBoost-Balanced-v1
model_type: xgboost.XGBClassifier
task: binary_classification
target: triple_barrier_label

description: |
  XGBoost classifier optimized for imbalanced multi-asset prediction.
  Uses class weights and SMOTE to handle label imbalance.

intended_use:
  - Daily rebalancing strategies
  - Multi-instrument portfolios
  - Mean-reversion signals

performance:
  train:
    auc: 0.783
    precision_at_10: 0.651
    sharpe: 1.23
  validation:
    auc: 0.721
    precision_at_10: 0.587
    sharpe: 0.98
  test:
    auc: 0.698
    precision_at_10: 0.534
    sharpe: 0.84

limitations:
  - Performance degrades in high-volatility regimes
  - Requires retraining every 30 days
  - Feature drift detected after 60 days
  - Not suitable for intraday trading (designed for daily)

computational_requirements:
  training_time: "15 min (252 days, 50 instruments)"
  inference_time: "< 1ms per prediction"
  memory: "2 GB RAM"
  gpu_required: false

hyperparameters:
  n_estimators: 500
  max_depth: 7
  learning_rate: 0.05
  scale_pos_weight: 5.0

feature_importance_top10:
  - rsi_14: 0.082
  - volume_ratio: 0.071
  - returns_20d: 0.065
  - ...

training_details:
  train_period: 2020-01-01 to 2023-12-31
  validation_period: 2024-01-01 to 2024-06-30
  test_period: 2024-07-01 to 2024-12-31
  cross_validation: WalkForward (5 splits, 21-day test)
  
biases:
  - US market hours bias (90% of training data)
  - Large-cap bias (small caps underrepresented)
  - Survivorship bias (delisted stocks excluded)
```

---

## 🎓 Model Selection Criteria

### Primary Metrics (Must Exceed Thresholds)

| Metric | Threshold | Rationale |
|--------|-----------|-----------|
| **AUC** | > 0.60 | Baseline discriminative power |
| **Precision@10** | > 0.40 | Top predictions must be accurate |
| **Expected Value/Trade** | > 0.5% | After costs, profitable |
| **Sharpe Ratio** | > 1.0 | Risk-adjusted returns |
| **Calibration Error** | < 0.10 | Probabilities trustworthy |

### Secondary Metrics (Trade-offs)

| Metric | Consideration |
|--------|---------------|
| **Turnover** | Lower is better (reduce costs) |
| **Training Time** | Faster enables more frequent retraining |
| **Inference Time** | < 10ms for real-time trading |
| **Memory Footprint** | < 4GB for production servers |
| **Interpretability** | Linear > Trees > Neural Nets |

### Per-Instrument Analysis

```python
# Example: Instrument-specific performance
results_by_instrument = benchmark_suite.run(X, y, instruments=['SPY', 'AAPL', 'BTC-USD'])

# Select best model per instrument
for instrument in instruments:
    best_model = results_by_instrument.query(f"instrument == '{instrument}'").sort_values('mean_sharpe', ascending=False).iloc[0]
    print(f"{instrument}: {best_model['model']} (Sharpe={best_model['mean_sharpe']:.2f})")
```

---

## 🧪 Validation Protocol

### 1. Data Splitting (Time-Series Aware)

```
|--- Train (2020-2022) ---|--- Val (2023) ---|--- Test (2024) ---|
          80%                      10%                10%

Walk-Forward CV within Train+Val:
Fold 1: Train[2020-2021], Test[2021 Q1]
Fold 2: Train[2020-2021 Q1], Test[2021 Q2]
Fold 3: Train[2020-2021 Q2], Test[2021 Q3]
...
```

### 2. Purging and Embargo

```python
# Purge overlapping labels
for train_idx, test_idx in cv.split(X, y):
    # Remove train samples whose labels overlap with test
    purged_train_idx = purge_overlapping(train_idx, test_idx, label_times)
    
    # Add embargo (e.g., 5 days) after test period
    embargoed_train_idx = embargo(purged_train_idx, test_idx, embargo_days=5)
```

### 3. Hyperparameter Optimization

```python
from optuna import create_study

def objective(trial):
    params = {
        'n_estimators': trial.suggest_int('n_estimators', 100, 1000),
        'max_depth': trial.suggest_int('max_depth', 3, 10),
        'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
    }
    
    model = XGBoostBaseline(**params)
    cv_scores = validator.cross_validate(model, X, y)
    
    # Optimize for Sharpe ratio (risk-adjusted returns)
    return np.mean(cv_scores['sharpe'])

study = create_study(direction='maximize')
study.optimize(objective, n_trials=100)
best_params = study.best_params
```

---

## 📊 Benchmark Report Format

### Summary Statistics

```python
benchmark_results = pd.DataFrame({
    'model': ['Logistic-L2', 'XGBoost', 'LightGBM', 'LSTM', 'Transformer'],
    'mean_auc': [0.632, 0.721, 0.718, 0.698, 0.705],
    'mean_precision_at_10': [0.412, 0.587, 0.574, 0.523, 0.541],
    'mean_sharpe': [0.68, 0.98, 0.94, 0.82, 0.87],
    'mean_turnover': [0.23, 0.41, 0.39, 0.52, 0.48],
    'train_time_minutes': [0.5, 15, 8, 45, 120],
    'inference_ms': [0.1, 0.8, 0.5, 5.2, 12.1],
})

# Rank models by composite score
benchmark_results['composite_score'] = (
    benchmark_results['mean_sharpe'] * 0.4 +
    benchmark_results['mean_precision_at_10'] * 0.3 +
    (1 - benchmark_results['mean_turnover']) * 0.2 +
    (1 / benchmark_results['train_time_minutes']) * 0.1
)

print(benchmark_results.sort_values('composite_score', ascending=False))
```

### Visualization

```python
import matplotlib.pyplot as plt
import seaborn as sns

# Metrics comparison
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# AUC comparison
axes[0, 0].bar(benchmark_results['model'], benchmark_results['mean_auc'])
axes[0, 0].set_title('AUC by Model')
axes[0, 0].set_ylabel('AUC')

# Precision@10 comparison
axes[0, 1].bar(benchmark_results['model'], benchmark_results['mean_precision_at_10'])
axes[0, 1].set_title('Precision@10 by Model')
axes[0, 1].set_ylabel('Precision@10')

# Sharpe Ratio comparison
axes[1, 0].bar(benchmark_results['model'], benchmark_results['mean_sharpe'])
axes[1, 0].set_title('Sharpe Ratio by Model')
axes[1, 0].set_ylabel('Sharpe')

# Training Time comparison
axes[1, 1].bar(benchmark_results['model'], benchmark_results['train_time_minutes'])
axes[1, 1].set_title('Training Time by Model')
axes[1, 1].set_ylabel('Minutes')

plt.tight_layout()
plt.savefig('benchmark_results.png')
```

---

## 🚀 Implementation Plan

### Week 1: Baseline Models
- ✅ Day 1-2: Linear models (Logistic/Linear Regression)
- ✅ Day 3-4: Tree ensembles (XGBoost/LightGBM/CatBoost)
- ✅ Day 5: Testing and validation

### Week 2: Sequential Models
- ⏳ Day 1-2: TCN implementation
- ⏳ Day 3-4: LSTM/GRU implementation
- ⏳ Day 5: Transformer baseline

### Week 3: Online Learning
- ⏳ Day 1-2: River integration
- ⏳ Day 3-4: Vowpal Wabbit integration
- ⏳ Day 5: Streaming evaluation

### Week 4: Evaluation Framework
- ⏳ Day 1: Evaluator + cost model
- ⏳ Day 2: Calibrator
- ⏳ Day 3: Cross-validation
- ⏳ Day 4: Benchmark suite
- ⏳ Day 5: Model cards

### Week 5: Integration & Testing
- ⏳ Day 1-2: End-to-end pipeline
- ⏳ Day 3-4: Comprehensive benchmarking
- ⏳ Day 5: Documentation + model cards

---

## 📚 References

### Academic Papers
1. **Model Calibration**:
   - Platt (1999): "Probabilistic Outputs for Support Vector Machines"
   - Zadrozny & Elkan (2001): "Obtaining Calibrated Probability Estimates"

2. **Time-Series CV**:
   - Lopez de Prado (2018): "Advances in Financial Machine Learning"
   - Bergmeir & Benítez (2012): "On the Use of Cross-validation for Time Series Predictor Evaluation"

3. **Cost-Sensitive Learning**:
   - Elkan (2001): "The Foundations of Cost-Sensitive Learning"
   - Zadrozny et al. (2003): "Cost-Sensitive Learning by Cost-Proportionate Example Weighting"

4. **Transformers for Time Series**:
   - Zhou et al. (2021): "Informer: Beyond Efficient Transformer for Long Sequence Time-Series Forecasting"
   - Li et al. (2019): "Enhancing the Locality and Breaking the Memory Bottleneck of Transformer on Time Series Forecasting"

5. **Online Learning**:
   - Bottou (2010): "Large-Scale Machine Learning with Stochastic Gradient Descent"
   - Langford et al. (2009): "Slow Learners are Fast" (Vowpal Wabbit)

---

## ✅ Success Criteria

### Technical Criteria
- ✅ 8+ baseline models implemented
- ✅ Cross-validation with purging/embargo
- ✅ Comprehensive metrics (10+ per model)
- ✅ Probability calibration working
- ✅ Cost-adjusted evaluation
- ✅ Model cards for all baselines

### Performance Criteria
- ✅ At least 3 models with AUC > 0.65
- ✅ At least 1 model with Precision@10 > 0.50
- ✅ At least 1 model with Sharpe > 1.0
- ✅ Inference time < 10ms for all models

### Documentation Criteria
- ✅ Benchmark report generated
- ✅ Model cards for all models
- ✅ API documentation complete
- ✅ Tutorial notebooks created

---

**Next Phase**: Phase 7 - Deployment & Live Trading Integration
