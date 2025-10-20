"""Tests for bouncehunter/agentic.py - Multi-agent orchestration system."""

import asyncio
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from src.bouncehunter.agentic import (
    Action,
    AgentMemory,
    Auditor,
    Context,
    Forecaster,
    Historian,
    NewsSentry,
    Orchestrator,
    Policy,
    RiskOfficer,
    Screener,
    Sentinel,
    Signal,
    Trader,
)


class TestDataClasses:
    """Test data class initialization and properties."""

    def test_policy_initialization(self):
        """Test Policy dataclass initialization."""
        config = MagicMock()
        policy = Policy(
            config=config,
            live_trading=True,
            min_bcs=0.65,
            min_bcs_highvix=0.70,
            max_concurrent=10,
            max_per_sector=4,
            allow_earnings=True,
            risk_pct_normal=0.015,
            risk_pct_highvix=0.008,
            preclose_only=True,
            news_veto_enabled=True,
            auto_adapt_thresholds=False,
            base_rate_floor=0.45,
            min_sample_size=25,
        )

        assert policy.config == config
        assert policy.live_trading is True
        assert policy.min_bcs == 0.65
        assert policy.min_bcs_highvix == 0.70
        assert policy.max_concurrent == 10
        assert policy.max_per_sector == 4
        assert policy.allow_earnings is True
        assert policy.risk_pct_normal == 0.015
        assert policy.risk_pct_highvix == 0.008
        assert policy.preclose_only is True
        assert policy.news_veto_enabled is True
        assert policy.auto_adapt_thresholds is False
        assert policy.base_rate_floor == 0.45
        assert policy.min_sample_size == 25

    def test_context_initialization(self):
        """Test Context dataclass initialization."""
        ctx = Context(
            dt="2025-10-19",
            regime="high_vix",
            vix_percentile=0.85,
            spy_dist_200dma=-0.12,
            is_market_hours=True,
            is_preclose=False,
        )

        assert ctx.dt == "2025-10-19"
        assert ctx.regime == "high_vix"
        assert ctx.vix_percentile == 0.85
        assert ctx.spy_dist_200dma == -0.12
        assert ctx.is_market_hours is True
        assert ctx.is_preclose is False

    def test_signal_initialization(self):
        """Test Signal dataclass initialization."""
        sig = Signal(
            ticker="AAPL",
            date="2025-10-19",
            close=150.25,
            z_score=-2.1,
            rsi2=25.5,
            dist_200dma=-0.08,
            probability=0.72,
            entry=148.50,
            stop=145.00,
            target=160.00,
            adv_usd=5000000,
            sector="Technology",
            notes="Strong bounce setup",
            vetoed=False,
            veto_reason="",
        )

        assert sig.ticker == "AAPL"
        assert sig.date == "2025-10-19"
        assert sig.close == 150.25
        assert sig.z_score == -2.1
        assert sig.rsi2 == 25.5
        assert sig.dist_200dma == -0.08
        assert sig.probability == 0.72
        assert sig.entry == 148.50
        assert sig.stop == 145.00
        assert sig.target == 160.00
        assert sig.adv_usd == 5000000
        assert sig.sector == "Technology"
        assert sig.notes == "Strong bounce setup"
        assert sig.vetoed is False
        assert sig.veto_reason == ""

    def test_action_initialization(self):
        """Test Action dataclass initialization."""
        action = Action(
            signal_id="AAPL_2025-10-19_1234567890",
            ticker="AAPL",
            action="BUY",
            size_pct=0.012,
            entry=148.50,
            stop=145.00,
            target=160.00,
            probability=0.72,
            regime="normal",
            reason="Approved by all agents",
        )

        assert action.signal_id == "AAPL_2025-10-19_1234567890"
        assert action.ticker == "AAPL"
        assert action.action == "BUY"
        assert action.size_pct == 0.012
        assert action.entry == 148.50
        assert action.stop == 145.00
        assert action.target == 160.00
        assert action.probability == 0.72
        assert action.regime == "normal"
        assert action.reason == "Approved by all agents"


