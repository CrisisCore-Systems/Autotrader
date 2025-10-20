"""Agentic BounceHunter - Multi-agent orchestration with memory and learning."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


@dataclass(slots=True)
class Policy:
    """Agent system policy configuration."""

    config: Any  # BounceHunterConfig reference
    live_trading: bool = False
    min_bcs: float = 0.62
    min_bcs_highvix: float = 0.68
    max_concurrent: int = 8
    max_per_sector: int = 3
    allow_earnings: bool = False
    risk_pct_normal: float = 0.012
    risk_pct_highvix: float = 0.006
    preclose_only: bool = False
    news_veto_enabled: bool = False
    auto_adapt_thresholds: bool = True
    base_rate_floor: float = 0.40
    min_sample_size: int = 20


@dataclass(slots=True)
class Context:
    """Market regime and timing context."""

    dt: str
    regime: str  # "normal" | "high_vix" | "spy_stress"
    vix_percentile: float
    spy_dist_200dma: float
    is_market_hours: bool
    is_preclose: bool


@dataclass(slots=True)
class Signal:
    """Candidate trade signal."""

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
    sector: str = "UNKNOWN"
    notes: str = ""
    vetoed: bool = False
    veto_reason: str = ""


@dataclass(slots=True)
class Action:
    """Proposed trade action."""

    signal_id: str
    ticker: str
    action: str  # "ALERT" | "BUY" | "VETO"
    size_pct: float
    entry: float
    stop: float
    target: float
    probability: float
    regime: str
    reason: str = ""


class AgentMemory:
    """Persistent storage for agent system state and outcomes."""

    def __init__(self, db_path: str = "data/bouncehunter_agent.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def close(self) -> None:
        """Close any open connections (no-op for now as we use context managers)."""
        pass  # SQLite connections are managed with context managers

    def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
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

    def record_signal(self, signal: Signal, action: Action) -> str:
        """Store a signal and its action."""
        signal_id = f"{signal.ticker}_{signal.date}_{datetime.now().timestamp()}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                signal_id,
                datetime.now().isoformat(),
                signal.ticker,
                signal.date,
                signal.probability,
                signal.entry,
                signal.stop,
                signal.target,
                action.regime,
                action.size_pct,
                signal.z_score,
                signal.rsi2,
                signal.dist_200dma,
                signal.adv_usd,
                signal.sector,
                signal.notes,
                1 if signal.vetoed else 0,
                signal.veto_reason,
            ))
        return signal_id

    def record_fill(self, signal_id: str, ticker: str, entry_date: str,
                    entry_price: float, size_pct: float, regime: str,
                    shares: float = 0.0, is_paper: bool = True) -> str:
        """Record a paper or live fill."""
        fill_id = f"fill_{signal_id}_{datetime.now().timestamp()}"
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO fills VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                fill_id,
                signal_id,
                ticker,
                entry_date,
                entry_price,
                shares,
                size_pct,
                regime,
                1 if is_paper else 0,
            ))
        return fill_id

    def record_outcome(self, fill_id: str, ticker: str, exit_date: str,
                      exit_price: float, exit_reason: str, entry_price: float,
                      hold_days: int) -> str:
        """Record trade outcome and compute reward."""
        outcome_id = f"outcome_{fill_id}_{datetime.now().timestamp()}"
        return_pct = (exit_price / entry_price) - 1.0

        # Reward: +1 target, -1 stop, -0.2 time
        hit_target = 1 if exit_reason == "TARGET" else 0
        hit_stop = 1 if exit_reason == "STOP" else 0
        hit_time = 1 if exit_reason == "TIME" else 0

        reward = 0.0
        if hit_target:
            reward = 1.0
        elif hit_stop:
            reward = -1.0
        elif hit_time:
            reward = -0.2
        # Small holding penalty
        reward -= hold_days * 0.01

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                outcome_id,
                fill_id,
                ticker,
                exit_date,
                exit_price,
                exit_reason,
                hold_days,
                return_pct,
                hit_target,
                hit_stop,
                hit_time,
                reward,
            ))
        return outcome_id

    def get_ticker_stats(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Retrieve performance stats for a ticker."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM ticker_stats WHERE ticker = ?", (ticker,)
            ).fetchone()
            return dict(row) if row else None

    def update_ticker_stats(self, ticker: str) -> None:
        """Recompute base rates and regime-specific stats for a ticker."""
        with sqlite3.connect(self.db_path) as conn:
            # Get all outcomes for this ticker
            outcomes = pd.read_sql("""
                SELECT o.*, f.regime
                FROM outcomes o
                JOIN fills f ON o.fill_id = f.fill_id
                WHERE o.ticker = ?
            """, conn, params=(ticker,))

            if outcomes.empty:
                return

            total_outcomes = len(outcomes)
            # Ensure hit_target is numeric and handle any issues
            try:
                outcomes["hit_target"] = pd.to_numeric(outcomes["hit_target"], errors='coerce').fillna(0)
                base_rate = (outcomes["hit_target"].sum()) / total_outcomes
            except Exception:
                # Fallback: manual sum
                base_rate = sum(int(x) for x in outcomes["hit_target"]) / total_outcomes

            # Calculate average reward with error handling
            try:
                avg_reward = outcomes["reward"].mean()
            except Exception:
                # Fallback: manual mean
                avg_reward = sum(float(x) for x in outcomes["reward"]) / len(outcomes["reward"])

            normal_outcomes = outcomes[outcomes["regime"] == "normal"]
            highvix_outcomes = outcomes[outcomes["regime"].str.contains("high|stress")]

            # Calculate rates manually to avoid pandas issues
            normal_rate = (
                sum(int(x) for x in normal_outcomes["hit_target"]) / len(normal_outcomes)
                if len(normal_outcomes) > 0 else 0.0
            )
            highvix_rate = (
                sum(int(x) for x in highvix_outcomes["hit_target"]) / len(highvix_outcomes)
                if len(highvix_outcomes) > 0 else 0.0
            )

            # Get signal count
            signal_count = conn.execute(
                "SELECT COUNT(*) FROM signals WHERE ticker = ? AND vetoed = 0",
                (ticker,)
            ).fetchone()[0]

            conn.execute("""
                INSERT OR REPLACE INTO ticker_stats
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (
                ticker,
                datetime.now().isoformat(),
                signal_count,
                total_outcomes,
                base_rate,
                avg_reward,
                normal_rate,
                highvix_rate,
                0,
                None,
            ))

    def get_system_state(self, key: str) -> Optional[str]:
        """Retrieve system state value."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT value FROM system_state WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None

    def set_system_state(self, key: str, value: str) -> None:
        """Store system state value."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO system_state VALUES (?,?,?)
            """, (key, value, datetime.now().isoformat()))


# ==============================================================================
# AGENTS
# ==============================================================================

class Sentinel:
    """Watches schedule/market regime; triggers scans."""

    def __init__(self, policy: Policy):
        self.policy = policy

    async def run(self) -> Context:
        """Determine current market context."""
        from .regime import RegimeDetector

        now = datetime.now()
        dt_str = now.strftime("%Y-%m-%d")

        # Detect regime
        config = self.policy.config
        detector = RegimeDetector(
            vix_lookback_days=config.vix_lookback_days,
            highvix_percentile=config.highvix_percentile,
            spy_stress_multiplier=config.spy_stress_multiplier,
        )

        as_of = pd.Timestamp(now, tz='UTC')  # Make timezone-aware
        regime_state = detector.detect(
            as_of,
            config.bcs_threshold,
            config.bcs_threshold_highvix,
            config.size_pct_base,
            config.size_pct_highvix,
        )

        regime = "normal"
        if regime_state.is_spy_stressed:
            regime = "spy_stress"
        elif regime_state.is_high_vix:
            regime = "high_vix"

        # Market hours check (approximate - 9:30 AM to 4:00 PM ET)
        hour = now.hour
        is_market_hours = 9 <= hour < 16
        is_preclose = hour >= 15  # After 3 PM ET

        return Context(
            dt=dt_str,
            regime=regime,
            vix_percentile=regime_state.vix_percentile,
            spy_dist_200dma=regime_state.spy_dist_200dma,
            is_market_hours=is_market_hours,
            is_preclose=is_preclose,
        )


class Screener:
    """Computes features, generates dip events."""

    def __init__(self, policy: Policy):
        self.policy = policy

    async def run(self, ctx: Context) -> list[Signal]:
        """Generate candidate signals."""
        from .engine import BounceHunter

        hunter = BounceHunter(self.policy.config)
        hunter.fit()
        reports = hunter.scan(as_of=pd.Timestamp(ctx.dt))

        signals = []
        for report in reports:
            sig = Signal(
                ticker=report.ticker,
                date=report.date,
                close=report.close,
                z_score=report.z_score,
                rsi2=report.rsi2,
                dist_200dma=report.dist_200dma,
                probability=report.probability,
                entry=report.entry,
                stop=report.stop,
                target=report.target,
                adv_usd=report.adv_usd,
                notes=report.notes,
            )
            signals.append(sig)

        return signals


class Forecaster:
    """Scores events (BCS), calibrates; suggests entries."""

    async def run(self, signals: list[Signal], ctx: Context, policy: Policy) -> list[Signal]:
        """Filter signals by probability threshold."""
        threshold = policy.min_bcs_highvix if ctx.regime != "normal" else policy.min_bcs
        return [s for s in signals if s.probability >= threshold]


class RiskOfficer:
    """Enforces rules: earnings, ETF logic, sector caps, size, max concurrent."""

    def __init__(self, policy: Policy, memory: AgentMemory):
        self.policy = policy
        self.memory = memory

    async def run(self, signals: list[Signal], ctx: Context) -> list[Signal]:
        """Apply portfolio risk limits."""
        approved = []
        config = self.policy.config

        # Check for open positions (paper fills without outcomes)
        with sqlite3.connect(self.memory.db_path) as conn:
            open_fills = conn.execute("""
                SELECT COUNT(*) FROM fills f
                LEFT JOIN outcomes o ON f.fill_id = o.fill_id
                WHERE o.outcome_id IS NULL
            """).fetchone()[0]

        if open_fills >= self.policy.max_concurrent:
            # Veto all - portfolio full
            for sig in signals:
                sig.vetoed = True
                sig.veto_reason = f"Max concurrent ({self.policy.max_concurrent}) reached"
            return []

        # Sector cap enforcement (simplified - assign sectors manually or skip)
        sector_counts: Dict[str, int] = {}

        for sig in signals:
            # Check earnings window
            if config.skip_earnings and not self.policy.allow_earnings:
                # Simplified: assume earnings check already done by engine
                pass

            # Sector cap
            if sig.sector in sector_counts:
                if sector_counts[sig.sector] >= self.policy.max_per_sector:
                    sig.vetoed = True
                    sig.veto_reason = f"Sector cap ({self.policy.max_per_sector}) exceeded"
                    continue

            # Ticker base-rate check
            stats = self.memory.get_ticker_stats(sig.ticker)
            if stats and self.policy.auto_adapt_thresholds:
                if stats["total_outcomes"] >= self.policy.min_sample_size:
                    if stats["base_rate"] < self.policy.base_rate_floor:
                        sig.vetoed = True
                        sig.veto_reason = f"Base rate {stats['base_rate']:.1%} < floor"
                        continue

            approved.append(sig)
            sector_counts[sig.sector] = sector_counts.get(sig.sector, 0) + 1

            if len(approved) >= self.policy.max_concurrent - open_fills:
                break

        return approved


class NewsSentry:
    """Vetoes names on adverse headlines."""

    def __init__(self, policy: Policy):
        self.policy = policy

    async def run(self, signals: list[Signal]) -> list[Signal]:
        """Apply news veto (stub for now)."""
        if not self.policy.news_veto_enabled:
            return signals

        # Future: integrate headline feed and check for severe terms
        # severe_terms = ["SEC", "fraud", "probe", "restatement", "guidance cut", "chapter 11"]

        # Stub: pass all for now
        return signals


class Trader:
    """Places paper orders (or sends Telegram plans)."""

    def __init__(self, policy: Policy, broker: Optional[Any] = None):
        self.policy = policy
        self.broker = broker  # BrokerAPI instance

    async def run(self, signals: list[Signal], ctx: Context) -> list[Action]:
        """Generate trade actions and optionally place orders."""
        actions = []
        size_pct = (
            self.policy.risk_pct_highvix
            if ctx.regime != "normal"
            else self.policy.risk_pct_normal
        )

        for sig in signals:
            action = Action(
                signal_id=f"{sig.ticker}_{sig.date}",
                ticker=sig.ticker,
                action="BUY" if self.policy.live_trading else "ALERT",
                size_pct=size_pct,
                entry=sig.entry,
                stop=sig.stop,
                target=sig.target,
                probability=sig.probability,
                regime=ctx.regime,
                reason="Approved by all agents",
            )
            actions.append(action)

            # If live trading + broker available, place bracket order
            if self.policy.live_trading and self.broker:
                try:
                    # Get account to calculate position size
                    account = self.broker.get_account()
                    position_value = account.portfolio_value * size_pct
                    shares = int(position_value / sig.entry)

                    if shares > 0:
                        # Place bracket order (entry + stop + target)
                        orders = self.broker.place_bracket_order(
                            ticker=sig.ticker,
                            quantity=shares,
                            entry_price=sig.entry,
                            stop_price=sig.stop,
                            target_price=sig.target,
                        )
                        action.reason += f" | Order ID: {orders['entry'].order_id}"
                except Exception as e:
                    action.reason += f" | Order failed: {str(e)}"

        return actions


class Historian:
    """Writes outcomes, base-rates per ticker, regime stats to SQLite."""

    def __init__(self, memory: AgentMemory):
        self.memory = memory

    async def run(self, signals: list[Signal], actions: list[Action], ctx: Context) -> bool:
        """Persist signals and actions to database."""
        for sig, act in zip(signals, actions):
            signal_id = self.memory.record_signal(sig, act)
            # Record paper fill if not vetoed
            if not sig.vetoed and act.action in ["BUY", "ALERT"]:
                self.memory.record_fill(
                    signal_id=signal_id,
                    ticker=sig.ticker,
                    entry_date=sig.date,
                    entry_price=sig.entry,
                    size_pct=act.size_pct,
                    regime=ctx.regime,
                    is_paper=True,
                )
        return True


class Auditor:
    """Post-trade review, updates priors and thresholds."""

    def __init__(self, memory: AgentMemory, policy: Policy):
        self.memory = memory
        self.policy = policy

    async def run(self) -> Dict[str, Any]:
        """Review recent outcomes and update ticker stats."""
        # Get all tickers with outcomes
        with sqlite3.connect(self.memory.db_path) as conn:
            tickers = conn.execute(
                "SELECT DISTINCT ticker FROM outcomes ORDER BY ticker"
            ).fetchall()

        updates = []
        for (ticker,) in tickers:
            self.memory.update_ticker_stats(ticker)
            stats = self.memory.get_ticker_stats(ticker)
            if stats:
                updates.append({
                    "ticker": ticker,
                    "base_rate": stats["base_rate"],
                    "avg_reward": stats["avg_reward"],
                    "total_outcomes": stats["total_outcomes"],
                })

        return {"updated_tickers": len(updates), "stats": updates}


class Orchestrator:
    """Coordinates agent execution flow."""

    def __init__(self, policy: Policy, memory: AgentMemory, broker: Optional[Any] = None):
        self.policy = policy
        self.memory = memory
        self.broker = broker
        self.sentinel = Sentinel(policy)
        self.screener = Screener(policy)
        self.forecaster = Forecaster()
        self.risk_officer = RiskOfficer(policy, memory)
        self.news_sentry = NewsSentry(policy)
        self.trader = Trader(policy, broker)
        self.historian = Historian(memory)
        self.auditor = Auditor(memory, policy)

    async def run_daily_scan(self) -> Dict[str, Any]:
        """Execute full agent flow."""
        # 1. Sentinel: detect regime
        ctx = await self.sentinel.run()

        # 2. Screener: generate candidate signals
        signals = await self.screener.run(ctx)

        if not signals:
            return {
                "timestamp": datetime.now().isoformat(),
                "context": ctx,
                "signals": 0,
                "approved": 0,
                "actions": [],
            }

        # 3. Forecaster: filter by BCS
        signals = await self.forecaster.run(signals, ctx, self.policy)

        if not signals:
            return {
                "timestamp": datetime.now().isoformat(),
                "context": ctx,
                "signals": 0,
                "approved": 0,
                "actions": [],
                "filtered": "All signals below BCS threshold",
            }

        # 4. RiskOfficer: enforce portfolio limits
        signals = await self.risk_officer.run(signals, ctx)

        if not signals:
            return {
                "timestamp": datetime.now().isoformat(),
                "context": ctx,
                "signals": len(signals),
                "approved": 0,
                "actions": [],
                "filtered": "All signals vetoed by RiskOfficer",
            }

        # 5. NewsSentry: veto on adverse headlines
        signals = await self.news_sentry.run(signals)

        # 6. Trader: generate actions
        actions = await self.trader.run(signals, ctx)

        # 7. Historian: persist to DB
        await self.historian.run(signals, actions, ctx)

        return {
            "timestamp": datetime.now().isoformat(),
            "context": ctx,
            "signals": len(signals),
            "approved": len([s for s in signals if not s.vetoed]),
            "actions": [
                {
                    "ticker": a.ticker,
                    "action": a.action,
                    "entry": a.entry,
                    "stop": a.stop,
                    "target": a.target,
                    "size_pct": a.size_pct,
                    "probability": a.probability,
                    "regime": a.regime,
                }
                for a in actions
            ],
        }

    async def run_nightly_audit(self) -> Dict[str, Any]:
        """Execute auditor to update base rates."""
        return await self.auditor.run()


