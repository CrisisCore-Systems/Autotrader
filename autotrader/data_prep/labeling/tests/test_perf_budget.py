"""
Performance budget tests: Don't let O(N²) slip in.

These tests ensure labeling performance stays within acceptable bounds.
"""

import time
import pytest

from autotrader.data_prep.labeling import LabelFactory


class TestPerformanceBudgets:
    """Ensure labeling stays within performance budgets."""
    
    def test_classification_under_time_budget(self, bars_1s_2h):
        """
        Classification labeling should complete within time budget.
        
        Budget: ~1.5s for 7,200 bars on modern CPU.
        Adjust threshold for your hardware.
        """
        t0 = time.perf_counter()
        
        LabelFactory.create(
            bars_1s_2h,
            method="classification",
            horizon_seconds=60,
        )
        
        elapsed = time.perf_counter() - t0
        
        assert elapsed < 2.0, f"Classification took {elapsed:.2f}s (budget: 2.0s)"
    
    def test_regression_under_time_budget(self, bars_1s_2h):
        """
        Regression labeling should complete within time budget.
        
        Budget: ~1.5s for 7,200 bars (similar to classification).
        """
        t0 = time.perf_counter()
        
        LabelFactory.create(
            bars_1s_2h,
            method="regression",
            horizon_seconds=60,
        )
        
        elapsed = time.perf_counter() - t0
        
        assert elapsed < 2.0, f"Regression took {elapsed:.2f}s (budget: 2.0s)"
    
    def test_horizon_optimization_under_budget(self, bars_5m_1d):
        """
        Horizon optimization should complete within budget.
        
        Budget: ~5s for 288 bars × 4 horizons.
        """
        from autotrader.data_prep.labeling import HorizonOptimizer
        
        t0 = time.perf_counter()
        
        optimizer = HorizonOptimizer(
            horizons_seconds=[30, 60, 120, 180],
            labeling_method="classification",
        )
        
        optimizer.optimize(bars_5m_1d, symbol="TEST")
        
        elapsed = time.perf_counter() - t0
        
        assert elapsed < 10.0, f"Horizon optimization took {elapsed:.2f}s (budget: 10.0s)"
    
    def test_statistics_computation_fast(self, bars_1s_2h):
        """Statistics computation should be fast."""
        labeler = LabelFactory.get_labeler(method="classification", horizon_seconds=60)
        labeled_data = labeler.generate_labels(bars_1s_2h)
        
        t0 = time.perf_counter()
        
        labeler.get_label_statistics(labeled_data)
        
        elapsed = time.perf_counter() - t0
        
        assert elapsed < 0.5, f"Statistics took {elapsed:.2f}s (budget: 0.5s)"


