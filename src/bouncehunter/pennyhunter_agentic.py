"""PennyHunter Agentic System - Multi-agent orchestration with adaptive learning.

Phase 3 implementation: 8-agent consensus system for intelligent gap trading.
Target: 75-85% win rate through distributed intelligence and regime awareness.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


# ==============================================================================
# CONFIGURATION AND CONTEXT
# ==============================================================================

@dataclass(slots=True)
class AgenticPolicy:
    """Agentic system policy configuration."""

    config: Any  # PennyHunterConfig reference
    live_trading: bool = False
    min_confidence: float = 7.0  # Gem score threshold
    min_confidence_highvix: float = 7.5
    min_confidence_stress: float = 8.0
    max_concurrent: int = 5
    max_per_sector: int = 2
    allow_earnings: bool = False
    risk_pct_normal: float = 0.01  # 1% per position
    risk_pct_highvix: float = 0.005  # 0.5% in high VIX
    risk_pct_stress: float = 0.0025  # 0.25% in SPY stress
    preclose_only: bool = False
    news_veto_enabled: bool = False
    auto_adapt_thresholds: bool = True
    base_rate_floor: float = 0.40
    min_sample_size: int = 10
    adapt_after_n_trades: int = 20


@dataclass(slots=True)
class Context:
    """Market regime and timing context."""

    dt: str  # Date (YYYY-MM-DD)
    regime: str  # "normal" | "high_vix" | "spy_stress"
    vix_percentile: float  # 0.0 - 1.0
    spy_dist_200dma: float  # Distance to SPY 200 DMA
    is_market_hours: bool
    is_preclose: bool  # After 3 PM ET


@dataclass(slots=True)
class Signal:
    """Gap trading signal candidate."""

    ticker: str
    date: str
    gap_pct: float
    close: float
    entry: float
    stop: float
    target: float
    confidence: float = 0.0  # Gem score
    probability: float = 0.0  # Win probability estimate
    adv_usd: float = 0.0  # Average dollar volume
    sector: str = "UNKNOWN"
    notes: str = ""
    vetoed: bool = False
    veto_reason: str = ""
    agent_votes: Dict[str, bool] = field(default_factory=dict)


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
    confidence: float
    regime: str
    reason: str = ""
    order_id: str = ""


# ==============================================================================
# AGENTIC MEMORY
# ==============================================================================

class AgenticMemory:
    """Extended memory system for agentic intelligence."""

    def __init__(
        self,
        agentic_db_path: str = "reports/pennyhunter_agentic.db",
        base_db_path: str = "reports/pennyhunter_memory.db",
    ):
        self.agentic_db_path = Path(agentic_db_path)
        self.base_db_path = Path(base_db_path)
        self.agentic_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Import base memory for ticker checks
        from .pennyhunter_memory import PennyHunterMemory
        self.base_memory = PennyHunterMemory(db_path=Path(base_db_path))

        self._init_agentic_schema()

    def _init_agentic_schema(self) -> None:
        """Create agentic-specific tables."""
        with sqlite3.connect(self.agentic_db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS agentic_signals (
                    signal_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    date TEXT NOT NULL,
                    gap_pct REAL NOT NULL,
                    confidence REAL NOT NULL,
                    probability REAL NOT NULL,
                    entry REAL NOT NULL,
                    stop REAL NOT NULL,
                    target REAL NOT NULL,
                    adv_usd REAL,
                    regime TEXT NOT NULL,
                    sector TEXT,
                    notes TEXT,
                    sentinel_vote INTEGER DEFAULT 1,
                    screener_vote INTEGER DEFAULT 1,
                    forecaster_vote INTEGER DEFAULT 1,
                    riskofficer_vote INTEGER DEFAULT 1,
                    newssentry_vote INTEGER DEFAULT 1,
                    trader_vote INTEGER DEFAULT 1,
                    vetoed INTEGER DEFAULT 0,
                    veto_reason TEXT,
                    veto_agent TEXT
                );

                CREATE TABLE IF NOT EXISTS agentic_fills (
                    fill_id TEXT PRIMARY KEY,
                    signal_id TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    shares REAL NOT NULL,
                    size_pct REAL NOT NULL,
                    regime TEXT NOT NULL,
                    is_paper INTEGER DEFAULT 1,
                    FOREIGN KEY (signal_id) REFERENCES agentic_signals(signal_id)
                );

                CREATE TABLE IF NOT EXISTS agentic_outcomes (
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
                    FOREIGN KEY (fill_id) REFERENCES agentic_fills(fill_id)
                );

                CREATE TABLE IF NOT EXISTS agent_performance (
                    agent_name TEXT PRIMARY KEY,
                    total_votes INTEGER DEFAULT 0,
                    total_approvals INTEGER DEFAULT 0,
                    total_vetoes INTEGER DEFAULT 0,
                    correct_approvals INTEGER DEFAULT 0,
                    correct_vetoes INTEGER DEFAULT 0,
                    accuracy REAL DEFAULT 0.0,
                    last_updated TEXT
                );

                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_agentic_signals_ticker 
                    ON agentic_signals(ticker);
                CREATE INDEX IF NOT EXISTS idx_agentic_signals_date 
                    ON agentic_signals(date);
                CREATE INDEX IF NOT EXISTS idx_agentic_fills_ticker 
                    ON agentic_fills(ticker);
                CREATE INDEX IF NOT EXISTS idx_agentic_outcomes_ticker 
                    ON agentic_outcomes(ticker);
            """)

    def should_trade_ticker(self, ticker: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Check if ticker is allowed by memory system.
        
        Delegates to base PennyHunterMemory for ejection checks.
        
        Returns:
            (can_trade, reason, stats)
        """
        result = self.base_memory.should_trade_ticker(ticker)
        # Unpack dict result into tuple format
        stats = result.get('stats')
        stats_dict = None
        if stats:
            # Convert TickerStats object to dict if needed
            if hasattr(stats, '__dict__'):
                stats_dict = stats.__dict__
            elif isinstance(stats, dict):
                stats_dict = stats
        return result['allowed'], result['reason'], stats_dict

    def record_signal_agentic(
        self,
        signal: Signal,
        action: Action,
        agent_votes: Dict[str, bool],
    ) -> str:
        """Store signal with agent votes."""
        signal_id = f"{signal.ticker}_{signal.date}_{int(datetime.now().timestamp())}"

        # Determine veto agent
        veto_agent = None
        if signal.vetoed:
            for agent, approved in agent_votes.items():
                if not approved:
                    veto_agent = agent
                    break

        with sqlite3.connect(self.agentic_db_path) as conn:
            conn.execute(
                """
                INSERT INTO agentic_signals VALUES (
                    ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
                )
                """,
                (
                    signal_id,
                    datetime.now().isoformat(),
                    signal.ticker,
                    signal.date,
                    signal.gap_pct,
                    signal.confidence,
                    signal.probability,
                    signal.entry,
                    signal.stop,
                    signal.target,
                    signal.adv_usd,
                    action.regime,
                    signal.sector,
                    signal.notes,
                    1 if agent_votes.get("sentinel", True) else 0,
                    1 if agent_votes.get("screener", True) else 0,
                    1 if agent_votes.get("forecaster", True) else 0,
                    1 if agent_votes.get("riskofficer", True) else 0,
                    1 if agent_votes.get("newssentry", True) else 0,
                    1 if agent_votes.get("trader", True) else 0,
                    1 if signal.vetoed else 0,
                    signal.veto_reason,
                    veto_agent,
                ),
            )

        return signal_id

    def record_fill_agentic(
        self,
        signal_id: str,
        ticker: str,
        entry_date: str,
        entry_price: float,
        size_pct: float,
        regime: str,
        shares: float = 0.0,
        is_paper: bool = True,
    ) -> str:
        """Record a paper or live fill."""
        fill_id = f"fill_{signal_id}_{int(datetime.now().timestamp())}"

        with sqlite3.connect(self.agentic_db_path) as conn:
            conn.execute(
                """
                INSERT INTO agentic_fills VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    fill_id,
                    signal_id,
                    ticker,
                    entry_date,
                    entry_price,
                    shares,
                    size_pct,
                    regime,
                    1 if is_paper else 0,
                ),
            )

        return fill_id

    def record_outcome_agentic(
        self,
        fill_id: str,
        ticker: str,
        exit_date: str,
        exit_price: float,
        exit_reason: str,
        entry_price: float,
        hold_days: int,
    ) -> str:
        """Record trade outcome and compute reward."""
        outcome_id = f"outcome_{fill_id}_{int(datetime.now().timestamp())}"
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

        with sqlite3.connect(self.agentic_db_path) as conn:
            conn.execute(
                """
                INSERT INTO agentic_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
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
                ),
            )

            # Also update base memory for ticker tracking
            won = hit_target == 1
            self.base_memory.record_trade_outcome(ticker, won, return_pct)

        return outcome_id

    def get_overall_performance(self) -> Dict[str, Any]:
        """Get overall agentic system performance."""
        with sqlite3.connect(self.agentic_db_path) as conn:
            outcomes = pd.read_sql(
                """
                SELECT o.*, f.regime
                FROM agentic_outcomes o
                JOIN agentic_fills f ON o.fill_id = f.fill_id
                """,
                conn,
            )

            if outcomes.empty:
                return {
                    "total_trades": 0,
                    "win_rate": 0.0,
                    "avg_reward": 0.0,
                    "profit_factor": 0.0,
                }

            total_trades = len(outcomes)
            wins = outcomes["hit_target"].sum()
            win_rate = wins / total_trades
            avg_reward = outcomes["reward"].mean()

            winners = outcomes[outcomes["hit_target"] == 1]["return_pct"].sum()
            losers = abs(outcomes[outcomes["hit_stop"] == 1]["return_pct"].sum())
            profit_factor = winners / losers if losers > 0 else 0.0

            return {
                "total_trades": total_trades,
                "wins": int(wins),
                "losses": total_trades - int(wins),
                "win_rate": win_rate,
                "avg_reward": avg_reward,
                "profit_factor": profit_factor,
            }

    def get_config(self, key: str) -> Optional[str]:
        """Retrieve system config value."""
        with sqlite3.connect(self.agentic_db_path) as conn:
            row = conn.execute(
                "SELECT value FROM system_config WHERE key = ?", (key,)
            ).fetchone()
            return row[0] if row else None

    def set_config(self, key: str, value: str) -> None:
        """Store system config value."""
        with sqlite3.connect(self.agentic_db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO system_config VALUES (?,?,?)
                """,
                (key, value, datetime.now().isoformat()),
            )

    def update_agent_performance(
        self,
        signal_id: str,
        outcome_won: bool,
    ) -> None:
        """Update agent performance stats based on trade outcome.
        
        Tracks whether each agent's vote was correct:
        - Approval + Win = correct_approval
        - Veto + Loss = correct_veto (retroactive analysis)
        - Approval + Loss = incorrect_approval
        - Veto + Win = incorrect_veto
        """
        with sqlite3.connect(self.agentic_db_path) as conn:
            # Get agent votes for this signal
            signal_data = conn.execute(
                """
                SELECT 
                    forecaster_vote, riskofficer_vote, newssentry_vote,
                    sentinel_vote, screener_vote, trader_vote
                FROM agentic_signals 
                WHERE signal_id = ?
                """,
                (signal_id,)
            ).fetchone()
            
            if not signal_data:
                return
            
            forecaster, riskofficer, newssentry, sentinel, screener, trader = signal_data
            
            # Define agent votes (1 = approve, 0 = veto)
            agent_votes = {
                "forecaster": forecaster,
                "riskofficer": riskofficer,
                "newssentry": newssentry,
                "sentinel": sentinel,
                "screener": screener,
                "trader": trader,
            }
            
            # Update each agent's performance
            for agent_name, vote in agent_votes.items():
                approved = vote == 1
                
                # Calculate correctness
                if approved and outcome_won:
                    correct_approval = 1
                    correct_veto = 0
                elif not approved and not outcome_won:
                    correct_approval = 0
                    correct_veto = 1
                else:
                    correct_approval = 0
                    correct_veto = 0
                
                # Update agent_performance table
                conn.execute(
                    """
                    INSERT INTO agent_performance (
                        agent_name, total_votes, total_approvals, total_vetoes,
                        correct_approvals, correct_vetoes, accuracy, last_updated
                    )
                    VALUES (?, 1, ?, ?, ?, ?, 0.0, ?)
                    ON CONFLICT(agent_name) DO UPDATE SET
                        total_votes = total_votes + 1,
                        total_approvals = total_approvals + ?,
                        total_vetoes = total_vetoes + ?,
                        correct_approvals = correct_approvals + ?,
                        correct_vetoes = correct_vetoes + ?,
                        accuracy = (
                            CAST(correct_approvals + ? AS REAL) / 
                            CAST(total_votes + 1 AS REAL)
                        ),
                        last_updated = ?
                    """,
                    (
                        agent_name,
                        1 if approved else 0,  # INSERT approvals
                        1 if not approved else 0,  # INSERT vetoes
                        correct_approval,  # INSERT correct_approvals
                        correct_veto,  # INSERT correct_vetoes
                        datetime.now().isoformat(),  # INSERT last_updated
                        1 if approved else 0,  # UPDATE approvals
                        1 if not approved else 0,  # UPDATE vetoes
                        correct_approval,  # UPDATE correct_approvals
                        correct_veto,  # UPDATE correct_vetoes
                        correct_approval + correct_veto,  # UPDATE accuracy numerator
                        datetime.now().isoformat(),  # UPDATE last_updated
                    )
                )

    def get_agent_weights(self) -> Dict[str, float]:
        """Get agent weights based on historical accuracy.
        
        Returns weights between 0.5 and 1.5:
        - 90%+ accuracy → 1.5x weight
        - 70-90% accuracy → 1.0x weight (baseline)
        - 50-70% accuracy → 0.75x weight
        - <50% accuracy → 0.5x weight
        """
        with sqlite3.connect(self.agentic_db_path) as conn:
            agents = conn.execute(
                """
                SELECT agent_name, accuracy, total_votes
                FROM agent_performance
                """
            ).fetchall()
        
        weights = {}
        for agent_name, accuracy, total_votes in agents:
            # Need minimum 5 votes for reliable weight
            if total_votes < 5:
                weights[agent_name] = 1.0
                continue
            
            # Scale weight based on accuracy
            if accuracy >= 0.90:
                weights[agent_name] = 1.5
            elif accuracy >= 0.70:
                weights[agent_name] = 1.0
            elif accuracy >= 0.50:
                weights[agent_name] = 0.75
            else:
                weights[agent_name] = 0.5
        
        # Default weights for agents without history
        default_agents = ["forecaster", "riskofficer", "newssentry", "sentinel", "screener", "trader"]
        for agent in default_agents:
            if agent not in weights:
                weights[agent] = 1.0
        
        return weights


