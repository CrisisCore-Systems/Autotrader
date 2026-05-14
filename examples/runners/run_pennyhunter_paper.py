#!/usr/bin/env python
"""
PennyHunter Paper Trading Runner

Runs PennyHunter scanner with Phase 1 enhancements, executes trades via paper broker,
and tracks results to validate win rate improvements.

Workflow:
1. Run scanner to find signals (with Phase 1 scoring)
2. Filter by market regime
3. Execute trades via PaperBroker
4. Monitor positions and exit at targets/stops
5. Log all trades and calculate statistics

Usage:
    python run_pennyhunter_paper.py
    python run_pennyhunter_paper.py --tickers SENS,SPCE,CLOV
    python run_pennyhunter_paper.py --account-size 200 --max-risk 5
"""

import sys
import argparse
import logging
from collections import OrderedDict
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import yaml
import json

# Resolve the repository root so direct script execution can import local packages.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from bouncehunter.broker import create_broker
from bouncehunter.agentic import AgentMemory, Signal as AgenticSignal, Action as AgenticAction
from bouncehunter.market_regime import MarketRegimeDetector, MarketRegime
from bouncehunter.signal_scoring import SignalScorer
from bouncehunter.penny_universe import PennyUniverse
from bouncehunter.advanced_filters import AdvancedRiskFilters
from bouncehunter.pennyhunter_memory import PennyHunterMemory
from bouncehunter.memory_tracker import MemoryTracker
from risk.regime_flip import RegimeFlip, RegimeInputs
from metrics.pnl import PnLTracker
import yfinance as yf

BLOCKLIST_FILE = PROJECT_ROOT / "configs" / "ticker_blocklist.txt"
RESULTS_HISTORY_FILE = PROJECT_ROOT / "reports" / "pennyhunter_cumulative_history.json"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
def deep_merge_dicts(base: Dict, override: Dict) -> Dict:
    """Recursively merge config dictionaries."""
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged

def load_config_file(config_path: Path) -> Dict:
    """Load YAML config with optional local-file inheritance via extends."""
    raw_config = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
    extends_value = raw_config.pop('extends', None)
    if not extends_value:
        return raw_config

    parent_path = (config_path.parent / extends_value).resolve()
    parent_config = load_config_file(parent_path)
    return deep_merge_dicts(parent_config, raw_config)


def load_tickers_from_file(file_path: Path) -> List[str]:
    """Load comma- or newline-delimited tickers from a text file."""
    content = file_path.read_text(encoding='utf-8')
    tickers = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        tickers.extend(item.strip().upper() for item in stripped.split(',') if item.strip())
    return tickers


