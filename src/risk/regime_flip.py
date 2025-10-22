"""
RegimeFlip: Hard regime gating with explicit flip conditions

Provides regime-aware entry gating by composing multiple market health checks
into a single allow_long decision with explainable reasons.
"""

from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class RegimeInputs:
    """Input data for regime flip decision"""
    vix: float
    vix_ma3: Optional[float] = None
    spy_ret_5d: Optional[float] = None
    spy_ma_fast: Optional[float] = None
    spy_ma_slow: Optional[float] = None
    breadth_above_20dma: Optional[float] = None  # 0..1
    adv_volume: Optional[float] = None
    dec_volume: Optional[float] = None


@dataclass
class RegimeDecision:
    """Result of regime flip decision"""
    allow_long: bool
    reason: str


class RegimeFlip:
    """
    Regime gating with explicit 'flip' conditions:
    - Volatility calming (VIX below threshold and falling)
    - Breadth thrust (>= breadth_min above 20DMA)
    - Volume thrust (adv/dec volume ratio >= volume_thrust_min)
    - Trend confirmation (fast MA > slow MA OR 5d return >= ret_min)
    All checks are ANDed with a minimum confirmations count.
    """

    def __init__(
        self,
        vix_low: float = 20.0,
        breadth_min: float = 0.55,
        volume_thrust_min: float = 1.20,
        ret_5d_min: float = 0.01,
        require_confirmations: int = 2,
    ):
        self.vix_low = vix_low
        self.breadth_min = breadth_min
        self.volume_thrust_min = volume_thrust_min
        self.ret_5d_min = ret_5d_min
        self.require_confirmations = require_confirmations

    def decide(self, x: RegimeInputs) -> RegimeDecision:
        """
        Make regime flip decision based on input data.
        
        Args:
            x: RegimeInputs with market data
            
        Returns:
            RegimeDecision with allow_long flag and reason string
        """
        checks: Dict[str, bool] = {}

        # 1) Volatility calming
        vix_ok = x.vix is not None and x.vix <= self.vix_low
        if vix_ok and x.vix_ma3 is not None:
            vix_ok = vix_ok and (x.vix <= x.vix_ma3)
        checks["vix_ok"] = bool(vix_ok)

        # 2) Breadth thrust
        breadth_ok = (
            x.breadth_above_20dma is not None and x.breadth_above_20dma >= self.breadth_min
        )
        checks["breadth_ok"] = bool(breadth_ok)

        # 3) Volume thrust
        vol_ratio = None
        if x.adv_volume and x.dec_volume and x.dec_volume > 0:
            vol_ratio = x.adv_volume / x.dec_volume
        vol_thrust_ok = vol_ratio is not None and vol_ratio >= self.volume_thrust_min
        checks["volume_thrust_ok"] = bool(vol_thrust_ok)

        # 4) Trend confirmation
        trend_ok = False
        if x.spy_ma_fast is not None and x.spy_ma_slow is not None:
            trend_ok = x.spy_ma_fast >= x.spy_ma_slow
        if not trend_ok and x.spy_ret_5d is not None:
            trend_ok = x.spy_ret_5d >= self.ret_5d_min
        checks["trend_ok"] = bool(trend_ok)

        passed = sum(1 for v in checks.values() if v)
        allow = passed >= self.require_confirmations

        reason_bits = [k for k, v in checks.items() if v]
        reason = " & ".join(reason_bits) if reason_bits else "no confirmations"
        return RegimeDecision(allow_long=allow, reason=reason)
