import json
from datetime import date, timedelta
from pathlib import Path

from src.pipeline.backtest import BacktestConfig, run_backtest


def test_run_backtest_creates_reports(tmp_path: Path) -> None:
    config = BacktestConfig(
        start=date(2023, 1, 1),
        end=date(2023, 4, 1),
        walk=timedelta(days=30),
        k=5,
        output_root=tmp_path,
        seed=99,
    )

    output_dir = run_backtest(config)
    summary_path = output_dir / "summary.json"
    weights_path = output_dir / "weights_suggestion.json"
    windows_path = output_dir / "windows.csv"

    assert summary_path.exists()
    assert weights_path.exists()
    assert windows_path.exists()

    summary = json.loads(summary_path.read_text())
    assert summary["config"]["k"] == 5
    assert summary["metrics"]["gem_score"]["precision_at_k"]["mean"] > 0.5

    weights = json.loads(weights_path.read_text())
    assert weights["weights"]["technicals"] == 0.35