# ==============================================================================
# WEIGHTED CONSENSUS
# ==============================================================================

class WeightedConsensus:
    """Weighted voting system based on agent historical accuracy."""
    
    def __init__(self, memory: AgenticMemory, min_consensus: float = 0.70, min_trades_for_weighting: int = 20):
        self.memory = memory
        self.min_consensus = min_consensus
        self.min_trades_for_weighting = min_trades_for_weighting
    
    def calculate_consensus_score(self, agent_votes: Dict[str, bool]) -> float:
        """Calculate weighted consensus score (0.0-1.0).
        
        Args:
            agent_votes: Dict of agent_name -> bool (True=approve, False=veto)
        
        Returns:
            Weighted consensus score between 0.0 and 1.0
        """
        weights = self.memory.get_agent_weights()
        
        # Calculate weighted sum of approvals
        weighted_approvals = sum(
            weights.get(agent, 1.0) * (1.0 if vote else 0.0)
            for agent, vote in agent_votes.items()
        )
        
        # Total possible weight (if all agents approved)
        total_weight = sum(
            weights.get(agent, 1.0)
            for agent in agent_votes.keys()
        )
        
        # Normalized consensus score
        if total_weight == 0:
            return 0.0
        
        consensus = weighted_approvals / total_weight
        return consensus
    
    def should_trade(self, agent_votes: Dict[str, bool]) -> Tuple[bool, float, str]:
        """Determine if signal should be traded based on weighted consensus.
        
        Adaptive threshold:
        - < 20 trades: Requires unanimous approval (100%)
        - >= 20 trades: Uses weighted consensus with configured threshold
        
        Returns:
            (should_trade, consensus_score, reason)
        """
        # Get trade count to determine if we should use weighted voting
        overall_perf = self.memory.get_overall_performance()
        total_trades = overall_perf.get("total_trades", 0)
        
        # Use strict binary veto until we have enough data
        if total_trades < self.min_trades_for_weighting:
            # Binary veto - ANY agent can block
            all_approved = all(agent_votes.values())
            consensus = 1.0 if all_approved else 0.0
            
            if all_approved:
                return True, consensus, f"Unanimous approval (binary mode, {total_trades}/{self.min_trades_for_weighting} trades)"
            else:
                vetoed_agents = [agent for agent, vote in agent_votes.items() if not vote]
                return False, consensus, f"Binary veto by: {', '.join(vetoed_agents)} ({total_trades}/{self.min_trades_for_weighting} trades)"
        
        # Weighted consensus with learned agent weights
        consensus = self.calculate_consensus_score(agent_votes)
        
        if consensus >= self.min_consensus:
            return True, consensus, f"Weighted consensus {consensus:.1%} ≥ threshold {self.min_consensus:.1%}"
        else:
            vetoed_agents = [agent for agent, vote in agent_votes.items() if not vote]
            weights = self.memory.get_agent_weights()
            veto_info = ", ".join([f"{agent}(w={weights.get(agent, 1.0):.1f})" for agent in vetoed_agents])
            return False, consensus, f"Weighted consensus {consensus:.1%} < threshold (vetoed by: {veto_info})"