class TestAgentMemory:
    """Test AgentMemory database operations."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing."""
        import gc
        import os
        
        # Use a more robust temp file approach
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)  # Close the file descriptor immediately
        
        yield db_path
        
        # Force garbage collection and wait before cleanup
        gc.collect()
        import time
        time.sleep(0.2)
        
        try:
            os.unlink(db_path)
        except PermissionError:
            # If still locked, try again after longer wait
            time.sleep(1.0)
            try:
                os.unlink(db_path)
            except PermissionError:
                # Last resort - just leave the file
                pass

    @pytest.fixture
    def memory(self, temp_db):
        """Create AgentMemory instance with temp database."""
        mem = AgentMemory(db_path=temp_db)
        yield mem
        mem.close()

    def test_init_creates_tables(self, temp_db):
        """Test that initialization creates all required tables."""
        memory = AgentMemory(db_path=temp_db)

        with sqlite3.connect(temp_db) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]

        expected_tables = [
            'signals', 'fills', 'outcomes', 'ticker_stats', 'system_state'
        ]
        for table in expected_tables:
            assert table in table_names

    def test_record_signal(self, memory):
        """Test recording a signal."""
        signal = Signal(
            ticker="AAPL",
            date="2025-10-19",
            close=150.25,
            z_score=-2.1,
            rsi2=25.5,
            dist_200dma=-0.08,
            probability=0.72,
            entry=148.50,
            stop=145.00,
            target=160.00,
            adv_usd=5000000,
            sector="Technology",
            notes="Strong bounce setup",
        )

        action = Action(
            signal_id="test_signal",
            ticker="AAPL",
            action="BUY",
            size_pct=0.012,
            entry=148.50,
            stop=145.00,
            target=160.00,
            probability=0.72,
            regime="normal",
        )

        signal_id = memory.record_signal(signal, action)

        # Verify signal was recorded
        with sqlite3.connect(memory.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM signals WHERE signal_id = ?", (signal_id,)
            ).fetchone()

        assert row is not None
        assert row[2] == "AAPL"  # ticker
        assert row[3] == "2025-10-19"  # date
        assert row[4] == 0.72  # probability
        assert row[5] == 148.50  # entry
        assert row[6] == 145.00  # stop
        assert row[7] == 160.00  # target
        assert row[8] == "normal"  # regime
        assert row[9] == 0.012  # size_pct

    def test_record_fill(self, memory):
        """Test recording a fill."""
        signal_id = "test_signal_123"
        fill_id = memory.record_fill(
            signal_id=signal_id,
            ticker="AAPL",
            entry_date="2025-10-19",
            entry_price=148.50,
            size_pct=0.012,
            regime="normal",
            shares=100.0,
            is_paper=True,
        )

        # Verify fill was recorded
        with sqlite3.connect(memory.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM fills WHERE fill_id = ?", (fill_id,)
            ).fetchone()

        assert row is not None
        assert row[1] == signal_id
        assert row[2] == "AAPL"
        assert row[3] == "2025-10-19"
        assert row[4] == 148.50
        assert row[5] == 100.0
        assert row[6] == 0.012
        assert row[7] == "normal"
        assert row[8] == 1  # is_paper

    def test_record_outcome(self, memory):
        """Test recording an outcome."""
        fill_id = "test_fill_123"
        outcome_id = memory.record_outcome(
            fill_id=fill_id,
            ticker="AAPL",
            exit_date="2025-10-22",
            exit_price=155.00,
            exit_reason="TARGET",
            entry_price=148.50,
            hold_days=3,
        )

        # Verify outcome was recorded
        with sqlite3.connect(memory.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM outcomes WHERE outcome_id = ?", (outcome_id,)
            ).fetchone()

        assert row is not None
        assert row[1] == fill_id
        assert row[2] == "AAPL"
        assert row[3] == "2025-10-22"
        assert row[4] == 155.00
        assert row[5] == "TARGET"
        assert row[6] == 3
        assert abs(row[7] - 0.0438) < 0.001  # return_pct ≈ 4.38%
        assert row[8] == 1  # hit_target
        assert row[9] == 0  # hit_stop
        assert row[10] == 0  # hit_time
        assert row[11] == 1.0 - 3 * 0.01  # reward = 1.0 - 0.03

    def test_get_ticker_stats_empty(self, memory):
        """Test getting stats for non-existent ticker."""
        stats = memory.get_ticker_stats("NONEXISTENT")
        assert stats is None

    def test_update_ticker_stats(self, memory):
        """Test updating ticker statistics."""
        # First create some test data
        signal_id = memory.record_signal(
            Signal(ticker="AAPL", date="2025-10-19", close=150.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.7, entry=148.0,
                   stop=145.0, target=158.0, adv_usd=5000000),
            Action(signal_id="test", ticker="AAPL", action="BUY", size_pct=0.01,
                   entry=148.0, stop=145.0, target=158.0, probability=0.7, regime="normal")
        )

        fill_id = memory.record_fill(signal_id, "AAPL", "2025-10-19", 148.0, 0.01, "normal")
        memory.record_outcome(fill_id, "AAPL", "2025-10-22", 155.0, "TARGET", 148.0, 3)

        # Update stats
        memory.update_ticker_stats("AAPL")

        # Verify stats
        stats = memory.get_ticker_stats("AAPL")
        assert stats is not None
        assert stats["ticker"] == "AAPL"
        assert stats["total_signals"] == 1
        assert stats["total_outcomes"] == 1
        assert stats["base_rate"] == 1.0  # 1 hit out of 1
        assert abs(stats["avg_reward"] - 0.97) < 0.01  # 1.0 - 0.03

    def test_system_state_operations(self, memory):
        """Test system state get/set operations."""
        # Test setting and getting
        memory.set_system_state("test_key", "test_value")
        value = memory.get_system_state("test_key")
        assert value == "test_value"

        # Test non-existent key
        value = memory.get_system_state("nonexistent")
        assert value is None

        # Test updating existing key
        memory.set_system_state("test_key", "updated_value")
        value = memory.get_system_state("test_key")
        assert value == "updated_value"


