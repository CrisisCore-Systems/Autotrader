#!/usr/bin/env python3
"""
Robust ticker universe builder for PennyHunter.

This script:
1. Starts with a comprehensive list of penny stocks
2. Validates each ticker is currently tradeable
3. Checks liquidity, price range, and exchange
4. Removes delisted/problematic tickers
5. Saves a clean, validated list

Usage:
    python scripts/build_ticker_universe.py
"""

import yfinance as yf
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
TICKER_FILE = PROJECT_ROOT / "configs" / "under10_tickers.txt"
BLOCKLIST_FILE = PROJECT_ROOT / "configs" / "ticker_blocklist.txt"

# Universe criteria
MIN_PRICE = 0.50  # Avoid extreme penny stocks
MAX_PRICE = 10.00  # Keep under $10
MIN_AVG_VOLUME = 500_000  # 500K shares/day minimum
MIN_DOLLAR_VOL = 1_000_000  # $1M/day minimum
LOOKBACK_DAYS = 10  # Days to check

# Comprehensive penny stock candidate list (Oct 2025)
# Source: Mix of popular penny stocks, former high-flyers, and microcaps
CANDIDATE_TICKERS = [
    # Energy/Clean Tech
    'PLUG', 'FCEL', 'GEVO', 'BLNK', 'CLSK', 'RIOT', 'MARA', 'HUT', 'BITF',
    'EVGO', 'CHPT', 'SPI',
    
    # Cannabis
    'SNDL', 'TLRY', 'ACB', 'CGC', 'HEXO', 'OGI', 'CRON',
    
    # Healthcare/Biotech
    'OCGN', 'SENS', 'ATOS', 'SAVA', 'NVAX', 'VXRT', 'SRNE', 'TNXP', 
    'PROG', 'PHUN', 'CETX', 'JAGX', 'TBLT',
    
    # Shipping/Transport
    'CTRM', 'EBON', 'SOS', 'NAKD', 'ZOM',
    
    # Space/Aviation
    'SPCE', 'ASTR', 'RDW', 'ACHR',
    
    # FinTech/Tech
    'SOFI', 'UPST', 'HOOD', 'BBAI', 'RSKD', 'GROM',
    
    # EV/Automotive
    'NIO', 'XPEV', 'LI', 'GOEV', 'RIDE', 'WKHS', 'FSR', 'MULN',
    
    # Healthcare/Med Devices
    'CLOV', 'HIMS', 'OTRK', 'DOCS',
    
    # Real Estate/REITs
    'AGNC', 'NRZ', 'TWO', 'CIM',
    
    # Retail/Consumer
    'BBB Y', 'GME', 'AMC', 'EXPR', 'KOSS',
    
    # Telecom
    'T', 'VZ', 'TMUS', 'S',
    
    # Banks (penny stocks)
    'SAN', 'BBVA', 'ING', 'DB', 'CS',
    
    # Industrial
    'COMP', 'INTR', 'ADT', 'APLD',
    
    # Misc Microcaps
    'ANY', 'GNUS', 'CARV', 'GLBS', 'TELL', 'MARK', 'LMND',
    'AHCO', 'SDIG', 'BTBT', 'EQOS', 'KULR', 'BNGO'
]


