"""Tests for database initialization script."""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.db.init_dev_databases import (
    create_bouncehunter_db,
    create_experiments_db,
    create_test_db,
)


def test_create_bouncehunter_db():
    """Test bouncehunter database creation with correct schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_bouncehunter.db"
        create_bouncehunter_db(str(db_path))
        
        # Verify database exists
        assert db_path.exists()
        
        # Verify tables exist
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check signals table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
        assert cursor.fetchone() is not None
        
        # Check fills table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fills'")
        assert cursor.fetchone() is not None
        
        # Check outcomes table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='outcomes'")
        assert cursor.fetchone() is not None
        
        # Check ticker_stats table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticker_stats'")
        assert cursor.fetchone() is not None
        
        # Check system_state table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_state'")
        assert cursor.fetchone() is not None
        
        # Verify indexes exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_signals_ticker'")
        assert cursor.fetchone() is not None
        
        conn.close()


def test_create_test_db():
    """Test test database creation (same structure as bouncehunter)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memory.db"
        create_test_db(str(db_path))
        
        # Verify database exists
        assert db_path.exists()
        
        # Verify it has the same structure as bouncehunter
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {'signals', 'fills', 'outcomes', 'ticker_stats', 'system_state'}
        assert expected_tables.issubset(tables)
        
        conn.close()


def test_create_experiments_db():
    """Test experiments database creation with correct schema."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_experiments.sqlite"
        create_experiments_db(str(db_path))
        
        # Verify database exists
        assert db_path.exists()
        
        # Verify tables exist
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check experiments table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='experiments'")
        assert cursor.fetchone() is not None
        
        # Check experiment_tags table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='experiment_tags'")
        assert cursor.fetchone() is not None
        
        # Verify index exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_created_at'")
        assert cursor.fetchone() is not None
        
        conn.close()


def test_bouncehunter_db_schema_columns():
    """Test that bouncehunter database has correct column definitions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_bouncehunter.db"
        create_bouncehunter_db(str(db_path))
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check signals table columns
        cursor.execute("PRAGMA table_info(signals)")
        signal_columns = {row[1] for row in cursor.fetchall()}
        
        expected_signal_cols = {
            'signal_id', 'timestamp', 'ticker', 'date', 'probability',
            'entry', 'stop', 'target', 'regime', 'size_pct', 'z_score',
            'rsi2', 'dist_200dma', 'adv_usd', 'sector', 'notes',
            'vetoed', 'veto_reason'
        }
        assert expected_signal_cols.issubset(signal_columns)
        
        conn.close()


def test_experiments_db_schema_columns():
    """Test that experiments database has correct column definitions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_experiments.sqlite"
        create_experiments_db(str(db_path))
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check experiments table columns
        cursor.execute("PRAGMA table_info(experiments)")
        exp_columns = {row[1] for row in cursor.fetchall()}
        
        expected_exp_cols = {
            'config_hash', 'created_at', 'description', 'feature_names',
            'feature_weights', 'feature_transformations', 'hyperparameters',
            'tags', 'config_json'
        }
        assert expected_exp_cols == exp_columns
        
        conn.close()


def test_database_idempotency():
    """Test that running create functions multiple times doesn't break the database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_idempotent.db"
        
        # Create database twice
        create_bouncehunter_db(str(db_path))
        create_bouncehunter_db(str(db_path))
        
        # Verify it still works
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        
        expected_tables = {'signals', 'fills', 'outcomes', 'ticker_stats', 'system_state'}
        assert expected_tables.issubset(tables)
        
        conn.close()
