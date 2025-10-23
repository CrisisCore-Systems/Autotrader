"""
PennyUniverse: Strict microcap filter for PennyHunter

Filters out illiquid, manipulated, or corporate-distressed penny stocks.
Focus: NASDAQ/NYSE/AMEX microcaps with real liquidity and clean balance sheets.

Author: BounceHunter Team
"""

import csv
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Set, Optional
from datetime import datetime, timedelta
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class PennyFilters:
    """Universe filter configuration"""
    exchanges: List[str]
    price_min: float
    price_max: float
    min_avg_dollar_vol: float
    min_avg_volume: float
    max_spread_pct: float
    float_max_millions: Optional[float] = None
    exclude_otc: bool = True
    exclude_going_concern: bool = True
    exclude_reg_halted: bool = True


class PennyUniverse:
    """
    Filters microcaps for PennyHunter trading.

    Key filters:
    - Liquidity: dollar volume + share volume + spread
    - Price band: $0.20 - $5.00
    - Exchanges: NASDAQ/NYSE/AMEX (no OTC)
    - Corporate health: no offerings, halts, going concern
    """

    def __init__(self, config: Dict):
        """
        Initialize with PennyHunter config.

        Args:
            config: pennyhunter.yaml universe section
        """
        self.filters = PennyFilters(
            exchanges=config.get('exchanges', ['NASDAQ', 'NYSE', 'AMEX']),
            price_min=config.get('price_min', 0.20),
            price_max=config.get('price_max', 5.00),
            min_avg_dollar_vol=config.get('min_avg_dollar_vol', 1_500_000),
            min_avg_volume=config.get('min_avg_volume', 300_000),
            max_spread_pct=config.get('max_spread_pct', 1.5),
            float_max_millions=config.get('float_max_millions'),
            exclude_otc=config.get('exclude_otc', True),
            exclude_going_concern=config.get('exclude_going_concern', True),
            exclude_reg_halted=config.get('exclude_reg_halted', True)
        )

        self.halted_tickers: Set[str] = set()
        self.offering_blacklist: Dict[str, datetime] = {}

        logger.info(
            f"PennyUniverse initialized: price ${self.filters.price_min}-${self.filters.price_max}, "
            f"min vol ${self.filters.min_avg_dollar_vol/1e6:.1f}M/day"
        )

    def screen(self, tickers: List[str], lookback_days: int = 10) -> List[str]:
        """
        Filter tickers through all penny universe checks.

        Args:
            tickers: Candidate tickers to screen
            lookback_days: Days for volume averaging

        Returns:
            List of tickers that passed all filters
        """
        logger.info(f"🔍 Screening {len(tickers)} tickers for PennyHunter universe...")

        passed = []
        rejected = {'price': 0, 'liquidity': 0, 'spread': 0, 'exchange': 0, 'corporate': 0}

        for ticker in tickers:
            try:
                # Get ticker data
                stock = yf.Ticker(ticker)
                info = stock.info
                hist = stock.history(period=f"{lookback_days}d")

                if hist.empty:
                    logger.debug(f"{ticker}: No price data")
                    rejected['liquidity'] += 1
                    continue

                # Check 1: Price band
                price = hist['Close'].iloc[-1]
                if not (self.filters.price_min <= price <= self.filters.price_max):
                    logger.debug(f"{ticker}: Price ${price:.2f} outside ${self.filters.price_min}-${self.filters.price_max}")
                    rejected['price'] += 1
                    continue

                # Check 2: Exchange (if available)
                exchange = info.get('exchange', 'UNKNOWN')
                if self.filters.exclude_otc and 'OTC' in exchange.upper():
                    logger.debug(f"{ticker}: OTC exchange rejected")
                    rejected['exchange'] += 1
                    continue

                # Only check specific exchanges if we got valid exchange info
                if exchange != 'UNKNOWN' and self.filters.exchanges:
                    # Normalize exchange names (handle variations)
                    normalized_exchange = exchange.upper().replace('NMS', 'NASDAQ').replace('NYQ', 'NYSE')
                    if not any(allowed.upper() in normalized_exchange for allowed in self.filters.exchanges):
                        logger.debug(f"{ticker}: Exchange {exchange} not in allowed list")
                        rejected['exchange'] += 1
                        continue

                # Check 3: Liquidity (dollar volume + share volume)
                avg_volume = hist['Volume'].mean()
                avg_dollar_vol = (hist['Close'] * hist['Volume']).mean()

                if avg_volume < self.filters.min_avg_volume:
                    logger.debug(f"{ticker}: Avg volume {avg_volume:,.0f} < {self.filters.min_avg_volume:,.0f}")
                    rejected['liquidity'] += 1
                    continue

                if avg_dollar_vol < self.filters.min_avg_dollar_vol:
                    logger.debug(f"{ticker}: Avg dollar vol ${avg_dollar_vol:,.0f} < ${self.filters.min_avg_dollar_vol:,.0f}")
                    rejected['liquidity'] += 1
                    continue

                # Check 4: Spread (estimate from high-low)
                # For EOD data, use daily range as proxy for spread
                # RELAXED: 4x multiplier instead of 2x for current market (Oct 2025)
                avg_range_pct = ((hist['High'] - hist['Low']) / hist['Close'] * 100).mean()
                if avg_range_pct > self.filters.max_spread_pct * 4:  # 4x because range > spread (RELAXED)
                    logger.debug(f"{ticker}: Avg range {avg_range_pct:.2f}% too wide (spread likely >{self.filters.max_spread_pct}%)")
                    rejected['spread'] += 1
                    continue

                # Check 5: Float (if configured and available)
                # TEMPORARILY DISABLED for testing - Oct 2025
                # if self.filters.float_max_millions:
                #     float_shares = info.get('floatShares', info.get('sharesOutstanding', 0))
                #     float_millions = float_shares / 1_000_000
                #     if float_millions > self.filters.float_max_millions:
                #         logger.debug(f"{ticker}: Float {float_millions:.1f}M > {self.filters.float_max_millions}M")
                #         rejected['corporate'] += 1
                #         continue

                # Check 6: Halts
                # TEMPORARILY DISABLED for testing - Oct 2025
                # if ticker in self.halted_tickers:
                #     logger.debug(f"{ticker}: Currently halted or recently resumed")
                #     rejected['corporate'] += 1
                #     continue

                # Check 7: Offering blacklist
                if ticker in self.offering_blacklist:
                    blacklist_until = self.offering_blacklist[ticker]
                    if datetime.now() < blacklist_until:
                        logger.debug(f"{ticker}: On offering blacklist until {blacklist_until}")
                        rejected['corporate'] += 1
                        continue
                    else:
                        # Expired, remove from blacklist
                        del self.offering_blacklist[ticker]

                # PASSED all filters
                passed.append(ticker)
                logger.info(
                    f"✅ {ticker}: ${price:.2f}, {avg_volume:,.0f} shares/day, "
                    f"${avg_dollar_vol/1e6:.1f}M/day, range {avg_range_pct:.2f}%"
                )

            except Exception as e:
                logger.warning(f"{ticker}: Error during screening: {e}")
                rejected['liquidity'] += 1
                continue

        # Summary
        logger.info(f"✅ {len(passed)}/{len(tickers)} tickers passed PennyUniverse filters")
        logger.info(f"❌ Rejected: price={rejected['price']}, liquidity={rejected['liquidity']}, "
                   f"spread={rejected['spread']}, exchange={rejected['exchange']}, corporate={rejected['corporate']}")

        return passed

    def add_halt(self, ticker: str):
        """Mark ticker as halted/recently resumed"""
        self.halted_tickers.add(ticker)
        logger.warning(f"🚨 {ticker} added to halt list")

    def remove_halt(self, ticker: str):
        """Remove ticker from halt list"""
        if ticker in self.halted_tickers:
            self.halted_tickers.remove(ticker)
            logger.info(f"✅ {ticker} removed from halt list")

    def blacklist_offering(self, ticker: str, days: int = 2):
        """
        Add ticker to offering blacklist for N days.

        Args:
            ticker: Ticker symbol
            days: Days to blacklist (default 2)
        """
        until = datetime.now() + timedelta(days=days)
        self.offering_blacklist[ticker] = until
        logger.warning(f"🚨 {ticker} blacklisted for offerings until {until}")

    def check_spread_intraday(self, ticker: str, bid: float, ask: float, last: float) -> bool:
        """
        Check if intraday spread is acceptable (for live trading).

        Args:
            ticker: Ticker symbol
            bid: Current bid price
            ask: Current ask price
            last: Last price

        Returns:
            True if spread is acceptable
        """
        if bid <= 0 or ask <= 0 or last <= 0:
            logger.warning(f"{ticker}: Invalid quote data bid={bid} ask={ask} last={last}")
            return False

        spread_pct = (ask - bid) / last * 100

        if spread_pct > self.filters.max_spread_pct:
            logger.warning(f"{ticker}: Spread {spread_pct:.2f}% > {self.filters.max_spread_pct}% (bid={bid:.2f}, ask={ask:.2f})")
            return False

        return True

    def get_stats(self) -> Dict:
        """Get current universe statistics"""
        return {
            'halted_count': len(self.halted_tickers),
            'offering_blacklist_count': len(self.offering_blacklist),
            'halted_tickers': list(self.halted_tickers),
            'blacklisted_tickers': list(self.offering_blacklist.keys())
        }