class TestSentinel:
    """Test Sentinel agent functionality."""

    @pytest.fixture
    def policy(self):
        """Create test policy."""
        config = MagicMock()
        config.vix_lookback_days = 30
        config.highvix_percentile = 0.8
        config.spy_stress_multiplier = 2.0
        config.bcs_threshold = 0.62
        config.bcs_threshold_highvix = 0.68
        config.size_pct_base = 0.012
        config.size_pct_highvix = 0.006
        return Policy(config=config)

    @pytest.fixture
    def sentinel(self, policy):
        """Create Sentinel instance."""
        return Sentinel(policy)

    @patch('src.bouncehunter.agentic.datetime')
    @patch('src.bouncehunter.regime.RegimeDetector')
    def test_run_normal_regime(self, mock_detector_class, mock_datetime, sentinel):
        """Test Sentinel run with normal regime."""
        # Mock datetime
        mock_datetime.now.return_value = datetime(2025, 10, 19, 10, 30)

        # Mock regime detector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector

        mock_regime_state = MagicMock()
        mock_regime_state.is_spy_stressed = False
        mock_regime_state.is_high_vix = False
        mock_regime_state.vix_percentile = 0.3
        mock_regime_state.spy_dist_200dma = 0.05
        mock_detector.detect.return_value = mock_regime_state

        # Run sentinel
        ctx = asyncio.run(sentinel.run())

        # Verify context
        assert ctx.dt == "2025-10-19"
        assert ctx.regime == "normal"
        assert ctx.vix_percentile == 0.3
        assert ctx.spy_dist_200dma == 0.05
        assert ctx.is_market_hours is True
        assert ctx.is_preclose is False

    @patch('src.bouncehunter.agentic.datetime')
    @patch('src.bouncehunter.regime.RegimeDetector')
    def test_run_high_vix_regime(self, mock_detector_class, mock_datetime, sentinel):
        """Test Sentinel run with high volatility regime."""
        # Mock datetime
        mock_datetime.now.return_value = datetime(2025, 10, 19, 15, 45)  # Pre-close

        # Mock regime detector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector

        mock_regime_state = MagicMock()
        mock_regime_state.is_spy_stressed = False
        mock_regime_state.is_high_vix = True
        mock_regime_state.vix_percentile = 0.85
        mock_regime_state.spy_dist_200dma = -0.12
        mock_detector.detect.return_value = mock_regime_state

        # Run sentinel
        ctx = asyncio.run(sentinel.run())

        # Verify context
        assert ctx.dt == "2025-10-19"
        assert ctx.regime == "high_vix"
        assert ctx.vix_percentile == 0.85
        assert ctx.spy_dist_200dma == -0.12
        assert ctx.is_market_hours is True
        assert ctx.is_preclose is True

    @patch('src.bouncehunter.agentic.datetime')
    @patch('src.bouncehunter.regime.RegimeDetector')
    def test_run_spy_stress_regime(self, mock_detector_class, mock_datetime, sentinel):
        """Test Sentinel run with SPY stress regime."""
        # Mock datetime
        mock_datetime.now.return_value = datetime(2025, 10, 19, 8, 30)  # Pre-market

        # Mock regime detector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector

        mock_regime_state = MagicMock()
        mock_regime_state.is_spy_stressed = True
        mock_regime_state.is_high_vix = True
        mock_regime_state.vix_percentile = 0.9
        mock_regime_state.spy_dist_200dma = -0.25
        mock_detector.detect.return_value = mock_regime_state

        # Run sentinel
        ctx = asyncio.run(sentinel.run())

        # Verify context
        assert ctx.dt == "2025-10-19"
        assert ctx.regime == "spy_stress"
        assert ctx.vix_percentile == 0.9
        assert ctx.spy_dist_200dma == -0.25
        assert ctx.is_market_hours is False
        assert ctx.is_preclose is False


class TestScreener:
    """Test Screener agent functionality."""

    @pytest.fixture
    def policy(self):
        """Create test policy."""
        config = MagicMock()
        return Policy(config=config)

    @pytest.fixture
    def screener(self, policy):
        """Create Screener instance."""
        return Screener(policy)

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        return Context(
            dt="2025-10-19",
            regime="normal",
            vix_percentile=0.3,
            spy_dist_200dma=0.05,
            is_market_hours=True,
            is_preclose=False,
        )

    @patch('src.bouncehunter.engine.BounceHunter')
    def test_run_with_signals(self, mock_bh_class, screener, mock_context):
        """Test Screener run generating signals."""
        # Mock BounceHunter
        mock_bh = MagicMock()
        mock_bh_class.return_value = mock_bh

        # Mock scan results
        mock_report = MagicMock()
        mock_report.ticker = "AAPL"
        mock_report.date = "2025-10-19"
        mock_report.close = 150.25
        mock_report.z_score = -2.1
        mock_report.rsi2 = 25.5
        mock_report.dist_200dma = -0.08
        mock_report.probability = 0.72
        mock_report.entry = 148.50
        mock_report.stop = 145.00
        mock_report.target = 160.00
        mock_report.adv_usd = 5000000
        mock_report.notes = "Strong bounce setup"

        mock_bh.scan.return_value = [mock_report]

        # Run screener
        signals = asyncio.run(screener.run(mock_context))

        # Verify signals
        assert len(signals) == 1
        sig = signals[0]
        assert sig.ticker == "AAPL"
        assert sig.date == "2025-10-19"
        assert sig.close == 150.25
        assert sig.probability == 0.72
        assert sig.entry == 148.50
        assert sig.stop == 145.00
        assert sig.target == 160.00

    @patch('src.bouncehunter.engine.BounceHunter')
    def test_run_no_signals(self, mock_bh_class, screener, mock_context):
        """Test Screener run with no signals."""
        # Mock BounceHunter
        mock_bh = MagicMock()
        mock_bh_class.return_value = mock_bh
        mock_bh.scan.return_value = []

        # Run screener
        signals = asyncio.run(screener.run(mock_context))

        # Verify no signals
        assert len(signals) == 0


