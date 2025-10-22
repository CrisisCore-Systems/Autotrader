# Ticker List Maintenance Log

## October 20, 2025 - Delisted Tickers Removed

### Delisted Tickers (Removed)
- **NAKD** - No data found, delisted
- **ZOM** - 404 error, delisted  
- **TELL** - No data found, delisted
- **GNUS** - No data found, delisted

### Files Updated

1. **`run_pennyhunter_nightly.py`** (line 381-383)
   - Removed: NAKD, ZOM, TELL, GNUS
   - Added: CLOV, EVGO, SPCE, SENS (already active)
   - Updated comment: "Updated Oct 2025 - removed delisted"

2. **`src/bouncehunter/penny_universe.py`** (line 301-302)
   - Removed: NAKD, ZOM, TELL, GNUS (duplicated SNDL also removed)
   - Added: CLOV, EVGO, SPCE, SENS, SOFI
   - Updated comment: "Updated Oct 2025 - removed delisted"

3. **`scripts/fetch_active_pennies.py`** (line 40, 53)
   - Removed: TELL (line 40), GNUS (line 53)
   - Added: CLOV, EVGO, SPCE to end of list
   - Updated comment: "Updated Oct 2025"

4. **`configs/under10_tickers.txt`**
   - Added 8 new active tickers:
     * PLUG, MARA, RIOT, GEVO (crypto miners)
     * ATOS, OCGN (biotech/pharma)
     * CLSK (crypto mining)
     * SOFI (fintech)

### Verified Active Tickers (Oct 20, 2025)

✅ **Working** (tested via yfinance):
- ADT, SAN, COMP, INTR
- SNDL, CLOV, EVGO, PLUG
- MARA, RIOT, GEVO, ATOS
- OCGN, CLSK, SOFI
- SPCE, SENS

❌ **Delisted** (confirmed):
- NAKD, ZOM, TELL, GNUS

### Scanner Test Results

**After cleanup**:
```
Scanning 20 tickers:
✅ 2/20 passed PennyUniverse filters (CLOV, EVGO)
❌ Rejected: price=3, liquidity=2, spread=1, exchange=12
```

**Before cleanup**:
```
Scanning 20 tickers:
❌ 4 delisted errors (NAKD, ZOM, TELL, GNUS)
✅ 0/20 passed (all rejected)
```

### Recommended Ticker Sources (Future)

For automated ticker discovery, consider:
1. **Finviz Screener** (free API)
   - Filter: Price < $10, Volume > 500K
   - Exchange: NASDAQ, NYSE, AMEX
   
2. **Yahoo Finance Screeners**
   - Pre-built "Penny Stocks" filter
   - Updated daily

3. **TradingView Scanner**
   - Custom screener for under-$10 stocks
   - Technical filters available

### Maintenance Schedule

**Weekly** (recommended):
- Quick test: `python run_pennyhunter_nightly.py`
- Check for 404 errors or "delisted" warnings
- Remove bad tickers immediately

**Monthly**:
- Run `scripts/fetch_active_pennies.py` to refresh full list
- Update `configs/under10_tickers.txt` with validated tickers
- Archive removed tickers in this log

**Quarterly**:
- Full review of all ticker lists across codebase
- Integrate with automated screener API (TODO)

### Next Actions

1. ✅ Removed delisted tickers from all files
2. ✅ Added fresh active tickers
3. ✅ Tested scanner (working)
4. ⏳ Commit changes to Git
5. ⏳ Consider automating ticker validation (Phase 3 enhancement)

---

**Last Updated**: October 20, 2025  
**Status**: Scanner working, delisted tickers removed  
**Active Ticker Count**: 18 in under10_tickers.txt
