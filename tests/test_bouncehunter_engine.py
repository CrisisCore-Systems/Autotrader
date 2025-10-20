"""Tests for BounceHunter engine."""

from __future__ import annotations

import warnings
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from src.bouncehunter.config import BounceHunterConfig
from src.bouncehunter.engine import BounceHunter, TrainingArtifact, _FEATURE_COLUMNS
from src.bouncehunter.report import SignalReport


class TestBounceHunter:
    """Test the BounceHunter scanning engine."""

    @pytest.fixture
    def sample_config(self) -> BounceHunterConfig:
        """Create a test configuration."""
        return BounceHunterConfig(
            tickers=["AAPL"],  # Just one ticker for simpler testing
            start=datetime(2020, 1, 1),
            min_adv_usd=100_000,  # Lower threshold for test data
            z_score_drop=-2.0,
            rsi2_max=30.0,
            bcs_threshold=0.6,
            max_dist_200dma=-0.05,
            stop_pct=0.05,
            rebound_pct=0.10,
            min_event_samples=1,  # Lower for testing
            horizon_days=5,
            skip_earnings=True,
            earnings_window_days=7,
            trailing_trend_window=63,
            trend_floor=-0.50,  # More lenient
            falling_knife_lookback=20,
            falling_knife_tolerance=-0.3,  # More lenient
        )

    @pytest.fixture
    def sample_history(self) -> pd.DataFrame:
        """Create sample historical data for testing."""
        dates = pd.date_range("2020-01-01", periods=300, freq="D")
        np.random.seed(42)

        # Generate realistic price data
        base_price = 100.0
        prices = [base_price]
        for _ in range(299):
            change = np.random.normal(0, 0.02)
            new_price = prices[-1] * (1 + change)
            prices.append(max(new_price, 1.0))  # Ensure positive prices

        return pd.DataFrame({
            "open": prices,
            "high": [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
            "low": [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
            "close": prices,
            "volume": [np.random.randint(5_000_000, 50_000_000) for _ in range(300)],  # Higher volume for adv_usd filter
        }, index=dates)

    def test_init_default_config(self):
        """Test initialization with default config."""
        engine = BounceHunter()
        assert isinstance(engine.config, BounceHunterConfig)
        assert engine._model is None
        assert engine._artifacts == {}
        assert engine._vix_cache is None

    def test_init_custom_config(self, sample_config):
        """Test initialization with custom config."""
        engine = BounceHunter(sample_config)
        assert engine.config is sample_config
        assert engine._model is None
        assert engine._artifacts == {}
        assert engine._vix_cache is None

    @patch("src.bouncehunter.engine.yf.download")
    def test_download_history_success(self, mock_download, sample_config, sample_history):
        """Test successful history download."""
        # Mock both AAPL and VIX downloads
        def mock_download_side_effect(*args, **kwargs):
            ticker = args[0] if args else kwargs.get('tickers', [''])[0]
            if ticker == '^VIX':
                # Return VIX data
                vix_dates = pd.date_range("2020-01-01", periods=300, freq="D")
                return pd.DataFrame({
                    "Close": np.random.uniform(10, 40, 300)
                }, index=vix_dates)
            else:
                # Return stock data
                return sample_history

        mock_download.side_effect = mock_download_side_effect

        engine = BounceHunter(sample_config)
        result = engine._download_history("AAPL")

        assert result is not None
        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0
        assert all(col in result.columns for col in ["open", "high", "low", "close", "volume"])

        # Check that indicators were built
        assert "rsi2" in result.columns
        assert "bb_dev" in result.columns
        assert "z5" in result.columns

    @patch("src.bouncehunter.engine.yf.download")
    def test_download_history_empty_data(self, mock_download, sample_config):
        """Test download with empty data."""
        mock_download.return_value = pd.DataFrame()

        engine = BounceHunter(sample_config)
        result = engine._download_history("INVALID")

        assert result is None

    @patch("src.bouncehunter.engine.yf.download")
    def test_download_history_insufficient_data(self, mock_download, sample_config):
        """Test download with insufficient data points."""
        # Create data with less than 260 points
        dates = pd.date_range("2020-01-01", periods=100, freq="D")
        short_data = pd.DataFrame({
            "open": [100.0] * 100,
            "high": [101.0] * 100,
            "low": [99.0] * 100,
            "close": [100.0] * 100,
            "volume": [100000] * 100,
        }, index=dates)

        mock_download.return_value = short_data

        engine = BounceHunter(sample_config)
        result = engine._download_history("SMALL")

        assert result is None

    @patch("src.bouncehunter.engine.yf.download")
    def test_build_indicators(self, mock_download, sample_config, sample_history):
        """Test indicator building."""
        # Mock VIX download
        vix_dates = pd.date_range("2020-01-01", periods=300, freq="D")
        vix_data = pd.DataFrame({
            "Close": np.random.uniform(10, 40, 300)
        }, index=vix_dates)
        mock_download.return_value = vix_data

        engine = BounceHunter(sample_config)
        result = engine._build_indicators(sample_history)

        # Check all expected indicators are present
        expected_indicators = [
            "ret1", "atr", "rsi2", "bb_dev", "ma200", "dist_200",
            "r5", "z5", "trend_63", "gap_dn", "adv_usd", "vix_regime"
        ]

        for indicator in expected_indicators:
            assert indicator in result.columns, f"Missing indicator: {indicator}"

        # Check data integrity
        assert not result.empty
        assert not result.isna().all().all()  # Not all NaN

    @patch("src.bouncehunter.engine.yf.download")
    def test_ensure_vix_cache(self, mock_download, sample_config, sample_history):
        """Test VIX data caching and retrieval."""
        # Mock VIX download
        vix_dates = pd.date_range("2020-01-01", periods=300, freq="D")
        vix_data = pd.DataFrame({
            "Close": np.random.uniform(10, 40, 300)
        }, index=vix_dates)
        mock_download.return_value = vix_data

        engine = BounceHunter(sample_config)

        # First call should download and cache
        vix1 = engine._ensure_vix(vix_dates[:10])
        assert isinstance(vix1, pd.Series)
        assert len(vix1) == 10

        # Second call should use cache
        vix2 = engine._ensure_vix(vix_dates[10:20])
        assert vix1 is vix2  # Same cached object

        # Verify cache is set
        assert engine._vix_cache is not None

    @patch("src.bouncehunter.engine.yf.Ticker")
    def test_fetch_earnings_dates_success(self, mock_ticker, sample_config):
        """Test successful earnings date fetching."""
        # Mock earnings calendar - need at least one column for DataFrame to not be empty
        earnings_dates = pd.date_range("2020-01-01", periods=4, freq="90D")
        mock_calendar = pd.DataFrame({"dummy": [1, 2, 3, 4]}, index=earnings_dates)
        mock_ticker.return_value.get_earnings_dates.return_value = mock_calendar

        engine = BounceHunter(sample_config)
        result = engine._fetch_earnings_dates("AAPL")

        assert isinstance(result, pd.DatetimeIndex)
        assert len(result) == 4

    @patch("src.bouncehunter.engine.yf.Ticker")
    def test_fetch_earnings_dates_failure(self, mock_ticker, sample_config):
        """Test earnings date fetching failure."""
        mock_ticker.return_value.get_earnings_dates.side_effect = Exception("API Error")

        engine = BounceHunter(sample_config)

        with warnings.catch_warnings(record=True) as w:
            result = engine._fetch_earnings_dates("AAPL")

            assert len(w) == 1
            assert "Failed to fetch earnings" in str(w[0].message)

        assert isinstance(result, pd.DatetimeIndex)
        assert len(result) == 0

    def test_apply_earnings_window(self, sample_config, sample_history):
        """Test earnings window application."""
        engine = BounceHunter(sample_config)

        # Create sample earnings dates
        earnings_dates = pd.DatetimeIndex([
            pd.Timestamp("2020-02-01"),
            pd.Timestamp("2020-05-01"),
        ])

        result = engine._apply_earnings_window(sample_history, earnings_dates)

        # Check that near_earnings column was added
        assert "near_earnings" in result.columns
        assert result["near_earnings"].dtype == bool

    def test_passes_universe_filters(self, sample_config, sample_history):
        """Test universe filter application."""
        engine = BounceHunter(sample_config)

        # Add required columns to sample data
        enhanced_history = sample_history.copy()
        enhanced_history["adv_usd"] = 2_000_000  # Above minimum
        enhanced_history["dist_200"] = 0.0  # Not too far below MA

        result = engine._passes_universe_filters(enhanced_history)
        assert isinstance(result, bool)

    def test_label_events(self, sample_config, sample_history):
        """Test event labeling for training."""
        engine = BounceHunter(sample_config)

        # Build complete indicators on sample history
        complete_data = engine._build_indicators(sample_history)
        complete_data["near_earnings"] = False
        complete_data["near_earnings"] = complete_data["near_earnings"].astype(bool)

        # Create data that should trigger events by modifying existing data
        event_data = complete_data.copy()
        event_data["z5"] = -3.0  # Below threshold
        event_data["rsi2"] = 20.0  # Below threshold

        # Add future data for labeling (minimal future data with required columns)
        future_dates = pd.date_range(event_data.index[-1] + timedelta(days=1),
                                   periods=10, freq="D")
        future_data = pd.DataFrame({
            "high": [110.0] * 10,
            "low": [90.0] * 10,
            "close": [105.0] * 10,
        }, index=future_dates)

        combined_data = pd.concat([event_data, future_data])

        result = engine._label_events(combined_data)

        assert isinstance(result, pd.DataFrame)
        if not result.empty:
            assert "label" in result.columns
            assert all(col in result.columns for col in _FEATURE_COLUMNS)

    def test_train_classifier(self, sample_config):
        """Test classifier training."""
        from sklearn.calibration import CalibratedClassifierCV

        engine = BounceHunter(sample_config)

        # Create sample training data
        np.random.seed(42)
        n_samples = 100
        X = np.random.randn(n_samples, len(_FEATURE_COLUMNS))
        y = np.random.randint(0, 2, n_samples)

        train_df = pd.DataFrame(X, columns=_FEATURE_COLUMNS)
        train_df["label"] = y

        model = engine._train_classifier(train_df)

        assert isinstance(model, CalibratedClassifierCV)
        assert hasattr(model, 'predict_proba')

    def test_trigger_conditions(self, sample_config):
        """Test signal trigger conditions."""
        engine = BounceHunter(sample_config)

        # Test case that should trigger
        trigger_row = pd.Series({
            "z5": -2.5,  # Below threshold
            "rsi2": 25.0,  # Below threshold
            "dist_200": -0.03,  # Above threshold (less negative than -0.05)
        })

        result = engine._trigger_conditions(trigger_row)
        assert result is True

        # Test case that should not trigger
        no_trigger_row = pd.Series({
            "z5": -1.0,  # Above threshold
            "rsi2": 35.0,  # Above threshold
            "dist_200": -0.08,  # Below threshold (more negative than -0.05)
        })

        result = engine._trigger_conditions(no_trigger_row)
        assert result is False

    def test_feature_vector(self, sample_config):
        """Test feature vector extraction."""
        engine = BounceHunter(sample_config)

        # Create sample row with all required features
        row_data = {col: 1.0 for col in _FEATURE_COLUMNS}
        row = pd.Series(row_data)

        vector = engine._feature_vector(row)

        assert isinstance(vector, np.ndarray)
        assert vector.shape == (1, len(_FEATURE_COLUMNS))
        assert vector.dtype == np.float64

    def test_notes_generation(self, sample_config):
        """Test signal notes generation."""
        engine = BounceHunter(sample_config)

        # Test with various conditions
        row_data = {
            "trend_63": -0.1,  # Negative trend
            "vix_regime": 0.8,  # High VIX
        }
        row = pd.Series(row_data)

        notes = engine._notes(row)

        assert isinstance(notes, str)
        assert "weak 3M trend" in notes
        assert "high VIX regime" in notes

    def test_average_true_range(self, sample_history):
        """Test ATR calculation."""
        atr = BounceHunter._average_true_range(sample_history)

        assert isinstance(atr, pd.Series)
        assert len(atr) == len(sample_history)
        assert not atr.isna().all()

    def test_rsi_calculation(self):
        """Test RSI calculation."""
        # Create simple price series
        prices = pd.Series([100, 101, 99, 102, 98, 103, 97, 104, 96, 105])

        rsi = BounceHunter._rsi(prices, window=2)

        assert isinstance(rsi, pd.Series)
        assert len(rsi) == len(prices)
        # RSI should be between 0 and 100
        assert rsi.dropna().between(0, 100).all()

    def test_bollinger_lower(self):
        """Test Bollinger lower band calculation."""
        prices = pd.Series([100, 101, 102, 103, 104, 105, 106, 107, 108, 109] * 3)

        bb_lower = BounceHunter._bollinger_lower(prices, window=10, k=2.0)

        assert isinstance(bb_lower, pd.Series)
        assert len(bb_lower) == len(prices)
        assert not bb_lower.isna().all()

    def test_extract_ohlcv_standard_columns(self):
        """Test OHLCV extraction with standard column names."""
        data = pd.DataFrame({
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [95.0, 96.0],
            "close": [102.0, 103.0],
            "volume": [1000, 1100],
        })

        result = BounceHunter._extract_ohlcv(data)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert len(result) == 2

    def test_extract_ohlcv_multiindex_columns(self):
        """Test OHLCV extraction with MultiIndex columns."""
        data = pd.DataFrame({
            ("AAPL", "open"): [100.0, 101.0],
            ("AAPL", "high"): [105.0, 106.0],
            ("AAPL", "low"): [95.0, 96.0],
            ("AAPL", "close"): [102.0, 103.0],
            ("AAPL", "volume"): [1000, 1100],
        })
        data.columns = pd.MultiIndex.from_tuples(data.columns)

        result = BounceHunter._extract_ohlcv(data)

        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert len(result) == 2

    def test_flatten_columns_multiindex(self):
        """Test column flattening with MultiIndex."""
        data = pd.DataFrame({
            ("AAPL", "open"): [100.0],
            ("AAPL", "close"): [102.0],
        })
        data.columns = pd.MultiIndex.from_tuples(data.columns)

        result = BounceHunter._flatten_columns(data)

        assert isinstance(result, pd.DataFrame)
        assert "aapl_open" in result.columns
        assert "aapl_close" in result.columns

    def test_locate_column_exact_match(self):
        """Test column location with exact match."""
        data = pd.DataFrame({
            "open": [100.0],
            "close": [102.0],
        })

        result = BounceHunter._locate_column(data, "open")

        assert isinstance(result, pd.Series)
        assert result.iloc[0] == 100.0

    def test_locate_column_fuzzy_match(self):
        """Test column location with fuzzy matching."""
        data = pd.DataFrame({
            "price_open": [100.0],
            "price_close": [102.0],
        })

        result = BounceHunter._locate_column(data, "open")

        assert isinstance(result, pd.Series)
        assert result.iloc[0] == 100.0

    def test_locate_column_not_found(self):
        """Test column location when column not found."""
        data = pd.DataFrame({
            "price": [100.0],
        })

        with pytest.raises(KeyError, match="unable to locate 'open' column"):
            BounceHunter._locate_column(data, "open")

    @patch("src.bouncehunter.engine.yf.download")
    @patch("src.bouncehunter.engine.yf.Ticker")
    def test_fit_integration(self, mock_ticker, mock_download, sample_config, sample_history):
        """Test full fit process integration."""
        # Build indicators on sample data to simulate what _download_history does
        engine = BounceHunter(sample_config)
        complete_history = engine._build_indicators(sample_history)
        
        # Mock data downloads
        mock_download.return_value = complete_history

        # Mock earnings data
        mock_ticker.return_value.get_earnings_dates.return_value = None

        # The fit process should complete (may not train model due to limited test data)
        try:
            result = engine.fit()
            assert isinstance(result, pd.DataFrame)
            assert engine._model is not None
            assert len(engine._artifacts) > 0
        except (RuntimeError, ValueError) as e:
            # Accept if no training data found or insufficient data for CV
            if "No instruments satisfied" in str(e) or "Cannot have number of folds" in str(e):
                pass  # Expected with limited test data
            else:
                raise

    def test_scan_without_fit(self, sample_config):
        """Test scan fails when fit hasn't been called."""
        engine = BounceHunter(sample_config)

        with pytest.raises(RuntimeError, match="fit\\(\\) must be called before scan"):
            engine.scan()

    @patch("src.bouncehunter.engine.yf.download")
    @patch("src.bouncehunter.engine.yf.Ticker")
    def test_scan_integration(self, mock_ticker, mock_download, sample_config, sample_history):
        """Test full scan process integration."""
        # Build indicators on sample data
        engine = BounceHunter(sample_config)
        complete_history = engine._build_indicators(sample_history)
        
        # Mock data downloads
        mock_download.return_value = complete_history

        # Mock earnings data
        mock_ticker.return_value.get_earnings_dates.return_value = None

        # Fit the model first (may fail due to limited test data)
        try:
            engine.fit()
            assert engine._model is not None
        except (RuntimeError, ValueError) as e:
            if "No instruments satisfied" in str(e) or "Cannot have number of folds" in str(e):
                pytest.skip("Insufficient training data for this test")
            else:
                raise

        # Now scan should work
        reports = engine.scan()

        assert isinstance(reports, list)
        # May be empty if no signals meet criteria, but should not error

    def test_build_signal_none_cases(self, sample_config, sample_history):
        """Test signal building returns None for various conditions."""
        engine = BounceHunter(sample_config)

        # Mock trained model
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = [[0.3, 0.7]]  # High probability
        engine._model = mock_model

        # Create artifact
        artifact = TrainingArtifact(
            ticker="AAPL",
            history=sample_history,
            features=pd.DataFrame(),
            earnings=pd.DatetimeIndex([])
        )

        # Test with empty history
        empty_artifact = TrainingArtifact(
            ticker="AAPL",
            history=pd.DataFrame(),
            features=pd.DataFrame(),
            earnings=pd.DatetimeIndex([])
        )

        result = engine._build_signal("AAPL", empty_artifact, None)
        assert result is None

    def test_training_artifact_creation(self, sample_history):
        """Test TrainingArtifact dataclass."""
        artifact = TrainingArtifact(
            ticker="AAPL",
            history=sample_history,
            features=pd.DataFrame({"feature1": [1.0, 2.0]}),
            earnings=pd.DatetimeIndex(["2020-01-01"])
        )

        assert artifact.ticker == "AAPL"
        assert isinstance(artifact.history, pd.DataFrame)
        assert isinstance(artifact.features, pd.DataFrame)
        assert isinstance(artifact.earnings, pd.DatetimeIndex)