class TestForecaster:
    """Test Forecaster agent functionality."""

    @pytest.fixture
    def forecaster(self):
        """Create Forecaster instance."""
        return Forecaster()

    @pytest.fixture
    def policy(self):
        """Create test policy."""
        return Policy(config=MagicMock(), min_bcs=0.65, min_bcs_highvix=0.70)

    @pytest.fixture
    def signals(self):
        """Create test signals."""
        return [
            Signal(ticker="AAPL", date="2025-10-19", close=150.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.72, entry=148.0,
                   stop=145.0, target=158.0, adv_usd=5000000),
            Signal(ticker="MSFT", date="2025-10-19", close=300.0, z_score=-1.8,
                   rsi2=28.0, dist_200dma=-0.05, probability=0.58, entry=296.0,
                   stop=290.0, target=315.0, adv_usd=3000000),
            Signal(ticker="GOOGL", date="2025-10-19", close=140.0, z_score=-2.2,
                   rsi2=22.0, dist_200dma=-0.12, probability=0.68, entry=138.0,
                   stop=135.0, target=150.0, adv_usd=2000000),
        ]

    def test_run_normal_regime_filtering(self, forecaster, policy, signals):
        """Test Forecaster filtering in normal regime."""
        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        filtered = asyncio.run(forecaster.run(signals, ctx, policy))

        # Should keep signals >= 0.65
        assert len(filtered) == 2
        tickers = [s.ticker for s in filtered]
        assert "AAPL" in tickers  # 0.72 >= 0.65
        assert "GOOGL" in tickers  # 0.68 >= 0.65
        assert "MSFT" not in tickers  # 0.58 < 0.65

    def test_run_high_vix_regime_filtering(self, forecaster, policy, signals):
        """Test Forecaster filtering in high volatility regime."""
        ctx = Context(dt="2025-10-19", regime="high_vix", vix_percentile=0.85,
                     spy_dist_200dma=-0.12, is_market_hours=True, is_preclose=False)

        filtered = asyncio.run(forecaster.run(signals, ctx, policy))

        # Should keep signals >= 0.70
        assert len(filtered) == 1
        assert filtered[0].ticker == "AAPL"  # 0.72 >= 0.70
        assert filtered[0].probability == 0.72

    def test_run_spy_stress_regime_filtering(self, forecaster, policy, signals):
        """Test Forecaster filtering in SPY stress regime."""
        ctx = Context(dt="2025-10-19", regime="spy_stress", vix_percentile=0.9,
                     spy_dist_200dma=-0.25, is_market_hours=True, is_preclose=False)

        filtered = asyncio.run(forecaster.run(signals, ctx, policy))

        # Should keep signals >= 0.70 (same as high_vix)
        assert len(filtered) == 1
        assert filtered[0].ticker == "AAPL"


