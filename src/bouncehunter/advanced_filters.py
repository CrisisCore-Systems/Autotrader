"""
Advanced Risk Filters Module

Implements tactical enhancements for quality and risk control:
1. Dynamic liquidity delta - Detect evaporating liquidity
2. Effective slippage estimate - Prevent surprise execution costs
3. Cash runway filter - Filter out high-risk money-burners
4. Sector diversification - Avoid concentration risk
5. Volume fade detection - Identify weak breakouts

Usage:
    from advanced_filters import AdvancedRiskFilters

    filters = AdvancedRiskFilters()

    # Check liquidity health
    liquidity_ok = filters.check_liquidity_delta(ticker, hist_data)

    # Estimate slippage
    slippage_pct = filters.estimate_slippage(ticker, position_size_dollars)

    # Check cash runway
    runway_ok = filters.check_cash_runway(ticker, min_months=6)

    # Get sector exposure
    sector = filters.get_sector(ticker)
"""

import yfinance as yf
import pandas as pd
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AdvancedRiskFilters:
    """Advanced risk and quality filters for penny stock selection"""

    def __init__(self):
        self.sector_exposure = {}  # Track sector concentration
        self.ticker_cache = {}     # Cache ticker data

    # ==================== LIQUIDITY DELTA ====================

    def check_liquidity_delta(
        self,
        ticker: str,
        hist: pd.DataFrame,
        threshold_pct: float = -30.0
    ) -> Tuple[bool, float, str]:
        """
        Check for evaporating liquidity (volume declining)

        Args:
            ticker: Stock ticker
            hist: Historical price data (needs 14+ days)
            threshold_pct: Max allowed volume decline % (default -30%)

        Returns:
            (passed, delta_pct, reason)
        """
        try:
            if len(hist) < 14:
                return False, 0, "Insufficient data"

            # Compare 14-day avg vs 7-day avg
            vol_14d = hist['Volume'].iloc[-14:].mean()
            vol_7d = hist['Volume'].iloc[-7:].mean()

            if vol_14d == 0:
                return False, 0, "No volume data"

            delta_pct = ((vol_7d - vol_14d) / vol_14d) * 100

            if delta_pct < threshold_pct:
                return False, delta_pct, f"Liquidity declining {delta_pct:.1f}%"

            return True, delta_pct, "Liquidity stable"

        except Exception as e:
            logger.debug(f"{ticker}: Liquidity delta error - {e}")
            return False, 0, str(e)

    # ==================== SLIPPAGE ESTIMATION ====================

    def estimate_slippage(
        self,
        ticker: str,
        position_size_dollars: float,
        hist: Optional[pd.DataFrame] = None
    ) -> Tuple[float, str]:
        """
        Estimate effective slippage based on volume and spread

        Uses approximation: slippage ≈ (position_size / daily_volume) * spread

        Args:
            ticker: Stock ticker
            position_size_dollars: Position size in dollars
            hist: Optional historical data

        Returns:
            (slippage_pct, reason)
        """
        try:
            if hist is None or len(hist) < 5:
                stock = yf.Ticker(ticker)
                hist = stock.history(period='10d')

            if len(hist) < 5:
                return 5.0, "Insufficient data (assume 5%)"

            # Average daily dollar volume
            avg_dollar_volume = (hist['Close'] * hist['Volume']).mean()

            if avg_dollar_volume == 0:
                return 5.0, "No volume data"

            # Position size as % of daily volume
            position_pct = (position_size_dollars / avg_dollar_volume) * 100

            # Average spread proxy (High-Low range)
            avg_spread = ((hist['High'] - hist['Low']) / hist['Close']).mean() * 100

            # Slippage estimate: position_pct * spread/2
            # (Half spread because we're not always at worst price)
            slippage_pct = (position_pct / 100) * (avg_spread / 2)

            # Cap at reasonable max
            slippage_pct = min(slippage_pct, 10.0)

            reason = f"Position {position_pct:.1f}% of volume, spread {avg_spread:.1f}%"
            return slippage_pct, reason

        except Exception as e:
            logger.debug(f"{ticker}: Slippage estimation error - {e}")
            return 5.0, str(e)

    # ==================== CASH RUNWAY ====================

    def check_cash_runway(
        self,
        ticker: str,
        min_months: float = 6.0
    ) -> Tuple[bool, float, str]:
        """
        Check if company has sufficient cash runway

        Formula: runway_months = (cash + equivalents) / quarterly_burn

        Args:
            ticker: Stock ticker
            min_months: Minimum acceptable runway in months

        Returns:
            (passed, runway_months, reason)
        """
        try:
            stock = yf.Ticker(ticker)

            # Get balance sheet
            balance_sheet = stock.balance_sheet
            if balance_sheet is None or balance_sheet.empty:
                return True, 999, "No financial data (pass by default)"

            # Get cash + equivalents
            cash_items = ['Cash And Cash Equivalents', 'Cash', 'CashAndCashEquivalents']
            cash = 0
            for item in cash_items:
                if item in balance_sheet.index:
                    cash = balance_sheet.loc[item].iloc[0]
                    break

            if cash <= 0:
                return True, 999, "No cash data (pass by default)"

            # Get quarterly cash flow
            cash_flow = stock.cashflow
            if cash_flow is None or cash_flow.empty:
                return True, 999, "No cash flow data (pass by default)"

            # Operating cash flow (negative = burn)
            ocf_items = ['Operating Cash Flow', 'OperatingCashFlow']
            quarterly_ocf = 0
            for item in ocf_items:
                if item in cash_flow.index:
                    quarterly_ocf = cash_flow.loc[item].iloc[0]
                    break

            # If cash flow positive, infinite runway
            if quarterly_ocf >= 0:
                return True, 999, f"Cash flow positive: ${quarterly_ocf/1e6:.1f}M/quarter"

            # Calculate burn rate and runway
            quarterly_burn = abs(quarterly_ocf)
            runway_months = (cash / quarterly_burn) * 3  # 3 months per quarter

            if runway_months < min_months:
                return False, runway_months, f"Only {runway_months:.1f} months runway (need {min_months})"

            return True, runway_months, f"{runway_months:.1f} months runway"

        except Exception as e:
            logger.debug(f"{ticker}: Cash runway error - {e}")
            return True, 999, f"Error (pass by default): {e}"

    # ==================== SECTOR DIVERSIFICATION ====================

    def track_sector(self, ticker: str, sector: str):
        """Track sector exposure"""
        if sector not in self.sector_exposure:
            self.sector_exposure[sector] = []
        self.sector_exposure[sector].append(ticker)

    def check_sector_diversification(
        self,
        ticker: str,
        sector: str,
        max_per_sector: int = 3
    ) -> Tuple[bool, int, str]:
        """
        Check if adding ticker would exceed sector concentration limit

        Args:
            ticker: Stock ticker
            sector: Sector name
            max_per_sector: Maximum tickers allowed per sector

        Returns:
            (passed, current_count, reason)
        """
        if sector not in self.sector_exposure:
            return True, 0, "First in sector"

        current_count = len(self.sector_exposure[sector])

        if ticker in self.sector_exposure[sector]:
            return True, current_count, "Already tracked"

        if current_count >= max_per_sector:
            return False, current_count, f"Sector full ({current_count}/{max_per_sector})"

        return True, current_count, f"Sector OK ({current_count}/{max_per_sector})"

    def reset_sector_tracking(self):
        """Reset sector exposure tracking"""
        self.sector_exposure = {}

    def get_sector(self, ticker: str) -> str:
        """Get sector for a ticker"""
        try:
            if ticker in self.ticker_cache:
                return self.ticker_cache[ticker].get('sector', 'UNKNOWN')

            stock = yf.Ticker(ticker)
            info = stock.info
            sector = info.get('sector', 'UNKNOWN')

            # Cache it
            if ticker not in self.ticker_cache:
                self.ticker_cache[ticker] = {}
            self.ticker_cache[ticker]['sector'] = sector

            return sector

        except Exception as e:
            logger.debug(f"{ticker}: Sector lookup error - {e}")
            return 'UNKNOWN'

    # ==================== VOLUME FADE DETECTION ====================

    def detect_volume_fade(
        self,
        ticker: str,
        hist: pd.DataFrame,
        lookback_days: int = 5
    ) -> Tuple[bool, float, str]:
        """
        Detect if volume is fading after a signal (weak breakout)

        Args:
            ticker: Stock ticker
            hist: Historical data
            lookback_days: Days to check for fade

        Returns:
            (is_fading, fade_pct, reason)
        """
        try:
            if len(hist) < lookback_days + 1:
                return False, 0, "Insufficient data"

            # Compare most recent day vs average of previous lookback days
            latest_vol = hist['Volume'].iloc[-1]
            avg_vol = hist['Volume'].iloc[-(lookback_days+1):-1].mean()

            if avg_vol == 0:
                return False, 0, "No volume data"

            fade_pct = ((latest_vol - avg_vol) / avg_vol) * 100

            # Fading if latest volume < 50% of recent average
            if fade_pct < -50:
                return True, fade_pct, f"Volume fading {fade_pct:.1f}%"

            return False, fade_pct, f"Volume stable {fade_pct:+.1f}%"

        except Exception as e:
            logger.debug(f"{ticker}: Volume fade error - {e}")
            return False, 0, str(e)

    # ==================== COMPREHENSIVE QUALITY GATE ====================

    def run_quality_gate(
        self,
        ticker: str,
        hist: pd.DataFrame,
        position_size_dollars: float = 100,
        config: Optional[Dict] = None
    ) -> Dict:
        """
        Run all advanced filters on a ticker

        Args:
            ticker: Stock ticker
            hist: Historical price data
            position_size_dollars: Expected position size
            config: Optional configuration overrides

        Returns:
            Dict with all filter results and overall pass/fail
        """
        if config is None:
            config = {
                'liquidity_delta_threshold': -30.0,
                'max_slippage_pct': 3.0,
                'min_cash_runway_months': 6.0,
                'max_per_sector': 3,
                'check_volume_fade': True
            }

        results = {
            'ticker': ticker,
            'passed': True,
            'checks': {}
        }

        # 1. Liquidity delta
        liq_ok, liq_delta, liq_reason = self.check_liquidity_delta(
            ticker, hist, config['liquidity_delta_threshold']
        )
        results['checks']['liquidity_delta'] = {
            'passed': liq_ok,
            'delta_pct': liq_delta,
            'reason': liq_reason
        }
        if not liq_ok:
            results['passed'] = False

        # 2. Slippage
        slippage, slip_reason = self.estimate_slippage(ticker, position_size_dollars, hist)
        slip_ok = slippage <= config['max_slippage_pct']
        results['checks']['slippage'] = {
            'passed': slip_ok,
            'slippage_pct': slippage,
            'reason': slip_reason
        }
        if not slip_ok:
            results['passed'] = False

        # 3. Cash runway
        runway_ok, runway_months, runway_reason = self.check_cash_runway(
            ticker, config['min_cash_runway_months']
        )
        results['checks']['cash_runway'] = {
            'passed': runway_ok,
            'runway_months': runway_months,
            'reason': runway_reason
        }
        if not runway_ok:
            results['passed'] = False

        # 4. Sector diversification
        sector = self.get_sector(ticker)
        sector_ok, sector_count, sector_reason = self.check_sector_diversification(
            ticker, sector, config['max_per_sector']
        )
        results['checks']['sector'] = {
            'passed': sector_ok,
            'sector_name': sector,
            'count': sector_count,
            'reason': sector_reason
        }
        if not sector_ok:
            results['passed'] = False

        # 5. Volume fade
        if config['check_volume_fade']:
            fade_detected, fade_pct, fade_reason = self.detect_volume_fade(ticker, hist)
            results['checks']['volume_fade'] = {
                'detected': fade_detected,
                'fade_pct': fade_pct,
                'reason': fade_reason
            }
            if fade_detected:
                results['passed'] = False

        return results


# ==================== UTILITY FUNCTIONS ====================

def format_quality_report(results: Dict) -> str:
    """Format quality gate results as readable text"""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"QUALITY GATE: {results['ticker']}")
    lines.append(f"{'='*60}")

    for check_name, check_data in results['checks'].items():
        status = "✅" if check_data.get('passed', True) and not check_data.get('detected', False) else "❌"
        lines.append(f"{status} {check_name.upper()}: {check_data.get('reason', 'N/A')}")

    lines.append(f"{'='*60}")
    overall = "✅ PASSED" if results['passed'] else "❌ FAILED"
    lines.append(f"Overall: {overall}")
    lines.append(f"{'='*60}\n")

    return '\n'.join(lines)


if __name__ == '__main__':
    # Example usage
    logging.basicConfig(level=logging.INFO)

    filters = AdvancedRiskFilters()

    test_ticker = 'CLOV'
    stock = yf.Ticker(test_ticker)
    hist = stock.history(period='30d')

    # Run quality gate
    results = filters.run_quality_gate(test_ticker, hist, position_size_dollars=100)

    # Print report
    print(format_quality_report(results))
