# Phase 6: Modeling Quick Start

**Status**: ✅ Ready to Implement  
**Prerequisite**: Phase 5 Complete (Features extracted, labels generated)

---

## 🚀 Quick Implementation (30 Minutes)

This guide helps you immediately start training and evaluating models on your Phase 5 features.

---

## Step 1: Prepare Your Data (5 min)

```python
from autotrader.data_prep.features import FeatureFactory, FeatureConfig
from autotrader.data_prep.labeling import TripleBarrierLabeler

# Extract features (from Phase 5)
config = FeatureConfig.balanced()
factory = FeatureFactory(config)
features = factory.extract_all(bars_df=bars)

# Generate labels
labeler = TripleBarrierLabeler(
    profit_target=0.02,  # 2%
    stop_loss=0.01,      # 1%
    horizon_days=5
)
labels = labeler.label(bars)

# Merge features + labels
df = features.join(labels, how='inner')

# Split features/target
feature_cols = [col for col in df.columns if col not in ['label', 'label_type', 'return']]
X = df[feature_cols]
y = (df['label'] == 1).astype(int)  # 1=profit, 0=loss/neutral

print(f"Features: {X.shape[1]}")
print(f"Samples: {len(X)}")
print(f"Label distribution: {y.value_counts()}")
```

---

## Step 2: Train Baseline Models (10 min)

### Option A: Use Existing LightGBM Pipeline

```python
from src.models.lightgbm_pipeline import LightGBMPipeline
from pathlib import Path

# Create pipeline (uses your existing implementation!)
pipeline = LightGBMPipeline(
    model_dir=Path("models/phase6_baseline"),
    params={
        "objective": "binary",
        "metric": "auc",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "scale_pos_weight": 5.0,  # Adjust for label imbalance
    }
)

# Train with cross-validation
cv_metrics = pipeline.cross_validate(
    X=X,
    y=y,
    n_splits=5,
    num_boost_round=500,
    early_stopping_rounds=50
)

print(f"CV AUC: {cv_metrics.roc_auc:.3f} ± {np.std([m.roc_auc for m in cv_metrics]):.3f}")
print(f"CV Precision: {cv_metrics.precision:.3f}")
print(f"CV Recall: {cv_metrics.recall:.3f}")

# Train final model
final_metrics = pipeline.train(
    X=X,
    y=y,
    num_boost_round=500,
    early_stopping_rounds=50
)

# Get predictions
predictions = pipeline.predict(X)
probabilities = pipeline.predict_proba(X)

# Feature importance
importance = pipeline.get_feature_importance()
print("\nTop 10 Features:")
print(importance.head(10))
```

### Option B: Quick Scikit-Learn Baselines

```python
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
import xgboost as xgb

# 1. Logistic Regression (L2 regularization)
lr = LogisticRegression(C=0.1, max_iter=1000, class_weight='balanced')
lr_scores = cross_val_score(lr, X, y, cv=5, scoring='roc_auc')
print(f"Logistic Regression AUC: {lr_scores.mean():.3f} ± {lr_scores.std():.3f}")

# 2. Random Forest
rf = RandomForestClassifier(n_estimators=100, max_depth=7, class_weight='balanced')
rf_scores = cross_val_score(rf, X, y, cv=5, scoring='roc_auc')
print(f"Random Forest AUC: {rf_scores.mean():.3f} ± {rf_scores.std():.3f}")

# 3. XGBoost
xgb_model = xgb.XGBClassifier(
    n_estimators=500,
    max_depth=7,
    learning_rate=0.05,
    scale_pos_weight=5.0
)
xgb_scores = cross_val_score(xgb_model, X, y, cv=5, scoring='roc_auc')
print(f"XGBoost AUC: {xgb_scores.mean():.3f} ± {xgb_scores.std():.3f}")
```

---

## Step 3: Evaluate with Trading Metrics (10 min)

