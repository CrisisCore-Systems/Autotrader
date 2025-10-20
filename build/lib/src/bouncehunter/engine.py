"""Core scanning engine for BounceHunter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import math
import warnings

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit

from .config import BounceHunterConfig
from .report import SignalReport


_FEATURE_COLUMNS = [
    "z5",
    "rsi2",
    "bb_dev",
    "dist_200",
    "trend_63",
    "gap_dn",
    "vix_regime",
]


@dataclass(slots=True)
class TrainingArtifact:
    ticker: str
    history: pd.DataFrame
    features: pd.DataFrame


class BounceHunter:
    """Scanner that scores mean-reversion opportunities."""

    def __init__(self, config: Optional[BounceHunterConfig] = None) -> None:
        self.config = config or BounceHunterConfig()
        self._model: Optional[CalibratedClassifierCV] = None
        self._artifacts: Dict[str, TrainingArtifact] = {}
        self._vix_cache: Optional[pd.Series] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fit(self) -> pd.DataFrame:
        """Download data, build features, and train the probability model."""

        datasets: List[pd.DataFrame] = []
        self._artifacts.clear()

        for ticker in self.config.tickers:
            history = self._download_history(ticker)
            if history is None:
                continue
            if not self._passes_universe_filters(history):
                continue
            feats = self._label_events(history)
            if feats.empty or len(feats) < self.config.min_event_samples:
                continue
            feats = feats.assign(ticker=ticker)
            datasets.append(feats)
            self._artifacts[ticker] = TrainingArtifact(ticker, history, feats)

        if not datasets:
            raise RuntimeError("No instruments satisfied the training filters")

        train_df = pd.concat(datasets, ignore_index=True)
        self._model = self._train_classifier(train_df)
        return train_df

    def scan(self, as_of: Optional[pd.Timestamp] = None) -> List[SignalReport]:
        """Produce candidate signals for the latest available session."""

        if not self._artifacts:
            raise RuntimeError("fit() must be called before scan().")
        if self._model is None:
            raise RuntimeError("Model has not been trained. Call fit() first.")

        reports: List[SignalReport] = []
        for ticker, artifact in self._artifacts.items():
            df = artifact.history
            if df.empty:
                continue
            as_of_ts = as_of or df.index[-1]
            if as_of_ts not in df.index:
                continue
            idx = df.index.get_loc(as_of_ts)
            if isinstance(idx, slice):
                idx = idx.stop - 1
            if idx < 0:
                continue
            today = df.iloc[idx]
            adv_usd = float((df["close"] * df["volume"]).rolling(21).mean().iloc[idx])
            if adv_usd < self.config.min_adv_usd:
                continue
            if not self._trigger_conditions(today):
                continue
            features = self._feature_vector(today)
            prob = float(self._model.predict_proba(features)[0, 1])
            if prob < self.config.bcs_threshold:
                continue
            if today["dist_200"] <= self.config.max_dist_200dma:
                continue
            report = SignalReport(
                ticker=ticker,
                date=str(as_of_ts.date()),
                close=float(today["close"]),
                z_score=float(today["z5"]),
                rsi2=float(today["rsi2"]),
                dist_200dma=float(today["dist_200"] * 100),
                probability=prob,
                entry=float(today["close"]),
                stop=round(float(today["close"] * (1.0 - self.config.stop_pct)), 2),
                target=round(float(today["close"] * (1.0 + self.config.rebound_pct)), 2),
                adv_usd=adv_usd,
                notes=self._notes(today),
            )
            reports.append(report)
        return reports

    # ------------------------------------------------------------------
    # Training helpers
    # ------------------------------------------------------------------
    def _train_classifier(self, train_df: pd.DataFrame) -> CalibratedClassifierCV:
        X = train_df[_FEATURE_COLUMNS].values
        y = train_df["label"].values
        base_model = LogisticRegression(
            max_iter=300,
            solver="lbfgs",
            class_weight="balanced",
        )
        splits = max(2, min(5, max(1, len(train_df) // 50)))
        cv = TimeSeriesSplit(n_splits=splits)
        calibrated = CalibratedClassifierCV(base_model, cv=cv, method="sigmoid")
        calibrated.fit(X, y)
        return calibrated

    # ------------------------------------------------------------------
    def _download_history(self, ticker: str) -> Optional[pd.DataFrame]:
        try:
            df = yf.download(
                ticker,
                start=self.config.start,
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:  # pragma: no cover - network errors
            warnings.warn(f"Failed to download {ticker}: {exc}")
            return None
        if df.empty:
            return None
        df = df.rename(columns=str.lower)
        df = df[~df.index.duplicated(keep="last")]
        df = df.loc[:, ["open", "high", "low", "close", "volume"]]
        df = df.dropna()
        if len(df) < 260:
            return None
        df = self._build_indicators(df)
        return df.dropna()

    def _build_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ret1"] = df["close"].pct_change()
        df["atr"] = self._average_true_range(df)
        df["rsi2"] = self._rsi(df["close"], window=2)
        bb_low = self._bollinger_lower(df["close"], window=20, k=2.0)
        df["bb_dev"] = (df["close"] - bb_low) / df["close"]
        df["ma200"] = df["close"].rolling(200).mean()
        df["dist_200"] = df["close"] / df["ma200"] - 1.0
        df["r5"] = df["close"].pct_change(5)
        vol = df["ret1"].rolling(60).std()
        df["z5"] = df["r5"] / (vol * math.sqrt(5))
        df["trend_63"] = df["close"].pct_change(63)
        df["gap_dn"] = df["open"] / df["close"].shift(1) - 1.0
        df["adv_usd"] = (df["close"] * df["volume"]).rolling(21).mean()
        vix = self._ensure_vix(df.index)
        df["vix_regime"] = vix.reindex(df.index).fillna(method="ffill").fillna(0.5)
        return df

    def _ensure_vix(self, index: pd.Index) -> pd.Series:
        if self._vix_cache is not None:
            return self._vix_cache
        try:
            raw = yf.download("^VIX", start=self.config.start, progress=False)
        except Exception:  # pragma: no cover - network dependent
            self._vix_cache = pd.Series(0.5, index=index)
            return self._vix_cache
        if raw.empty:
            self._vix_cache = pd.Series(0.5, index=index)
            return self._vix_cache
        closes = raw["Close"].copy()
        closes.index = pd.to_datetime(closes.index)
        percentile = closes.rolling(252, min_periods=40).apply(
            lambda window: pd.Series(window).rank(pct=True).iloc[-1]
        )
        percentile = percentile.fillna(0.5)
        self._vix_cache = percentile
        return percentile

    def _passes_universe_filters(self, df: pd.DataFrame) -> bool:
        config = self.config
        adv = float(df["adv_usd"].iloc[-1])
        if adv < config.min_adv_usd:
            return False
        if config.trailing_trend_window < len(df):
            trailing_ret = df["close"].iloc[-1] / df["close"].iloc[-config.trailing_trend_window] - 1.0
            if trailing_ret < config.trend_floor:
                return False
        window = min(config.falling_knife_lookback, len(df))
        recent = df.iloc[-window:]
        if (recent["dist_200"] < config.falling_knife_tolerance).mean() > 0.3:
            return False
        return True

    def _label_events(self, df: pd.DataFrame) -> pd.DataFrame:
        cfg = self.config
        events = df[(df["z5"] <= cfg.z_score_drop) & (df["rsi2"] <= cfg.rsi2_max)].copy()
        if events.empty:
            return pd.DataFrame(columns=_FEATURE_COLUMNS + ["label"])

        labels: List[int] = []
        for idx in events.index:
            entry = float(df.loc[idx, "close"])
            future = df.loc[idx:].iloc[1 : cfg.horizon_days + 1]
            if future.empty:
                labels.append(np.nan)
                continue
            min_draw = future["low"].min() / entry - 1.0
            hit_stop = min_draw <= -cfg.stop_pct
            target_gain = future["high"].max() / entry - 1.0
            hit_target = target_gain >= cfg.rebound_pct
            if hit_target and hit_stop:
                hit_target_day = future["high"].idxmax()
                hit_stop_day = future["low"].idxmin()
                labels.append(int(hit_target_day <= hit_stop_day))
            else:
                labels.append(int(hit_target and not hit_stop))

        events = events.assign(label=labels)
        events = events.dropna(subset=["label"])
        if events.empty:
            return pd.DataFrame(columns=_FEATURE_COLUMNS + ["label"])
        features = events[_FEATURE_COLUMNS].copy()
        features["label"] = events["label"].astype(int)
        return features

    # ------------------------------------------------------------------
    def _trigger_conditions(self, today: pd.Series) -> bool:
        cfg = self.config
        if not (today["z5"] <= cfg.z_score_drop and today["rsi2"] <= cfg.rsi2_max):
            return False
        if today["dist_200"] <= cfg.max_dist_200dma:
            return False
        return True

    def _feature_vector(self, row: pd.Series) -> np.ndarray:
        vector = row[_FEATURE_COLUMNS].values.astype(np.float64)
        return vector.reshape(1, -1)

    def _notes(self, today: pd.Series) -> str:
        notes: List[str] = []
        if today["trend_63"] < 0:
            notes.append("weak 3M trend")
        if today["vix_regime"] > 0.75:
            notes.append("high VIX regime")
        return "; ".join(notes)

    # ------------------------------------------------------------------
    @staticmethod
    def _average_true_range(df: pd.DataFrame, window: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return true_range.rolling(window).mean()

    @staticmethod
    def _rsi(series: pd.Series, window: int) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1 / window, min_periods=window).mean()
        avg_loss = loss.ewm(alpha=1 / window, min_periods=window).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _bollinger_lower(series: pd.Series, window: int, k: float) -> pd.Series:
        sma = series.rolling(window).mean()
        std = series.rolling(window).std()
        return sma - k * std