def load_ticker_blocklist() -> set:
    """Load ticker blocklist from configs/ticker_blocklist.txt"""
    if not BLOCKLIST_FILE.exists():
        return set()
    
    blocklist = set()
    with open(BLOCKLIST_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if line.startswith('-'):
                    ticker = line.lstrip('- ').split('#')[0].strip()
                    if ticker:
                        blocklist.add(ticker.upper())
                else:
                    blocklist.add(line.upper())
    
    if blocklist:
        logger.info(f"📋 Loaded blocklist: {sorted(blocklist)}")
    
    return blocklist


class PennyHunterPaperTrader:
    """Paper trading system for PennyHunter"""

    def __init__(
        self,
        config: dict,
        account_size: float = 200.0,
        max_risk_per_trade: float = 5.0,
        history_file: Optional[Path] = None,
        penny_memory_db: Optional[Path] = None,
        agent_memory_db: Optional[Path] = None,
    ):
        self.config = config
        self.account_size = account_size
        self.max_risk_per_trade = max_risk_per_trade
        self.results_history_file = history_file or RESULTS_HISTORY_FILE
        
        # PHASE 2 OPTIMIZATION: Load ticker blocklist
        self.ticker_blocklist = load_ticker_blocklist()

        # Initialize components
        self.broker = create_broker("paper", initial_cash=account_size)

        regime_config = config.get('guards', {}).get('market_regime', {})
        if regime_config.get('enabled', False):
            self.regime_detector = MarketRegimeDetector(
                vix_low=regime_config.get('vix_thresholds', {}).get('low', 20),
                vix_medium=regime_config.get('vix_thresholds', {}).get('medium', 30),
                vix_high=regime_config.get('vix_thresholds', {}).get('high', 40),
                require_spy_above_ma=regime_config.get('require_spy_above_200ma', True),
                require_spy_green=regime_config.get('require_spy_green_day', False)
            )
        else:
            self.regime_detector = None

        min_score = config.get('signals', {}).get('runner_vwap', {}).get('min_signal_score', 7.0)
        # TEMPORARILY LOWERED for testing - Oct 2025 (normal: 7.0)
        min_score = 5.5
        self.scorer = SignalScorer(min_score_threshold=min_score)

        self.universe = PennyUniverse(config['universe'])

        # NEW: Advanced risk filters
        self.advanced_filters = AdvancedRiskFilters()
        self.advanced_filters_enabled = config.get('advanced_filters', {}).get('enabled', True)
        self.advanced_filter_config = self._build_advanced_filter_config(config)
        self.scan_filter_config = self._build_scan_filter_config(config)
        self.ticker_cooldown_config = self._build_ticker_cooldown_config(config)

        # NEW: Phase 2.5 Memory System
        self.memory = PennyHunterMemory(penny_memory_db)
        self.memory_enabled = config.get('memory', {}).get('enabled', True)
        logger.info(f"📊 Memory System: {'ENABLED' if self.memory_enabled else 'DISABLED'}")

        # Phase 2.5 richer tracking schema for signal quality and regime-aware outcomes
        self.agent_memory_db = agent_memory_db or (PROJECT_ROOT / "reports" / "bouncehunter_agent.db")
        self.agent_memory = AgentMemory(str(self.agent_memory_db))
        self.memory_tracker = MemoryTracker(str(self.agent_memory_db))
        logger.info(f"🧠 Agent memory tracking: {self.agent_memory_db}")

        # PHASE 2.5: RegimeFlip (optional hard regime gate)
        regime_flip_config = config.get('guards', {}).get('regime_flip', {})
        if regime_flip_config.get('enabled', False):
            self.regime_flip = RegimeFlip(
                vix_low=regime_flip_config.get('vix_low', 20.0),
                breadth_min=regime_flip_config.get('breadth_min', 0.55),
                volume_thrust_min=regime_flip_config.get('volume_thrust_min', 1.2),
                ret_5d_min=regime_flip_config.get('ret_5d_min', 0.01),
                require_confirmations=regime_flip_config.get('require_confirmations', 2)
            )
            logger.info(f"🔒 RegimeFlip: ENABLED (require {regime_flip_config.get('require_confirmations', 2)} confirmations)")
        else:
            self.regime_flip = None

        # Track trades
        self.trades_log = []
        self.rejected_signals = []
        self.scan_diagnostics = []
        self.cooldown_decisions = []
        self.active_positions = {}
        self.base_risk_per_trade = max_risk_per_trade
        self.current_risk_per_trade = max_risk_per_trade
        self.regime_snapshot: Optional[MarketRegime] = None

    def _record_scan_near_miss(self, ticker: str, current, gap_pct: float, vol_spike: float, reason: str, extra: Optional[Dict] = None) -> None:
        """Capture the latest near-miss per ticker during historical scan selection."""
        if any(item.get('ticker') == ticker for item in self.scan_diagnostics):
            return

        diagnostic = {
            'ticker': ticker,
            'date': current.name.strftime('%Y-%m-%d') if hasattr(current.name, 'strftime') else str(current.name),
            'gap_pct': float(gap_pct),
            'vol_spike': float(vol_spike),
            'reason': reason,
        }
        if extra:
            diagnostic.update(extra)
        self.scan_diagnostics.append(diagnostic)

    @staticmethod
    def _build_advanced_filter_config(config: Dict) -> Dict:
        """Resolve advanced quality-gate thresholds from YAML config."""
        advanced_filters = config.get('advanced_filters', {})
        return {
            'liquidity_delta_threshold': advanced_filters.get('liquidity_health', {}).get('delta_threshold_pct', -30.0),
            'max_slippage_pct': advanced_filters.get('slippage_control', {}).get('max_slippage_pct', 5.0),
            'min_cash_runway_months': advanced_filters.get('financial_health', {}).get('min_cash_runway_months', 6.0),
            'max_per_sector': advanced_filters.get('diversification', {}).get('max_per_sector', 3),
            'check_volume_fade': advanced_filters.get('breakout_quality', {}).get('check_volume_fade', True),
        }
    @staticmethod
    def _build_scan_filter_config(config: Dict) -> Dict:
        """Resolve historical scan thresholds from YAML config."""
        scan_filters = config.get('signals', {}).get('runner_vwap', {}).get('paper_scan', {})
        return {
            'gap_min_pct': float(scan_filters.get('gap_min_pct', 10.0)),
            'gap_max_pct': float(scan_filters.get('gap_max_pct', 15.0)),
            'volume_min_mult': float(scan_filters.get('volume_min_mult', 4.0)),
            'volume_max_mult': scan_filters.get('volume_max_mult', 10.0),
            'allow_extreme_volume_above_mult': scan_filters.get('allow_extreme_volume_above_mult', 15.0),
        }

    @staticmethod
    def _build_ticker_cooldown_config(config: Dict) -> Dict:
        """Resolve optional post-close ticker cooldown rules from YAML config."""
        cooldown = config.get('experiments', {}).get('ticker_cooldown', {})
        return {
            'enabled': bool(cooldown.get('enabled', False)),
            'mode': cooldown.get('mode', 'next_session_prefer_alternate'),
        }

    def _pending_cooldown_trade(self) -> Optional[Dict]:
        """Return the most recent closed trade whose next-session cooldown has not yet been consumed."""
        closed_trades = [
            trade for trade in self.trades_log
            if trade.get('status') == 'closed' and trade.get('ticker') and trade.get('exit_time')
        ]
        closed_trades.sort(
            key=lambda trade: (
                trade.get('exit_time') or '',
                trade.get('entry_time') or '',
                str(trade.get('signal_id') or trade.get('id') or ''),
            ),
            reverse=True,
        )

        for trade in closed_trades:
            exit_time = trade.get('exit_time') or ''
            trade_identity = (
                trade.get('signal_id'),
                trade.get('fill_id'),
                trade.get('entry_time'),
                trade.get('ticker'),
            )
            if any(
                (
                    candidate.get('signal_id'),
                    candidate.get('fill_id'),
                    candidate.get('entry_time'),
                    candidate.get('ticker'),
                ) != trade_identity
                and (candidate.get('entry_time') or '') > exit_time
                for candidate in self.trades_log
            ):
                continue
            return trade

        return None

    def apply_ticker_cooldown(self, signals: List[Dict]) -> List[Dict]:
        """Filter or suppress same-ticker re-entry for the next session after a close."""
        self.cooldown_decisions = []
        if not signals or not self.ticker_cooldown_config.get('enabled', False):
            return signals

        cooldown_trade = self._pending_cooldown_trade()
        if not cooldown_trade:
            return signals

        blocked_ticker = cooldown_trade['ticker']
        alternate_signals = [signal for signal in signals if signal.get('ticker') != blocked_ticker]
        blocked_signals = [signal for signal in signals if signal.get('ticker') == blocked_ticker]

        if not blocked_signals:
            return signals

        decision = {
            'mode': self.ticker_cooldown_config.get('mode'),
            'blocked_ticker': blocked_ticker,
            'trigger_trade': {
                'ticker': cooldown_trade.get('ticker'),
                'entry_time': cooldown_trade.get('entry_time'),
                'exit_time': cooldown_trade.get('exit_time'),
                'exit_reason': cooldown_trade.get('exit_reason'),
                'pnl': cooldown_trade.get('pnl'),
            },
            'eligible_tickers': [signal.get('ticker') for signal in signals],
            'blocked_candidates': [signal.get('ticker') for signal in blocked_signals],
            'reason': None,
        }

        if alternate_signals:
            decision['decision'] = 'prefer_alternate'
            decision['selected_tickers'] = [signal.get('ticker') for signal in alternate_signals]
            decision['reason'] = 'repeat_ticker_blocked_alternate_available'
            self.cooldown_decisions.append(decision)
            logger.info(
                "🧊 Cooldown blocks %s re-entry; preferring alternate ticker(s): %s",
                blocked_ticker,
                ', '.join(decision['selected_tickers']),
            )
            return alternate_signals

        decision['decision'] = 'skip_repeat_without_alternative'
        decision['selected_tickers'] = []
        decision['reason'] = 'repeat_ticker_suppressed_no_alternate'
        self.cooldown_decisions.append(decision)
        logger.info(
            "🧊 Cooldown blocks %s re-entry and no alternate ticker exists; skipping trade",
            blocked_ticker,
        )
        return []

    @staticmethod
    def _volume_rule_matches(vol_spike: float, scan_filters: Dict) -> bool:
        """Evaluate the configured scan volume rule."""
        volume_min = float(scan_filters.get('volume_min_mult', 4.0))
        volume_max = scan_filters.get('volume_max_mult')
        extreme_above = scan_filters.get('allow_extreme_volume_above_mult')

        if volume_max is None:
            return vol_spike >= volume_min

        volume_max = float(volume_max)
        if volume_min <= vol_spike <= volume_max:
            return True

        if extreme_above is not None and vol_spike >= float(extreme_above):
            return True

        return False

    @staticmethod
    def _parse_trade_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse stored trade timestamps when available."""
        if not value:
            return None

        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except ValueError:
            return None

    @staticmethod
    def _trade_signal_date(trade: Dict) -> Optional[str]:
        """Return the historical signal date when the trade carries one."""
        explicit = trade.get('signal_date') or trade.get('date')
        if explicit:
            return str(explicit)

        signal_id = str(trade.get('signal_id') or '')
        parts = signal_id.split('_')
        if len(parts) >= 3:
            candidate = parts[1]
            if len(candidate) == 10 and candidate.count('-') == 2:
                return candidate

        return None

    @classmethod
    def _trade_setup_key(cls, trade: Dict) -> str:
        """Build a stable identity for one historical setup across repeated runs."""
        ticker = str(trade.get('ticker') or 'UNKNOWN')
        signal_type = str(trade.get('signal_type') or 'UNKNOWN')
        signal_date = cls._trade_signal_date(trade)
        if signal_date:
            return f"{ticker}|{signal_type}|{signal_date}"

        entry_price = round(float(trade.get('entry_price', 0) or 0), 4)
        gap_pct = round(float(trade.get('gap_pct', 0) or 0), 2)
        vol_mult = round(float(trade.get('vol_mult', trade.get('vol_spike', 0)) or 0), 2)
        return f"{ticker}|{signal_type}|{entry_price}|{gap_pct}|{vol_mult}"

    @classmethod
    def _canonicalize_history(cls, history: Dict) -> Dict:
        """Collapse duplicate trade setups while preserving session markers."""
        markers = []
        deduped_trades: "OrderedDict[str, Dict]" = OrderedDict()

        for item in history.get('trades', []):
            if item.get('type') == 'session_marker':
                markers.append(item)
                continue
            deduped_trades[cls._trade_setup_key(item)] = item

        history['trades'] = markers + list(deduped_trades.values())
        return history

    def _signal_already_processed(self, ticker: str, signal_date: Optional[str]) -> bool:
        """Return True when a historical signal has already been traded in prior runs."""
        if not signal_date:
            return False

        expected_prefix = f"{ticker}_{signal_date}_"
        for trade in self.trades_log:
            if trade.get('ticker') != ticker:
                continue
            if trade.get('signal_date') == signal_date:
                return True
            signal_id = str(trade.get('signal_id') or '')
            if signal_id.startswith(expected_prefix):
                return True

        return False

    def _normalized_regime_label(self, regime: Optional[str]) -> str:
        """Normalize regime labels to the tracker's expected vocabulary."""
        normalized = str(regime or "normal").strip().lower()
        if normalized in {"high_vix", "highvix", "spy_stress"}:
            return "highvix"
        return "normal"

    def _classify_signal_quality(self, signal: Dict) -> str:
        """Classify the signal using the Phase 2.5 tracker heuristic."""
        return self.memory_tracker.classify_signal_quality(
            {
                'gap_pct': signal.get('gap_pct', 0),
                'volume_ratio': signal.get('vol_spike', signal.get('vol_mult', 0)),
                'regime': self._normalized_regime_label(
                    self.regime_snapshot.regime if self.regime_snapshot else signal.get('market_regime')
                ),
            }
        )

    def _record_phase25_signal(self, signal: Dict, trade: Dict) -> None:
        """Persist signal and fill data into the richer Phase 2.5 tracking schema."""
        quality = self._classify_signal_quality(signal)
        position_value = trade['shares'] * trade['entry_price']
        size_fraction = position_value / self.account_size if self.account_size else 0.0
        regime_label = self._normalized_regime_label(trade.get('market_regime'))

        agentic_signal = AgenticSignal(
            ticker=trade['ticker'],
            date=signal.get('date', datetime.now().strftime('%Y-%m-%d')),
            close=trade['entry_price'],
            z_score=0.0,
            rsi2=50.0,
            dist_200dma=0.0,
            probability=max(0.0, min(1.0, trade.get('score', 0.0) / 10.0)),
            entry=trade['entry_price'],
            stop=trade['stop_loss'],
            target=trade['take_profit'],
            adv_usd=position_value,
            notes=f"{trade['signal_type']} quality={quality}",
        )
        agentic_action = AgenticAction(
            signal_id="",
            ticker=trade['ticker'],
            action="BUY",
            size_pct=size_fraction,
            entry=trade['entry_price'],
            stop=trade['stop_loss'],
            target=trade['take_profit'],
            probability=agentic_signal.probability,
            regime=regime_label,
            reason=f"paper_runner:{trade['signal_type']}",
        )

        signal_id = self.agent_memory.record_signal(agentic_signal, agentic_action)
        fill_id = self.agent_memory.record_fill(
            signal_id=signal_id,
            ticker=trade['ticker'],
            entry_date=trade['entry_time'],
            entry_price=trade['entry_price'],
            size_pct=size_fraction,
            regime=regime_label,
            shares=trade['shares'],
            is_paper=True,
        )

        self.memory_tracker.log_signal_quality(
            signal_id=signal_id,
            ticker=trade['ticker'],
            quality=quality,
            gap_pct=trade.get('gap_pct', 0),
            volume_ratio=trade.get('vol_mult', 0),
            regime=regime_label,
            vix_level=trade.get('vix_level'),
            spy_state='GREEN' if self.regime_snapshot and self.regime_snapshot.spy_day_change_pct >= 0 else 'RED',
        )

        trade['signal_id'] = signal_id
        trade['fill_id'] = fill_id
        trade['signal_quality'] = quality

    def _record_phase25_outcome(self, trade: Dict) -> None:
        """Persist closed-trade outcome data into the richer Phase 2.5 tracking schema."""
        if trade.get('phase25_outcome_synced'):
            return

        fill_id = trade.get('fill_id')
        entry_price = trade.get('entry_price')
        exit_price = trade.get('exit_price', trade.get('exit'))
        exit_time = trade.get('exit_time')
        if not fill_id or entry_price in (None, 0) or exit_price in (None, 0) or not exit_time:
            return

        entry_dt = self._parse_trade_datetime(trade.get('entry_time'))
        exit_dt = self._parse_trade_datetime(exit_time)
        hold_days = 0
        if entry_dt and exit_dt:
            hold_days = max(0, (exit_dt - entry_dt).days)

        exit_reason = str(
            trade.get('exit_reason') or trade.get('outcome') or ('TARGET' if trade.get('pnl', 0) > 0 else 'STOP')
        ).upper()

        self.agent_memory.record_outcome(
            fill_id=fill_id,
            ticker=trade['ticker'],
            exit_date=exit_time,
            exit_price=float(exit_price),
            exit_reason=exit_reason,
            entry_price=float(entry_price),
            hold_days=hold_days,
        )
        self.memory_tracker.update_ticker_performance(trade['ticker'])
        trade['phase25_outcome_synced'] = True

    @staticmethod
    def _quality_gate_failures(quality_results: Dict) -> List[Dict]:
        """Extract only the failing quality-gate checks for reporting."""
        failures = []
        for check_name, check_data in quality_results.get('checks', {}).items():
            passed = check_data.get('passed', True)
            detected = check_data.get('detected', False)
            if not passed or detected:
                failures.append(
                    {
                        'check': check_name,
                        'reason': check_data.get('reason'),
                    }
                )
        return failures

    def _record_rejected_signal(self, signal: Dict, stage: str, reasons: List[Dict], details: Optional[Dict] = None) -> None:
        """Persist a rejected candidate so no-trade runs still leave a usable audit trail."""
        rejected = {
            'ticker': signal['ticker'],
            'signal_type': signal.get('signal_type'),
            'date': signal.get('date'),
            'price': signal.get('price'),
            'gap_pct': signal.get('gap_pct', 0),
            'vol_mult': signal.get('vol_mult', signal.get('vol_spike', 0)),
            'score': signal.get('score'),
            'stage': stage,
            'reasons': reasons,
            'recorded_at': datetime.now().isoformat(),
        }
        if details:
            rejected['details'] = details
        self.rejected_signals.append(rejected)

    def _load_cumulative_history(self) -> Dict:
        """Load or initialize cumulative PennyHunter session history."""
        if not self.results_history_file.exists():
            return {
                'first_trade_date': None,
                'last_updated': None,
                'total_sessions': 0,
                'trades': [],
                'metadata': {
                    'phase': '2',
                    'goal': 'Accumulate 20+ trades to validate 65-75% win rate',
                    'current_milestone': 'Phase 2 validation in progress',
                },
            }

        with open(self.results_history_file, 'r', encoding='utf-8') as f:
            history = json.load(f)

        return self._canonicalize_history(history)

    def _save_cumulative_history(self, history: Dict) -> None:
        """Persist cumulative PennyHunter session history."""
        self.results_history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.results_history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)

    def _append_session_history(self, report: Dict) -> None:
        """Append the latest paper-run audit to cumulative history."""
        history = self._load_cumulative_history()
        report_timestamp = report['generated_at']

        if not history['first_trade_date'] and report.get('trades'):
            history['first_trade_date'] = report_timestamp

        history['last_updated'] = report_timestamp
        history['total_sessions'] += 1
        session_id = history['total_sessions']

        history['trades'].append(
            {
                'session_id': session_id,
                'date': report_timestamp,
                'type': 'session_marker',
                'source': 'run_pennyhunter_paper',
                'trading_stats': report.get('trading_stats', {}),
                'rejected_signals': report.get('rejected_signals', []),
                'scan_near_misses': report.get('scan_near_misses', []),
                'cooldown_decisions': report.get('cooldown_decisions', []),
            }
        )

        trade_indexes = {
            self._trade_setup_key(trade): index
            for index, trade in enumerate(history['trades'])
            if trade.get('type') != 'session_marker'
        }

        for trade in report.get('trades', []):
            trade_record = dict(trade)
            trade_record['session_id'] = session_id
            trade_key = self._trade_setup_key(trade_record)
            existing_index = trade_indexes.get(trade_key)
            if existing_index is not None:
                history['trades'][existing_index] = trade_record
            else:
                history['trades'].append(trade_record)
                trade_indexes[trade_key] = len(history['trades']) - 1

        self._save_cumulative_history(self._canonicalize_history(history))

    @staticmethod
    def _latest_market_bar(ticker: str) -> Optional[Dict]:
        """Fetch the latest daily bar used for simple paper-trade reconciliation."""
        hist = yf.Ticker(ticker).history(period='5d', interval='1d')
        if hist is None or hist.empty:
            return None

        row = hist.iloc[-1]
        timestamp = hist.index[-1]
        return {
            'close': float(row['Close']),
            'low': float(row['Low']),
            'high': float(row['High']),
            'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
        }

    @staticmethod
    def _apply_exit_from_bar(trade: Dict, bar: Dict) -> bool:
        """Close an active trade if the latest bar breached stop or target."""
        if trade.get('status') != 'active':
            return False

        stop_loss = float(trade.get('stop_loss', 0) or 0)
        take_profit = float(trade.get('take_profit', 0) or 0)
        low = float(bar['low'])
        high = float(bar['high'])

        exit_reason = None
        exit_price = None
        if low <= stop_loss:
            exit_reason = 'STOP'
            exit_price = stop_loss
        elif high >= take_profit:
            exit_reason = 'TARGET'
            exit_price = take_profit

        if exit_reason is None:
            return False

        entry_price = float(trade.get('entry_price', 0) or 0)
        shares = float(trade.get('shares', 0) or 0)
        pnl = (exit_price - entry_price) * shares
        pnl_pct = ((exit_price / entry_price) - 1.0) * 100 if entry_price else 0.0

        trade['status'] = 'closed'
        trade['exit_time'] = bar['timestamp']
        trade['exit_price'] = exit_price
        trade['exit_reason'] = exit_reason
        trade['pnl'] = pnl
        trade['return_pct'] = pnl_pct
        trade['pnl_pct'] = pnl_pct
        trade['hold_days'] = max(0, (datetime.now() - datetime.fromisoformat(trade['entry_time'])).days) if trade.get('entry_time') else 0
        return True

    def load_existing_results(self, output_path: str) -> None:
        """Load the latest paper-trade report so active positions can be reconciled across runs."""
        output_file = Path(output_path)
        if not output_file.exists():
            return

        with open(output_file, 'r', encoding='utf-8') as f:
            report = json.load(f)

        self.trades_log = report.get('trades', [])
        self.rejected_signals = []
        self.cooldown_decisions = []
        self.active_positions = {
            trade['ticker']: trade
            for trade in self.trades_log
            if trade.get('status') == 'active' and trade.get('ticker')
        }

    def reconcile_active_positions(self) -> None:
        """Update persisted active positions against the latest market bar."""
        closed_tickers = []
        for ticker, trade in list(self.active_positions.items()):
            try:
                bar = self._latest_market_bar(ticker)
                if not bar:
                    continue
                if self._apply_exit_from_bar(trade, bar):
                    closed_tickers.append(ticker)
                    logger.info(
                        "🔄 Reconciled %s to %s at $%.2f based on latest bar",
                        ticker,
                        trade['exit_reason'],
                        trade['exit_price'],
                    )
            except Exception as exc:
                logger.error("Failed to reconcile %s: %s", ticker, exc, exc_info=True)

        for ticker in closed_tickers:
            self.active_positions.pop(ticker, None)

    def reconcile_cumulative_history(self) -> None:
        """Update historical active trades in cumulative history against the latest market bar."""
        history = self._load_cumulative_history()
        updated = False
        for trade in history.get('trades', []):
            if trade.get('type') == 'session_marker' or trade.get('status') != 'active' or not trade.get('ticker'):
                continue
            try:
                bar = self._latest_market_bar(trade['ticker'])
                if bar and self._apply_exit_from_bar(trade, bar):
                    updated = True
            except Exception as exc:
                logger.error("Failed to reconcile cumulative trade %s: %s", trade.get('ticker'), exc, exc_info=True)

        if updated:
            history['last_updated'] = datetime.now().isoformat()
            self._save_cumulative_history(history)

    def check_market_regime(self) -> bool:
        """Check if market regime allows penny trading"""
        if not self.regime_detector:
            logger.info("Market regime checking disabled")
            self.regime_snapshot = None
            self.current_risk_per_trade = self.base_risk_per_trade
            return True

        regime = self.refresh_regime(force_refresh=True)

        if regime is None:
            logger.warning("⚠️ Market regime unavailable, defaulting to trading allowed")
            self.current_risk_per_trade = self.base_risk_per_trade
            return True

        logger.info(
            "📊 Market Regime: %s | SPY Δ %.2f%% | VIX %.1f → %s",
            regime.regime.upper(),
            regime.spy_day_change_pct,
            regime.vix_level,
            "ALLOWED" if regime.allow_penny_trading else "BLOCKED",
        )

        if not regime.allow_penny_trading:
            logger.warning(f"⚠️ Reason: {regime.reason}")

        return regime.allow_penny_trading

    def refresh_regime(self, force_refresh: bool = False) -> Optional[MarketRegime]:
        """Refresh cached market regime snapshot and adjust risk budget."""
        if not self.regime_detector:
            self.regime_snapshot = None
            self.current_risk_per_trade = self.base_risk_per_trade
            return None

        try:
            regime = self.regime_detector.get_regime(force_refresh=force_refresh)
            self.regime_snapshot = regime

            vix = float(regime.vix_level or 20.0)
            self.current_risk_per_trade = self.dynamic_risk_per_trade(vix)

            return regime

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Failed to refresh market regime: %s", exc, exc_info=True)
            self.regime_snapshot = None
            self.current_risk_per_trade = self.base_risk_per_trade
            return None

    def check_regime_flip(self) -> bool:
        """
        Check RegimeFlip gate (optional hard regime confirmation).
        Returns True if trading allowed, False otherwise.
        """
        if not self.regime_flip:
            return True  # Not enabled, allow trading

        try:
            # Fetch VIX data
            vix_ticker = yf.Ticker("^VIX")
            vix_hist = vix_ticker.history(period="5d")
            if len(vix_hist) < 1:
                logger.warning("⚠️ RegimeFlip: VIX data unavailable, allowing trade")
                return True
            
            vix = vix_hist['Close'].iloc[-1]
            vix_ma3 = vix_hist['Close'].tail(3).mean() if len(vix_hist) >= 3 else None

            # Fetch SPY data for trend
            spy_ticker = yf.Ticker("SPY")
            spy_hist = spy_ticker.history(period="30d")
            
            spy_ma_fast = None
            spy_ma_slow = None
            spy_ret_5d = None
            
            if len(spy_hist) >= 20:
                spy_ma_fast = spy_hist['Close'].tail(10).mean()
                spy_ma_slow = spy_hist['Close'].tail(20).mean()
            
            if len(spy_hist) >= 5:
                spy_ret_5d = (spy_hist['Close'].iloc[-1] / spy_hist['Close'].iloc[-5] - 1)

            # Note: Breadth and adv/dec volume are optional and not easily available
            # The gate will work with just VIX and trend data
            inputs = RegimeInputs(
                vix=vix,
                vix_ma3=vix_ma3,
                spy_ret_5d=spy_ret_5d,
                spy_ma_fast=spy_ma_fast,
                spy_ma_slow=spy_ma_slow,
                breadth_above_20dma=None,  # Optional
                adv_volume=None,  # Optional
                dec_volume=None   # Optional
            )

            decision = self.regime_flip.decide(inputs)
            logger.info(f"🔒 RegimeFlip: allow_long={decision.allow_long} reason={decision.reason}")

            if not decision.allow_long:
                logger.warning(f"⚠️ RegimeFlip BLOCKS trading: {decision.reason}")

            return decision.allow_long

        except Exception as e:
            logger.error(f"RegimeFlip check failed: {e}", exc_info=True)
            logger.warning("⚠️ RegimeFlip: Error occurred, allowing trade (fail-soft)")
            return True

    def dynamic_risk_per_trade(self, vix: float) -> float:
        """
        Scale risk per trade based on VIX volatility.
        
        Args:
            vix: Current VIX level
            
        Returns:
            Scaled risk amount
        """
        # Scale risk down when VIX is high
        # Formula: base_risk * clamp(20 / max(10, vix), 0.5, 1.0)
        scale_factor = 20.0 / max(10.0, vix)
        scale_factor = max(0.5, min(1.0, scale_factor))

        scaled_risk = self.base_risk_per_trade * scale_factor

        if scale_factor < 1.0 or scale_factor > 1.0:
            logger.info(
                "📉 VIX=%.1f: Adjusting risk budget to $%.2f (factor=%.2f)",
                vix,
                scaled_risk,
                scale_factor,
            )

        return scaled_risk

    def scan_for_signals(self, tickers: List[str]) -> List[Dict]:
        """Scan tickers for high-scoring signals"""
        logger.info(f"🔍 Scanning {len(tickers)} tickers for signals...")
        self.scan_diagnostics = []

        regime = self.regime_snapshot or self.refresh_regime()
        spy_green = True
        vix_level = 20.0
        if regime:
            spy_green = regime.spy_day_change_pct >= 0
            vix_level = float(regime.vix_level or vix_level)

        logger.info(
            "🛰️  Regime context for scan: %s (SPY Δ %.2f%% | VIX %.1f)",
            regime.regime.upper() if regime else "UNKNOWN",
            regime.spy_day_change_pct if regime else 0.0,
            vix_level,
        )
        logger.info(
            "🧪 Scan thresholds: gap %.1f-%.1f%% | volume >= %.1fx%s",
            self.scan_filter_config['gap_min_pct'],
            self.scan_filter_config['gap_max_pct'],
            self.scan_filter_config['volume_min_mult'],
            "" if self.scan_filter_config.get('volume_max_mult') is None else f" and <= {float(self.scan_filter_config['volume_max_mult']):.1f}x or >= {float(self.scan_filter_config['allow_extreme_volume_above_mult']):.1f}x",
        )

        # Filter universe
        passed_tickers = self.universe.screen(tickers, lookback_days=10)
        logger.info(f"✅ {len(passed_tickers)} tickers passed universe filters")

        signals = []

        for ticker in passed_tickers:
            # Simple EOD signal approximation
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period='90d')  # Extended lookback for testing

                if len(hist) < 5:
                    continue

                # Prefer the most recent qualifying setup instead of replaying the oldest one.
                for i in range(len(hist) - 1, 0, -1):
                    current = hist.iloc[i]
                    prev = hist.iloc[i-1]

                    gap_pct = (current['Open'] - prev['Close']) / prev['Close'] * 100
                    avg_vol = hist['Volume'].iloc[max(0, i-10):i].mean()
                    vol_spike = current['Volume'] / avg_vol if avg_vol > 0 else 1.0
                    
                    # PHASE 2 OPTIMIZATION: Check blocklist first
                    if ticker in self.ticker_blocklist:
                        logger.info(f"🚫 {ticker}: On blocklist (underperformer)")
                        self._record_scan_near_miss(
                            ticker,
                            current,
                            gap_pct,
                            vol_spike,
                            'blocklisted',
                        )
                        break
                    
                    # PHASE 2 OPTIMIZATION: Gap filter (10-15% sweet spot = 70% win rate)
                    if gap_pct < self.scan_filter_config['gap_min_pct'] or gap_pct > self.scan_filter_config['gap_max_pct']:
                        if 7 <= gap_pct <= 18:
                            self._record_scan_near_miss(
                                ticker,
                                current,
                                gap_pct,
                                vol_spike,
                                'gap_outside_sweet_spot',
                                {'target_gap_range': f"{self.scan_filter_config['gap_min_pct']:.0f}-{self.scan_filter_config['gap_max_pct']:.0f}"},
                            )
                        continue  # Skip this day, check next
                    
                    # PHASE 2 OPTIMIZATION: Volume filter is config-driven for controlled experiments.
                    vol_ok = self._volume_rule_matches(float(vol_spike), self.scan_filter_config)
                    if not vol_ok:
                        volume_target = f">= {self.scan_filter_config['volume_min_mult']:.1f}x"
                        if self.scan_filter_config.get('volume_max_mult') is not None:
                            volume_target = (
                                f"{self.scan_filter_config['volume_min_mult']:.1f}-{float(self.scan_filter_config['volume_max_mult']):.1f}x"
                            )
                            if self.scan_filter_config.get('allow_extreme_volume_above_mult') is not None:
                                volume_target += f" or >={float(self.scan_filter_config['allow_extreme_volume_above_mult']):.1f}x"
                        self._record_scan_near_miss(
                            ticker,
                            current,
                            gap_pct,
                            vol_spike,
                            'volume_outside_sweet_spot',
                            {'target_volume_rule': volume_target},
                        )
                        continue  # Skip this day, check next

                    if gap_pct >= 7:  # Keep this check for backward compatibility
                        signal_date = current.name.strftime('%Y-%m-%d')
                        if self._signal_already_processed(ticker, signal_date):
                            self._record_scan_near_miss(
                                ticker,
                                current,
                                gap_pct,
                                vol_spike,
                                'already_processed',
                            )
                            continue

                        # Score the signal (for logging, not filtering)
                        score = self.scorer.score_runner_vwap(
                            ticker=ticker,
                            gap_pct=gap_pct,
                            volume_spike=vol_spike,
                            float_millions=15,  # Assume mid-range
                            vwap_reclaim=True,
                            rsi=50.0,
                            spy_green=spy_green,
                            vix_level=vix_level,
                            premarket_volume_mult=vol_spike if vol_spike > 1.5 else None,
                            confirmation_bars=0
                        )

                        # PHASE 2 OPTIMIZATION: Accept all signals that pass gap/volume filters
                        # Score is logged but NOT used for filtering (not predictive)
                        signals.append({
                            'ticker': ticker,
                            'signal_type': 'runner_vwap',
                            'price': current['Close'],
                            'gap_pct': gap_pct,
                            'vol_spike': vol_spike,
                            'score': score.total_score,
                            'components': score.components,
                            'date': signal_date,
                            'hist': hist  # Store for advanced filtering
                        })
                        logger.info(f"🟢 {ticker} ({signal_date}): Gap {gap_pct:.1f}%, Vol {vol_spike:.1f}x, Score {score.total_score:.1f}/10.0 ✅")
                        break  # Only take first qualifying signal per ticker

            except Exception as e:
                logger.error(f"{ticker}: Error scanning - {e}", exc_info=True)

        logger.info(f"🎯 Found {len(signals)} signals above threshold")
        if not signals and self.scan_diagnostics:
            logger.info("🔎 Near misses from latest scan:")
            for diagnostic in self.scan_diagnostics[:10]:
                logger.info(
                    "   %s (%s): %s | gap %.1f%% | vol %.1fx",
                    diagnostic['ticker'],
                    diagnostic['date'],
                    diagnostic['reason'],
                    diagnostic['gap_pct'],
                    diagnostic['vol_spike'],
                )
        return signals

    def calculate_position_size(self, entry_price: float, stop_price: float) -> int:
        """Calculate position size based on $5 risk per trade"""
        risk_per_share = abs(entry_price - stop_price)

        if risk_per_share <= 0:
            logger.warning("Invalid risk calculation")
            return 0

        shares = int(self.current_risk_per_trade / risk_per_share)

        # Cap position size at account size
        max_shares = int(self.account_size / entry_price)
        shares = min(shares, max_shares)

        logger.info(f"Position size: {shares} shares (risk ${risk_per_share:.2f}/share = ${shares * risk_per_share:.2f} total)")
        return shares

    def execute_signal(self, signal: Dict) -> bool:
        """Execute a trade based on signal"""
        ticker = signal['ticker']
        entry_price = signal['price']

        # NEW: Check memory system - auto-eject chronic underperformers
        if self.memory_enabled:
            check = self.memory.should_trade_ticker(ticker)
            if not check['allowed']:
                logger.warning(f"❌ {ticker} BLOCKED BY MEMORY: {check['reason']}")
                if check['stats']:
                    stats = check['stats']
                    logger.warning(f"   Stats: {stats.win_rate*100:.1f}% WR ({stats.wins}W/{stats.losses}L), Status: {stats.status}")
                self._record_rejected_signal(
                    signal,
                    stage='memory_gate',
                    reasons=[{'check': 'memory_gate', 'reason': check['reason']}],
                    details={'status': check['stats'].status if check['stats'] else None},
                )
                return False
            elif check['stats'] and check['stats'].status == 'monitored':
                logger.info(f"👁️ {ticker} MONITORED: {check['reason']}")
                stats = check['stats']
                logger.info(f"   Stats: {stats.win_rate*100:.1f}% WR ({stats.wins}W/{stats.losses}L)")

        # NEW: Run advanced quality gate if enabled
        if self.advanced_filters_enabled and 'hist' in signal:
            logger.info(f"🔍 Running advanced quality gate for {ticker}...")

            position_size_dollars = self.current_risk_per_trade * 20  # Approx position size
            quality_results = self.advanced_filters.run_quality_gate(
                ticker,
                signal['hist'],
                position_size_dollars,
                config=self.advanced_filter_config,
            )

            if not quality_results['passed']:
                logger.warning(f"❌ {ticker} FAILED quality gate:")
                failures = self._quality_gate_failures(quality_results)
                for failure in failures:
                    logger.warning(f"   {failure['check']}: {failure['reason']}")
                self._record_rejected_signal(
                    signal,
                    stage='advanced_quality_gate',
                    reasons=failures,
                )
                return False
            else:
                logger.info(f"✅ {ticker} passed quality gate")
                # Track sector
                sector = quality_results['checks']['sector']['sector_name']
                self.advanced_filters.track_sector(ticker, sector)

        # Calculate stop and target based on signal type
        if signal['signal_type'] == 'runner_vwap':
            stop_loss = entry_price * 0.95  # 5% stop
            take_profit = entry_price * 1.10  # 10% target
        else:  # FRD bounce
            stop_loss = entry_price * 0.97  # 3% stop
            take_profit = entry_price * 1.07  # 7% target

        # Calculate position size
        shares = self.calculate_position_size(entry_price, stop_loss)

        if shares == 0:
            logger.warning(f"{ticker}: Position size calculated as 0 - skipping")
            return False

        # Place bracket order
        try:
            logger.info(f"📈 ENTERING {ticker}: {shares} shares @ ${entry_price:.2f}")
            logger.info(f"   Stop: ${stop_loss:.2f} | Target: ${take_profit:.2f}")

            orders = self.broker.place_bracket_order(
                ticker=ticker,
                quantity=shares,
                entry_price=entry_price,
                stop_price=stop_loss,
                target_price=take_profit
            )

            # Track the trade
            trade = {
                'ticker': ticker,
                'entry_time': datetime.now().isoformat(),
                'entry_price': entry_price,
                'shares': shares,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'signal_type': signal['signal_type'],
                'signal_date': signal.get('date'),
                'score': signal['score'],
                'gap_pct': signal.get('gap_pct', 0),
                'vol_mult': signal.get('vol_mult', signal.get('vol_spike', 0)),
                'status': 'active',
                'orders': {k: v.order_id for k, v in orders.items()},
                'market_regime': self.regime_snapshot.regime if self.regime_snapshot else 'UNKNOWN',
                'vix_level': float(self.regime_snapshot.vix_level) if self.regime_snapshot else None,
                'risk_dollars': self.current_risk_per_trade,
            }

            self._record_phase25_signal(signal, trade)

            self.active_positions[ticker] = trade
            self.trades_log.append(trade)

            logger.info(f"✅ {ticker} position opened successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to execute {ticker}: {e}")
            return False

    def record_trade_outcome(self, trade: Dict):
        """Record completed trade outcome in memory system"""
        if not self.memory_enabled:
            return

        try:
            won = trade.get('pnl', 0) > 0
            pnl = trade.get('pnl', 0)
            trade_date = trade.get('exit_time', datetime.now().isoformat())
            outcome_key = self.memory.build_outcome_key(
                ticker=trade.get('ticker', ''),
                trade_date=trade_date,
                signal_id=trade.get('signal_id'),
                signal_date=trade.get('signal_date'),
                entry_time=trade.get('entry_time'),
                entry_price=trade.get('entry_price'),
                shares=trade.get('shares'),
                pnl=pnl,
            )

            self.memory.record_trade_outcome(
                ticker=trade['ticker'],
                won=won,
                pnl=pnl,
                trade_date=trade_date,
                outcome_key=outcome_key,
            )
            self._record_phase25_outcome(trade)

            status = "WIN ✅" if won else "LOSS ❌"
            logger.info(f"📝 Memory updated: {trade['ticker']} {status} ${pnl:.2f}")

        except Exception as e:
            logger.error(f"Failed to record trade outcome: {e}")

    def save_results(self, output_path: str):
        """Save trading results to file"""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Record completed trades in memory
        completed_trades = [t for t in self.trades_log if t.get('status') == 'closed']
        for trade in completed_trades:
            self.record_trade_outcome(trade)

        # Calculate statistics
        total_trades = len(self.trades_log)

        wins = [t for t in completed_trades if t.get('pnl', 0) > 0]
        losses = [t for t in completed_trades if t.get('pnl', 0) < 0]

        win_rate = (len(wins) / len(completed_trades) * 100) if completed_trades else 0

        total_pnl = sum(t.get('pnl', 0) for t in completed_trades)
        avg_win = sum(t['pnl'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl'] for t in losses) / len(losses) if losses else 0

        account = self.broker.get_account()

        report = {
            'generated_at': datetime.now().isoformat(),
            'account_summary': {
                'starting_capital': self.account_size,
                'current_cash': account.cash,
                'portfolio_value': account.portfolio_value,
                'total_pnl': account.portfolio_value - self.account_size,
                'return_pct': (account.portfolio_value - self.account_size) / self.account_size * 100
            },
            'trading_stats': {
                'total_trades': total_trades,
                'completed_trades': len(completed_trades),
                'active_trades': len(self.active_positions),
                'rejected_signals': len(self.rejected_signals),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate_pct': win_rate,
                'total_pnl': total_pnl,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0
            },
            'trades': self.trades_log,
            'rejected_signals': self.rejected_signals,
            'scan_near_misses': self.scan_diagnostics,
            'cooldown_decisions': self.cooldown_decisions,
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2)

        self._append_session_history(report)

        logger.info(f"💾 Results saved to {output_file}")

        # Print summary
        print("\n" + "="*70)
        print("PENNYHUNTER PAPER TRADING RESULTS")
        print("="*70)
        print(f"Starting Capital: ${self.account_size:.2f}")
        print(f"Current Value: ${account.portfolio_value:.2f}")
        print(f"Total P&L: ${total_pnl:.2f} ({report['account_summary']['return_pct']:.1f}%)")
        print()
        print(f"Total Trades: {total_trades}")
        print(f"Completed: {len(completed_trades)} | Active: {len(self.active_positions)}")
        print(f"Rejected Signals: {len(self.rejected_signals)}")
        print(f"Scan Near Misses: {len(self.scan_diagnostics)}")
        print(f"Wins: {len(wins)} | Losses: {len(losses)}")
        print(f"Win Rate: {win_rate:.1f}%")
        if wins:
            print(f"Avg Win: ${avg_win:.2f} | Avg Loss: ${avg_loss:.2f}")
        if self.rejected_signals:
            print("Rejected Candidates:")
            for rejected in self.rejected_signals[:5]:
                reason_text = '; '.join(
                    f"{item['check']}: {item['reason']}" for item in rejected.get('reasons', [])
                )
                print(f"   {rejected['ticker']}: {reason_text}")
        if self.scan_diagnostics:
            print("Near Misses:")
            for diagnostic in self.scan_diagnostics[:5]:
                print(
                    f"   {diagnostic['ticker']} ({diagnostic['date']}): {diagnostic['reason']} "
                    f"| gap {diagnostic['gap_pct']:.1f}% | vol {diagnostic['vol_spike']:.1f}x"
                )
        print("="*70 + "\n")

        # NEW: Display memory system stats
        if self.memory_enabled:
            print("="*70)
            print("MEMORY SYSTEM STATUS (Phase 2.5 Auto-Ejection)")
            print("="*70)

            all_stats = self.memory.get_all_ticker_stats()
            ejected = [s for s in all_stats if s.status == 'ejected']
            monitored = [s for s in all_stats if s.status == 'monitored']
            active = [s for s in all_stats if s.status == 'active']

            print(f"Active: {len(active)} | Monitored: {len(monitored)} | Ejected: {len(ejected)}")
            print()

            if ejected:
                print("EJECTED TICKERS:")
                for stat in ejected:
                    print(f"   {stat.ticker}: {stat.win_rate*100:.1f}% WR ({stat.wins}W/{stat.losses}L)")
                    if stat.ejection_reason:
                        print(f"      Reason: {stat.ejection_reason}")
                print()

            if monitored:
                print("MONITORED TICKERS (Underperforming - Watch Closely):")
                for stat in monitored:
                    print(f"   {stat.ticker}: {stat.win_rate*100:.1f}% WR ({stat.wins}W/{stat.losses}L), P&L: ${stat.total_pnl:.2f}")
                print()

            if active:
                print("ACTIVE TICKERS:")
                # Show top performers
                active_sorted = sorted(active, key=lambda s: s.win_rate, reverse=True)[:5]
                for stat in active_sorted:
                    print(f"   {stat.ticker}: {stat.win_rate*100:.1f}% WR ({stat.wins}W/{stat.losses}L), P&L: ${stat.total_pnl:.2f}")
                if len(active) > 5:
                    print(f"   ... and {len(active)-5} more")

            print("="*70 + "\n")


def main():
    parser = argparse.ArgumentParser(description='PennyHunter Paper Trading')
    parser.add_argument('--config', default='configs/pennyhunter.yaml', help='Config file')
    parser.add_argument('--tickers', help='Comma-separated tickers (or use --ticker-file)')
    parser.add_argument('--ticker-file', default='configs/active_pennies.txt',
                       help='Primary file with ticker list; merged with config universe ticker_file when present')
    parser.add_argument('--account-size', type=float, default=200.0,
                       help='Account size (default $200)')
    parser.add_argument('--max-risk', type=float, default=5.0,
                       help='Max risk per trade (default $5)')
    parser.add_argument('--output', default='reports/pennyhunter_paper_trades.json',
                       help='Output file for results')
    parser.add_argument('--history-file', default='reports/pennyhunter_cumulative_history.json',
                       help='Cumulative history file to update')
    parser.add_argument('--penny-memory-db', default='reports/pennyhunter_memory.db',
                       help='PennyHunter memory SQLite path')
    parser.add_argument('--agent-memory-db', default='reports/bouncehunter_agent.db',
                       help='Agent memory SQLite path')
    args = parser.parse_args()

    # Load config
    config = load_config_file(Path(args.config))

    # Get tickers
    if args.tickers:
        tickers = [t.strip().upper() for t in args.tickers.split(',') if t.strip()]
    else:
        tickers = []
        ticker_sources = []

        primary_ticker_file = Path(args.ticker_file)
        if primary_ticker_file.exists():
            tickers.extend(load_tickers_from_file(primary_ticker_file))
            ticker_sources.append(str(primary_ticker_file))
        else:
            logger.warning(f"Ticker file not found: {primary_ticker_file}")

        config_ticker_file_value = config.get('universe', {}).get('ticker_file')
        if config_ticker_file_value:
            config_ticker_file = Path(config_ticker_file_value)
            if config_ticker_file.exists():
                tickers.extend(load_tickers_from_file(config_ticker_file))
                ticker_sources.append(str(config_ticker_file))
            else:
                logger.warning(f"Configured universe ticker file not found: {config_ticker_file}")

        tickers = list(dict.fromkeys(tickers))
        if ticker_sources:
            logger.info(f"Loaded {len(tickers)} tickers from {', '.join(ticker_sources)}")
        else:
            logger.error("No ticker sources found")
            logger.info("Run: python scripts/fetch_active_pennies.py")
            sys.exit(1)

    # Initialize trader
    trader = PennyHunterPaperTrader(
        config,
        args.account_size,
        args.max_risk,
        history_file=Path(args.history_file),
        penny_memory_db=Path(args.penny_memory_db),
        agent_memory_db=Path(args.agent_memory_db),
    )
    trader.load_existing_results(args.output)
    trader.reconcile_active_positions()
    trader.reconcile_cumulative_history()

    # Check market regime
    if not trader.check_market_regime():
        logger.warning("Market regime blocks penny trading - exiting")
        sys.exit(1)

    # Check RegimeFlip gate (if enabled)
    if not trader.check_regime_flip():
        logger.warning("RegimeFlip blocks penny trading - exiting")
        sys.exit(1)

    # Scan for signals
    signals = trader.scan_for_signals(tickers)
    signals = trader.apply_ticker_cooldown(signals)

    if not signals:
        logger.warning("No executable signals remained after scan filters and cooldown rules")
        trader.save_results(args.output)
        sys.exit(0)

    # Execute top signals (limit to 1 position for $200 account)
    max_positions = 1
    executed = 0

    for signal in signals[:max_positions]:
        if trader.execute_signal(signal):
            executed += 1

    logger.info(f"✅ Executed {executed}/{len(signals)} signals")

    # Save results
    trader.save_results(args.output)

    sys.exit(0)


if __name__ == '__main__':
    main()
