"""Signal reporting utilities for BounceHunter."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List

import pandas as pd


@dataclass(slots=True)
class SignalReport:
    """Serializable representation of a bounce candidate."""

    ticker: str
    date: str
    close: float
    z_score: float
    rsi2: float
    dist_200dma: float
    probability: float
    entry: float
    stop: float
    target: float
    adv_usd: float
    notes: str = ""

    def as_dict(self) -> Dict[str, float | str]:
        data = asdict(self)
        # round floats for readability
        for key, value in list(data.items()):
            if isinstance(value, float):
                data[key] = round(value, 4)
        return data

    @staticmethod
    def to_frame(reports: Iterable["SignalReport"]) -> pd.DataFrame:
        rows: List[Dict[str, float | str]] = [signal.as_dict() for signal in reports]
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df = df.sort_values("probability", ascending=False).reset_index(drop=True)
        return df