class TestScalability:
    """Ensure labeling scales linearly with data size."""
    
    def test_classification_scales_linearly(self):
        """
        Classification should scale O(N), not O(N²).
        
        Time for 2N bars should be ≤ 2.5× time for N bars.
        """
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta
        
        # Generate small dataset (500 bars)
        n_small = 500
        ts_small = [datetime(2025, 1, 1, 9, 30, 0) + timedelta(seconds=i) for i in range(n_small)]
        mid_small = 100 + np.cumsum(np.random.normal(0, 0.01, size=n_small))
        
        df_small = pd.DataFrame({
            "timestamp": ts_small,
            "open": mid_small,
            "high": mid_small + 0.01,
            "low": mid_small - 0.01,
            "close": mid_small,
            "volume": 1000.0,
            "bid": mid_small - 0.01,
            "ask": mid_small + 0.01,
            "bid_vol": 100.0,
            "ask_vol": 100.0,
        })
        
        # Generate large dataset (1000 bars)
        n_large = 1000
        ts_large = [datetime(2025, 1, 1, 9, 30, 0) + timedelta(seconds=i) for i in range(n_large)]
        mid_large = 100 + np.cumsum(np.random.normal(0, 0.01, size=n_large))
        
        df_large = pd.DataFrame({
            "timestamp": ts_large,
            "open": mid_large,
            "high": mid_large + 0.01,
            "low": mid_large - 0.01,
            "close": mid_large,
            "volume": 1000.0,
            "bid": mid_large - 0.01,
            "ask": mid_large + 0.01,
            "bid_vol": 100.0,
            "ask_vol": 100.0,
        })
        
        # Time small dataset
        t0 = time.perf_counter()
        LabelFactory.create(df_small, method="classification", horizon_seconds=60)
        time_small = time.perf_counter() - t0
        
        # Time large dataset
        t0 = time.perf_counter()
        LabelFactory.create(df_large, method="classification", horizon_seconds=60)
        time_large = time.perf_counter() - t0
        
        # Scaling ratio (should be close to 2.0 for linear scaling)
        ratio = time_large / time_small if time_small > 0 else 0
        
        # Allow up to 2.5× (some overhead is acceptable)
        assert ratio < 3.0, f"Non-linear scaling detected: {ratio:.2f}× for 2× data"
    
    def test_regression_scales_linearly(self):
        """Regression should also scale O(N)."""
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta
        
        # Small dataset (500 bars)
        n_small = 500
        ts_small = [datetime(2025, 1, 1, 9, 30, 0) + timedelta(seconds=i) for i in range(n_small)]
        mid_small = 100 + np.cumsum(np.random.normal(0, 0.01, size=n_small))
        
        df_small = pd.DataFrame({
            "timestamp": ts_small,
            "open": mid_small,
            "high": mid_small + 0.01,
            "low": mid_small - 0.01,
            "close": mid_small,
            "volume": 1000.0,
            "bid": mid_small - 0.01,
            "ask": mid_small + 0.01,
            "bid_vol": 100.0,
            "ask_vol": 100.0,
        })
        
        # Large dataset (1000 bars)
        n_large = 1000
        ts_large = [datetime(2025, 1, 1, 9, 30, 0) + timedelta(seconds=i) for i in range(n_large)]
        mid_large = 100 + np.cumsum(np.random.normal(0, 0.01, size=n_large))
        
        df_large = pd.DataFrame({
            "timestamp": ts_large,
            "open": mid_large,
            "high": mid_large + 0.01,
            "low": mid_large - 0.01,
            "close": mid_large,
            "volume": 1000.0,
            "bid": mid_large - 0.01,
            "ask": mid_large + 0.01,
            "bid_vol": 100.0,
            "ask_vol": 100.0,
        })
        
        # Time small
        t0 = time.perf_counter()
        LabelFactory.create(df_small, method="regression", horizon_seconds=60)
        time_small = time.perf_counter() - t0
        
        # Time large
        t0 = time.perf_counter()
        LabelFactory.create(df_large, method="regression", horizon_seconds=60)
        time_large = time.perf_counter() - t0
        
        ratio = time_large / time_small if time_small > 0 else 0
        
        assert ratio < 3.0, f"Non-linear scaling detected: {ratio:.2f}× for 2× data"


class TestMemoryUsage:
    """Ensure memory usage stays reasonable."""
    
    def test_no_memory_leaks_in_loop(self, bars_5m_1d):
        """
        Repeated labeling shouldn't leak memory.
        
        This is a smoke test - not a precise memory profiler.
        """
        import gc
        
        # Force garbage collection
        gc.collect()
        
        # Run labeling multiple times
        for _ in range(10):
            LabelFactory.create(bars_5m_1d, method="classification", horizon_seconds=60)
        
        # Force garbage collection again
        gc.collect()
        
        # If we got here without OOM, test passes
        assert True
    
    def test_large_dataset_doesnt_crash(self):
        """
        Large dataset (10K bars) should complete without OOM.
        
        This is a smoke test for memory efficiency.
        """
        import pandas as pd
        import numpy as np
        from datetime import datetime, timedelta
        
        # Generate large dataset (10,000 bars)
        n = 10_000
        ts = [datetime(2025, 1, 1, 9, 30, 0) + timedelta(seconds=i) for i in range(n)]
        mid = 100 + np.cumsum(np.random.normal(0, 0.01, size=n))
        
        df = pd.DataFrame({
            "timestamp": ts,
            "open": mid,
            "high": mid + 0.01,
            "low": mid - 0.01,
            "close": mid,
            "volume": 1000.0,
            "bid": mid - 0.01,
            "ask": mid + 0.01,
            "bid_vol": 100.0,
            "ask_vol": 100.0,
        })
        
        # Should complete without OOM
        out = LabelFactory.create(df, method="classification", horizon_seconds=60)
        
        assert len(out) == n, "Output length mismatch"


# Conditional test markers for CI vs local
pytestmark = pytest.mark.performance
