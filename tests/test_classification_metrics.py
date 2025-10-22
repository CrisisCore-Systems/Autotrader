"""Tests for classification metrics (ROC/AUC, PR curves)."""

import numpy as np
import pytest
from typing import Dict

from backtest.extended_metrics import (
    ClassificationMetrics,
    calculate_classification_metrics,
    calculate_extended_metrics,
)


class MockTokenSnapshot:
    """Mock token snapshot for testing."""
    
    def __init__(self, token: str, features: Dict[str, float], future_return_7d: float):
        self.token = token
        self.features = features
        self.future_return_7d = future_return_7d


class TestCalculateClassificationMetrics:
    """Test classification metrics calculation."""
    
    def test_perfect_classification(self):
        """Test perfect classification (all predictions correct)."""
        # Higher predictions for positive returns, lower for negative
        predictions = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
        actuals = np.array([0.05, 0.03, 0.02, -0.01, -0.02, -0.03])
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        assert metrics.roc_auc == pytest.approx(1.0, abs=0.01)
        assert metrics.pr_auc == pytest.approx(1.0, abs=0.01)
        assert metrics.sample_size == 6
        assert 0.0 <= metrics.baseline_accuracy <= 1.0
    
    def test_random_classification(self):
        """Test random predictions (AUC should be around 0.5)."""
        np.random.seed(42)
        predictions = np.random.randn(50)
        actuals = np.random.randn(50)
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # ROC AUC should be close to 0.5 for random predictions
        assert 0.3 < metrics.roc_auc < 0.7
        assert metrics.sample_size == 50
    
    def test_inverse_classification(self):
        """Test inverse predictions (low AUC)."""
        # Lower predictions for positive returns, higher for negative
        predictions = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9])
        actuals = np.array([0.05, 0.03, 0.02, -0.01, -0.02, -0.03])
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # Should have low AUC (worse than random)
        assert metrics.roc_auc < 0.5
    
    def test_with_nan_values(self):
        """Test handling of NaN values."""
        predictions = np.array([0.9, np.nan, 0.7, 0.3, 0.2])
        actuals = np.array([0.05, 0.03, np.nan, -0.01, -0.02])
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # Should filter out NaNs
        assert metrics.sample_size == 3
        assert not np.isnan(metrics.roc_auc)
    
    def test_insufficient_data(self):
        """Test with insufficient data."""
        predictions = np.array([0.9])
        actuals = np.array([0.05])
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        assert metrics.roc_auc == 0.5  # Default for insufficient data
        assert metrics.sample_size == 1
    
    def test_single_class(self):
        """Test with only one class (all positive or all negative returns)."""
        predictions = np.array([0.9, 0.8, 0.7, 0.6])
        actuals = np.array([0.05, 0.03, 0.02, 0.01])  # All positive
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # Should handle gracefully
        assert metrics.sample_size == 4
        assert 0.0 <= metrics.roc_auc <= 1.0
    
    def test_baseline_accuracy_calculation(self):
        """Test baseline accuracy (majority class) calculation."""
        # 3 positive, 2 negative
        predictions = np.array([0.9, 0.8, 0.7, 0.3, 0.2])
        actuals = np.array([0.05, 0.03, 0.02, -0.01, -0.02])
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # Baseline should be 3/5 = 0.6 (majority class)
        assert metrics.baseline_accuracy == 0.6
    
    def test_roc_curve_properties(self):
        """Test ROC curve properties."""
        predictions = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
        actuals = np.array([0.05, 0.03, 0.02, -0.01, -0.02, -0.03])
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # ROC curve should start at (0,0) and end at (1,1)
        assert metrics.roc_curve_fpr[0] == pytest.approx(0.0, abs=0.01)
        assert metrics.roc_curve_tpr[0] == pytest.approx(0.0, abs=0.01)
        assert metrics.roc_curve_fpr[-1] == pytest.approx(1.0, abs=0.01)
        assert metrics.roc_curve_tpr[-1] == pytest.approx(1.0, abs=0.01)
        
        # TPR should be monotonically increasing
        assert all(metrics.roc_curve_tpr[i] <= metrics.roc_curve_tpr[i+1] 
                  for i in range(len(metrics.roc_curve_tpr)-1))
    
    def test_pr_curve_properties(self):
        """Test Precision-Recall curve properties."""
        predictions = np.array([0.9, 0.8, 0.7, 0.3, 0.2, 0.1])
        actuals = np.array([0.05, 0.03, 0.02, -0.01, -0.02, -0.03])
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # Precision and recall should be in [0, 1]
        assert all(0.0 <= p <= 1.0 for p in metrics.pr_curve_precision)
        assert all(0.0 <= r <= 1.0 for r in metrics.pr_curve_recall)
    
    def test_moderate_classification(self):
        """Test moderate classification performance."""
        np.random.seed(42)
        # Create moderately correlated data
        actuals = np.random.randn(50)
        noise = np.random.randn(50) * 0.5
        predictions = actuals + noise
        
        metrics = calculate_classification_metrics(predictions, actuals)
        
        # Should have moderate AUC (better than random)
        assert 0.5 < metrics.roc_auc < 1.0
        assert 0.0 < metrics.pr_auc <= 1.0


