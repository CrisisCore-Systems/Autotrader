"""
Advanced Order Flow Analysis and Market Maker Detection.

Implements sophisticated microstructure analysis including:
- Order flow imbalance detection
- Market maker identification
- Liquidity provision analysis
- High-frequency trading signal generation
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Deque
from collections import deque
from datetime import datetime, timedelta

from src.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class OrderFlowSnapshot:
    """Snapshot of order flow at a point in time."""
    timestamp: datetime
    symbol: str
    
    # Order book metrics
    bid_volume: float
    ask_volume: float
    bid_depth: float  # Cumulative volume at N levels
    ask_depth: float
    
    # Trade metrics
    buy_volume: float  # Aggressor buy volume
    sell_volume: float  # Aggressor sell volume
    trade_count: int
    
    # Price metrics
    best_bid: float
    best_ask: float
    mid_price: float
    last_price: float
    
    # Derived metrics
    @property
    def order_book_imbalance(self) -> float:
        """Calculate order book imbalance."""
        total = self.bid_volume + self.ask_volume
        if total == 0:
            return 0.0
        return (self.bid_volume - self.ask_volume) / total
    
    @property
    def trade_imbalance(self) -> float:
        """Calculate trade flow imbalance."""
        total = self.buy_volume + self.sell_volume
        if total == 0:
            return 0.0
        return (self.buy_volume - self.sell_volume) / total
    
    @property
    def spread_bps(self) -> float:
        """Calculate spread in basis points."""
        if self.mid_price == 0:
            return 0.0
        spread = self.best_ask - self.best_bid
        return (spread / self.mid_price) * 10000


@dataclass
class OrderFlowImbalance:
    """Order flow imbalance signal."""
    timestamp: datetime
    symbol: str
    
    # Raw imbalances
    book_imbalance: float  # -1 to 1
    trade_imbalance: float  # -1 to 1
    
    # Weighted composite
    composite_imbalance: float  # -1 to 1
    
    # Statistical significance
    z_score: float
    confidence: float  # 0 to 1
    
    # Predicted price direction
    predicted_direction: int  # -1, 0, or 1
    predicted_magnitude: float


class OrderFlowImbalanceDetector:
    """
    Detect order flow imbalance and predict short-term price movements.
    
    Uses combination of order book and trade flow imbalances to identify
    supply/demand imbalances that predict price movement.
    """
    
    def __init__(
        self,
        lookback_window: int = 100,
        book_weight: float = 0.4,
        trade_weight: float = 0.6,
        threshold: float = 0.3,  # Imbalance threshold for signal
    ):
        """
        Initialize detector.
        
        Args:
            lookback_window: Number of snapshots for statistics
            book_weight: Weight for order book imbalance
            trade_weight: Weight for trade imbalance
            threshold: Minimum imbalance for signal
        """
        self.lookback_window = lookback_window
        self.book_weight = book_weight
        self.trade_weight = trade_weight
        self.threshold = threshold
        
        # Historical data
        self.history: Deque[OrderFlowSnapshot] = deque(maxlen=lookback_window)
        self.imbalance_history: List[float] = []
    
    def update(self, snapshot: OrderFlowSnapshot) -> Optional[OrderFlowImbalance]:
        """
        Update with new snapshot and detect imbalance.
        
        Args:
            snapshot: New order flow snapshot
        
        Returns:
            OrderFlowImbalance if detected, None otherwise
        """
        self.history.append(snapshot)
        
        if len(self.history) < self.lookback_window // 2:
            return None  # Not enough data
        
        # Calculate composite imbalance
        book_imb = snapshot.order_book_imbalance
        trade_imb = snapshot.trade_imbalance
        
        composite = (
            self.book_weight * book_imb +
            self.trade_weight * trade_imb
        )
        
        # Calculate z-score
        self.imbalance_history.append(composite)
        recent_imbalances = self.imbalance_history[-self.lookback_window:]
        
        mean = np.mean(recent_imbalances)
        std = np.std(recent_imbalances)
        
        if std > 0:
            z_score = (composite - mean) / std
        else:
            z_score = 0.0
        
        # Calculate confidence
        confidence = min(1.0, abs(z_score) / 3.0)  # 3-sigma = 100% confidence
        
        # Predict direction
        if abs(composite) < self.threshold:
            direction = 0
        elif composite > 0:
            direction = 1  # Bullish (more buying pressure)
        else:
            direction = -1  # Bearish (more selling pressure)
        
        # Predict magnitude (larger imbalance = larger expected move)
        magnitude = abs(composite)
        
        # Create signal
        signal = OrderFlowImbalance(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            book_imbalance=book_imb,
            trade_imbalance=trade_imb,
            composite_imbalance=composite,
            z_score=z_score,
            confidence=confidence,
            predicted_direction=direction,
            predicted_magnitude=magnitude,
        )
        
        # Log significant imbalances
        if abs(z_score) > 2.0:
            logger.info(
                f"Significant imbalance detected: {snapshot.symbol} "
                f"composite={composite:.3f}, z={z_score:.2f}, "
                f"direction={'BUY' if direction > 0 else 'SELL' if direction < 0 else 'NEUTRAL'}"
            )
        
        return signal


@dataclass
class MarketMakerActivity:
    """Market maker activity metrics."""
    timestamp: datetime
    symbol: str
    
    # Quote activity
    quote_updates_per_second: float
    quote_cancellation_rate: float
    quote_spread_tightness: float  # How tight vs market
    
    # Inventory management
    estimated_position: float
    position_change_rate: float
    
    # Liquidity provision
    provided_liquidity_ratio: float  # Passive fills / total fills
    captured_spread_bps: float
    
    # Adverse selection
    adverse_selection_cost: float  # Loss from being picked off
    
    # Classification
    is_market_maker: bool
    confidence: float


class MarketMakerDetector:
    """
    Detect and analyze market maker activity.
    
    Identifies market makers by their characteristic behavior:
    - High quote update frequency
    - Tight spreads
    - Two-sided quoting
    - Inventory mean reversion
    """
    
    def __init__(
        self,
        lookback_seconds: int = 60,
        quote_update_threshold: float = 10.0,  # Updates per second
        spread_tightness_threshold: float = 0.8,  # Ratio of market spread
    ):
        self.lookback_seconds = lookback_seconds
        self.quote_update_threshold = quote_update_threshold
        self.spread_tightness_threshold = spread_tightness_threshold
        
        # Track quote activity
        self.quote_updates: Dict[str, Deque[datetime]] = {}
        self.cancellations: Dict[str, Deque[datetime]] = {}
        
        # Track trades
        self.trades: Dict[str, List[Dict]] = {}
    
    def update_quote(
        self,
        timestamp: datetime,
        symbol: str,
        bid: float,
        ask: float,
        is_cancellation: bool = False,
    ):
        """Update quote activity."""
        if symbol not in self.quote_updates:
            self.quote_updates[symbol] = deque()
            self.cancellations[symbol] = deque()
        
        self.quote_updates[symbol].append(timestamp)
        
        if is_cancellation:
            self.cancellations[symbol].append(timestamp)
        
        # Remove old data
        cutoff = timestamp - timedelta(seconds=self.lookback_seconds)
        while (self.quote_updates[symbol] and 
               self.quote_updates[symbol][0] < cutoff):
            self.quote_updates[symbol].popleft()
        
        while (self.cancellations[symbol] and 
               self.cancellations[symbol][0] < cutoff):
            self.cancellations[symbol].popleft()
    
    def update_trade(
        self,
        timestamp: datetime,
        symbol: str,
        price: float,
        size: float,
        side: str,  # 'buy' or 'sell'
        is_passive: bool,  # Was liquidity provider
    ):
        """Update trade activity."""
        if symbol not in self.trades:
            self.trades[symbol] = []
        
        self.trades[symbol].append({
            'timestamp': timestamp,
            'price': price,
            'size': size,
            'side': side,
            'is_passive': is_passive,
        })
        
        # Remove old trades
        cutoff = timestamp - timedelta(seconds=self.lookback_seconds)
        self.trades[symbol] = [
            t for t in self.trades[symbol]
            if t['timestamp'] >= cutoff
        ]
    
    def analyze(
        self,
        timestamp: datetime,
        symbol: str,
        current_spread_bps: float,
        market_spread_bps: float,
    ) -> MarketMakerActivity:
        """
        Analyze market maker activity.
        
        Args:
            timestamp: Current timestamp
            symbol: Symbol to analyze
            current_spread_bps: Current spread in bps
            market_spread_bps: Typical market spread in bps
        
        Returns:
            MarketMakerActivity metrics
        """
        # Quote activity
        if symbol in self.quote_updates:
            updates = len(self.quote_updates[symbol])
            cancels = len(self.cancellations[symbol])
            
            updates_per_sec = updates / self.lookback_seconds
            cancel_rate = cancels / updates if updates > 0 else 0
        else:
            updates_per_sec = 0
            cancel_rate = 0
        
        # Spread tightness
        if market_spread_bps > 0:
            spread_tightness = current_spread_bps / market_spread_bps
        else:
            spread_tightness = 1.0
        
        # Liquidity provision
        if symbol in self.trades and self.trades[symbol]:
            trades = self.trades[symbol]
            passive_fills = sum(1 for t in trades if t['is_passive'])
            provided_ratio = passive_fills / len(trades)
            
            # Estimate captured spread
            # (simplified - would need actual fill prices vs quotes)
            captured_spread = current_spread_bps * provided_ratio
        else:
            provided_ratio = 0
            captured_spread = 0
        
        # Classify as market maker
        is_mm = (
            updates_per_sec >= self.quote_update_threshold and
            spread_tightness <= self.spread_tightness_threshold and
            provided_ratio >= 0.5
        )
        
        # Confidence based on how strongly criteria are met
        confidence = min(1.0, (
            (updates_per_sec / self.quote_update_threshold) * 0.4 +
            (1.0 - spread_tightness) * 0.3 +
            provided_ratio * 0.3
        ))
        
        return MarketMakerActivity(
            timestamp=timestamp,
            symbol=symbol,
            quote_updates_per_second=updates_per_sec,
            quote_cancellation_rate=cancel_rate,
            quote_spread_tightness=spread_tightness,
            estimated_position=0,  # Would need order tracking
            position_change_rate=0,
            provided_liquidity_ratio=provided_ratio,
            captured_spread_bps=captured_spread,
            adverse_selection_cost=0,  # Would need price impact analysis
            is_market_maker=is_mm,
            confidence=confidence,
        )


@dataclass
class HFTSignal:
    """High-frequency trading signal."""
    timestamp: datetime
    symbol: str
    signal_type: str  # 'momentum', 'reversion', 'imbalance'
    direction: int  # -1, 0, or 1
    strength: float  # 0 to 1
    holding_period: timedelta  # Expected holding period
    entry_price: float
    target_price: Optional[float]
    stop_price: Optional[float]


class HFTSignalGenerator:
    """
    Generate high-frequency trading signals.
    
    Combines order flow imbalance, market maker activity,
    and microstructure features to generate trading signals.
    """
    
    def __init__(
        self,
        imbalance_detector: OrderFlowImbalanceDetector,
        mm_detector: MarketMakerDetector,
    ):
        self.imbalance_detector = imbalance_detector
        self.mm_detector = mm_detector
        
        self.signals: List[HFTSignal] = []
    
    def generate_signal(
        self,
        snapshot: OrderFlowSnapshot,
        mm_activity: MarketMakerActivity,
    ) -> Optional[HFTSignal]:
        """
        Generate HFT signal from current market state.
        
        Args:
            snapshot: Current order flow snapshot
            mm_activity: Market maker activity metrics
        
        Returns:
            HFTSignal if conditions met, None otherwise
        """
        # Get order flow imbalance
        imbalance = self.imbalance_detector.update(snapshot)
        
        if imbalance is None or imbalance.confidence < 0.5:
            return None
        
        # Determine signal type and parameters
        
        # Imbalance-driven momentum signal
        if abs(imbalance.z_score) > 2.0 and imbalance.confidence > 0.7:
            # Strong imbalance suggests short-term momentum
            signal_type = 'imbalance'
            direction = imbalance.predicted_direction
            strength = imbalance.confidence
            holding_period = timedelta(seconds=5)  # Very short term
            
            # Price targets based on recent volatility
            spread = snapshot.best_ask - snapshot.best_bid
            if direction > 0:
                entry = snapshot.best_ask
                target = entry + spread * 2
                stop = entry - spread
            elif direction < 0:
                entry = snapshot.best_bid
                target = entry - spread * 2
                stop = entry + spread
            else:
                return None
        
        # Market maker exploitation (fade the quote)
        elif mm_activity.is_market_maker and mm_activity.quote_cancellation_rate > 0.3:
            # High cancellation rate suggests MM is backing away
            # Fade their quotes
            signal_type = 'reversion'
            
            # If book imbalance is extreme, expect reversion
            if abs(snapshot.order_book_imbalance) > 0.5:
                direction = -1 if snapshot.order_book_imbalance > 0 else 1
                strength = 0.6
                holding_period = timedelta(seconds=10)
                
                entry = snapshot.mid_price
                spread = snapshot.best_ask - snapshot.best_bid
                if direction > 0:
                    target = entry + spread * 1.5
                    stop = entry - spread * 0.5
                else:
                    target = entry - spread * 1.5
                    stop = entry + spread * 0.5
            else:
                return None
        
        else:
            return None
        
        # Create signal
        signal = HFTSignal(
            timestamp=snapshot.timestamp,
            symbol=snapshot.symbol,
            signal_type=signal_type,
            direction=direction,
            strength=strength,
            holding_period=holding_period,
            entry_price=entry,
            target_price=target,
            stop_price=stop,
        )
        
        self.signals.append(signal)
        
        logger.info(
            f"HFT signal generated: {signal_type} {snapshot.symbol} "
            f"direction={'BUY' if direction > 0 else 'SELL'} "
            f"strength={strength:.2f}"
        )
        
        return signal