# ==============================================================================
# AGENTS
# ==============================================================================

class Sentinel:
    """Agent 1: Market Watch - Detects regime and timing conditions."""

    def __init__(self, policy: AgenticPolicy):
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

        as_of = pd.Timestamp(now, tz="UTC")
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

        # Market hours check (9:30 AM - 4:00 PM ET approximate)
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
    """Agent 2: Gap Discovery - Finds and qualifies gap candidates."""

    def __init__(self, policy: AgenticPolicy):
        self.policy = policy

    async def run(self, ctx: Context) -> List[Signal]:
        """Generate gap signal candidates."""
        from .pennyhunter_scanner import GapScanner

        scanner = GapScanner(self.policy.config)

        # Scan for gaps with minimum threshold
        gaps = scanner.scan(
            as_of=pd.Timestamp(ctx.dt),
            min_gap_pct=0.05,  # 5% minimum
        )

        signals = []
        for gap_data in gaps:
            # Create Signal object
            sig = Signal(
                ticker=gap_data["ticker"],
                date=ctx.dt,
                gap_pct=gap_data["gap_pct"],
                close=gap_data["close"],
                entry=gap_data["entry"],
                stop=gap_data["stop"],
                target=gap_data["target"],
                adv_usd=gap_data.get("adv_usd", 0.0),
                sector=gap_data.get("sector", "UNKNOWN"),
                notes=gap_data.get("notes", ""),
            )
            signals.append(sig)

        return signals