class TestExtendedMetricsWithClassification:
    """Test extended metrics with classification metrics included."""
    
    def test_extended_metrics_with_classification(self):
        """Test that classification metrics are included in extended metrics."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.05),
            MockTokenSnapshot("TOKEN2", {}, 0.03),
            MockTokenSnapshot("TOKEN3", {}, -0.02),
            MockTokenSnapshot("TOKEN4", {}, 0.04),
            MockTokenSnapshot("TOKEN5", {}, -0.01),
        ]
        predictions = np.array([0.9, 0.7, 0.3, 0.8, 0.2])
        
        metrics = calculate_extended_metrics(
            snapshots, predictions, include_classification=True
        )
        
        assert metrics.classification_metrics is not None
        assert isinstance(metrics.classification_metrics, ClassificationMetrics)
        assert metrics.classification_metrics.sample_size == 5
        assert 0.0 <= metrics.classification_metrics.roc_auc <= 1.0
    
    def test_extended_metrics_without_classification(self):
        """Test that classification metrics can be disabled."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.05),
            MockTokenSnapshot("TOKEN2", {}, 0.03),
        ]
        predictions = np.array([0.9, 0.7])
        
        metrics = calculate_extended_metrics(
            snapshots, predictions, include_classification=False
        )
        
        assert metrics.classification_metrics is None
    
    def test_classification_metrics_to_dict(self):
        """Test conversion to dictionary."""
        snapshots = [
            MockTokenSnapshot("TOKEN1", {}, 0.05),
            MockTokenSnapshot("TOKEN2", {}, 0.03),
            MockTokenSnapshot("TOKEN3", {}, -0.02),
        ]
        predictions = np.array([0.9, 0.7, 0.3])
        
        metrics = calculate_extended_metrics(
            snapshots, predictions, include_classification=True
        )
        
        result_dict = metrics.to_dict()
        
        assert 'classification_metrics' in result_dict
        assert 'roc_auc' in result_dict['classification_metrics']
        assert 'pr_auc' in result_dict['classification_metrics']
        assert 'baseline_accuracy' in result_dict['classification_metrics']
    
    def test_classification_metrics_summary_string(self):
        """Test summary string includes classification metrics."""
        snapshots = [
            MockTokenSnapshot(f"TOKEN{i}", {}, 0.01 * (i % 2 * 2 - 1))
            for i in range(10)
        ]
        predictions = np.array([0.1 * i for i in range(10)])
        
        metrics = calculate_extended_metrics(
            snapshots, predictions, include_classification=True
        )
        
        summary = metrics.summary_string()
        
        assert "CLASSIFICATION METRICS" in summary or "ROC/PR" in summary
        assert "ROC AUC" in summary
        assert "PR AUC" in summary


class TestClassificationMetricsDataclass:
    """Test ClassificationMetrics dataclass."""
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = ClassificationMetrics(
            roc_auc=0.85,
            roc_curve_fpr=np.array([0.0, 0.5, 1.0]),
            roc_curve_tpr=np.array([0.0, 0.8, 1.0]),
            roc_curve_thresholds=np.array([1.0, 0.5, 0.0]),
            pr_auc=0.80,
            pr_curve_precision=np.array([1.0, 0.8, 0.6]),
            pr_curve_recall=np.array([0.0, 0.5, 1.0]),
            pr_curve_thresholds=np.array([1.0, 0.5]),
            baseline_accuracy=0.6,
            sample_size=100,
        )
        
        result = metrics.to_dict()
        
        assert result['roc_auc'] == 0.85
        assert result['pr_auc'] == 0.80
        assert result['baseline_accuracy'] == 0.6
        assert result['sample_size'] == 100
        # Curve arrays should not be in dict (for JSON serialization)
        assert 'roc_curve_fpr' not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
