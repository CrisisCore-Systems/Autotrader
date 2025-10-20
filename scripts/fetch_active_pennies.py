#!/usr/bin/env python
"""
Fetch Active Penny Stocks

Uses yfinance to screen for active, liquid penny stocks that meet PennyHunter criteria.
Saves results to configs/active_pennies.txt for use with scanner.

Criteria:
- Price: $0.20 - $5.00
- Volume: >500k shares/day average
- Market Cap: >$10M (avoid micro shells)
- Exchanges: NASDAQ, NYSE, AMEX only
- Not delisted/suspended

Usage:
    python scripts/fetch_active_pennies.py
    python scripts/fetch_active_pennies.py --output configs/my_pennies.txt
    python scripts/fetch_active_pennies.py --min-volume 1000000 --max-price 3.00
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
import yfinance as yf
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Curated list of penny stocks that are typically active
# (This is a starting list - we'll validate each one)
PENNY_CANDIDATES = [
    # Tech/Crypto
    'SNDL', 'GEVO', 'PLUG', 'ATOS', 'TELL', 'OCGN',
    # Shipping
    'SHIP', 'CTRM', 'EGLE', 'TOPS', 'GLBS', 'DSSI',
    # Energy/Battery
    'MULN', 'FFIE', 'NILE', 'EXPR', 'BBIG',
    # Biotech
    'SENS', 'TNXP', 'VXRT', 'AGRX', 'TXMD',
    # EV/Auto
    'RIDE', 'WKHS', 'GOEV', 'FSR', 'AYRO',
    # Misc
    'MMAT', 'VEON', 'IMMP', 'SXTC', 'VKTX',
    'JAGX', 'IDEX', 'XELA', 'KOSS', 'WIMI',
    # Recent movers (check if still active)
    'SOFI', 'WISH', 'MILE', 'HITI', 'GNUS',
    'INUV', 'FAMI', 'BFRI', 'BRQS', 'KIRK',
    # More recent
    'BLNK', 'CHPT', 'CLSK', 'MARA', 'RIOT',
    'BTBT', 'WULF', 'SOUN', 'AITX', 'EBON',
]


def validate_ticker(ticker: str, min_price: float, max_price: float, 
                    min_volume: int, min_mcap: float) -> dict:
    """
    Validate a ticker meets penny stock criteria.
    
    Returns:
        Dict with ticker info or None if invalid
    """
    try:
        stock = yf.Ticker(ticker)
        
        # Get recent data
        hist = stock.history(period='5d')
        if len(hist) == 0:
            logger.debug(f"{ticker}: No recent data - possibly delisted")
            return None
            
        # Get latest price and volume
        latest = hist.iloc[-1]
        price = latest['Close']
        volume = latest['Volume']
        
        # Calculate average volume over last 5 days
        avg_volume = hist['Volume'].mean()
        
        # Get market cap (if available)
        info = stock.info
        market_cap = info.get('marketCap', 0)
        exchange = info.get('exchange', 'UNKNOWN')
        
        # Validate price
        if price < min_price or price > max_price:
            logger.debug(f"{ticker}: Price ${price:.2f} outside range ${min_price}-${max_price}")
            return None
            
        # Validate volume
        if avg_volume < min_volume:
            logger.debug(f"{ticker}: Volume {avg_volume:,.0f} below min {min_volume:,}")
            return None
            
        # Validate market cap
        if market_cap > 0 and market_cap < min_mcap:
            logger.debug(f"{ticker}: Market cap ${market_cap:,.0f} below min ${min_mcap:,.0f}")
            return None
            
        # Validate exchange
        valid_exchanges = ['NMS', 'NYQ', 'ASE', 'NASDAQ', 'NYSE', 'AMEX']
        if exchange not in valid_exchanges:
            logger.debug(f"{ticker}: Exchange '{exchange}' not in approved list")
            return None
            
        logger.info(f"✅ {ticker}: ${price:.2f} | Vol {avg_volume:,.0f} | MCap ${market_cap:,.0f} | {exchange}")
        
        return {
            'ticker': ticker,
            'price': price,
            'avg_volume': avg_volume,
            'market_cap': market_cap,
            'exchange': exchange,
            'date': datetime.now().strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        logger.debug(f"{ticker}: Error - {e}")
        return None


def screen_pennies(candidates: list, min_price: float = 0.20, max_price: float = 5.00,
                   min_volume: int = 500000, min_mcap: float = 10000000) -> list:
    """
    Screen list of candidates for valid penny stocks.
    
    Args:
        candidates: List of ticker symbols to check
        min_price: Minimum price (default $0.20)
        max_price: Maximum price (default $5.00)
        min_volume: Minimum avg daily volume (default 500k)
        min_mcap: Minimum market cap (default $10M)
        
    Returns:
        List of dicts with ticker info
    """
    logger.info(f"🔍 Screening {len(candidates)} penny stock candidates...")
    logger.info(f"Criteria: ${min_price:.2f}-${max_price:.2f}, Vol >{min_volume:,}, MCap >${min_mcap:,.0f}")
    
    valid_tickers = []
    
    for ticker in candidates:
        result = validate_ticker(ticker, min_price, max_price, min_volume, min_mcap)
        if result:
            valid_tickers.append(result)
    
    logger.info(f"✅ Found {len(valid_tickers)} valid penny stocks")
    
    return valid_tickers


def save_results(tickers: list, output_path: str):
    """Save ticker list to file"""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Active Penny Stocks\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"# Count: {len(tickers)}\n")
        f.write(f"#\n")
        f.write(f"# Ticker | Price | Avg Volume | Market Cap | Exchange\n")
        f.write(f"#" + "-"*70 + "\n")
        
        for t in tickers:
            f.write(f"# {t['ticker']:6} | ${t['price']:5.2f} | {t['avg_volume']:12,.0f} | ${t['market_cap']:15,.0f} | {t['exchange']}\n")
        
        f.write(f"\n")
        
        # Just the ticker symbols (comma-separated for easy use)
        ticker_list = ','.join([t['ticker'] for t in tickers])
        f.write(ticker_list + "\n")
    
    logger.info(f"💾 Saved {len(tickers)} tickers to {output_file}")
    
    # Also save as CSV for analysis
    csv_path = output_file.with_suffix('.csv')
    df = pd.DataFrame(tickers)
    df.to_csv(csv_path, index=False)
    logger.info(f"💾 Saved CSV to {csv_path}")


def main():
    parser = argparse.ArgumentParser(description='Fetch active penny stocks')
    parser.add_argument('--output', default='configs/active_pennies.txt', 
                       help='Output file path')
    parser.add_argument('--min-price', type=float, default=0.20,
                       help='Minimum price (default $0.20)')
    parser.add_argument('--max-price', type=float, default=5.00,
                       help='Maximum price (default $5.00)')
    parser.add_argument('--min-volume', type=int, default=500000,
                       help='Minimum avg daily volume (default 500k)')
    parser.add_argument('--min-mcap', type=float, default=10000000,
                       help='Minimum market cap (default $10M)')
    parser.add_argument('--extra-tickers', 
                       help='Additional tickers to check (comma-separated)')
    args = parser.parse_args()
    
    # Build candidate list
    candidates = PENNY_CANDIDATES.copy()
    
    if args.extra_tickers:
        extra = [t.strip().upper() for t in args.extra_tickers.split(',')]
        candidates.extend(extra)
        logger.info(f"Added {len(extra)} extra tickers to check")
    
    # Remove duplicates
    candidates = list(set(candidates))
    
    # Screen tickers
    valid_tickers = screen_pennies(
        candidates,
        min_price=args.min_price,
        max_price=args.max_price,
        min_volume=args.min_volume,
        min_mcap=args.min_mcap
    )
    
    if not valid_tickers:
        logger.error("❌ No valid penny stocks found!")
        sys.exit(1)
    
    # Save results
    save_results(valid_tickers, args.output)
    
    # Print summary
    print("\n" + "="*70)
    print("ACTIVE PENNY STOCKS FOUND")
    print("="*70)
    print(f"Total: {len(valid_tickers)}")
    print(f"\nTicker List (copy for scanner):")
    print(','.join([t['ticker'] for t in valid_tickers]))
    print("="*70 + "\n")
    
    sys.exit(0)


if __name__ == '__main__':
    main()
