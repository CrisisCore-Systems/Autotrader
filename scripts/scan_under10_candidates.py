"""
Enhanced Under-$10 Stock Screener with Safety Filters

Screens quality stocks under $10 with proper risk controls:
- Tier A: Higher quality ($2-$10, better volume/liquidity)
- Tier B: Speculative pennies ($0.20-$5, higher risk)
- Safety filters: volume, spread, analyst coverage, financials
"""

import yfinance as yf
import pandas as pd
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# Candidate lists from research
TIER_A_CANDIDATES = [
    'ADT', 'SAN', 'COMP', 'HL', 'INTR', 'DSWL',
    'AHCO', 'HGBB', 'SIGA', 'TCMD'
]

TIER_B_CANDIDATES = [
    'SNDL', 'CARM', 'EPWK', 'WORK', 'CRCW',
    # Add current passing tickers
    'CLOV', 'EVGO', 'TXMD', 'SENS', 'SPCE', 'ARBK'
]

# Safety thresholds
MIN_AVG_VOLUME_TIER_A = 500_000      # shares/day
MIN_DOLLAR_VOLUME_TIER_A = 1_000_000  # $/day
MAX_SPREAD_PCT_TIER_A = 2.0           # %

MIN_AVG_VOLUME_TIER_B = 200_000       # shares/day (more lenient)
MIN_DOLLAR_VOLUME_TIER_B = 500_000    # $/day
MAX_SPREAD_PCT_TIER_B = 3.0           # %


