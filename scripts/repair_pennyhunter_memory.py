"""Repair PennyHunter memory DB from visible paper-trade results."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
from pathlib import Path


def load_memory_class():
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "src" / "bouncehunter" / "pennyhunter_memory.py"
    spec = importlib.util.spec_from_file_location("pennyhunter_memory_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load PennyHunterMemory from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PennyHunterMemory


def read_ticker_stats(db_path: Path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT ticker, total_trades, wins, losses, total_pnl, status, ejection_reason
        FROM ticker_stats
        ORDER BY ticker
        """
    )
    rows = cur.fetchall()
    try:
        cur.execute("SELECT COUNT(*) FROM recorded_outcomes")
        outcome_count = cur.fetchone()[0]
    except sqlite3.OperationalError:
        outcome_count = 0
    conn.close()
    return rows, outcome_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-trades-file", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--skip-second-pass", action="store_true")
    args = parser.parse_args()

    paper_trades_file = Path(args.paper_trades_file)
    db_path = Path(args.db_path)

    trades_report = json.loads(paper_trades_file.read_text(encoding="utf-8"))
    trades = trades_report.get("trades", [])
    PennyHunterMemory = load_memory_class()

    before_rows, before_outcome_count = read_ticker_stats(db_path)

    memory = PennyHunterMemory(db_path=db_path)
    memory.rebuild_from_trades(trades, reset=True)
    after_rows, after_outcome_count = read_ticker_stats(db_path)

    after_second_rows = None
    after_second_outcome_count = None
    if not args.skip_second_pass:
        memory.rebuild_from_trades(trades, reset=False)
        after_second_rows, after_second_outcome_count = read_ticker_stats(db_path)

    print(
        json.dumps(
            {
                "before_rows": before_rows,
                "before_outcome_count": before_outcome_count,
                "after_rows": after_rows,
                "after_outcome_count": after_outcome_count,
                "after_second_rows": after_second_rows,
                "after_second_outcome_count": after_second_outcome_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()