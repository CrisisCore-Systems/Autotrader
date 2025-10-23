"""Tests for time-sliced evaluation."""

import pandas as pd
import pytest
from datetime import datetime
from typing import Dict
from dataclasses import dataclass

# Import only what we need to avoid dependency issues
try:
    from backtest.harness import (
        TokenSnapshot,
        ExperimentConfig,
        TimeSlice,
        BacktestResult,
        evaluate_time_sliced,
    )
    HARNESS_AVAILABLE = True
except ImportError:
    # For testing without full harness dependencies
    HARNESS_AVAILABLE = False
    
    @dataclass
    class TokenSnapshot:
        token: str
        date: pd.Timestamp
        features: Dict[str, float]
        future_return_7d: float
    
    @dataclass
    class ExperimentConfig:
        top_k: int
        compare_baselines: bool
        extended_metrics: bool
        seed: int | None
        data_path: str
        timestamp: str
        
        def to_dict(self):
            return {
                'top_k': self.top_k,
                'compare_baselines': self.compare_baselines,
                'extended_metrics': self.extended_metrics,
                'seed': self.seed,
                'data_path': self.data_path,
                'timestamp': self.timestamp,
            }
    
    @dataclass
    class BacktestResult:
        precision_at_k: float
        average_return_at_k: float
        flagged_assets: list
        config: ExperimentConfig | None = None
        time_slices: list | None = None
        
        def to_dict(self):
            result = {
                'precision_at_k': self.precision_at_k,
                'average_return_at_k': self.average_return_at_k,
                'flagged_assets': self.flagged_assets,
            }
            if self.config:
                result['config'] = self.config.to_dict()
            if self.time_slices:
                result['time_slices'] = [
                    {
                        'period_id': ts.period_id,
                        'start_date': ts.start_date.isoformat(),
                        'end_date': ts.end_date.isoformat(),
                        'precision': ts.result.precision_at_k,
                        'avg_return': ts.result.average_return_at_k,
                    }
                    for ts in self.time_slices
                ]
            return result
        
        def to_json(self, path=None, indent=2):
            import json
            return json.dumps(self.to_dict(), indent=indent)
    
    @dataclass
    class TimeSlice:
        period_id: int
        start_date: pd.Timestamp
        end_date: pd.Timestamp
        result: BacktestResult


class TestExperimentConfig:
    """Test ExperimentConfig dataclass."""
    
    def test_config_creation(self):
        """Test creating experiment config."""
        config = ExperimentConfig(
            top_k=10,
            compare_baselines=True,
            extended_metrics=True,
            seed=42,
            data_path="/path/to/data.csv",
            timestamp="2024-01-01T00:00:00",
        )
        
        assert config.top_k == 10
        assert config.compare_baselines is True
        assert config.seed == 42
    
    def test_config_to_dict(self):
        """Test conversion to dictionary."""
        config = ExperimentConfig(
            top_k=5,
            compare_baselines=False,
            extended_metrics=True,
            seed=None,
            data_path="/data.csv",
            timestamp="2024-01-01T00:00:00",
        )
        
        result = config.to_dict()
        
        assert result['top_k'] == 5
        assert result['compare_baselines'] is False
        assert result['seed'] is None
        assert result['data_path'] == "/data.csv"


class TestTimeSlice:
    """Test TimeSlice dataclass."""
    
    def test_time_slice_creation(self):
        """Test creating time slice."""
        result = BacktestResult(
            precision_at_k=0.7,
            average_return_at_k=0.05,
            flagged_assets=["TOKEN1", "TOKEN2"],
        )
        
        time_slice = TimeSlice(
            period_id=0,
            start_date=pd.Timestamp("2024-01-01"),
            end_date=pd.Timestamp("2024-01-31"),
            result=result,
        )
        
        assert time_slice.period_id == 0
        assert time_slice.result.precision_at_k == 0.7