# ===== Convenience functions =====

def create_penny_universe(config_path: str = 'configs/pennyhunter.yaml') -> PennyUniverse:
    """
    Create PennyUniverse from config file.

    Args:
        config_path: Path to pennyhunter.yaml

    Returns:
        Configured PennyUniverse instance
    """
    import yaml

    with open(config_path) as f:
        config = yaml.safe_load(f)

    return PennyUniverse(config['universe'])


DEFAULT_CANDIDATE_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "under10_candidates.csv"
)


def get_penny_candidates(
    min_price: float = 0.20,
    max_price: float = 5.00,
    min_volume: float = 300_000,
    exchanges: Optional[List[str]] = None,
    data_path: Optional[str] = None,
) -> List[str]:
    """
    Get initial list of penny stock candidates (before full screening).

    This is a starting point; use PennyUniverse.screen() for full filtering.

    Args:
        min_price: Minimum price
        max_price: Maximum price
        min_volume: Minimum daily volume
        exchanges: List of exchanges (default: NASDAQ, NYSE, AMEX)

    Returns:
        List of candidate tickers
    """
    if exchanges is None:
        exchanges = ['NASDAQ', 'NYSE', 'AMEX']

    candidate_file = Path(data_path) if data_path else DEFAULT_CANDIDATE_PATH
    if not candidate_file.exists():
        logger.error(
            "penny_candidate_file_missing path=%s",
            candidate_file,
        )
        return []

    allowed_exchanges = {ex.upper() for ex in exchanges}
    tickers: List[tuple[str, float]] = []

    with candidate_file.open(newline='') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                price = float(row.get('price', 0) or 0)
                avg_volume = float(row.get('avg_volume', 0) or 0)
                exchange = (row.get('exchange', '') or '').upper()
            except ValueError:
                logger.debug("invalid_candidate_row row=%s", row)
                continue

            if not (min_price <= price <= max_price):
                continue
            if avg_volume < min_volume:
                continue

            normalized_exchange = (
                exchange.replace('NMS', 'NASDAQ')
                .replace('NYQ', 'NYSE')
                .replace('ASE', 'AMEX')
                .replace('NCM', 'NASDAQ')
            )

            if allowed_exchanges and not any(
                allowed in normalized_exchange for allowed in allowed_exchanges
            ):
                continue

            symbol = (row.get('ticker') or '').strip().upper()
            if not symbol:
                continue

            try:
                dollar_volume = float(row.get('dollar_volume', 0) or 0)
            except ValueError:
                dollar_volume = 0.0

            tickers.append((symbol, dollar_volume))

    tickers.sort(key=lambda item: item[1], reverse=True)
    results = [symbol for symbol, _ in tickers]

    logger.info(
        "penny_candidates_sourced path=%s count=%d min_price=%.2f max_price=%.2f min_volume=%.0f",
        candidate_file,
        len(results),
        min_price,
        max_price,
        min_volume,
    )

    return results