def validate_ticker(ticker: str) -> Tuple[bool, Dict]:
    """
    Validate if a ticker meets our criteria.
    
    Returns:
        (is_valid, stats_dict)
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Get historical data
        hist = stock.history(period=f"{LOOKBACK_DAYS}d")
        
        if hist.empty or len(hist) < 5:
            logger.debug(f"❌ {ticker}: Insufficient price data ({len(hist)} days)")
            return False, {'reason': 'no_data'}
        
        # Get current price
        current_price = hist['Close'].iloc[-1]
        
        # Check price range
        if current_price < MIN_PRICE:
            logger.debug(f"❌ {ticker}: Price ${current_price:.2f} < ${MIN_PRICE}")
            return False, {'reason': 'price_too_low', 'price': current_price}
        
        if current_price > MAX_PRICE:
            logger.debug(f"❌ {ticker}: Price ${current_price:.2f} > ${MAX_PRICE}")
            return False, {'reason': 'price_too_high', 'price': current_price}
        
        # Check volume
        avg_volume = hist['Volume'].mean()
        if avg_volume < MIN_AVG_VOLUME:
            logger.debug(f"❌ {ticker}: Avg volume {avg_volume:,.0f} < {MIN_AVG_VOLUME:,.0f}")
            return False, {'reason': 'low_volume', 'volume': avg_volume}
        
        # Check dollar volume
        avg_dollar_vol = (hist['Close'] * hist['Volume']).mean()
        if avg_dollar_vol < MIN_DOLLAR_VOL:
            logger.debug(f"❌ {ticker}: Avg dollar vol ${avg_dollar_vol:,.0f} < ${MIN_DOLLAR_VOL:,.0f}")
            return False, {'reason': 'low_dollar_volume', 'dollar_vol': avg_dollar_vol}
        
        # Get exchange info (if available)
        info = stock.info
        exchange = info.get('exchange', 'UNKNOWN')
        
        # Reject OTC
        if 'OTC' in exchange.upper() or 'PINK' in exchange.upper():
            logger.debug(f"❌ {ticker}: OTC/Pink Sheets exchange")
            return False, {'reason': 'otc_exchange', 'exchange': exchange}
        
        # Calculate daily range
        avg_range_pct = ((hist['High'] - hist['Low']) / hist['Close'] * 100).mean()
        
        # PASSED - collect stats
        stats = {
            'price': current_price,
            'avg_volume': avg_volume,
            'avg_dollar_vol': avg_dollar_vol,
            'exchange': exchange,
            'avg_range_pct': avg_range_pct,
            'days_data': len(hist)
        }
        
        logger.info(
            f"✅ {ticker}: ${current_price:.2f}, {avg_volume:,.0f} shares/day, "
            f"${avg_dollar_vol/1e6:.1f}M/day, {exchange}"
        )
        
        return True, stats
        
    except Exception as e:
        logger.debug(f"❌ {ticker}: Error during validation: {e}")
        return False, {'reason': 'error', 'error': str(e)}


def load_blocklist() -> List[str]:
    """Load ticker blocklist."""
    if not BLOCKLIST_FILE.exists():
        return []
    
    blocklist = []
    with open(BLOCKLIST_FILE, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Handle both plain text and YAML format
                if line.startswith('- '):
                    ticker = line[2:].split(':')[0].strip()
                else:
                    ticker = line.split('#')[0].split(':')[0].strip()
                if ticker:
                    blocklist.append(ticker.upper())
    
    return blocklist


def build_universe() -> List[str]:
    """
    Build validated ticker universe.
    
    Returns:
        List of validated tickers
    """
    logger.info("=" * 70)
    logger.info("BUILDING ROBUST TICKER UNIVERSE")
    logger.info("=" * 70)
    logger.info(f"Criteria: Price ${MIN_PRICE}-${MAX_PRICE}, Volume {MIN_AVG_VOLUME:,.0f}+, Dollar Vol ${MIN_DOLLAR_VOL/1e6:.1f}M+")
    logger.info(f"Candidates: {len(CANDIDATE_TICKERS)} tickers")
    logger.info("")
    
    # Load blocklist
    blocklist = load_blocklist()
    logger.info(f"📋 Loaded blocklist: {len(blocklist)} tickers")
    if blocklist:
        logger.info(f"   Blocked: {', '.join(blocklist)}")
    logger.info("")
    
    # Filter out blocklist
    candidates = [t for t in CANDIDATE_TICKERS if t.upper() not in blocklist]
    logger.info(f"🔍 Screening {len(candidates)} candidates (after blocklist)...")
    logger.info("")
    
    # Validate each ticker
    validated = []
    stats_dict = {}
    rejection_reasons = {}
    
    for i, ticker in enumerate(candidates, 1):
        logger.info(f"[{i}/{len(candidates)}] Checking {ticker}...")
        
        is_valid, stats = validate_ticker(ticker)
        
        if is_valid:
            validated.append(ticker)
            stats_dict[ticker] = stats
        else:
            reason = stats.get('reason', 'unknown')
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
    
    # Summary
    logger.info("")
    logger.info("=" * 70)
    logger.info("VALIDATION COMPLETE")
    logger.info("=" * 70)
    logger.info(f"✅ VALIDATED: {len(validated)}/{len(candidates)} tickers passed")
    logger.info(f"❌ REJECTED: {len(candidates) - len(validated)} tickers")
    logger.info("")
    
    if rejection_reasons:
        logger.info("Rejection breakdown:")
        for reason, count in sorted(rejection_reasons.items(), key=lambda x: -x[1]):
            logger.info(f"   {reason}: {count}")
    logger.info("")
    
    # Sort by dollar volume (highest first)
    validated_sorted = sorted(
        validated,
        key=lambda t: stats_dict[t]['avg_dollar_vol'],
        reverse=True
    )
    
    # Show top 20
    logger.info("Top 20 by dollar volume:")
    for i, ticker in enumerate(validated_sorted[:20], 1):
        stats = stats_dict[ticker]
        logger.info(
            f"   {i:2d}. {ticker:6s} ${stats['price']:6.2f}  "
            f"{stats['avg_volume']/1e6:5.1f}M shares/day  "
            f"${stats['avg_dollar_vol']/1e6:5.1f}M/day  "
            f"{stats['exchange']}"
        )
    
    logger.info("")
    logger.info("=" * 70)
    
    return validated_sorted


def save_universe(tickers: List[str]):
    """Save validated tickers to file."""
    # Backup old file
    if TICKER_FILE.exists():
        backup_path = TICKER_FILE.with_suffix(f'.backup.{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt')
        TICKER_FILE.rename(backup_path)
        logger.info(f"📦 Backed up old file to: {backup_path.name}")
    
    # Write new file
    with open(TICKER_FILE, 'w') as f:
        f.write(f"# PennyHunter Validated Ticker Universe\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Criteria: ${MIN_PRICE}-${MAX_PRICE}, {MIN_AVG_VOLUME:,}+ volume, ${MIN_DOLLAR_VOL/1e6:.1f}M+ dollar vol\n")
        f.write(f"# Total: {len(tickers)} tickers\n")
        f.write(f"#\n")
        for ticker in tickers:
            f.write(f"{ticker}\n")
    
    logger.info(f"💾 Saved {len(tickers)} tickers to: {TICKER_FILE}")
    logger.info("")


def main():
    """Main execution."""
    # Build universe
    validated_tickers = build_universe()
    
    if not validated_tickers:
        logger.error("❌ No tickers validated! Check criteria or candidate list.")
        return
    
    # Save to file
    save_universe(validated_tickers)
    
    # Final summary
    logger.info("🎉 UNIVERSE BUILD COMPLETE!")
    logger.info(f"   {len(validated_tickers)} validated tickers ready for PennyHunter")
    logger.info(f"   Expected signals: {len(validated_tickers) * 0.1:.0f}-{len(validated_tickers) * 0.3:.0f} per day (10-30% gap rate)")
    logger.info("")
    logger.info("📋 NEXT STEPS:")
    logger.info("   1. Review new ticker list in configs/under10_tickers.txt")
    logger.info("   2. Run scanner: python run_pennyhunter_nightly.py")
    logger.info("   3. Test signals: python scripts/daily_validation.py")
    logger.info("")


if __name__ == "__main__":
    main()
