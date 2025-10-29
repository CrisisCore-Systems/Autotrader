"""
Signal Scoring System for PennyHunter

Scores signals 0-10 based on confluence of factors.
Only trades signals above minimum score threshold.

Author: BounceHunter Team
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SignalScore:
    """Signal score breakdown"""
    ticker: str
    signal_type: str  # 'runner_vwap' or 'frd_bounce'
    timestamp: datetime
    total_score: float
    max_score: float
    confidence_pct: float
    components: Dict[str, float]
    passed_threshold: bool
    recommendation: str


class SignalScorer:
    """
    Scores penny stock signals based on multiple factors.

    Higher scores = higher probability setups.
    Only trade signals above threshold (default 7/10).
    """

    def __init__(
        self,
        min_score_threshold: float = 7.0,
        max_score: float = 10.0
    ):
        """
        Initialize signal scorer.

        Args:
            min_score_threshold: Minimum score to trade (0-10)
            max_score: Maximum possible score
        """
        self.min_score_threshold = min_score_threshold
        self.max_score = max_score

        logger.info(f"SignalScorer initialized: min_threshold={min_score_threshold}/{max_score}")

    def _score_gap_size(self, gap_pct: float) -> float:
        """Score gap size (0-3 points)."""
        if gap_pct >= 50:
            return 3.0
        elif gap_pct >= 30:
            return 2.0
        elif gap_pct >= 20:
            return 1.0
        else:
            return 0.0
    
    def _score_volume_spike(self, volume_spike: float) -> float:
        """Score volume spike (0-2 points)."""
        if volume_spike >= 5.0:
            return 2.0
        elif volume_spike >= 3.0:
            return 1.5
        elif volume_spike >= 2.5:
            return 1.0
        else:
            return 0.5
    
    def _score_float(self, float_millions: Optional[float]) -> float:
        """Score float size (0-2 points)."""
        if float_millions is None:
            return 0.0
        if float_millions < 10:
            return 2.0
        elif float_millions < 20:
            return 1.5
        elif float_millions < 50:
            return 0.5
        else:
            return 0.0
    
    def _score_rsi(self, rsi: Optional[float]) -> float:
        """Score RSI recovery (0-1 point)."""
        if rsi is None:
            return 0.0
        if rsi > 50:
            return 1.0
        elif rsi > 30:
            return 0.5
        else:
            return 0.0
    
    def _score_market_regime(self, spy_green: bool, vix_level: float) -> float:
        """Score market regime (0-1 point)."""
        if spy_green and vix_level < 20:
            return 1.0
        elif spy_green or vix_level < 25:
            return 0.5
        else:
            return 0.0
    
    def _score_pm_volume(self, premarket_volume_mult: Optional[float]) -> float:
        """Score premarket volume (0-1 point, bonus)."""
        if premarket_volume_mult is None:
            return 0.0
        if premarket_volume_mult >= 3.0:
            return 1.0
        elif premarket_volume_mult >= 2.0:
            return 0.5
        else:
            return 0.0
    
    def _score_confirmation_bars(self, confirmation_bars: int) -> float:
        """Score confirmation bars (0-1 point, bonus)."""
        if confirmation_bars >= 2:
            return 1.0
        elif confirmation_bars == 1:
            return 0.5
        else:
            return 0.0
    
    def _get_recommendation(self, total_score: float) -> str:
        """Get recommendation based on total score."""
        if total_score >= 8.5:
            return "STRONG BUY - High probability setup"
        elif total_score >= 7.0:
            return "BUY - Good setup"
        elif total_score >= 5.0:
            return "WATCH - Monitor for improvement"
        else:
            return "PASS - Low probability"
    
    def score_runner_vwap(
        self,
        ticker: str,
        gap_pct: float,
        volume_spike: float,
        float_millions: Optional[float],
        vwap_reclaim: bool,
        rsi: Optional[float],
        spy_green: bool,
        vix_level: float,
        premarket_volume_mult: Optional[float] = None,
        confirmation_bars: int = 0
    ) -> SignalScore:
        """
        Score Runner VWAP signal.

        Args:
            ticker: Ticker symbol
            gap_pct: Gap size percentage
            volume_spike: Volume vs average
            float_millions: Float in millions (None if unknown)
            vwap_reclaim: Has VWAP been reclaimed
            rsi: RSI value (None if unknown)
            spy_green: Is SPY green today
            vix_level: Current VIX level
            premarket_volume_mult: PM volume vs daily avg
            confirmation_bars: Number of confirmation bars

        Returns:
            SignalScore with breakdown
        """
        components = {
            'gap': self._score_gap_size(gap_pct),
            'volume': self._score_volume_spike(volume_spike),
            'float': self._score_float(float_millions),
            'vwap_reclaim': 1.0 if vwap_reclaim else 0.0,
            'rsi': self._score_rsi(rsi),
            'market_regime': self._score_market_regime(spy_green, vix_level),
            'pm_volume': self._score_pm_volume(premarket_volume_mult),
            'confirmation': self._score_confirmation_bars(confirmation_bars),
        }

        # Calculate total
        total_score = sum(components.values())
        confidence_pct = (total_score / self.max_score) * 100
        passed = total_score >= self.min_score_threshold
        recommendation = self._get_recommendation(total_score)

        score = SignalScore(
            ticker=ticker,
            signal_type='runner_vwap',
            timestamp=datetime.now(),
            total_score=total_score,
            max_score=self.max_score,
            confidence_pct=confidence_pct,
            components=components,
            passed_threshold=passed,
            recommendation=recommendation
        )

        logger.info(
            f"📊 {ticker} Runner VWAP Score: {total_score:.1f}/{self.max_score} "
            f"({confidence_pct:.0f}%) → {'✅ TRADE' if passed else '❌ SKIP'}"
        )

        return score

    def _score_prior_strength(self, prior_range_mult_atr: float) -> float:
        """Score prior day strength (0-2 points)."""
        if prior_range_mult_atr >= 4.0:
            return 2.0
        elif prior_range_mult_atr >= 3.0:
            return 1.5
        elif prior_range_mult_atr >= 2.5:
            return 1.0
        else:
            return 0.5
    
    def _score_gap_down(self, gap_pct: float) -> float:
        """Score gap size (0-2 points)."""
        gap_abs = abs(gap_pct)
        if gap_abs >= 15:
            return 2.0
        elif gap_abs >= 10:
            return 1.5
        elif gap_abs >= 5:
            return 1.0
        else:
            return 0.5
    
    def _score_rsi2(self, rsi2: float) -> float:
        """Score RSI(2) oversold (0-2 points)."""
        if rsi2 < 3:
            return 2.0
        elif rsi2 < 5:
            return 1.5
        elif rsi2 < 10:
            return 1.0
        else:
            return 0.0
    
    def _score_vwap_band(self, z_score: float) -> float:
        """Score VWAP band touch (0-1 point)."""
        if z_score <= -2.0:
            return 1.0
        elif z_score <= -1.5:
            return 0.5
        else:
            return 0.0
    
    def _score_volume_climax(self, volume_climax: float) -> float:
        """Score volume climax (0-1 point)."""
        if volume_climax >= 4.0:
            return 1.0
        elif volume_climax >= 2.5:
            return 0.5
        else:
            return 0.0
    
    def _score_float_frd(self, float_millions: Optional[float]) -> float:
        """Score float for FRD bounce (0-1 point)."""
        if float_millions is None:
            return 0.0
        if float_millions < 20:
            return 1.0
        elif float_millions < 50:
            return 0.5
        else:
            return 0.0
    
    def _score_market_regime_frd(self, spy_green: bool, vix_level: float) -> float:
        """Score market regime for FRD (0-1 point)."""
        if spy_green and vix_level < 25:
            return 1.0
        elif spy_green or vix_level < 30:
            return 0.5
        else:
            return 0.0
    
    def _get_frd_recommendation(self, total_score: float) -> str:
        """Get recommendation for FRD bounce based on total score."""
        if total_score >= 8.5:
            return "STRONG BUY - High probability bounce"
        elif total_score >= 7.0:
            return "BUY - Good bounce setup"
        elif total_score >= 5.0:
            return "WATCH - Monitor for confirmation"
        else:
            return "PASS - Low probability"
    
    def score_frd_bounce(
        self,
        ticker: str,
        prior_range_mult_atr: float,
        gap_pct: float,
        rsi2: float,
        z_score: float,
        volume_climax: float,
        float_millions: Optional[float],
        support_confluence: bool,
        spy_green: bool,
        vix_level: float,
        confirmation_bars: int = 0
    ) -> SignalScore:
        """
        Score FRD Bounce signal.

        Args:
            ticker: Ticker symbol
            prior_range_mult_atr: Prior day range / ATR
            gap_pct: Gap down percentage (negative)
            rsi2: RSI(2) value
            z_score: Z-score from VWAP (-2 = at lower band)
            volume_climax: Volume spike on flush
            float_millions: Float in millions
            support_confluence: Flush at prior support level
            spy_green: Is SPY green today
            vix_level: Current VIX level
            confirmation_bars: Number of confirmation bars

        Returns:
            SignalScore with breakdown
        """
        components = {
            'prior_strength': self._score_prior_strength(prior_range_mult_atr),
            'gap': self._score_gap_down(gap_pct),
            'rsi2': self._score_rsi2(rsi2),
            'vwap_band': self._score_vwap_band(z_score),
            'volume_climax': self._score_volume_climax(volume_climax),
            'float': self._score_float_frd(float_millions),
            'support': 1.0 if support_confluence else 0.0,
            'market_regime': self._score_market_regime_frd(spy_green, vix_level),
            'confirmation': self._score_confirmation_bars(confirmation_bars),
        }

        # Calculate total
        total_score = sum(components.values())
        confidence_pct = (total_score / self.max_score) * 100
        passed = total_score >= self.min_score_threshold
        recommendation = self._get_frd_recommendation(total_score)

        score = SignalScore(
            ticker=ticker,
            signal_type='frd_bounce',
            timestamp=datetime.now(),
            total_score=total_score,
            max_score=self.max_score,
            confidence_pct=confidence_pct,
            components=components,
            passed_threshold=passed,
            recommendation=recommendation
        )

        logger.info(
            f"📊 {ticker} FRD Bounce Score: {total_score:.1f}/{self.max_score} "
            f"({confidence_pct:.0f}%) → {'✅ TRADE' if passed else '❌ SKIP'}"
        )

        return score

    def print_score_breakdown(self, score: SignalScore):
        """Print detailed score breakdown"""
        print(f"\n{'='*60}")
        print(f"{score.ticker} - {score.signal_type.upper()} SIGNAL SCORE")
        print(f"{'='*60}")
        print(f"Total: {score.total_score:.1f}/{score.max_score} ({score.confidence_pct:.0f}%)")
        print(f"Status: {'✅ PASSED' if score.passed_threshold else '❌ FAILED'} (threshold: {self.min_score_threshold})")
        print(f"\nBreakdown:")
        for component, value in sorted(score.components.items(), key=lambda x: -x[1]):
            bar = '█' * int(value * 5)
            print(f"  {component:20s}: {value:4.1f} {bar}")
        print(f"\nRecommendation: {score.recommendation}")
        print(f"{'='*60}\n")


# ===== CLI testing =====

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("SIGNAL SCORING TEST")
    print("="*70)

    scorer = SignalScorer(min_score_threshold=7.0)

    # Test Runner VWAP signals
    print("\n" + "-"*70)
    print("RUNNER VWAP SIGNALS")
    print("-"*70)

    # Strong signal
    score1 = scorer.score_runner_vwap(
        ticker="TMQ",
        gap_pct=35.0,
        volume_spike=4.2,
        float_millions=8.5,
        vwap_reclaim=True,
        rsi=55.0,
        spy_green=True,
        vix_level=18.0,
        premarket_volume_mult=3.5,
        confirmation_bars=2
    )
    scorer.print_score_breakdown(score1)

    # Weak signal
    score2 = scorer.score_runner_vwap(
        ticker="WEAK",
        gap_pct=22.0,
        volume_spike=2.0,
        float_millions=75.0,
        vwap_reclaim=False,
        rsi=25.0,
        spy_green=False,
        vix_level=32.0,
        premarket_volume_mult=1.2,
        confirmation_bars=0
    )
    scorer.print_score_breakdown(score2)

    # Test FRD Bounce signals
    print("\n" + "-"*70)
    print("FRD BOUNCE SIGNALS")
    print("-"*70)

    # Strong signal
    score3 = scorer.score_frd_bounce(
        ticker="GEVO",
        prior_range_mult_atr=3.5,
        gap_pct=-12.0,
        rsi2=2.8,
        z_score=-2.2,
        volume_climax=5.0,
        float_millions=15.0,
        support_confluence=True,
        spy_green=True,
        vix_level=22.0,
        confirmation_bars=2
    )
    scorer.print_score_breakdown(score3)

    # Weak signal
    score4 = scorer.score_frd_bounce(
        ticker="WEAK2",
        prior_range_mult_atr=2.0,
        gap_pct=-6.0,
        rsi2=12.0,
        z_score=-1.0,
        volume_climax=1.5,
        float_millions=80.0,
        support_confluence=False,
        spy_green=False,
        vix_level=35.0,
        confirmation_bars=0
    )
    scorer.print_score_breakdown(score4)
