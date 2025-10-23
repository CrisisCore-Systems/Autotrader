"""Initialize development databases with schema only.

This script creates empty development databases with the correct schema.
Database files should NOT be committed to version control.

Usage:
    python scripts/db/init_dev_databases.py

Creates:
    - bouncehunter_memory.db: Agent memory for trading signals
    - test_memory.db: Test database with same structure
    - experiments.sqlite: Experiment tracking database
"""

import sqlite3
import sys
from pathlib import Path


def create_bouncehunter_db(db_path: str = "bouncehunter_memory.db") -> None:
    """Create bouncehunter_memory.db with schema.
    
    This database stores agent memory for the BounceHunter trading system,
    including signals, fills, outcomes, and ticker statistics.
    
    Args:
        db_path: Path to database file (default: bouncehunter_memory.db)
    """
    print(f"Creating {db_path}...")
    
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            signal_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            probability REAL NOT NULL,
            entry REAL NOT NULL,
            stop REAL NOT NULL,
            target REAL NOT NULL,
            regime TEXT NOT NULL,
            size_pct REAL NOT NULL,
            z_score REAL,
            rsi2 REAL,
            dist_200dma REAL,
            adv_usd REAL,
            sector TEXT,
            notes TEXT,
            vetoed INTEGER DEFAULT 0,
            veto_reason TEXT
        );

        CREATE TABLE IF NOT EXISTS fills (
            fill_id TEXT PRIMARY KEY,
            signal_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            entry_date TEXT NOT NULL,
            entry_price REAL NOT NULL,
            shares REAL NOT NULL,
            size_pct REAL NOT NULL,
            regime TEXT NOT NULL,
            is_paper INTEGER DEFAULT 1,
            FOREIGN KEY (signal_id) REFERENCES signals(signal_id)
        );

        CREATE TABLE IF NOT EXISTS outcomes (
            outcome_id TEXT PRIMARY KEY,
            fill_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            exit_date TEXT NOT NULL,
            exit_price REAL NOT NULL,
            exit_reason TEXT NOT NULL,
            hold_days INTEGER NOT NULL,
            return_pct REAL NOT NULL,
            hit_target INTEGER DEFAULT 0,
            hit_stop INTEGER DEFAULT 0,
            hit_time INTEGER DEFAULT 0,
            reward REAL NOT NULL,
            FOREIGN KEY (fill_id) REFERENCES fills(fill_id)
        );

        CREATE TABLE IF NOT EXISTS ticker_stats (
            ticker TEXT PRIMARY KEY,
            last_updated TEXT NOT NULL,
            total_signals INTEGER DEFAULT 0,
            total_outcomes INTEGER DEFAULT 0,
            base_rate REAL DEFAULT 0.0,
            avg_reward REAL DEFAULT 0.0,
            normal_regime_rate REAL DEFAULT 0.0,
            highvix_regime_rate REAL DEFAULT 0.0,
            ejected INTEGER DEFAULT 0,
            eject_reason TEXT
        );

        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_signals_ticker ON signals(ticker);
        CREATE INDEX IF NOT EXISTS idx_signals_date ON signals(date);
        CREATE INDEX IF NOT EXISTS idx_fills_ticker ON fills(ticker);
        CREATE INDEX IF NOT EXISTS idx_outcomes_ticker ON outcomes(ticker);
    """)
    
    conn.commit()
    conn.close()
    print(f"✓ {db_path} created successfully")


def create_test_db(db_path: str = "test_memory.db") -> None:
    """Create test_memory.db with schema.
    
    Test database with the same structure as bouncehunter_memory.db
    for use in testing environments.
    
    Args:
        db_path: Path to database file (default: test_memory.db)
    """
    print(f"Creating {db_path}...")
    # Same schema as bouncehunter_memory.db
    create_bouncehunter_db(db_path)


def create_experiments_db(db_path: str = "experiments.sqlite") -> None:
    """Create experiments.sqlite with schema.
    
    This database tracks experiment configurations for reproducibility,
    including feature sets, weights, and hyperparameters.
    
    Args:
        db_path: Path to database file (default: experiments.sqlite)
    """
    print(f"Creating {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create experiments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            config_hash TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            description TEXT,
            feature_names TEXT NOT NULL,
            feature_weights TEXT NOT NULL,
            feature_transformations TEXT,
            hyperparameters TEXT,
            tags TEXT,
            config_json TEXT NOT NULL
        )
    """)
    
    # Create index on created_at for temporal queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_created_at 
        ON experiments(created_at)
    """)
    
    # Create tags table for better searching
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS experiment_tags (
            config_hash TEXT NOT NULL,
            tag TEXT NOT NULL,
            PRIMARY KEY (config_hash, tag),
            FOREIGN KEY (config_hash) REFERENCES experiments(config_hash)
        )
    """)
    
    conn.commit()
    conn.close()
    print(f"✓ {db_path} created successfully")


def main():
    """Initialize all development databases."""
    # Change to repository root if script is run from scripts/db
    script_path = Path(__file__).resolve()
    repo_root = script_path.parent.parent.parent
    
    print("=" * 60)
    print("Database Initialization Script")
    print("=" * 60)
    print(f"Working directory: {repo_root}")
    print()
    
    # Create databases in repository root
    try:
        create_bouncehunter_db(str(repo_root / "bouncehunter_memory.db"))
        create_test_db(str(repo_root / "test_memory.db"))
        create_experiments_db(str(repo_root / "experiments.sqlite"))
        
        print()
        print("=" * 60)
        print("✓ All databases created successfully!")
        print("=" * 60)
        print()
        print("NOTE: These databases are NOT tracked in git.")
        print("They will be automatically ignored by .gitignore")
        print()
        
        return 0
    except Exception as e:
        print(f"ERROR: Failed to initialize databases: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