```python
from sklearn.metrics import (
    precision_score, recall_score, f1_score, 
    roc_auc_score, precision_recall_curve
)
import numpy as np

def precision_at_k(y_true, y_proba, k=10):
    """Precision of top k% predictions."""
    threshold = np.percentile(y_proba, 100 - k)
    y_pred = (y_proba >= threshold).astype(int)
    return precision_score(y_true, y_pred)

def expected_value_per_trade(y_true, y_proba, avg_return=0.02, cost=0.001):
    """
    Expected value per trade after costs.
    
    EV = P(win) × avg_return - cost
    """
    return y_proba.mean() * avg_return - cost

# Evaluate
y_pred = (probabilities >= 0.5).astype(int)

metrics = {
    'AUC': roc_auc_score(y, probabilities),
    'Precision': precision_score(y, y_pred),
    'Recall': recall_score(y, y_pred),
    'F1': f1_score(y, y_pred),
    'Precision@10': precision_at_k(y, probabilities, k=10),
    'Precision@20': precision_at_k(y, probabilities, k=20),
    'EV per Trade': expected_value_per_trade(y, probabilities),
}

print("\n📊 Trading Metrics:")
for metric, value in metrics.items():
    print(f"  {metric}: {value:.4f}")

# Precision-Recall curve
precisions, recalls, thresholds = precision_recall_curve(y, probabilities)

# Find optimal threshold (maximize F1)
f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
optimal_idx = np.argmax(f1_scores)
optimal_threshold = thresholds[optimal_idx]

print(f"\n🎯 Optimal Threshold: {optimal_threshold:.3f}")
print(f"  Precision: {precisions[optimal_idx]:.3f}")
print(f"  Recall: {recalls[optimal_idx]:.3f}")
print(f"  F1: {f1_scores[optimal_idx]:.3f}")
```

---

## Step 4: Walk-Forward Validation (5 min)

```python
from sklearn.model_selection import TimeSeriesSplit

def walk_forward_validation(X, y, model, n_splits=5):
    """
    Time-series aware cross-validation.
    
    Train on past, test on future (no lookahead!).
    """
    tscv = TimeSeriesSplit(n_splits=n_splits)
    
    scores = []
    for train_idx, test_idx in tscv.split(X):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        # Train
        model.fit(X_train, y_train)
        
        # Predict
        y_proba = model.predict_proba(X_test)[:, 1]
        
        # Evaluate
        scores.append({
            'auc': roc_auc_score(y_test, y_proba),
            'precision_at_10': precision_at_k(y_test, y_proba, k=10),
        })
    
    return pd.DataFrame(scores)

# Run walk-forward validation
from sklearn.ensemble import GradientBoostingClassifier

model = GradientBoostingClassifier(
    n_estimators=100,
    learning_rate=0.1,
    max_depth=5
)

wf_scores = walk_forward_validation(X, y, model, n_splits=5)

print("\n📈 Walk-Forward Results:")
print(f"  Mean AUC: {wf_scores['auc'].mean():.3f} ± {wf_scores['auc'].std():.3f}")
print(f"  Mean Precision@10: {wf_scores['precision_at_10'].mean():.3f} ± {wf_scores['precision_at_10'].std():.3f}")
print("\nPer-fold:")
print(wf_scores)
```

---

## Step 5: Model Comparison Dashboard (5 min)

```python
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Train multiple models
models = {
    'Logistic Regression': LogisticRegression(C=0.1, max_iter=1000, class_weight='balanced'),
    'Random Forest': RandomForestClassifier(n_estimators=100, max_depth=7, class_weight='balanced'),
    'XGBoost': xgb.XGBClassifier(n_estimators=100, max_depth=7, learning_rate=0.1),
    'LightGBM': lgb.LGBMClassifier(n_estimators=100, max_depth=7, learning_rate=0.1),
}

results = []
for name, model in models.items():
    # Cross-validate
    auc_scores = cross_val_score(model, X, y, cv=5, scoring='roc_auc')
    
    # Train final model for predictions
    model.fit(X, y)
    y_proba = model.predict_proba(X)[:, 1]
    
    results.append({
        'Model': name,
        'Mean AUC': auc_scores.mean(),
        'Std AUC': auc_scores.std(),
        'Precision@10': precision_at_k(y, y_proba, k=10),
        'EV per Trade': expected_value_per_trade(y, y_proba),
    })

comparison = pd.DataFrame(results)
comparison = comparison.sort_values('Mean AUC', ascending=False)

print("\n🏆 Model Comparison:")
print(comparison.to_string(index=False))

# Visualization
fig, axes = plt.subplots(1, 3, figsize=(15, 4))

# AUC comparison
axes[0].barh(comparison['Model'], comparison['Mean AUC'])
axes[0].set_xlabel('AUC')
axes[0].set_title('Model AUC Comparison')
axes[0].axvline(0.6, color='red', linestyle='--', label='Baseline')
axes[0].legend()

# Precision@10 comparison
axes[1].barh(comparison['Model'], comparison['Precision@10'])
axes[1].set_xlabel('Precision@10')
axes[1].set_title('Top 10% Precision')
axes[1].axvline(0.5, color='red', linestyle='--', label='Random')
axes[1].legend()

# EV per Trade
axes[2].barh(comparison['Model'], comparison['EV per Trade'])
axes[2].set_xlabel('Expected Value')
axes[2].set_title('Expected Value per Trade')
axes[2].axvline(0, color='red', linestyle='--', label='Break-even')
axes[2].legend()

plt.tight_layout()
plt.savefig('models/phase6_comparison.png')
plt.show()

print("\n✅ Comparison chart saved to: models/phase6_comparison.png")
```