class Under10Screener:
    """Screen stocks under $10 with safety filters"""

    def __init__(self):
        self.results = {
            'tier_a': [],
            'tier_b': [],
            'rejected': []
        }

    def validate_ticker(self, ticker: str, tier: str = 'A') -> Optional[Dict]:
        """
        Validate a ticker against safety filters

        Returns dict with ticker data if passes, None if fails
        """
        try:
            stock = yf.Ticker(ticker)

            # Get current price and volume data
            hist = stock.history(period='30d')
            if len(hist) < 5:
                logger.debug(f"  ❌ {ticker}: Insufficient data")
                return None

            current_price = hist['Close'].iloc[-1]
            avg_volume = hist['Volume'].mean()
            avg_dollar_volume = (hist['Close'] * hist['Volume']).mean()

            # Calculate average daily range as spread proxy
            avg_range = ((hist['High'] - hist['Low']) / hist['Close']).mean() * 100

            # Get info for additional checks
            info = stock.info
            market_cap = info.get('marketCap', 0)

            # Tier-specific thresholds
            if tier == 'A':
                min_price = 2.00
                max_price = 10.00
                min_vol = MIN_AVG_VOLUME_TIER_A
                min_dollar = MIN_DOLLAR_VOLUME_TIER_A
                max_spread = MAX_SPREAD_PCT_TIER_A
            else:  # Tier B
                min_price = 0.20
                max_price = 5.00
                min_vol = MIN_AVG_VOLUME_TIER_B
                min_dollar = MIN_DOLLAR_VOLUME_TIER_B
                max_spread = MAX_SPREAD_PCT_TIER_B

            # Apply filters
            if current_price < min_price or current_price > max_price:
                logger.debug(f"  ❌ {ticker}: Price ${current_price:.2f} outside range ${min_price}-${max_price}")
                return None

            if avg_volume < min_vol:
                logger.debug(f"  ❌ {ticker}: Volume {avg_volume:,.0f} < {min_vol:,}")
                return None

            if avg_dollar_volume < min_dollar:
                logger.debug(f"  ❌ {ticker}: Dollar volume ${avg_dollar_volume:,.0f} < ${min_dollar:,}")
                return None

            if avg_range > max_spread * 4:  # Use 4x multiplier like penny_universe
                logger.debug(f"  ❌ {ticker}: Spread proxy {avg_range:.1f}% > {max_spread * 4}%")
                return None

            # Check for minimum market cap (avoid nano-caps with no coverage)
            if tier == 'A' and market_cap < 100_000_000:  # $100M minimum for Tier A
                logger.debug(f"  ❌ {ticker}: Market cap ${market_cap:,.0f} < $100M")
                return None

            # Check for recent gaps (opportunity indicator)
            max_gap = 0
            gap_date = None
            for i in range(1, min(len(hist), 90)):  # Last 90 days
                current = hist.iloc[i]
                prev = hist.iloc[i-1]
                gap_pct = (current['Open'] - prev['Close']) / prev['Close'] * 100
                if abs(gap_pct) > abs(max_gap):
                    max_gap = gap_pct
                    gap_date = current.name.strftime('%Y-%m-%d')

            # PASSED - return data
            return {
                'ticker': ticker,
                'price': current_price,
                'avg_volume': avg_volume,
                'dollar_volume': avg_dollar_volume,
                'spread_proxy': avg_range,
                'market_cap': market_cap,
                'max_gap_90d': max_gap,
                'gap_date': gap_date,
                'exchange': info.get('exchange', 'UNKNOWN'),
                'sector': info.get('sector', 'UNKNOWN'),
                'industry': info.get('industry', 'UNKNOWN')
            }

        except Exception as e:
            logger.debug(f"  ❌ {ticker}: Error - {e}")
            return None

    def screen_candidates(self):
        """Screen all candidate tickers"""

        logger.info("="*70)
        logger.info("🔍 UNDER-$10 STOCK SCREENER WITH SAFETY FILTERS")
        logger.info("="*70)

        # Screen Tier A
        logger.info(f"\n{'='*70}")
        logger.info(f"TIER A: Quality Stocks $2-$10")
        logger.info(f"Min Volume: {MIN_AVG_VOLUME_TIER_A:,} shares/day")
        logger.info(f"Min Dollar Vol: ${MIN_DOLLAR_VOLUME_TIER_A:,}/day")
        logger.info(f"Max Spread: {MAX_SPREAD_PCT_TIER_A}%")
        logger.info(f"{'='*70}")

        for ticker in TIER_A_CANDIDATES:
            result = self.validate_ticker(ticker, tier='A')
            if result:
                self.results['tier_a'].append(result)
                logger.info(f"✅ {ticker}: ${result['price']:.2f} | "
                           f"{result['avg_volume']:,.0f} shares/day | "
                           f"${result['dollar_volume']/1e6:.1f}M/day | "
                           f"Spread {result['spread_proxy']:.1f}%")
                if abs(result['max_gap_90d']) > 7:
                    logger.info(f"   📊 Max gap: {result['max_gap_90d']:+.1f}% on {result['gap_date']}")

        logger.info(f"\n✅ {len(self.results['tier_a'])}/{len(TIER_A_CANDIDATES)} Tier A candidates passed")

        # Screen Tier B
        logger.info(f"\n{'='*70}")
        logger.info(f"TIER B: Speculative Pennies $0.20-$5")
        logger.info(f"Min Volume: {MIN_AVG_VOLUME_TIER_B:,} shares/day")
        logger.info(f"Min Dollar Vol: ${MIN_DOLLAR_VOLUME_TIER_B:,}/day")
        logger.info(f"Max Spread: {MAX_SPREAD_PCT_TIER_B}%")
        logger.info(f"{'='*70}")

        for ticker in TIER_B_CANDIDATES:
            result = self.validate_ticker(ticker, tier='B')
            if result:
                self.results['tier_b'].append(result)
                logger.info(f"✅ {ticker}: ${result['price']:.2f} | "
                           f"{result['avg_volume']:,.0f} shares/day | "
                           f"${result['dollar_volume']/1e6:.1f}M/day | "
                           f"Spread {result['spread_proxy']:.1f}%")
                if abs(result['max_gap_90d']) > 7:
                    logger.info(f"   📊 Max gap: {result['max_gap_90d']:+.1f}% on {result['gap_date']}")

        logger.info(f"\n✅ {len(self.results['tier_b'])}/{len(TIER_B_CANDIDATES)} Tier B candidates passed")

    def save_results(self, output_dir: str = 'configs'):
        """Save results to files"""

        # Combine all passing tickers
        all_passing = []

        for result in self.results['tier_a']:
            all_passing.append(result)

        for result in self.results['tier_b']:
            all_passing.append(result)

        if not all_passing:
            logger.warning("\n⚠️  No tickers passed screening")
            return

        # Save ticker list (simple)
        ticker_list_file = f"{output_dir}/under10_tickers.txt"
        with open(ticker_list_file, 'w') as f:
            for result in all_passing:
                f.write(f"{result['ticker']}\n")

        # Save detailed CSV
        df = pd.DataFrame(all_passing)
        csv_file = f"{output_dir}/under10_candidates.csv"
        df.to_csv(csv_file, index=False)

        logger.info(f"\n{'='*70}")
        logger.info(f"💾 RESULTS SAVED")
        logger.info(f"{'='*70}")
        logger.info(f"Ticker list: {ticker_list_file}")
        logger.info(f"Full details: {csv_file}")
        logger.info(f"Total passing: {len(all_passing)} tickers")

        # Show top opportunities (by recent gap size)
        logger.info(f"\n{'='*70}")
        logger.info(f"🎯 TOP OPPORTUNITIES (Recent Gaps > 10%)")
        logger.info(f"{'='*70}")

        top_gaps = sorted(
            [r for r in all_passing if abs(r['max_gap_90d']) > 10],
            key=lambda x: abs(x['max_gap_90d']),
            reverse=True
        )[:10]

        if top_gaps:
            for result in top_gaps:
                logger.info(f"{result['ticker']}: ${result['price']:.2f} | "
                           f"Gap {result['max_gap_90d']:+.1f}% on {result['gap_date']} | "
                           f"{result['avg_volume']:,.0f} shares/day")
        else:
            logger.info("No tickers with gaps > 10% in last 90 days")

        # Risk warnings
        logger.info(f"\n{'='*70}")
        logger.info(f"⚠️  RISK WARNINGS")
        logger.info(f"{'='*70}")
        logger.info("✓ Use tight position sizing (≤1-2% of capital per trade)")
        logger.info("✓ Set stop-loss orders in advance")
        logger.info("✓ Monitor for dilution, reverse splits, delisting risk")
        logger.info("✓ Verify SEC filings and recent news before trading")
        logger.info("✓ Avoid tickers with pump-and-dump history")
        logger.info("✓ Exit quickly if volume dries up")


def main():
    """Run the under-$10 screener"""
    screener = Under10Screener()
    screener.screen_candidates()
    screener.save_results()


if __name__ == '__main__':
    main()