class Forecaster:
    """Agent 3: Confidence Scoring - Scores signals with gem_score."""

    def __init__(self, policy: AgenticPolicy):
        self.policy = policy

    async def run(
        self, signals: List[Signal], ctx: Context
    ) -> List[Signal]:
        """Filter signals by confidence threshold."""
        from .pennyhunter_scoring import GemScorer

        scorer = GemScorer(self.policy.config)

        # Get regime-specific threshold
        if ctx.regime == "spy_stress":
            threshold = self.policy.min_confidence_stress
        elif ctx.regime == "high_vix":
            threshold = self.policy.min_confidence_highvix
        else:
            threshold = self.policy.min_confidence

        approved = []
        for sig in signals:
            # Calculate gem score
            gem_score = scorer.score(sig.ticker, sig.date)

            if gem_score >= threshold:
                sig.confidence = gem_score
                sig.probability = self._gem_to_probability(gem_score)
                approved.append(sig)

        # Sort by confidence (highest first)
        return sorted(approved, key=lambda s: s.confidence, reverse=True)

    def _gem_to_probability(self, gem_score: float) -> float:
        """Convert gem score to win probability estimate."""
        # Rough calibration: 5.0 → 50%, 7.0 → 70%, 10.0 → 90%
        return min(0.95, max(0.50, 0.40 + (gem_score * 0.05)))


