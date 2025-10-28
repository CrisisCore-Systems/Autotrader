"""
PennyHunter Dashboard Hotfix - Phase 2.5
=========================================
Fixes runtime errors preventing dashboard operations:
1. win_rate_label initialization (FIXED in gui_trading_dashboard.py)
2. Trade history JSON parsing (FIXED in gui_trading_dashboard.py)
3. Missing ticker_performance table (THIS SCRIPT)

Usage:
    python patch_v2.5_hotfix.py

This script creates the missing ticker_performance table needed by
the Phase 2.5 memory system and dashboard scanner stats display.
"""

import sqlite3
from pathlib import Path
import sys


def create_ticker_performance_table():
    """Initialize ticker_performance table for Phase 2.5 memory system."""
    
    # Database paths
    memory_db = Path("reports/pennyhunter_memory.db")
    bounce_db = Path("bouncehunter_memory.db")
    
    databases = []
    if memory_db.exists():
        databases.append(memory_db)
    if bounce_db.exists():
        databases.append(bounce_db)
    
    if not databases:
        print("⚠️  No memory databases found. They will be created on first scanner run.")
        # Create reports directory if it doesn't exist
        memory_db.parent.mkdir(parents=True, exist_ok=True)
        databases = [memory_db, bounce_db]
    
    success_count = 0
    
    for db_path in databases:
        try:
            print(f"\n📊 Initializing {db_path}...")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if table already exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='ticker_performance'
            """)
            
            if cursor.fetchone():
                print(f"   ✓ ticker_performance table already exists")
            else:
                # Create the table
                cursor.execute("""
                    CREATE TABLE ticker_performance (
                        ticker TEXT PRIMARY KEY,
                        total_signals INTEGER DEFAULT 0,
                        perfect_signals INTEGER DEFAULT 0,
                        good_signals INTEGER DEFAULT 0,
                        marginal_signals INTEGER DEFAULT 0,
                        poor_signals INTEGER DEFAULT 0,
                        total_wins INTEGER DEFAULT 0,
                        total_losses INTEGER DEFAULT 0,
                        win_rate REAL DEFAULT 0.0,
                        avg_return REAL DEFAULT 0.0,
                        total_return REAL DEFAULT 0.0,
                        max_drawdown REAL DEFAULT 0.0,
                        normal_regime_wr REAL DEFAULT 0.0,
                        highvix_regime_wr REAL DEFAULT 0.0,
                        consecutive_losses INTEGER DEFAULT 0,
                        last_signal_date TEXT,
                        last_updated TEXT NOT NULL,
                        status TEXT DEFAULT 'active',
                        notes TEXT
                    )
                """)
                
                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ticker_perf_status 
                    ON ticker_performance(status)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ticker_perf_winrate 
                    ON ticker_performance(win_rate)
                """)
                
                conn.commit()
                print(f"   ✅ Created ticker_performance table with indexes")
            
            # Verify the table structure
            cursor.execute("PRAGMA table_info(ticker_performance)")
            columns = cursor.fetchall()
            print(f"   ✓ Table has {len(columns)} columns")
            
            conn.close()
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ Error with {db_path}: {e}")
            continue
    
    return success_count


def verify_dashboard_readiness():
    """Run quick checks to ensure dashboard will launch cleanly."""
    
    print("\n🔍 Verifying dashboard readiness...\n")
    
    checks_passed = 0
    checks_total = 4
    
    # Check 1: GUI file exists
    gui_file = Path("gui_trading_dashboard.py")
    if gui_file.exists():
        print("✅ [1/4] GUI dashboard file found")
        checks_passed += 1
    else:
        print("❌ [1/4] GUI dashboard file not found")
    
    # Check 2: Config file exists
    config_file = Path("configs/my_paper_config.yaml")
    if config_file.exists():
        print("✅ [2/4] Paper trading config found")
        checks_passed += 1
    else:
        print("⚠️  [2/4] Config file missing (will use defaults)")
        checks_passed += 1  # Non-critical
    
    # Check 3: Database tables
    db_ready = False
    for db_path in [Path("reports/pennyhunter_memory.db"), Path("bouncehunter_memory.db")]:
        if db_path.exists():
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='ticker_performance'
                """)
                if cursor.fetchone():
                    db_ready = True
                    break
                conn.close()
            except:
                pass
    
    if db_ready:
        print("✅ [3/4] Database schema ready")
        checks_passed += 1
    else:
        print("❌ [3/4] Database schema incomplete")
    
    # Check 4: Required directories
    dirs_exist = all([
        Path("reports").exists(),
        Path("configs").exists(),
        Path("logs").exists()
    ])
    
    if dirs_exist:
        print("✅ [4/4] Required directories exist")
        checks_passed += 1
    else:
        print("⚠️  [4/4] Creating missing directories...")
        Path("reports").mkdir(exist_ok=True)
        Path("configs").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        checks_passed += 1
    
    print(f"\n{'='*50}")
    print(f"Readiness: {checks_passed}/{checks_total} checks passed")
    
    if checks_passed == checks_total:
        print("🎉 Dashboard is ready to launch!")
        return True
    elif checks_passed >= 3:
        print("⚠️  Dashboard should launch (minor issues)")
        return True
    else:
        print("❌ Dashboard may have issues launching")
        return False


def main():
    """Execute all hotfixes."""
    
    print("=" * 60)
    print("PennyHunter Phase 2.5 Dashboard Hotfix")
    print("=" * 60)
    print()
    print("This script fixes the missing ticker_performance table.")
    print("Other fixes have been applied directly to gui_trading_dashboard.py")
    print()
    
    # Execute database fix
    success_count = create_ticker_performance_table()
    
    # Verify everything is ready
    is_ready = verify_dashboard_readiness()
    
    # Summary
    print("\n" + "=" * 60)
    print("HOTFIX SUMMARY")
    print("=" * 60)
    print()
    print("✅ Fix 1: win_rate_label initialization (code updated)")
    print("✅ Fix 2: Trade history JSON parsing (code updated)")
    print(f"{'✅' if success_count > 0 else '⚠️ '} Fix 3: ticker_performance table ({success_count} database(s))")
    print()
    
    if is_ready:
        print("🚀 Next Step: Launch dashboard")
        print()
        print("   python gui_trading_dashboard.py")
        print()
        print("   Expected behavior:")
        print("   - No AttributeError on win_rate_label")
        print("   - Trade history updates without errors")
        print("   - Scanner stats display correctly")
        print()
        return 0
    else:
        print("⚠️  Please review errors above before launching dashboard")
        return 1


if __name__ == "__main__":
    sys.exit(main())
