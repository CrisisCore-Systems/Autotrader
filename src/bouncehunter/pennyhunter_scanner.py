"""
PennyHunter Gap Scanner Module
Discovers pre-market gap signals from ticker universe.

PRODUCTION VERSION - Real gap discovery with volume and market cap validation.
"""

import logging
from typing import List, Optional
from datetime import datetime, timedelta
import yfinance as yf

logger = logging.getLogger(__name__)


class GapScanner:
    """
    Scans ticker universe for gap-up signals.

    Production implementation that identifies:
    - Gaps >= 5% from previous close
    - Volume validation (>200k shares or >2x avg)
    - Market cap >= $100M
    - Listed exchanges (NYSE, NASDAQ, not OTC)
    """

    def __init__(self, config: Optional[any] = None):
        """
        Initialize gap scanner.

        Args:
            config: Optional configuration object with scanner settings
        """
        self.config = config

        # Scanner thresholds
        self.min_gap_pct = getattr(config, 'min_gap_pct', 5.0) if config else 5.0
        self.min_volume = getattr(config, 'min_volume', 200_000) if config else 200_000
        self.min_market_cap = getattr(config, 'min_market_cap', 100_000_000) if config else 100_000_000
        self.volume_spike_min = getattr(config, 'volume_spike_min', 2.0) if config else 2.0

        logger.info(
            f"GapScanner initialized: gap>={self.min_gap_pct}%, "
            f"vol>={self.min_volume:,}, mcap>=${self.min_market_cap/1e6:.0f}M, "
            f"vol_spike>={self.volume_spike_min}x"
        )

    def scan(self, ticker_list: List[str], date: Optional[str] = None) -> List[dict]:
        """
        Scan ticker list for gap signals.

        Args:
            ticker_list: List of tickers to scan
            date: Optional date string (YYYY-MM-DD). If None, uses today.

        Returns:
            List of gap signal dictionaries with ticker, gap_pct, volume, etc.
        """
        if date is None:
            scan_date = datetime.now()
        else:
            scan_date = datetime.strptime(date, "%Y-%m-%d")

        signals = []

        logger.info(f"Scanning {len(ticker_list)} tickers for gaps on {scan_date.strftime('%Y-%m-%d')}...")

        for ticker in ticker_list:
            try:
                signal = self._check_ticker(ticker, scan_date)
                if signal:
                    signals.append(signal)
                    logger.info(
                        f"✅ Gap signal: {ticker} +{signal['gap_pct']:.1f}% "
                        f"(vol {signal['volume']:,}, mcap ${signal['market_cap']/1e6:.0f}M)"
                    )
            except Exception as e:
                logger.warning(f"Error scanning {ticker}: {e}")
                continue

        logger.info(f"Scan complete: {len(signals)} gap signals found")
        return signals

    def _check_ticker(self, ticker: str, date: datetime) -> Optional[dict]:
        """
        Check if ticker has a valid gap signal.

        Returns:
            Dictionary with signal data if gap detected, None otherwise
        """
        # Fetch historical data (need 2 days minimum)
        start_date = date - timedelta(days=10)  # Get 10 days for avg volume
        end_date = date + timedelta(days=1)

        stock = yf.Ticker(ticker)

        # Get price data
        hist = stock.history(start=start_date.strftime("%Y-%m-%d"),
                             end=end_date.strftime("%Y-%m-%d"))

        if hist.empty or len(hist) < 2:
            return None

        # Find signal day
        signal_day = hist[hist.index.date == date.date()]
        if signal_day.empty:
            # Try next trading day
            signal_day = hist[hist.index.date >= date.date()].head(1)
            if signal_day.empty:
                return None

        # Get previous close
        prev_days = hist[hist.index < signal_day.index[0]]
        if prev_days.empty:
            return None

        prev_close = prev_days['Close'].iloc[-1]
        signal_open = signal_day['Open'].iloc[0]
        signal_volume = signal_day['Volume'].iloc[0]

        # Calculate gap percentage
        gap_pct = ((signal_open - prev_close) / prev_close) * 100

        # Check gap threshold
        if gap_pct < self.min_gap_pct:
            return None

        # Get market cap
        try:
            info = stock.info
            market_cap = info.get('marketCap', 0)
            exchange = info.get('exchange', 'UNKNOWN')
        except Exception:
            market_cap = 0
            exchange = 'UNKNOWN'

        # Validate market cap
        if market_cap < self.min_market_cap:
            logger.debug(f"{ticker}: Market cap ${market_cap/1e6:.0f}M below threshold")
            return None

        # Validate exchange (avoid OTC)
        if exchange not in ['NMS', 'NYQ', 'NASDAQ', 'NYSE', 'PCX', 'BATS']:
            logger.debug(f"{ticker}: Exchange '{exchange}' not supported")
            return None

        # Calculate volume spike vs 10-day average
        avg_volume = hist['Volume'].iloc[:-1].mean()  # Exclude signal day
        volume_spike = signal_volume / avg_volume if avg_volume > 0 else 0

        # Validate volume (either absolute or spike)
        if signal_volume < self.min_volume and volume_spike < self.volume_spike_min:
            logger.debug(
                f"{ticker}: Volume {signal_volume:,} below threshold "
                f"(spike {volume_spike:.1f}x)"
            )
            return None

        # Valid gap signal
        return {
            'ticker': ticker,
            'date': date.strftime("%Y-%m-%d"),
            'gap_pct': gap_pct,
            'prev_close': prev_close,
            'open': signal_open,
            'volume': int(signal_volume),
            'avg_volume': int(avg_volume),
            'volume_spike': volume_spike,
            'market_cap': market_cap,
            'exchange': exchange,
        }


# ===== CLI Testing =====

if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO)

    print("\n" + "="*70)
    print("GAP SCANNER TEST")
    print("="*70)

    # Test with default configuration
    scanner = GapScanner()

    # Test ticker list (from under10_tickers.txt)
    test_tickers = ["ADT", "SAN", "COMP", "INTR", "AHCO", "SNDL", "CLOV", "EVGO", "SENS", "SPCE"]

    # Scan for today
    if len(sys.argv) > 1:
        # Allow date override via CLI
        scan_date = sys.argv[1]
        print(f"\nScanning for date: {scan_date}")
        signals = scanner.scan(test_tickers, date=scan_date)
    else:
        print("\nScanning for today...")
        signals = scanner.scan(test_tickers)

    # Display results
    if signals:
        print(f"\n✅ Found {len(signals)} gap signals:")
        print("\nTicker  Gap%    Volume    Spike   Market Cap    Exchange")
        print("-" * 70)
        for sig in signals:
            print(
                f"{sig['ticker']:6s}  {sig['gap_pct']:5.1f}%  "
                f"{sig['volume']:9,}  {sig['volume_spike']:5.1f}x  "
                f"${sig['market_cap']/1e6:7.0f}M  {sig['exchange']:10s}"
            )
    else:
        print("\n❌ No gap signals found")

    print("\n" + "="*70)