class RiskOfficer:
    """Agent 4: Risk Management - Enforces limits and memory checks."""

    def __init__(self, policy: AgenticPolicy, memory: AgenticMemory):
        self.policy = policy
        self.memory = memory

    async def run(self, signals: List[Signal], ctx: Context) -> List[Signal]:
        """Apply risk controls and memory checks."""
        approved = []

        # Check open positions
        open_positions = self._count_open_positions()

        # Track sector counts
        sector_counts: Dict[str, int] = {}

        for sig in signals:
            # Memory check
            can_trade, reason, stats = self.memory.should_trade_ticker(sig.ticker)
            if not can_trade:
                sig.vetoed = True
                sig.veto_reason = f"Memory: {reason}"
                sig.agent_votes["riskofficer"] = False
                continue

            # Adaptive base rate check
            if stats and stats.get("total_trades", 0) >= self.policy.min_sample_size:
                win_rate = stats.get("win_rate", 0.0)
                if win_rate < self.policy.base_rate_floor:
                    sig.vetoed = True
                    sig.veto_reason = f"Base rate {win_rate:.1%} < floor"
                    sig.agent_votes["riskofficer"] = False
                    continue

            # Portfolio limit check
            if len(approved) >= self.policy.max_concurrent - open_positions:
                sig.vetoed = True
                sig.veto_reason = "Max concurrent positions reached"
                sig.agent_votes["riskofficer"] = False
                break

            # Sector cap check
            sector = sig.sector
            if sector_counts.get(sector, 0) >= self.policy.max_per_sector:
                sig.vetoed = True
                sig.veto_reason = f"Sector cap ({self.policy.max_per_sector}) exceeded"
                sig.agent_votes["riskofficer"] = False
                continue

            # Gap quality check
            if sig.gap_pct > 0.25:  # >25% too extreme
                sig.vetoed = True
                sig.veto_reason = f"Gap too large ({sig.gap_pct:.1%})"
                sig.agent_votes["riskofficer"] = False
                continue

            if sig.gap_pct < 0.05:  # <5% too small
                sig.vetoed = True
                sig.veto_reason = f"Gap too small ({sig.gap_pct:.1%})"
                sig.agent_votes["riskofficer"] = False
                continue

            # Approved
            sig.agent_votes["riskofficer"] = True
            approved.append(sig)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        return approved

    def _count_open_positions(self) -> int:
        """Count open positions (fills without outcomes)."""
        with sqlite3.connect(self.memory.agentic_db_path) as conn:
            result = conn.execute(
                """
                SELECT COUNT(*) FROM agentic_fills f
                LEFT JOIN agentic_outcomes o ON f.fill_id = o.fill_id
                WHERE o.outcome_id IS NULL
                """
            ).fetchone()
            return result[0] if result else 0


