"""Backtest harness scaffold for GemScore evaluation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import pandas as pd

from src.core.scoring import compute_gem_score


@dataclass
class TokenSnapshot:
    token: str
    date: pd.Timestamp
    features: Dict[str, float]
    future_return_7d: float


@dataclass
class BacktestResult:
    precision_at_k: float
    average_return_at_k: float
    flagged_assets: List[str]


def load_snapshots(path: Path) -> Iterable[TokenSnapshot]:
    """Load token snapshots from CSV file."""

    df = pd.read_csv(path, parse_dates=["date"])
    feature_cols = [col for col in df.columns if col.startswith("f_")]
    for _, row in df.iterrows():
        features = {col.replace("f_", ""): row[col] for col in feature_cols}
        yield TokenSnapshot(
            token=row["token"],
            date=row["date"],
            features=features,
            future_return_7d=row["future_return_7d"],
        )


def evaluate_period(snapshots: Iterable[TokenSnapshot], top_k: int = 10) -> BacktestResult:
    """Compute precision@K and average return for flagged assets."""

    scored = []
    for snapshot in snapshots:
        result = compute_gem_score(snapshot.features)
        scored.append((snapshot, result.score))

    scored.sort(key=lambda item: item[1], reverse=True)
    top_assets = scored[:top_k]
    flagged_returns = [snap.future_return_7d for snap, _ in top_assets]
    positives = [r for r in flagged_returns if r > 0]

    precision_at_k = len(positives) / max(1, top_k)
    average_return_at_k = float(pd.Series(flagged_returns).mean()) if flagged_returns else 0.0

    return BacktestResult(
        precision_at_k=precision_at_k,
        average_return_at_k=average_return_at_k,
        flagged_assets=[snap.token for snap, _ in top_assets],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="GemScore backtest harness")
    parser.add_argument("data", type=Path, help="Path to CSV with features")
    parser.add_argument("--top-k", type=int, default=10)
    args = parser.parse_args()

    snapshots = list(load_snapshots(args.data))
    result = evaluate_period(snapshots, top_k=args.top_k)
    print("Precision@K:", round(result.precision_at_k, 3))
    print("Average Return@K:", round(result.average_return_at_k, 3))
    print("Flagged Assets:", ", ".join(result.flagged_assets))


if __name__ == "__main__":
    main()