class TestRiskOfficer:
    """Test RiskOfficer agent functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        import gc
        import os
        
        # Use a more robust temp file approach
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)  # Close the file descriptor immediately
        
        yield db_path
        
        # Force garbage collection and wait before cleanup
        gc.collect()
        import time
        time.sleep(0.2)
        
        try:
            os.unlink(db_path)
        except PermissionError:
            # If still locked, try again after longer wait
            time.sleep(1.0)
            try:
                os.unlink(db_path)
            except PermissionError:
                # Last resort - just leave the file
                pass

    @pytest.fixture
    def memory(self, temp_db):
        """Create AgentMemory instance."""
        return AgentMemory(db_path=temp_db)

    @pytest.fixture
    def policy(self):
        """Create test policy."""
        config = MagicMock()
        config.skip_earnings = True
        return Policy(
            config=config,
            max_concurrent=3,
            max_per_sector=2,
            auto_adapt_thresholds=True,
            base_rate_floor=0.40,
            min_sample_size=5,
        )

    @pytest.fixture
    def risk_officer(self, policy, memory):
        """Create RiskOfficer instance."""
        return RiskOfficer(policy, memory)

    @pytest.fixture
    def signals(self):
        """Create test signals."""
        return [
            Signal(ticker="AAPL", date="2025-10-19", close=150.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.72, entry=148.0,
                   stop=145.0, target=158.0, adv_usd=5000000, sector="Technology"),
            Signal(ticker="MSFT", date="2025-10-19", close=300.0, z_score=-1.8,
                   rsi2=28.0, dist_200dma=-0.05, probability=0.75, entry=296.0,
                   stop=290.0, target=315.0, adv_usd=3000000, sector="Technology"),
            Signal(ticker="JPM", date="2025-10-19", close=200.0, z_score=-2.1,
                   rsi2=24.0, dist_200dma=-0.08, probability=0.70, entry=197.0,
                   stop=193.0, target=210.0, adv_usd=4000000, sector="Financial"),
        ]

    def test_run_under_concurrent_limit(self, risk_officer, signals):
        """Test RiskOfficer with signals under concurrent limit."""
        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        approved = asyncio.run(risk_officer.run(signals, ctx))

        # Should approve all signals (under limit)
        assert len(approved) == 3
        assert all(not s.vetoed for s in approved)

    def test_run_at_concurrent_limit(self, risk_officer, signals):
        """Test RiskOfficer at concurrent limit."""
        # Add some open fills to reach the limit
        for i in range(2):  # Leave room for 1 more
            risk_officer.memory.record_fill(
                signal_id=f"existing_{i}",
                ticker=f"EXIST{i}",
                entry_date="2025-10-18",
                entry_price=100.0,
                size_pct=0.01,
                regime="normal",
            )

        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        approved = asyncio.run(risk_officer.run(signals, ctx))

        # Should approve only 1 signal (max_concurrent = 3, 2 open = 1 available)
        assert len(approved) == 1
        assert not approved[0].vetoed

    def test_run_over_concurrent_limit(self, risk_officer, signals):
        """Test RiskOfficer over concurrent limit."""
        # Add fills to exceed the limit
        for i in range(3):  # At the limit
            risk_officer.memory.record_fill(
                signal_id=f"existing_{i}",
                ticker=f"EXIST{i}",
                entry_date="2025-10-18",
                entry_price=100.0,
                size_pct=0.01,
                regime="normal",
            )

        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        approved = asyncio.run(risk_officer.run(signals, ctx))

        # Should veto all signals
        assert len(approved) == 0
        assert all(s.vetoed for s in signals)
        assert all("Max concurrent" in s.veto_reason for s in signals)

    def test_run_sector_cap_enforcement(self, risk_officer, signals):
        """Test RiskOfficer sector cap enforcement."""
        # Modify signals to have same sector
        for sig in signals:
            sig.sector = "Technology"

        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        approved = asyncio.run(risk_officer.run(signals, ctx))

        # Should approve only 2 (max_per_sector = 2)
        assert len(approved) == 2
        assert not any(s.vetoed for s in approved)

        # Third signal should be vetoed
        vetoed_signals = [s for s in signals if s.vetoed]
        assert len(vetoed_signals) == 1
        assert "Sector cap" in vetoed_signals[0].veto_reason

    def test_run_base_rate_filtering(self, risk_officer, signals):
        """Test RiskOfficer base rate filtering."""
        # Create poor performance history for AAPL
        signal_id = risk_officer.memory.record_signal(
            Signal(ticker="AAPL", date="2025-10-15", close=145.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.7, entry=143.0,
                   stop=140.0, target=155.0, adv_usd=5000000),
            Action(signal_id="test", ticker="AAPL", action="BUY", size_pct=0.01,
                   entry=143.0, stop=140.0, target=155.0, probability=0.7, regime="normal")
        )

        fill_id = risk_officer.memory.record_fill(signal_id, "AAPL", "2025-10-15", 143.0, 0.01, "normal")
        risk_officer.memory.record_outcome(fill_id, "AAPL", "2025-10-16", 139.0, "STOP", 143.0, 1)

        # Update stats (simulate multiple poor outcomes)
        for _ in range(4):  # Need min_sample_size = 5
            risk_officer.memory.record_outcome(fill_id, "AAPL", "2025-10-16", 139.0, "STOP", 143.0, 1)

        risk_officer.memory.update_ticker_stats("AAPL")

        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        approved = asyncio.run(risk_officer.run(signals, ctx))

        # AAPL should be vetoed due to poor base rate
        aapl_signal = next(s for s in signals if s.ticker == "AAPL")
        assert aapl_signal.vetoed
        assert "base rate" in aapl_signal.veto_reason.lower()

        # Others should be approved
        other_signals = [s for s in approved if s.ticker != "AAPL"]
        assert len(other_signals) == 2


class TestNewsSentry:
    """Test NewsSentry agent functionality."""

    @pytest.fixture
    def policy_disabled(self):
        """Create policy with news veto disabled."""
        return Policy(config=MagicMock(), news_veto_enabled=False)

    @pytest.fixture
    def policy_enabled(self):
        """Create policy with news veto enabled."""
        return Policy(config=MagicMock(), news_veto_enabled=True)

    @pytest.fixture
    def news_sentry_disabled(self, policy_disabled):
        """Create NewsSentry with veto disabled."""
        return NewsSentry(policy_disabled)

    @pytest.fixture
    def news_sentry_enabled(self, policy_enabled):
        """Create NewsSentry with veto enabled."""
        return NewsSentry(policy_enabled)

    @pytest.fixture
    def signals(self):
        """Create test signals."""
        return [
            Signal(ticker="AAPL", date="2025-10-19", close=150.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.72, entry=148.0,
                   stop=145.0, target=158.0, adv_usd=5000000),
            Signal(ticker="MSFT", date="2025-10-19", close=300.0, z_score=-1.8,
                   rsi2=28.0, dist_200dma=-0.05, probability=0.75, entry=296.0,
                   stop=290.0, target=315.0, adv_usd=3000000),
        ]

    def test_run_disabled_passes_all(self, news_sentry_disabled, signals):
        """Test NewsSentry with veto disabled passes all signals."""
        result = asyncio.run(news_sentry_disabled.run(signals))

        assert result == signals
        assert len(result) == 2

    def test_run_enabled_stub_implementation(self, news_sentry_enabled, signals):
        """Test NewsSentry with veto enabled (currently stub implementation)."""
        result = asyncio.run(news_sentry_enabled.run(signals))

        # Currently just passes all signals (stub implementation)
        assert result == signals
        assert len(result) == 2


class TestTrader:
    """Test Trader agent functionality."""

    @pytest.fixture
    def policy_paper(self):
        """Create policy for paper trading."""
        return Policy(
            config=MagicMock(),
            live_trading=False,
            risk_pct_normal=0.012,
            risk_pct_highvix=0.006,
        )

    @pytest.fixture
    def policy_live(self):
        """Create policy for live trading."""
        return Policy(
            config=MagicMock(),
            live_trading=True,
            risk_pct_normal=0.012,
            risk_pct_highvix=0.006,
        )

    @pytest.fixture
    def trader_paper(self, policy_paper):
        """Create Trader for paper trading."""
        return Trader(policy_paper)

    @pytest.fixture
    def trader_live(self, policy_live):
        """Create Trader for live trading."""
        return Trader(policy_live, broker=MagicMock())

    @pytest.fixture
    def signals(self):
        """Create test signals."""
        return [
            Signal(ticker="AAPL", date="2025-10-19", close=150.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.72, entry=148.0,
                   stop=145.0, target=158.0, adv_usd=5000000),
            Signal(ticker="MSFT", date="2025-10-19", close=300.0, z_score=-1.8,
                   rsi2=28.0, dist_200dma=-0.05, probability=0.75, entry=296.0,
                   stop=290.0, target=315.0, adv_usd=3000000),
        ]

    def test_run_paper_trading_normal_regime(self, trader_paper, signals):
        """Test Trader paper trading in normal regime."""
        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        actions = asyncio.run(trader_paper.run(signals, ctx))

        assert len(actions) == 2

        # Check first action
        action1 = actions[0]
        assert action1.ticker == "AAPL"
        assert action1.action == "ALERT"  # Paper trading
        assert action1.size_pct == 0.012  # Normal regime
        assert action1.entry == 148.0
        assert action1.stop == 145.0
        assert action1.target == 158.0
        assert action1.probability == 0.72
        assert action1.regime == "normal"
        assert "Approved by all agents" in action1.reason

    def test_run_paper_trading_high_vix_regime(self, trader_paper, signals):
        """Test Trader paper trading in high volatility regime."""
        ctx = Context(dt="2025-10-19", regime="high_vix", vix_percentile=0.85,
                     spy_dist_200dma=-0.12, is_market_hours=True, is_preclose=False)

        actions = asyncio.run(trader_paper.run(signals, ctx))

        assert len(actions) == 2

        # Check size_pct for high vix
        for action in actions:
            assert action.size_pct == 0.006  # High vix regime
            assert action.action == "ALERT"  # Paper trading

    @patch('src.bouncehunter.agentic.datetime')
    def test_run_live_trading_with_broker(self, mock_datetime, trader_live, signals):
        """Test Trader live trading with broker."""
        mock_datetime.now.return_value = datetime(2025, 10, 19, 10, 30)

        # Mock broker
        mock_account = MagicMock()
        mock_account.portfolio_value = 100000
        trader_live.broker.get_account.return_value = mock_account

        # Mock bracket order response
        mock_order = MagicMock()
        mock_order.order_id = "BRACKET_123"
        trader_live.broker.place_bracket_order.return_value = {
            'entry': mock_order,
            'stop': MagicMock(),
            'target': MagicMock()
        }

        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        actions = asyncio.run(trader_live.run(signals, ctx))

        assert len(actions) == 2

        # Check actions
        for action in actions:
            assert action.action == "BUY"  # Live trading
            assert action.size_pct == 0.012  # Normal regime
            assert "Order ID: BRACKET_123" in action.reason

        # Verify broker calls
        assert trader_live.broker.get_account.call_count == 2  # Once per signal
        assert trader_live.broker.place_bracket_order.call_count == 2

    def test_run_live_trading_broker_error(self, trader_live, signals):
        """Test Trader live trading with broker error."""
        # Mock broker to raise exception
        trader_live.broker.get_account.side_effect = Exception("Connection failed")

        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        actions = asyncio.run(trader_live.run(signals, ctx))

        assert len(actions) == 2

        # Check error handling
        for action in actions:
            assert action.action == "BUY"  # Still live trading
            assert "Order failed: Connection failed" in action.reason


class TestHistorian:
    """Test Historian agent functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        import gc
        import os
        
        # Use a more robust temp file approach
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)  # Close the file descriptor immediately
        
        yield db_path
        
        # Force garbage collection and wait before cleanup
        gc.collect()
        import time
        time.sleep(0.2)
        
        try:
            os.unlink(db_path)
        except PermissionError:
            # If still locked, try again after longer wait
            time.sleep(1.0)
            try:
                os.unlink(db_path)
            except PermissionError:
                # Last resort - just leave the file
                pass

    @pytest.fixture
    def memory(self, temp_db):
        """Create AgentMemory instance."""
        return AgentMemory(db_path=temp_db)

    @pytest.fixture
    def historian(self, memory):
        """Create Historian instance."""
        return Historian(memory)

    @pytest.fixture
    def signals_and_actions(self):
        """Create test signals and actions."""
        signals = [
            Signal(ticker="AAPL", date="2025-10-19", close=150.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.72, entry=148.0,
                   stop=145.0, target=158.0, adv_usd=5000000),
            Signal(ticker="MSFT", date="2025-10-19", close=300.0, z_score=-1.8,
                   rsi2=28.0, dist_200dma=-0.05, probability=0.75, entry=296.0,
                   stop=290.0, target=315.0, adv_usd=3000000, vetoed=True),
        ]

        actions = [
            Action(signal_id="test1", ticker="AAPL", action="BUY", size_pct=0.012,
                   entry=148.0, stop=145.0, target=158.0, probability=0.72, regime="normal"),
            Action(signal_id="test2", ticker="MSFT", action="VETO", size_pct=0.012,
                   entry=296.0, stop=290.0, target=315.0, probability=0.75, regime="normal"),
        ]

        return signals, actions

    def test_run_records_signals_and_fills(self, historian, signals_and_actions):
        """Test Historian records signals and fills."""
        signals, actions = signals_and_actions

        ctx = Context(dt="2025-10-19", regime="normal", vix_percentile=0.3,
                     spy_dist_200dma=0.05, is_market_hours=True, is_preclose=False)

        result = asyncio.run(historian.run(signals, actions, ctx))

        assert result is True

        # Check signals recorded
        with sqlite3.connect(historian.memory.db_path) as conn:
            signal_count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
            fill_count = conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]

        assert signal_count == 2  # Both signals recorded
        assert fill_count == 1  # Only non-vetoed signal gets fill