---

## 🎓 Best Practices

### 1. Feature Selection

```python
from sklearn.feature_selection import SelectKBest, f_classif

# Select top 50 features by F-statistic
selector = SelectKBest(f_classif, k=50)
X_selected = selector.fit_transform(X, y)
selected_features = X.columns[selector.get_support()]

print(f"Selected {len(selected_features)} features:")
print(selected_features.tolist())
```

### 2. Handle Class Imbalance

```python
from imblearn.over_sampling import SMOTE
from imblearn.under_sampling import RandomUnderSampler
from imblearn.pipeline import Pipeline as ImbPipeline

# Balanced sampling pipeline
sampler = ImbPipeline([
    ('over', SMOTE(sampling_strategy=0.5)),  # Oversample minority to 50%
    ('under', RandomUnderSampler(sampling_strategy=0.8))  # Undersample majority
])

X_resampled, y_resampled = sampler.fit_resample(X, y)
print(f"Original: {y.value_counts()}")
print(f"Resampled: {pd.Series(y_resampled).value_counts()}")
```

### 3. Probability Calibration

```python
from sklearn.calibration import CalibratedClassifierCV

# Calibrate probabilities
calibrated_model = CalibratedClassifierCV(
    base_estimator=xgb_model,
    method='isotonic',  # or 'sigmoid' for Platt scaling
    cv=5
)

calibrated_model.fit(X, y)
calibrated_proba = calibrated_model.predict_proba(X)[:, 1]

# Compare calibration
from sklearn.calibration import calibration_curve

prob_true, prob_pred = calibration_curve(y, probabilities, n_bins=10)
prob_true_cal, prob_pred_cal = calibration_curve(y, calibrated_proba, n_bins=10)

plt.figure(figsize=(8, 6))
plt.plot([0, 1], [0, 1], 'k--', label='Perfect Calibration')
plt.plot(prob_pred, prob_true, 's-', label='Before Calibration')
plt.plot(prob_pred_cal, prob_true_cal, 'o-', label='After Calibration')
plt.xlabel('Predicted Probability')
plt.ylabel('True Probability')
plt.title('Calibration Curves')
plt.legend()
plt.savefig('models/calibration_curves.png')
plt.show()
```

### 4. Save and Load Models

```python
import joblib

# Save model
model_path = Path("models/phase6_baseline/xgboost_v1.pkl")
model_path.parent.mkdir(parents=True, exist_ok=True)
joblib.dump(xgb_model, model_path)

# Save metadata
metadata = {
    'model_type': 'XGBoost',
    'features': feature_cols,
    'n_features': len(feature_cols),
    'train_samples': len(X),
    'metrics': metrics,
    'optimal_threshold': optimal_threshold,
    'trained_at': pd.Timestamp.now().isoformat(),
}

import json
with open(model_path.with_suffix('.json'), 'w') as f:
    json.dump(metadata, f, indent=2)

# Load model
loaded_model = joblib.load(model_path)
loaded_metadata = json.load(open(model_path.with_suffix('.json')))

print(f"Loaded model trained at: {loaded_metadata['trained_at']}")
```

---

## 📊 Complete Example Script

Save this as `scripts/train_phase6_baseline.py`:

