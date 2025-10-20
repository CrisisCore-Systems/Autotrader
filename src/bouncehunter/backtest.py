"""Walk-forward backtesting utilities for BounceHunter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

import numpy as np
import pandas as pd

from .config import BounceHunterConfig
from .engine import BounceHunter, TrainingArtifact


@dataclass(slots=True)
class TradeRecord:
    ticker: str
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    return_pct: float
    hold_days: int
    hit_target: bool
    hit_stop: bool
    probability: float
    z_score: float
    rsi2: float

    def as_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "entry_date": self.entry_date.date().isoformat(),
            "exit_date": self.exit_date.date().isoformat(),
            "entry_price": round(self.entry_price, 4),
            "exit_price": round(self.exit_price, 4),
            "return_pct": round(self.return_pct, 4),
            "hold_days": int(self.hold_days),
            "hit_target": self.hit_target,
            "hit_stop": self.hit_stop,
            "probability": round(self.probability, 4),
            "z_score": round(self.z_score, 4),
            "rsi2": round(self.rsi2, 2),
        }


@dataclass(slots=True)
class BacktestMetrics:
    total_trades: int
    win_rate: float
    avg_return: float
    expectancy: float
    cumulative_return: float
    max_drawdown: float
    profit_factor: float
    average_hold: float

    def as_dict(self) -> dict[str, float]:
        return {
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "avg_return": round(self.avg_return, 4),
            "expectancy": round(self.expectancy, 4),
            "cumulative_return": round(self.cumulative_return, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "profit_factor": round(self.profit_factor, 4),
            "average_hold": round(self.average_hold, 2),
        }


@dataclass(slots=True)
class BacktestResult:
    trades: List[TradeRecord]
    metrics: BacktestMetrics

    def trades_frame(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame()
        return pd.DataFrame([trade.as_dict() for trade in self.trades])

    def summary_frame(self) -> pd.DataFrame:
        return pd.DataFrame([self.metrics.as_dict()])


class BounceHunterBacktester:
    """Walk-forward simulator that repeatedly retrains BounceHunter."""

    def __init__(
        self,
        config: Optional[BounceHunterConfig] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_training_events: int = 0,
    ) -> None:
        self.config = config or BounceHunterConfig()
        self.start_date = pd.Timestamp(start_date) if start_date else None
        self.end_date = pd.Timestamp(end_date) if end_date else None
        self.max_training_events = max_training_events
        self._engine = BounceHunter(self.config)

    def run(self) -> BacktestResult:
        self._engine.fit()
        trades: List[TradeRecord] = []
        for ticker, artifact in self._engine._artifacts.items():
            trades.extend(self._backtest_ticker(ticker, artifact))
        metrics = self._compute_metrics(trades)
        return BacktestResult(trades=trades, metrics=metrics)

    # ------------------------------------------------------------------
    def _backtest_ticker(self, ticker: str, artifact: TrainingArtifact) -> List[TradeRecord]:
        df = artifact.history
        features = artifact.features
        cfg = self.config
        trades: List[TradeRecord] = []
        dates = self._eligible_dates(df.index)
        for current_date in dates:
            if current_date not in df.index:
                continue
            today = df.loc[current_date]
            if cfg.skip_earnings and bool(today.get("near_earnings", False)):
                continue
            if not self._engine._trigger_conditions(today):
                continue
            past_events = features.loc[features.index < current_date]
            if self.max_training_events > 0:
                past_events = past_events.iloc[-self.max_training_events :]
            if len(past_events) < cfg.min_event_samples:
                continue
            try:
                model = self._engine._train_classifier(past_events)
            except ValueError:
                continue
            prob = float(model.predict_proba(self._engine._feature_vector(today))[0, 1])
            if prob < cfg.bcs_threshold:
                continue
            trade = self._simulate_trade(ticker, current_date, today, df)
            if trade:
                trade.probability = prob
                trade.z_score = float(today["z5"])
                trade.rsi2 = float(today["rsi2"])
                trades.append(trade)
        return trades

    def _eligible_dates(self, index: pd.Index) -> Sequence[pd.Timestamp]:
        start = self.start_date or index[0]
        end = self.end_date or index[-1]
        mask = (index >= start) & (index <= end)
        return list(index[mask])

    def _simulate_trade(
        self,
        ticker: str,
        entry_date: pd.Timestamp,
        today: pd.Series,
        history: pd.DataFrame,
    ) -> Optional[TradeRecord]:
        cfg = self.config
        future = history.loc[entry_date:].iloc[1 : cfg.horizon_days + 1]
        if future.empty:
            return None
        entry_price = float(today["close"])
        target_price = entry_price * (1.0 + cfg.rebound_pct)
        stop_price = entry_price * (1.0 - cfg.stop_pct)
        hit_target_date = self._first_cross(future["high"], target_price, greater=True)
        hit_stop_date = self._first_cross(future["low"], stop_price, greater=False)
        exit_date, exit_price, hit_target, hit_stop = self._resolve_exit(
            future,
            entry_price,
            target_price,
            stop_price,
            hit_target_date,
            hit_stop_date,
        )
        if exit_date is None:
            exit_date = future.index[-1]
            exit_price = float(future["close"].iloc[-1])
            hit_target = False
            hit_stop = False
        return_pct = (exit_price / entry_price) - 1.0
        hold_days = len(history.loc[entry_date:exit_date]) - 1
        return TradeRecord(
            ticker=ticker,
            entry_date=entry_date,
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            return_pct=return_pct,
            hold_days=hold_days,
            hit_target=hit_target,
            hit_stop=hit_stop,
            probability=0.0,
            z_score=float(today["z5"]),
            rsi2=float(today["rsi2"]),
        )

    @staticmethod
    def _first_cross(series: pd.Series, threshold: float, *, greater: bool) -> Optional[pd.Timestamp]:
        comparator = (series >= threshold) if greater else (series <= threshold)
        matches = series[comparator]
        if matches.empty:
            return None
        return matches.index[0]

    @staticmethod
    def _resolve_exit(
        future: pd.DataFrame,
        entry_price: float,
        target_price: float,
        stop_price: float,
        target_date: Optional[pd.Timestamp],
        stop_date: Optional[pd.Timestamp],
    ) -> tuple[Optional[pd.Timestamp], Optional[float], bool, bool]:
        if target_date is None and stop_date is None:
            return None, None, False, False
        if target_date is not None and stop_date is not None:
            if target_date <= stop_date:
                return target_date, target_price, True, False
            return stop_date, stop_price, False, True
        if target_date is not None:
            return target_date, target_price, True, False
        return stop_date, stop_price, False, True

    def _compute_metrics(self, trades: Iterable[TradeRecord]) -> BacktestMetrics:
        trades_list = list(trades)
        if not trades_list:
            return BacktestMetrics(
                total_trades=0,
                win_rate=0.0,
                avg_return=0.0,
                expectancy=0.0,
                cumulative_return=0.0,
                max_drawdown=0.0,
                profit_factor=0.0,
                average_hold=0.0,
            )
        returns = np.array([trade.return_pct for trade in trades_list], dtype=float)
        wins = returns[returns > 0]
        losses = returns[returns <= 0]
        win_rate = float(len(wins) / len(returns)) if len(returns) else 0.0
        avg_return = float(returns.mean())
        expectancy = float((wins.mean() if len(wins) else 0.0) * win_rate + (losses.mean() if len(losses) else 0.0) * (1 - win_rate))
        cumulative_return = float(np.prod(1 + returns) - 1.0)
        equity_curve = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(equity_curve)
        drawdowns = 1 - equity_curve / running_max
        max_drawdown = float(np.nanmax(drawdowns)) if len(drawdowns) else 0.0
        gross_profit = float(np.sum(wins)) if len(wins) else 0.0
        gross_loss = float(np.sum(-losses)) if len(losses) else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
        avg_hold = float(np.mean([trade.hold_days for trade in trades_list]))
        return BacktestMetrics(
            total_trades=len(trades_list),
            win_rate=win_rate,
            avg_return=avg_return,
            expectancy=expectancy,
            cumulative_return=cumulative_return,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            average_hold=avg_hold,
        )