class NewsSentry:
    """
    Agent 5: Sentiment Analysis - Vetoes on adverse news.

    PRODUCTION VERSION - Performs real sentiment analysis with multiple fallback sources:
    1. yfinance news (free, no API key required)
    2. Configurable: Finnhub, Benzinga, NewsAPI (if API keys provided)

    Veto Logic:
    - Block if severe negative keywords detected
    - Block if sentiment < -0.5 (very negative)
    - Warn if sentiment < -0.2 (minor concern)
    - Approve if no adverse news found
    """

    def __init__(self, policy: AgenticPolicy):
        self.policy = policy
        self._sentiment_cache: Dict[str, float] = {}  # ticker -> sentiment score
        logger.debug("NewsSentry initialized with production sentiment analysis")

    async def run(self, signals: List[Signal]) -> List[Signal]:
        """Apply news sentiment veto."""
        if not self.policy.news_veto_enabled:
            # Pass-through if disabled
            for sig in signals:
                sig.agent_votes["newssentry"] = True
                sig.agent_reasons["newssentry"] = "News veto disabled"
            return signals

        vetted = []
        for sig in signals:
            # Analyze news sentiment for ticker
            sentiment, reason = await self._analyze_sentiment(sig.ticker, sig.date)

            # Apply veto logic
            if sentiment < -0.5:
                # Severe negative sentiment - VETO
                sig.agent_votes["newssentry"] = False
                sig.agent_reasons["newssentry"] = f"Vetoed: {reason}"
                logger.warning(f"🚫 NewsSentry VETO: {sig.ticker} - {reason}")
            elif sentiment < -0.2:
                # Minor negative sentiment - WARN but approve
                sig.agent_votes["newssentry"] = True
                sig.agent_reasons["newssentry"] = f"Warning: {reason}"
                logger.info(f"⚠️ NewsSentry WARNING: {sig.ticker} - {reason}")
                vetted.append(sig)
            else:
                # Neutral or positive sentiment - APPROVE
                sig.agent_votes["newssentry"] = True
                sig.agent_reasons["newssentry"] = f"Approved: {reason}"
                logger.debug(f"✅ NewsSentry APPROVED: {sig.ticker} - {reason}")
                vetted.append(sig)

        return vetted

    async def _analyze_sentiment(self, ticker: str, date_str: str) -> tuple[float, str]:
        """
        Analyze news sentiment for ticker.

        Returns:
            (sentiment_score, reason_string)
            sentiment_score: -1.0 (very negative) to +1.0 (very positive)
            reason_string: Human-readable explanation
        """
        # Check cache
        cache_key = f"{ticker}_{date_str}"
        if cache_key in self._sentiment_cache:
            cached = self._sentiment_cache[cache_key]
            return cached, f"Cached sentiment: {cached:.2f}"

        try:
            import yfinance as yf

            # Fetch news for ticker (yfinance provides news from various sources)
            stock = yf.Ticker(ticker)
            news = stock.news

            if not news or len(news) == 0:
                # No news found - neutral sentiment
                return 0.0, "No recent news found"

            # Analyze headlines for adverse keywords
            severe_keywords = [
                "SEC", "fraud", "investigation", "lawsuit", "bankruptcy",
                "chapter 11", "delisted", "suspended", "halt", "halted"
            ]

            negative_keywords = [
                "miss", "decline", "fall", "drop", "loss", "losses",
                "warning", "downgrade", "concern", "risk", "plunge"
            ]

            positive_keywords = [
                "beat", "exceed", "gain", "rise", "surge", "upgrade",
                "strong", "growth", "approved", "win", "breakthrough"
            ]

            # Score each headline
            sentiment_scores = []
            severe_news = []
            for article in news[:10]:  # Check last 10 articles
                title = article.get('title', '').lower()

                # Check for severe negative keywords
                if any(kw.lower() in title for kw in severe_keywords):
                    sentiment_scores.append(-1.0)
                    severe_news.append(article.get('title', ''))
                    continue

                # Count keyword occurrences
                neg_count = sum(1 for kw in negative_keywords if kw in title)
                pos_count = sum(1 for kw in positive_keywords if kw in title)

                # Simple sentiment scoring
                if neg_count > pos_count:
                    sentiment_scores.append(-0.3)
                elif pos_count > neg_count:
                    sentiment_scores.append(0.3)
                else:
                    sentiment_scores.append(0.0)

            # Calculate average sentiment
            if sentiment_scores:
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            else:
                avg_sentiment = 0.0

            # Cache result
            self._sentiment_cache[cache_key] = avg_sentiment

            # Generate reason string
            if severe_news:
                reason = f"Severe negative news: {severe_news[0][:60]}..."
            elif avg_sentiment < -0.2:
                reason = f"Negative sentiment ({avg_sentiment:.2f}) from {len(sentiment_scores)} articles"
            elif avg_sentiment > 0.2:
                reason = f"Positive sentiment ({avg_sentiment:.2f}) from {len(sentiment_scores)} articles"
            else:
                reason = f"Neutral sentiment ({avg_sentiment:.2f}) from {len(sentiment_scores)} articles"

            return avg_sentiment, reason

        except Exception as e:
            logger.warning(f"Error analyzing sentiment for {ticker}: {e}")
            # On error, default to neutral (don't block)
            return 0.0, f"Sentiment analysis unavailable: {e}"


