"""Comprehensive tests for BounceHunter backtesting functionality."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from src.bouncehunter.backtest import (
    BacktestMetrics,
    BacktestResult,
    BounceHunterBacktester,
    TradeRecord,
)
from src.bouncehunter.config import BounceHunterConfig
from src.bouncehunter.engine import BounceHunter, TrainingArtifact


class TestTradeRecord:
    """Tests for TradeRecord data class."""

    def test_trade_record_creation(self):
        """Test basic TradeRecord creation and attributes."""
        trade = TradeRecord(
            ticker="AAPL",
            entry_date=pd.Timestamp("2023-01-01"),
            exit_date=pd.Timestamp("2023-01-05"),
            entry_price=150.0,
            exit_price=157.5,
            return_pct=0.05,
            hold_days=4,
            hit_target=True,
            hit_stop=False,
            probability=0.75,
            z_score=-2.1,
            rsi2=8.5,
        )

        assert trade.ticker == "AAPL"
        assert trade.entry_date == pd.Timestamp("2023-01-01")
        assert trade.exit_date == pd.Timestamp("2023-01-05")
        assert trade.entry_price == 150.0
        assert trade.exit_price == 157.5
        assert trade.return_pct == 0.05
        assert trade.hold_days == 4
        assert trade.hit_target is True
        assert trade.hit_stop is False
        assert trade.probability == 0.75
        assert trade.z_score == -2.1
        assert trade.rsi2 == 8.5

    def test_trade_record_as_dict(self):
        """Test TradeRecord serialization to dictionary."""
        trade = TradeRecord(
            ticker="MSFT",
            entry_date=pd.Timestamp("2023-02-01"),
            exit_date=pd.Timestamp("2023-02-03"),
            entry_price=250.0,
            exit_price=245.0,
            return_pct=-0.02,
            hold_days=2,
            hit_target=False,
            hit_stop=True,
            probability=0.65,
            z_score=-1.8,
            rsi2=12.3,
        )

        result = trade.as_dict()

        expected = {
            "ticker": "MSFT",
            "entry_date": "2023-02-01",
            "exit_date": "2023-02-03",
            "entry_price": 250.0,
            "exit_price": 245.0,
            "return_pct": -0.02,
            "hold_days": 2,
            "hit_target": False,
            "hit_stop": True,
            "probability": 0.65,
            "z_score": -1.8,
            "rsi2": 12.3,
        }

        assert result == expected


class TestBacktestMetrics:
    """Tests for BacktestMetrics data class."""

    def test_backtest_metrics_creation(self):
        """Test basic BacktestMetrics creation."""
        metrics = BacktestMetrics(
            total_trades=10,
            win_rate=0.6,
            avg_return=0.025,
            expectancy=0.015,
            cumulative_return=0.285,
            max_drawdown=0.08,
            profit_factor=1.5,
            average_hold=3.2,
        )

        assert metrics.total_trades == 10
        assert metrics.win_rate == 0.6
        assert metrics.avg_return == 0.025
        assert metrics.expectancy == 0.015
        assert metrics.cumulative_return == 0.285
        assert metrics.max_drawdown == 0.08
        assert metrics.profit_factor == 1.5
        assert metrics.average_hold == 3.2

    def test_backtest_metrics_as_dict(self):
        """Test BacktestMetrics serialization."""
        metrics = BacktestMetrics(
            total_trades=5,
            win_rate=0.4,
            avg_return=-0.01,
            expectancy=-0.005,
            cumulative_return=-0.048,
            max_drawdown=0.12,
            profit_factor=0.7,
            average_hold=2.8,
        )

        result = metrics.as_dict()

        expected = {
            "total_trades": 5,
            "win_rate": 0.4,
            "avg_return": -0.01,
            "expectancy": -0.005,
            "cumulative_return": -0.048,
            "max_drawdown": 0.12,
            "profit_factor": 0.7,
            "average_hold": 2.8,
        }

        assert result == expected


class TestBacktestResult:
    """Tests for BacktestResult data class."""

    def test_backtest_result_creation(self):
        """Test BacktestResult creation with trades."""
        trades = [
            TradeRecord(
                ticker="AAPL",
                entry_date=pd.Timestamp("2023-01-01"),
                exit_date=pd.Timestamp("2023-01-03"),
                entry_price=150.0,
                exit_price=157.5,
                return_pct=0.05,
                hold_days=2,
                hit_target=True,
                hit_stop=False,
                probability=0.8,
                z_score=-2.0,
                rsi2=8.0,
            )
        ]

        metrics = BacktestMetrics(
            total_trades=1,
            win_rate=1.0,
            avg_return=0.05,
            expectancy=0.05,
            cumulative_return=0.05,
            max_drawdown=0.0,
            profit_factor=float("inf"),
            average_hold=2.0,
        )

        result = BacktestResult(trades=trades, metrics=metrics)

        assert len(result.trades) == 1
        assert result.metrics.total_trades == 1

    def test_backtest_result_trades_frame(self):
        """Test conversion of trades to DataFrame."""
        trades = [
            TradeRecord(
                ticker="AAPL",
                entry_date=pd.Timestamp("2023-01-01"),
                exit_date=pd.Timestamp("2023-01-03"),
                entry_price=150.0,
                exit_price=157.5,
                return_pct=0.05,
                hold_days=2,
                hit_target=True,
                hit_stop=False,
                probability=0.8,
                z_score=-2.0,
                rsi2=8.0,
            ),
            TradeRecord(
                ticker="MSFT",
                entry_date=pd.Timestamp("2023-01-02"),
                exit_date=pd.Timestamp("2023-01-04"),
                entry_price=250.0,
                exit_price=245.0,
                return_pct=-0.02,
                hold_days=2,
                hit_target=False,
                hit_stop=True,
                probability=0.6,
                z_score=-1.5,
                rsi2=12.0,
            ),
        ]

        result = BacktestResult(trades=trades, metrics=MagicMock())

        df = result.trades_frame()

        assert len(df) == 2
        assert list(df.columns) == [
            "ticker", "entry_date", "exit_date", "entry_price", "exit_price",
            "return_pct", "hold_days", "hit_target", "hit_stop", "probability",
            "z_score", "rsi2"
        ]
        assert df.iloc[0]["ticker"] == "AAPL"
        assert df.iloc[1]["ticker"] == "MSFT"

    def test_backtest_result_empty_trades_frame(self):
        """Test trades_frame with empty trades list."""
        result = BacktestResult(trades=[], metrics=MagicMock())

        df = result.trades_frame()

        assert len(df) == 0
        assert isinstance(df, pd.DataFrame)

    def test_backtest_result_summary_frame(self):
        """Test conversion of metrics to summary DataFrame."""
        metrics = BacktestMetrics(
            total_trades=10,
            win_rate=0.6,
            avg_return=0.025,
            expectancy=0.015,
            cumulative_return=0.285,
            max_drawdown=0.08,
            profit_factor=1.5,
            average_hold=3.2,
        )

        result = BacktestResult(trades=[], metrics=metrics)

        df = result.summary_frame()

        assert len(df) == 1
        assert df.iloc[0]["total_trades"] == 10
        assert df.iloc[0]["win_rate"] == 0.6


class TestBounceHunterBacktester:
    """Tests for BounceHunterBacktester class."""

    @pytest.fixture
    def sample_config(self):
        """Sample BounceHunterConfig for testing."""
        return BounceHunterConfig(
            tickers=["AAPL", "MSFT"],
            start="2020-01-01",
            z_score_drop=-1.5,
            rsi2_max=10.0,
            bcs_threshold=0.6,
            rebound_pct=0.03,
            stop_pct=0.03,
            horizon_days=5,
            min_event_samples=5,  # Lower for testing
        )

    @pytest.fixture
    def mock_engine(self):
        """Mock BounceHunter engine."""
        engine = MagicMock(spec=BounceHunter)

        # Mock artifacts
        artifact = MagicMock(spec=TrainingArtifact)
        artifact.history = pd.DataFrame({
            "close": [100.0, 98.0, 102.0, 101.0, 103.0],
            "high": [101.0, 99.0, 103.0, 102.0, 104.0],
            "low": [99.0, 97.0, 101.0, 100.0, 102.0],
            "z5": [-2.0, -1.8, -1.5, -1.2, -1.0],
            "rsi2": [8.0, 9.0, 10.0, 11.0, 12.0],
            "near_earnings": [False, False, False, False, False],
        }, index=pd.date_range("2023-01-01", periods=5))

        artifact.features = pd.DataFrame({
            "feature1": [1.0, 2.0, 3.0],
            "feature2": [0.5, 1.5, 2.5],
        }, index=pd.date_range("2023-01-01", periods=3))

        engine._artifacts = {"AAPL": artifact}
        return engine

    def test_backtester_initialization(self, sample_config):
        """Test BounceHunterBacktester initialization."""
        backtester = BounceHunterBacktester(
            config=sample_config,
            start_date="2023-01-01",
            end_date="2023-12-31",
            max_training_events=100,
        )

        assert backtester.config == sample_config
        assert backtester.start_date == pd.Timestamp("2023-01-01")
        assert backtester.end_date == pd.Timestamp("2023-12-31")
        assert backtester.max_training_events == 100

    def test_backtester_default_initialization(self):
        """Test BounceHunterBacktester with default parameters."""
        backtester = BounceHunterBacktester()

        assert isinstance(backtester.config, BounceHunterConfig)
        assert backtester.start_date is None
        assert backtester.end_date is None
        assert backtester.max_training_events == 0

    @patch("src.bouncehunter.backtest.BounceHunter")
    def test_backtester_run_method(self, mock_bh_class, sample_config, mock_engine):
        """Test the main run method."""
        mock_bh_class.return_value = mock_engine

        backtester = BounceHunterBacktester(config=sample_config)

        # Mock the _backtest_ticker method to return some trades
        mock_trade = TradeRecord(
            ticker="AAPL",
            entry_date=pd.Timestamp("2023-01-01"),
            exit_date=pd.Timestamp("2023-01-03"),
            entry_price=100.0,
            exit_price=103.0,
            return_pct=0.03,
            hold_days=2,
            hit_target=True,
            hit_stop=False,
            probability=0.7,
            z_score=-2.0,
            rsi2=8.0,
        )

        with patch.object(backtester, "_backtest_ticker", return_value=[mock_trade]):
            with patch.object(backtester, "_compute_metrics") as mock_compute:
                mock_metrics = BacktestMetrics(
                    total_trades=1,
                    win_rate=1.0,
                    avg_return=0.03,
                    expectancy=0.03,
                    cumulative_return=0.03,
                    max_drawdown=0.0,
                    profit_factor=float("inf"),
                    average_hold=2.0,
                )
                mock_compute.return_value = mock_metrics

                result = backtester.run()

                assert len(result.trades) == 1
                assert result.metrics.total_trades == 1
                mock_bh_class.assert_called_once_with(sample_config)
                mock_engine.fit.assert_called_once()

    def test_eligible_dates_with_date_range(self, sample_config):
        """Test _eligible_dates with date range filtering."""
        backtester = BounceHunterBacktester(
            config=sample_config,
            start_date="2023-01-02",
            end_date="2023-01-04",
        )

        index = pd.date_range("2023-01-01", periods=5)
        result = backtester._eligible_dates(index)

        expected_dates = [
            pd.Timestamp("2023-01-02"),
            pd.Timestamp("2023-01-03"),
            pd.Timestamp("2023-01-04"),
        ]

        assert result == expected_dates

    def test_eligible_dates_no_filtering(self, sample_config):
        """Test _eligible_dates with no date filtering."""
        backtester = BounceHunterBacktester(config=sample_config)

        index = pd.date_range("2023-01-01", periods=3)
        result = backtester._eligible_dates(index)

        assert result == list(index)

    @patch("src.bouncehunter.backtest.BounceHunter")
    def test_simulate_trade_hit_target(self, mock_bh_class, sample_config):
        """Test trade simulation that hits target price."""
        backtester = BounceHunterBacktester(config=sample_config)

        # Create test data where price hits target on day 2
        entry_date = pd.Timestamp("2023-01-01")
        history = pd.DataFrame({
            "close": [100.0, 101.0, 103.5, 104.0, 105.0],  # Target is 103.0
            "high": [101.0, 102.0, 104.0, 105.0, 106.0],    # Hits 104.0 > 103.0 on day 2
            "low": [99.0, 100.0, 102.0, 103.0, 104.0],
        }, index=pd.date_range("2023-01-01", periods=5))

        today = pd.Series({
            "close": 100.0,
            "z5": -2.0,
            "rsi2": 8.0,
        })

        trade = backtester._simulate_trade("AAPL", entry_date, today, history)

        assert trade is not None
        assert trade.ticker == "AAPL"
        assert trade.entry_date == entry_date
        assert trade.exit_date == pd.Timestamp("2023-01-03")  # Day 2 from entry
        assert trade.entry_price == 100.0
        assert trade.exit_price == 103.0  # Target price
        assert trade.return_pct == pytest.approx(0.03, abs=1e-10)
        assert trade.hit_target is True
        assert trade.hit_stop is False

    @patch("src.bouncehunter.backtest.BounceHunter")
    def test_simulate_trade_hit_stop(self, mock_bh_class, sample_config):
        """Test trade simulation that hits stop price."""
        backtester = BounceHunterBacktester(config=sample_config)

        # Create test data where price hits stop on day 3
        entry_date = pd.Timestamp("2023-01-01")
        history = pd.DataFrame({
            "close": [100.0, 99.5, 98.0, 97.0, 96.0],     # Stop is 97.0
            "high": [101.0, 100.0, 99.0, 98.0, 97.0],
            "low": [99.0, 98.5, 96.5, 96.0, 95.0],        # Hits 96.5 < 97.0 on day 2
        }, index=pd.date_range("2023-01-01", periods=5))

        today = pd.Series({
            "close": 100.0,
            "z5": -2.0,
            "rsi2": 8.0,
        })

        trade = backtester._simulate_trade("AAPL", entry_date, today, history)

        assert trade is not None
        assert trade.hit_target is False
        assert trade.hit_stop is True
        assert trade.exit_price == 97.0  # Stop price
        assert trade.return_pct == pytest.approx(-0.03, abs=1e-10)

    @patch("src.bouncehunter.backtest.BounceHunter")
    def test_simulate_trade_no_exit_within_horizon(self, mock_bh_class, sample_config):
        """Test trade simulation that doesn't hit target or stop within horizon."""
        backtester = BounceHunterBacktester(config=sample_config)

        # Create test data where price stays within range
        entry_date = pd.Timestamp("2023-01-01")
        history = pd.DataFrame({
            "close": [100.0, 100.5, 101.0, 100.8, 101.2],  # Stays within range
            "high": [101.0, 101.5, 102.0, 101.8, 102.2],    # Never hits target (103.0)
            "low": [99.0, 99.5, 99.0, 99.8, 100.2],         # Never hits stop (97.0)
        }, index=pd.date_range("2023-01-01", periods=5))

        today = pd.Series({
            "close": 100.0,
            "z5": -2.0,
            "rsi2": 8.0,
        })

        trade = backtester._simulate_trade("AAPL", entry_date, today, history)

        assert trade is not None
        assert trade.hit_target is False
        assert trade.hit_stop is False
        assert trade.exit_date == pd.Timestamp("2023-01-05")  # Last day of horizon
        assert trade.exit_price == 101.2  # Last close price

    @patch("src.bouncehunter.backtest.BounceHunter")
    def test_simulate_trade_insufficient_history(self, mock_bh_class, sample_config):
        """Test trade simulation with insufficient future history."""
        backtester = BounceHunterBacktester(config=sample_config)

        entry_date = pd.Timestamp("2023-01-01")
        history = pd.DataFrame({
            "close": [100.0],  # Only current day
            "high": [101.0],
            "low": [99.0],
        }, index=pd.date_range("2023-01-01", periods=1))

        today = pd.Series({
            "close": 100.0,
            "z5": -2.0,
            "rsi2": 8.0,
        })

        trade = backtester._simulate_trade("AAPL", entry_date, today, history)

        assert trade is None  # No future data to simulate

    def test_first_cross_greater_true(self):
        """Test _first_cross with greater=True (looking for highs above threshold)."""
        series = pd.Series([100.0, 101.0, 99.0, 102.0, 103.0])
        threshold = 101.5

        result = BounceHunterBacktester._first_cross(series, threshold, greater=True)

        assert result == 3  # Index of first value >= 101.5

    def test_first_cross_greater_false(self):
        """Test _first_cross with greater=False (looking for lows below threshold)."""
        series = pd.Series([100.0, 99.0, 101.0, 98.0, 97.0])
        threshold = 98.5

        result = BounceHunterBacktester._first_cross(series, threshold, greater=False)

        assert result == 3  # Index of first value <= 98.5

    def test_first_cross_no_match(self):
        """Test _first_cross when threshold is never crossed."""
        series = pd.Series([100.0, 101.0, 102.0])
        threshold = 103.0

        result = BounceHunterBacktester._first_cross(series, threshold, greater=True)

        assert result is None

    def test_resolve_exit_target_first(self):
        """Test _resolve_exit when target is hit before stop."""
        result = BounceHunterBacktester._resolve_exit(
            MagicMock(), 100.0, 103.0, 97.0,
            pd.Timestamp("2023-01-02"), pd.Timestamp("2023-01-04")
        )

        assert result == (pd.Timestamp("2023-01-02"), 103.0, True, False)

    def test_resolve_exit_stop_first(self):
        """Test _resolve_exit when stop is hit before target."""
        result = BounceHunterBacktester._resolve_exit(
            MagicMock(), 100.0, 103.0, 97.0,
            pd.Timestamp("2023-01-04"), pd.Timestamp("2023-01-02")
        )

        assert result == (pd.Timestamp("2023-01-02"), 97.0, False, True)

    def test_resolve_exit_same_day(self):
        """Test _resolve_exit when both target and stop hit on same day."""
        result = BounceHunterBacktester._resolve_exit(
            MagicMock(), 100.0, 103.0, 97.0,
            pd.Timestamp("2023-01-02"), pd.Timestamp("2023-01-02")
        )

        assert result == (pd.Timestamp("2023-01-02"), 103.0, True, False)

    def test_resolve_exit_no_exit(self):
        """Test _resolve_exit when neither target nor stop is hit."""
        result = BounceHunterBacktester._resolve_exit(
            MagicMock(), 100.0, 103.0, 97.0, None, None
        )

        assert result == (None, None, False, False)

    def test_compute_metrics_with_trades(self):
        """Test metrics computation with sample trades."""
        trades = [
            TradeRecord(
                ticker="AAPL",
                entry_date=pd.Timestamp("2023-01-01"),
                exit_date=pd.Timestamp("2023-01-03"),
                entry_price=100.0,
                exit_price=103.0,
                return_pct=0.03,
                hold_days=2,
                hit_target=True,
                hit_stop=False,
                probability=0.7,
                z_score=-2.0,
                rsi2=8.0,
            ),
            TradeRecord(
                ticker="MSFT",
                entry_date=pd.Timestamp("2023-01-02"),
                exit_date=pd.Timestamp("2023-01-04"),
                entry_price=200.0,
                exit_price=194.0,
                return_pct=-0.03,
                hold_days=2,
                hit_target=False,
                hit_stop=True,
                probability=0.6,
                z_score=-1.8,
                rsi2=9.0,
            ),
        ]

        backtester = BounceHunterBacktester()
        metrics = backtester._compute_metrics(trades)

        assert metrics.total_trades == 2
        assert metrics.win_rate == 0.5
        assert metrics.avg_return == 0.0  # (0.03 + (-0.03)) / 2
        assert metrics.cumulative_return == pytest.approx(-0.0009, abs=1e-4)  # (1.03 * 0.97) - 1 ≈ -0.0009
        assert metrics.max_drawdown >= 0.0
        assert metrics.average_hold == 2.0

    def test_compute_metrics_empty_trades(self):
        """Test metrics computation with no trades."""
        backtester = BounceHunterBacktester()
        metrics = backtester._compute_metrics([])

        assert metrics.total_trades == 0
        assert metrics.win_rate == 0.0
        assert metrics.avg_return == 0.0
        assert metrics.expectancy == 0.0
        assert metrics.cumulative_return == 0.0
        assert metrics.max_drawdown == 0.0
        assert metrics.profit_factor == 0.0
        assert metrics.average_hold == 0.0

    def test_compute_metrics_all_wins(self):
        """Test metrics computation with all winning trades."""
        trades = [
            TradeRecord(
                ticker="AAPL",
                entry_date=pd.Timestamp("2023-01-01"),
                exit_date=pd.Timestamp("2023-01-03"),
                entry_price=100.0,
                exit_price=103.0,
                return_pct=0.03,
                hold_days=2,
                hit_target=True,
                hit_stop=False,
                probability=0.7,
                z_score=-2.0,
                rsi2=8.0,
            ),
            TradeRecord(
                ticker="MSFT",
                entry_date=pd.Timestamp("2023-01-02"),
                exit_date=pd.Timestamp("2023-01-04"),
                entry_price=200.0,
                exit_price=206.0,
                return_pct=0.03,
                hold_days=2,
                hit_target=True,
                hit_stop=False,
                probability=0.8,
                z_score=-2.1,
                rsi2=7.5,
            ),
        ]

        backtester = BounceHunterBacktester()
        metrics = backtester._compute_metrics(trades)

        assert metrics.total_trades == 2
        assert metrics.win_rate == 1.0
        assert metrics.avg_return == 0.03
        assert metrics.cumulative_return == pytest.approx(0.0609, abs=1e-4)
        assert metrics.profit_factor == float("inf")
        assert metrics.max_drawdown == 0.0

    def test_compute_metrics_all_losses(self):
        """Test metrics computation with all losing trades."""
        trades = [
            TradeRecord(
                ticker="AAPL",
                entry_date=pd.Timestamp("2023-01-01"),
                exit_date=pd.Timestamp("2023-01-03"),
                entry_price=100.0,
                exit_price=97.0,
                return_pct=-0.03,
                hold_days=2,
                hit_target=False,
                hit_stop=True,
                probability=0.6,
                z_score=-1.8,
                rsi2=9.0,
            ),
        ]

        backtester = BounceHunterBacktester()
        metrics = backtester._compute_metrics(trades)

        assert metrics.total_trades == 1
        assert metrics.win_rate == 0.0
        assert metrics.avg_return == pytest.approx(-0.03, abs=1e-10)
        assert metrics.cumulative_return == pytest.approx(-0.03, abs=1e-10)
        assert metrics.profit_factor == 0.0
        assert metrics.max_drawdown >= 0.0