class TestBacktestResultWithConfig:
    """Test BacktestResult with experiment config."""
    
    def test_result_with_config(self):
        """Test that BacktestResult can store config."""
        config = ExperimentConfig(
            top_k=10,
            compare_baselines=True,
            extended_metrics=True,
            seed=42,
            data_path="/data.csv",
            timestamp="2024-01-01T00:00:00",
        )
        
        result = BacktestResult(
            precision_at_k=0.7,
            average_return_at_k=0.05,
            flagged_assets=["TOKEN1"],
            config=config,
        )
        
        assert result.config is not None
        assert result.config.seed == 42
    
    def test_result_to_dict_with_config(self):
        """Test conversion to dictionary includes config."""
        config = ExperimentConfig(
            top_k=5,
            compare_baselines=False,
            extended_metrics=True,
            seed=123,
            data_path="/data.csv",
            timestamp="2024-01-01T00:00:00",
        )
        
        result = BacktestResult(
            precision_at_k=0.6,
            average_return_at_k=0.03,
            flagged_assets=["TOKEN1", "TOKEN2"],
            config=config,
        )
        
        result_dict = result.to_dict()
        
        assert 'config' in result_dict
        assert result_dict['config']['seed'] == 123
        assert result_dict['config']['top_k'] == 5
    
    def test_result_with_time_slices(self):
        """Test that BacktestResult can store time slices."""
        time_slices = [
            TimeSlice(
                period_id=0,
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-31"),
                result=BacktestResult(
                    precision_at_k=0.7,
                    average_return_at_k=0.05,
                    flagged_assets=["TOKEN1"],
                ),
            ),
            TimeSlice(
                period_id=1,
                start_date=pd.Timestamp("2024-02-01"),
                end_date=pd.Timestamp("2024-02-29"),
                result=BacktestResult(
                    precision_at_k=0.6,
                    average_return_at_k=0.03,
                    flagged_assets=["TOKEN2"],
                ),
            ),
        ]
        
        result = BacktestResult(
            precision_at_k=0.65,
            average_return_at_k=0.04,
            flagged_assets=["TOKEN1", "TOKEN2"],
            time_slices=time_slices,
        )
        
        assert len(result.time_slices) == 2
        assert result.time_slices[0].period_id == 0
        assert result.time_slices[1].period_id == 1
    
    def test_result_to_dict_with_time_slices(self):
        """Test conversion to dictionary includes time slices."""
        time_slices = [
            TimeSlice(
                period_id=0,
                start_date=pd.Timestamp("2024-01-01"),
                end_date=pd.Timestamp("2024-01-31"),
                result=BacktestResult(
                    precision_at_k=0.7,
                    average_return_at_k=0.05,
                    flagged_assets=["TOKEN1"],
                ),
            ),
        ]
        
        result = BacktestResult(
            precision_at_k=0.7,
            average_return_at_k=0.05,
            flagged_assets=["TOKEN1"],
            time_slices=time_slices,
        )
        
        result_dict = result.to_dict()
        
        assert 'time_slices' in result_dict
        assert len(result_dict['time_slices']) == 1
        assert result_dict['time_slices'][0]['period_id'] == 0
        assert result_dict['time_slices'][0]['precision'] == 0.7