class TestAuditor:
    """Test Auditor agent functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        import gc
        import os
        
        # Use a more robust temp file approach
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)  # Close the file descriptor immediately
        
        yield db_path
        
        # Force garbage collection and wait before cleanup
        gc.collect()
        import time
        time.sleep(0.2)
        
        try:
            os.unlink(db_path)
        except PermissionError:
            # If still locked, try again after longer wait
            time.sleep(1.0)
            try:
                os.unlink(db_path)
            except PermissionError:
                # Last resort - just leave the file
                pass

    @pytest.fixture
    def memory(self, temp_db):
        """Create AgentMemory instance."""
        return AgentMemory(db_path=temp_db)

    @pytest.fixture
    def policy(self):
        """Create test policy."""
        return Policy(config=MagicMock())

    @pytest.fixture
    def auditor(self, memory, policy):
        """Create Auditor instance."""
        return Auditor(memory, policy)

    def test_run_no_outcomes(self, auditor):
        """Test Auditor run with no outcomes."""
        result = asyncio.run(auditor.run())

        assert result["updated_tickers"] == 0
        assert result["stats"] == []

    def test_run_with_outcomes(self, auditor):
        """Test Auditor run with outcomes."""
        # Create test data for AAPL
        signal_id = auditor.memory.record_signal(
            Signal(ticker="AAPL", date="2025-10-15", close=145.0, z_score=-2.0,
                   rsi2=25.0, dist_200dma=-0.1, probability=0.7, entry=143.0,
                   stop=140.0, target=155.0, adv_usd=5000000),
            Action(signal_id="test", ticker="AAPL", action="BUY", size_pct=0.01,
                   entry=143.0, stop=140.0, target=155.0, probability=0.7, regime="normal")
        )

        fill_id = auditor.memory.record_fill(signal_id, "AAPL", "2025-10-15", 143.0, 0.01, "normal")

        # Add multiple outcomes
        for i in range(3):
            exit_price = 150.0 if i < 2 else 138.0  # 2 wins, 1 loss
            exit_reason = "TARGET" if i < 2 else "STOP"
            auditor.memory.record_outcome(fill_id, "AAPL", f"2025-10-{16+i}", exit_price, exit_reason, 143.0, 1)

        # Run auditor
        result = asyncio.run(auditor.run())

        assert result["updated_tickers"] == 1
        assert len(result["stats"]) == 1

        stats = result["stats"][0]
        assert stats["ticker"] == "AAPL"
        assert stats["base_rate"] == 2/3  # 2 wins out of 3
        assert stats["total_outcomes"] == 3
        assert "avg_reward" in stats


class TestOrchestrator:
    """Test Orchestrator integration functionality."""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database."""
        import gc
        import os
        
        # Use a more robust temp file approach
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)  # Close the file descriptor immediately
        
        yield db_path
        
        # Force garbage collection and wait before cleanup
        gc.collect()
        import time
        time.sleep(0.2)
        
        try:
            os.unlink(db_path)
        except PermissionError:
            # If still locked, try again after longer wait
            time.sleep(1.0)
            try:
                os.unlink(db_path)
            except PermissionError:
                # Last resort - just leave the file
                pass

    @pytest.fixture
    def memory(self, temp_db):
        """Create AgentMemory instance."""
        return AgentMemory(db_path=temp_db)

    @pytest.fixture
    def policy(self):
        """Create test policy."""
        config = MagicMock()
        config.vix_lookback_days = 30
        config.highvix_percentile = 0.8
        config.spy_stress_multiplier = 2.0
        config.bcs_threshold = 0.62
        config.bcs_threshold_highvix = 0.68
        config.size_pct_base = 0.012
        config.size_pct_highvix = 0.006
        return Policy(
            config=config,
            live_trading=False,
            min_bcs=0.65,
            min_bcs_highvix=0.70,
            max_concurrent=5,
            max_per_sector=3,
        )

    @pytest.fixture
    def orchestrator(self, policy, memory):
        """Create Orchestrator instance."""
        return Orchestrator(policy, memory)

    @patch('src.bouncehunter.agentic.datetime')
    @patch('src.bouncehunter.regime.RegimeDetector')
    @patch('src.bouncehunter.engine.BounceHunter')
    def test_run_daily_scan_full_flow(self, mock_bh_class, mock_detector_class,
                                     mock_datetime, orchestrator):
        """Test full daily scan flow."""
        # Mock datetime
        mock_datetime.now.return_value = datetime(2025, 10, 19, 10, 30)

        # Mock regime detector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_regime_state = MagicMock()
        mock_regime_state.is_spy_stressed = False
        mock_regime_state.is_high_vix = False
        mock_regime_state.vix_percentile = 0.3
        mock_regime_state.spy_dist_200dma = 0.05
        mock_detector.detect.return_value = mock_regime_state

        # Mock BounceHunter
        mock_bh = MagicMock()
        mock_bh_class.return_value = mock_bh

        mock_report = MagicMock()
        mock_report.ticker = "AAPL"
        mock_report.date = "2025-10-19"
        mock_report.close = 150.25
        mock_report.z_score = -2.1
        mock_report.rsi2 = 25.5
        mock_report.dist_200dma = -0.08
        mock_report.probability = 0.72
        mock_report.entry = 148.50
        mock_report.stop = 145.00
        mock_report.target = 160.00
        mock_report.adv_usd = 5000000
        mock_report.notes = "Strong bounce setup"

        mock_bh.scan.return_value = [mock_report]

        # Run daily scan
        result = asyncio.run(orchestrator.run_daily_scan())

        # Verify result structure
        assert "timestamp" in result
        assert "context" in result
        assert result["signals"] == 1
        assert result["approved"] == 1
        assert len(result["actions"]) == 1

        action = result["actions"][0]
        assert action["ticker"] == "AAPL"
        assert action["action"] == "ALERT"  # Paper trading
        assert action["size_pct"] == 0.012  # Normal regime

    @patch('src.bouncehunter.agentic.datetime')
    @patch('src.bouncehunter.regime.RegimeDetector')
    @patch('src.bouncehunter.engine.BounceHunter')
    def test_run_daily_scan_no_signals(self, mock_bh_class, mock_detector_class,
                                      mock_datetime, orchestrator):
        """Test daily scan with no signals generated."""
        # Mock datetime
        mock_datetime.now.return_value = datetime(2025, 10, 19, 10, 30)

        # Mock regime detector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_regime_state = MagicMock()
        mock_regime_state.is_spy_stressed = False
        mock_regime_state.is_high_vix = False
        mock_regime_state.vix_percentile = 0.3
        mock_regime_state.spy_dist_200dma = 0.05
        mock_detector.detect.return_value = mock_regime_state

        # Mock BounceHunter with no signals
        mock_bh = MagicMock()
        mock_bh_class.return_value = mock_bh
        mock_bh.scan.return_value = []

        # Run daily scan
        result = asyncio.run(orchestrator.run_daily_scan())

        # Verify result
        assert result["signals"] == 0
        assert result["approved"] == 0
        assert len(result["actions"]) == 0

    @patch('src.bouncehunter.agentic.datetime')
    @patch('src.bouncehunter.regime.RegimeDetector')
    @patch('src.bouncehunter.engine.BounceHunter')
    def test_run_daily_scan_filtered_by_bcs(self, mock_bh_class, mock_detector_class,
                                           mock_datetime, orchestrator):
        """Test daily scan with signals filtered by BCS threshold."""
        # Mock datetime
        mock_datetime.now.return_value = datetime(2025, 10, 19, 10, 30)

        # Mock regime detector
        mock_detector = MagicMock()
        mock_detector_class.return_value = mock_detector
        mock_regime_state = MagicMock()
        mock_regime_state.is_spy_stressed = False
        mock_regime_state.is_high_vix = False
        mock_regime_state.vix_percentile = 0.3
        mock_regime_state.spy_dist_200dma = 0.05
        mock_detector.detect.return_value = mock_regime_state

        # Mock BounceHunter with low probability signal
        mock_bh = MagicMock()
        mock_bh_class.return_value = mock_bh

        mock_report = MagicMock()
        mock_report.ticker = "AAPL"
        mock_report.date = "2025-10-19"
        mock_report.close = 150.25
        mock_report.z_score = -2.1
        mock_report.rsi2 = 25.5
        mock_report.dist_200dma = -0.08
        mock_report.probability = 0.60  # Below min_bcs = 0.65
        mock_report.entry = 148.50
        mock_report.stop = 145.00
        mock_report.target = 160.00
        mock_report.adv_usd = 5000000
        mock_report.notes = "Weak signal"

        mock_bh.scan.return_value = [mock_report]

        # Run daily scan
        result = asyncio.run(orchestrator.run_daily_scan())

        # Verify signal was filtered
        assert result["signals"] == 0  # Filtered out
        assert result["approved"] == 0
        assert len(result["actions"]) == 0
        assert "below BCS threshold" in result["filtered"]

    def test_run_nightly_audit(self, orchestrator):
        """Test nightly audit run."""
        result = asyncio.run(orchestrator.run_nightly_audit())

        # Should return empty result initially
        assert result["updated_tickers"] == 0
        assert result["stats"] == []