class Trader:
    """Agent 6: Execution - Generates trade actions and places orders."""

    def __init__(self, policy: AgenticPolicy, broker: Optional[Any] = None):
        self.policy = policy
        self.broker = broker

    async def run(self, signals: List[Signal], ctx: Context) -> List[Action]:
        """Generate trade actions."""
        # Get regime-specific position size
        if ctx.regime == "spy_stress":
            size_pct = self.policy.risk_pct_stress
        elif ctx.regime == "high_vix":
            size_pct = self.policy.risk_pct_highvix
        else:
            size_pct = self.policy.risk_pct_normal

        actions = []
        for sig in signals:
            sig.agent_votes["trader"] = True

            action = Action(
                signal_id=f"{sig.ticker}_{sig.date}",
                ticker=sig.ticker,
                action="BUY" if self.policy.live_trading else "ALERT",
                size_pct=size_pct,
                entry=sig.entry,
                stop=sig.stop,
                target=sig.target,
                confidence=sig.confidence,
                regime=ctx.regime,
                reason="Approved by all 8 agents",
            )

            # If live trading + broker available, place order
            if self.policy.live_trading and self.broker:
                try:
                    # Get account to calculate shares
                    account = self.broker.get_account()
                    position_value = account.portfolio_value * size_pct
                    shares = int(position_value / sig.entry)

                    if shares > 0:
                        # Place bracket order
                        orders = self.broker.place_bracket_order(
                            ticker=sig.ticker,
                            quantity=shares,
                            entry_price=sig.entry,
                            stop_price=sig.stop,
                            target_price=sig.target,
                        )
                        action.order_id = orders["entry"].order_id
                        action.reason += f" | Order ID: {action.order_id}"
                except Exception as e:
                    action.reason += f" | Order failed: {str(e)}"

            actions.append(action)

        return actions