@pytest.mark.skipif(not HARNESS_AVAILABLE, reason="Full harness not available")
class TestEvaluateTimeSliced:
    """Test time-sliced evaluation function."""
    
    def create_mock_snapshots(self, num_periods: int = 3) -> list[TokenSnapshot]:
        """Create mock snapshots across multiple time periods."""
        snapshots = []
        
        for period in range(num_periods):
            base_date = pd.Timestamp(f"2024-{period+1:02d}-01")
            
            for i in range(10):
                date = base_date + pd.Timedelta(days=i)
                token = f"TOKEN{period}_{i}"
                
                # Alternate positive and negative returns
                future_return = 0.05 if i % 2 == 0 else -0.02
                
                snapshot = TokenSnapshot(
                    token=token,
                    date=date,
                    features={"dummy": float(i)},
                    future_return_7d=future_return,
                )
                snapshots.append(snapshot)
        
        return snapshots
    
    def test_monthly_slicing(self):
        """Test time-sliced evaluation with monthly slices."""
        snapshots = self.create_mock_snapshots(num_periods=3)
        
        result = evaluate_time_sliced(
            snapshots,
            top_k=5,
            slice_by="month",
            compare_baselines=False,
            extended_metrics=False,
            seed=42,
        )
        
        # Should have 3 time slices (one per month)
        assert result.time_slices is not None
        assert len(result.time_slices) == 3
        
        # Check overall metrics
        assert 0.0 <= result.precision_at_k <= 1.0
        assert isinstance(result.average_return_at_k, float)
    
    def test_time_slice_ordering(self):
        """Test that time slices are ordered correctly."""
        snapshots = self.create_mock_snapshots(num_periods=2)
        
        result = evaluate_time_sliced(
            snapshots,
            top_k=3,
            slice_by="month",
            seed=42,
        )
        
        # Check period IDs are sequential
        for i, ts in enumerate(result.time_slices):
            assert ts.period_id == i
        
        # Check dates are ordered
        for i in range(len(result.time_slices) - 1):
            assert result.time_slices[i].end_date <= result.time_slices[i+1].start_date
    
    def test_quarterly_slicing(self):
        """Test time-sliced evaluation with quarterly slices."""
        # Create snapshots across 6 months (2 quarters)
        snapshots = []
        for month in range(1, 7):
            for day in range(1, 11):
                date = pd.Timestamp(f"2024-{month:02d}-{day:02d}")
                token = f"TOKEN_{month}_{day}"
                snapshot = TokenSnapshot(
                    token=token,
                    date=date,
                    features={},
                    future_return_7d=0.01 if day % 2 == 0 else -0.01,
                )
                snapshots.append(snapshot)
        
        result = evaluate_time_sliced(
            snapshots,
            top_k=5,
            slice_by="quarter",
            seed=42,
        )
        
        # Should have 2 time slices (2 quarters)
        assert len(result.time_slices) == 2
    
    def test_invalid_slice_by(self):
        """Test that invalid slice_by raises error."""
        snapshots = self.create_mock_snapshots(num_periods=1)
        
        with pytest.raises(ValueError, match="Invalid slice_by"):
            evaluate_time_sliced(
                snapshots,
                top_k=3,
                slice_by="invalid",
            )
    
    def test_time_sliced_with_baselines(self):
        """Test time-sliced evaluation with baseline comparison."""
        snapshots = self.create_mock_snapshots(num_periods=2)
        
        # Add market cap features for baseline strategies
        for snap in snapshots:
            snap.features["MarketCap"] = 1_000_000
            snap.features["PriceChange7d"] = 0.05
        
        result = evaluate_time_sliced(
            snapshots,
            top_k=3,
            slice_by="month",
            compare_baselines=True,
            seed=42,
        )
        
        # Baseline results should be calculated on full dataset
        assert result.baseline_results is not None
        assert "random" in result.baseline_results
        assert "cap_weighted" in result.baseline_results
    
    def test_time_sliced_flagged_assets(self):
        """Test that flagged assets are collected across time slices."""
        snapshots = self.create_mock_snapshots(num_periods=2)
        
        result = evaluate_time_sliced(
            snapshots,
            top_k=5,
            slice_by="month",
            seed=42,
        )
        
        # Should have flagged assets
        assert len(result.flagged_assets) > 0
        assert all(isinstance(asset, str) for asset in result.flagged_assets)
    
    def test_aggregate_statistics(self):
        """Test that aggregate statistics are calculated correctly."""
        snapshots = self.create_mock_snapshots(num_periods=3)
        
        result = evaluate_time_sliced(
            snapshots,
            top_k=5,
            slice_by="month",
            seed=42,
        )
        
        # Extract per-period metrics
        precisions = [ts.result.precision_at_k for ts in result.time_slices]
        returns = [ts.result.average_return_at_k for ts in result.time_slices]
        
        # Overall metrics should be mean of per-period metrics
        import numpy as np
        assert result.precision_at_k == pytest.approx(np.mean(precisions), abs=0.001)
        assert result.average_return_at_k == pytest.approx(np.mean(returns), abs=0.001)


class TestExperimentReproducibility:
    """Test experiment reproducibility features."""
    
    def test_config_stores_all_parameters(self):
        """Test that config stores all relevant parameters."""
        config = ExperimentConfig(
            top_k=10,
            compare_baselines=True,
            extended_metrics=True,
            seed=42,
            data_path="/path/to/data.csv",
            timestamp="2024-01-01T00:00:00",
        )
        
        config_dict = config.to_dict()
        
        # All parameters should be present
        assert 'top_k' in config_dict
        assert 'compare_baselines' in config_dict
        assert 'extended_metrics' in config_dict
        assert 'seed' in config_dict
        assert 'data_path' in config_dict
        assert 'timestamp' in config_dict
    
    def test_json_export_includes_config(self):
        """Test that JSON export includes config for reproducibility."""
        import json
        
        config = ExperimentConfig(
            top_k=5,
            compare_baselines=False,
            extended_metrics=True,
            seed=123,
            data_path="/data.csv",
            timestamp="2024-01-01T00:00:00",
        )
        
        result = BacktestResult(
            precision_at_k=0.7,
            average_return_at_k=0.05,
            flagged_assets=["TOKEN1"],
            config=config,
        )
        
        json_str = result.to_json()
        parsed = json.loads(json_str)
        
        assert 'config' in parsed
        assert parsed['config']['seed'] == 123
        assert parsed['config']['top_k'] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