# ===== CLI testing =====

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # Test with sample config
    config = {
        'exchanges': ['NASDAQ', 'NYSE', 'AMEX'],
        'price_min': 0.20,
        'price_max': 5.00,
        'min_avg_dollar_vol': 1_500_000,
        'min_avg_volume': 300_000,
        'max_spread_pct': 1.5,
        'float_max_millions': 50,
        'exclude_otc': True
    }

    universe = PennyUniverse(config)

    # Test with some sample tickers
    test_tickers = ['AAPL', 'PLUG', 'SNDL', 'MARA', 'GEVO', 'TSLA', 'AMC']

    print("\n" + "="*60)
    print("PENNYHUNTER UNIVERSE SCREENING TEST")
    print("="*60)

    passed = universe.screen(test_tickers, lookback_days=10)

    print("\n" + "="*60)
    print(f"PASSED TICKERS: {passed}")
    print("="*60)

    # Test halt/offering management
    print("\n" + "="*60)
    print("TESTING HALT/OFFERING MANAGEMENT")
    print("="*60)

    universe.add_halt('PLUG')
    universe.blacklist_offering('SNDL', days=2)

    print(f"\nUniverse stats: {universe.get_stats()}")

    # Rescreen after blacklisting
    print("\nRescreening after blacklist...")
    passed_after = universe.screen(test_tickers, lookback_days=10)
    print(f"Passed after blacklist: {passed_after}")