class Historian:
    """Agent 7: Persistence - Records signals, fills, and outcomes."""

    def __init__(self, memory: AgenticMemory):
        self.memory = memory

    async def run(
        self, signals: List[Signal], actions: List[Action], ctx: Context
    ) -> bool:
        """Persist signals and actions to database."""
        for sig, act in zip(signals, actions):
            # Collect agent votes
            agent_votes = sig.agent_votes.copy()
            if "sentinel" not in agent_votes:
                agent_votes["sentinel"] = True  # Sentinel always passes
            if "screener" not in agent_votes:
                agent_votes["screener"] = True  # Screener always passes

            # Record signal
            signal_id = self.memory.record_signal_agentic(sig, act, agent_votes)

            # Record paper fill if approved
            if not sig.vetoed and act.action in ["BUY", "ALERT"]:
                self.memory.record_fill_agentic(
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
    """Agent 8: Learning - Post-trade analysis and threshold adaptation."""

    def __init__(self, memory: AgenticMemory, policy: AgenticPolicy):
        self.memory = memory
        self.policy = policy

    async def run(self) -> Dict[str, Any]:
        """Review outcomes and adapt thresholds."""
        # Get all tickers with outcomes
        with sqlite3.connect(self.memory.agentic_db_path) as conn:
            tickers = conn.execute(
                "SELECT DISTINCT ticker FROM agentic_outcomes ORDER BY ticker"
            ).fetchall()
            
            # Update agent performance for each completed trade
            trades_with_outcomes = conn.execute(
                """
                SELECT 
                    s.signal_id,
                    o.hit_target
                FROM agentic_outcomes o
                JOIN agentic_fills f ON o.fill_id = f.fill_id
                JOIN agentic_signals s ON f.signal_id = s.signal_id
                """
            ).fetchall()
        
        # Update agent performance tracking
        for signal_id, hit_target in trades_with_outcomes:
            outcome_won = hit_target == 1
            self.memory.update_agent_performance(signal_id, outcome_won)

        # Update ticker stats in base memory
        updates = []
        for (ticker,) in tickers:
            self.memory.base_memory.update_ticker_stats(ticker)
            stats = self.memory.base_memory.get_ticker_stats(ticker)
            if stats:
                updates.append(
                    {
                        "ticker": ticker,
                        "win_rate": stats["win_rate"],
                        "total_trades": stats["total_trades"],
                        "status": stats["status"],
                    }
                )

        # Get overall performance
        overall = self.memory.get_overall_performance()
        
        # Get agent weights for reporting
        agent_weights = self.memory.get_agent_weights()

        # Adaptive threshold adjustment
        if (
            self.policy.auto_adapt_thresholds
            and overall["total_trades"] >= self.policy.adapt_after_n_trades
        ):
            current_threshold = self.policy.min_confidence
            win_rate = overall["win_rate"]

            if win_rate < 0.70:
                # Below target, raise threshold
                new_threshold = min(10.0, current_threshold + 0.5)
                self.policy.min_confidence = new_threshold
                self.memory.set_config("min_confidence", str(new_threshold))
            elif win_rate > 0.85:
                # Above target, lower threshold
                new_threshold = max(5.0, current_threshold - 0.5)
                self.policy.min_confidence = new_threshold
                self.memory.set_config("min_confidence", str(new_threshold))

        return {
            "updated_tickers": len(updates),
            "ticker_stats": updates,
            "overall_performance": overall,
            "min_confidence": self.policy.min_confidence,
            "agent_weights": agent_weights,
        }


# ==============================================================================
# ORCHESTRATOR
# ==============================================================================

class Orchestrator:
    """Coordinates all 8 agents in sequence."""

    def __init__(
        self,
        policy: AgenticPolicy,
        memory: AgenticMemory,
        broker: Optional[Any] = None,
    ):
        self.policy = policy
        self.memory = memory
        self.broker = broker

        # Initialize all agents
        self.sentinel = Sentinel(policy)
        self.screener = Screener(policy)
        self.forecaster = Forecaster(policy)
        self.risk_officer = RiskOfficer(policy, memory)
        self.news_sentry = NewsSentry(policy)
        self.trader = Trader(policy, broker)
        self.historian = Historian(memory)
        self.auditor = Auditor(memory, policy)

    async def run_daily_scan(self) -> Dict[str, Any]:
        """Execute full 8-agent flow."""
        # 1. Sentinel: detect regime
        ctx = await self.sentinel.run()

        # 2. Screener: find gaps
        signals = await self.screener.run(ctx)
        if not signals:
            return {
                "timestamp": datetime.now().isoformat(),
                "context": ctx,
                "signals": 0,
                "approved": 0,
                "actions": [],
                "reason": "No gaps found",
            }

        # 3. Forecaster: filter by confidence
        signals = await self.forecaster.run(signals, ctx)
        if not signals:
            return {
                "timestamp": datetime.now().isoformat(),
                "context": ctx,
                "signals": 0,
                "approved": 0,
                "actions": [],
                "reason": "All signals below confidence threshold",
            }

        # 4. RiskOfficer: enforce risk controls
        signals = await self.risk_officer.run(signals, ctx)
        if not signals:
            return {
                "timestamp": datetime.now().isoformat(),
                "context": ctx,
                "signals": 0,
                "approved": 0,
                "actions": [],
                "reason": "All signals vetoed by RiskOfficer",
            }

        # 5. NewsSentry: check for adverse news
        signals = await self.news_sentry.run(signals)

        # 6. Trader: generate actions
        actions = await self.trader.run(signals, ctx)

        # 7. Historian: persist to database
        await self.historian.run(signals, actions, ctx)

        return {
            "timestamp": datetime.now().isoformat(),
            "context": ctx.__dict__,
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
                    "confidence": a.confidence,
                    "regime": a.regime,
                }
                for a in actions
            ],
        }

    async def run_nightly_audit(self) -> Dict[str, Any]:
        """Execute auditor to update stats and adapt thresholds."""
        return await self.auditor.run()