```python
"""
Phase 6: Train and evaluate baseline models.

Usage:
    python scripts/train_phase6_baseline.py --instrument SPY --horizon 5
"""

import argparse
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import json

from autotrader.data_prep.features import FeatureFactory, FeatureConfig
from autotrader.data_prep.labeling import TripleBarrierLabeler
from src.models.lightgbm_pipeline import LightGBMPipeline

from sklearn.metrics import (
    roc_auc_score, precision_score, recall_score,
    f1_score, precision_recall_curve
)


def precision_at_k(y_true, y_proba, k=10):
    """Precision of top k% predictions."""
    threshold = np.percentile(y_proba, 100 - k)
    y_pred = (y_proba >= threshold).astype(int)
    return precision_score(y_true, y_pred)


def expected_value_per_trade(y_true, y_proba, avg_return=0.02, cost=0.001):
    """Expected value per trade after costs."""
    return y_proba.mean() * avg_return - cost


def main(args):
    print(f"🚀 Training baseline model for {args.instrument} (horizon={args.horizon}d)")
    
    # 1. Load data
    print("\n1️⃣ Loading data...")
    bars = pd.read_parquet(f"data/{args.instrument}_bars.parquet")
    print(f"  Loaded {len(bars)} bars")
    
    # 2. Extract features
    print("\n2️⃣ Extracting features...")
    config = FeatureConfig.balanced()
    factory = FeatureFactory(config)
    features = factory.extract_all(bars_df=bars)
    print(f"  Extracted {features.shape[1]} features")
    
    # 3. Generate labels
    print("\n3️⃣ Generating labels...")
    labeler = TripleBarrierLabeler(
        profit_target=0.02,
        stop_loss=0.01,
        horizon_days=args.horizon
    )
    labels = labeler.label(bars)
    print(f"  Generated {len(labels)} labels")
    
    # 4. Merge and prepare
    df = features.join(labels, how='inner')
    feature_cols = [col for col in df.columns if col not in ['label', 'label_type', 'return']]
    X = df[feature_cols]
    y = (df['label'] == 1).astype(int)
    
    print(f"\n📊 Dataset:")
    print(f"  Features: {X.shape[1]}")
    print(f"  Samples: {len(X)}")
    print(f"  Label distribution: {y.value_counts().to_dict()}")
    
    # 5. Train model
    print("\n4️⃣ Training LightGBM model...")
    pipeline = LightGBMPipeline(
        model_dir=Path(f"models/{args.instrument}_h{args.horizon}"),
        params={
            "objective": "binary",
            "metric": "auc",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "scale_pos_weight": 5.0,
        }
    )
    
    # Cross-validation
    cv_metrics = pipeline.cross_validate(X, y, n_splits=5)
    print(f"  CV AUC: {cv_metrics.roc_auc:.3f}")
    print(f"  CV Precision: {cv_metrics.precision:.3f}")
    
    # Train final model
    final_metrics = pipeline.train(X, y)
    probabilities = pipeline.predict_proba(X)
    
    # 6. Evaluate
    print("\n5️⃣ Evaluation:")
    y_pred = (probabilities >= 0.5).astype(int)
    
    metrics = {
        'auc': roc_auc_score(y, probabilities),
        'precision': precision_score(y, y_pred),
        'recall': recall_score(y, y_pred),
        'f1': f1_score(y, y_pred),
        'precision_at_10': precision_at_k(y, probabilities, k=10),
        'precision_at_20': precision_at_k(y, probabilities, k=20),
        'ev_per_trade': expected_value_per_trade(y, probabilities),
    }
    
    for metric, value in metrics.items():
        print(f"  {metric}: {value:.4f}")
    
    # Find optimal threshold
    precisions, recalls, thresholds = precision_recall_curve(y, probabilities)
    f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
    optimal_idx = np.argmax(f1_scores)
    optimal_threshold = thresholds[optimal_idx]
    
    print(f"\n🎯 Optimal Threshold: {optimal_threshold:.3f}")
    print(f"  Precision: {precisions[optimal_idx]:.3f}")
    print(f"  Recall: {recalls[optimal_idx]:.3f}")
    
    # 7. Save metadata
    metadata = {
        'instrument': args.instrument,
        'horizon': args.horizon,
        'n_features': len(feature_cols),
        'n_samples': len(X),
        'metrics': metrics,
        'optimal_threshold': float(optimal_threshold),
        'feature_importance_top10': pipeline.get_feature_importance().head(10).to_dict(),
        'trained_at': pd.Timestamp.now().isoformat(),
    }
    
    metadata_path = pipeline.model_dir / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Model saved to: {pipeline.model_dir}")
    print(f"✅ Metadata saved to: {metadata_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--instrument', default='SPY', help='Instrument to train on')
    parser.add_argument('--horizon', type=int, default=5, help='Prediction horizon (days)')
    args = parser.parse_args()
    
    main(args)
```

Run it:
```bash
python scripts/train_phase6_baseline.py --instrument SPY --horizon 5
```

---

## 🎯 Next Steps

1. **Run the quick start** (above) to get baseline results
2. **Try different models** (Logistic, XGBoost, LightGBM)
3. **Tune hyperparameters** using Optuna (see PHASE_6_MODELING_SPECIFICATION.md)
4. **Evaluate per instrument** to find best model for each asset
5. **Deploy best model** using your existing infrastructure

---

## 📚 Resources

- **Existing Implementation**: `src/models/lightgbm_pipeline.py`
- **Full Specification**: `PHASE_6_MODELING_SPECIFICATION.md`
- **Phase 5 Features**: `MICROSTRUCTURE_FEATURES.md`
- **Phase 5 Labels**: `FEATURE_STORE_GUIDE.md`

---

**Ready to train? Start with Step 1!** 🚀
