# PennyHunter Guide 🎯

**Microcap trading preset for BounceHunter — Built for $200 accounts**

---

## Quick Start

```powershell
# 1. Run nightly scanner after market close
python run_pennyhunter_nightly.py

# 2. Scan specific tickers
python run_pennyhunter_nightly.py --tickers PLUG,MARA,RIOT,GEVO

# 3. Save report to file
python run_pennyhunter_nightly.py --output reports/pennyhunter_scan.txt

# 4. (Future) Live intraday with Questrade
python src/bouncehunter/agentic_cli.py --broker questrade --config configs/pennyhunter.yaml
```

---

## The PennyHunter Philosophy

Penny stocks are **NOT** normal stocks. They:
- Gap 20-50% on news/rumors then crash
- Halt mid-day for offerings
- Have 1-3% spreads (vs 0.01% on large caps)
- Get diluted via ATMs/convertibles
- Get pumped by retail/Discord/Twitter

**PennyHunter's edge:**
- Trade ONLY liquid microcaps ($1.5M+ volume/day)
- Use 2 proven playbooks (Runner VWAP, FRD Bounce)
- Risk $5 per trade (2.5% of $200 account)
- 1 position max (no portfolio risk)
- Strict guards (halts, offerings, SSR, spread)

---

## Universe Filters (What We Touch)

### Price Band
- **Min:** $0.20 (avoid sub-$0.20 manipulation)
- **Max:** $5.00 (microcap focus)

### Liquidity (CRITICAL)
- **Dollar volume:** ≥ $1.5M/day (10-day avg)
- **Share volume:** ≥ 300k shares/day (10-day avg)
- **Spread:** < 1.5% (avoid slippage traps)

### Exchanges
- **Allowed:** NASDAQ, NYSE, AMEX
- **Excluded:** OTC (too risky for $200 account)
- *Optional:* TSX/TSXV (Canadian small caps)

### Corporate Health
- ❌ No tickers with recent **offerings** (ATM/direct offerings nuke runners)
- ❌ No **regulatory halts**
- ❌ No **going concern warnings** (8-K red flags)
- ✅ Prefer **float < 50M** (tighter float = more explosive)

---

## Playbook 1: Runner VWAP (Gap & Go) 🚀

**Setup:**
- Premarket gap ≥ **+20%** on news/hype
- Opens above PM VWAP
- Volume spike ≥ **2.5×** average

**Entry:**
- VWAP reclaim (after first pullback)
- OR break of premarket high

**Exit:**
- **Take Profit:** +8% (scale 50%), +15% (rest)
- **Stop Loss:** Break of VWAP
- **Time Stop:** 40 minutes (if no move, exit)

**Example:**
```
TMQ gaps +24% on FDA approval news
Opens $1.86, PM VWAP $1.82
First pullback to $1.80 (holds VWAP)
Reclaims VWAP at $1.84 with 3.1× volume
Entry: $1.87
Stop: $1.79 (VWAP break)
TP1: $2.02 (+8%)
TP2: $2.15 (+15%)
```

**Guards:**
- Abort if spread > 1.5% (too wide)
- Skip if halted (wait 15min after resume)
- Skip within 24-48h of offerings

---

## Playbook 2: FRD Bounce (First Red Day) 📉

**Setup:**
- Prior day: range > **2.5× ATR(14)**, close in top 30%
- Today: gaps down ≥ -5%
- Panic flush: **RSI(2) < 5**, price hits **-2σ VWAP band**

**Entry:**
- Reclaim of flush candle high (confirms buyers stepping in)

**Exit:**
- **Take Profit:** +5% (scale 50%), +10% (rest)
- **Stop Loss:** -4% (tight for mean-revert)
- **Time Stop:** 3 hours (if no bounce, exit)

**Example:**
```
GEVO rallies from $1.20 to $2.80 (range 2.6×ATR), closes $2.70
Next day gaps down to $2.40 (-11%)
Sells off to $2.20 (-2σ band), RSI(2) = 3.2
Reclaims $2.30 flush high at 10:45 AM
Entry: $2.32
Stop: $2.22 (-4%)
TP1: $2.44 (+5%)
TP2: $2.55 (+10%)
```

**Guards:**
- Must have prior day strength (close in top 30%)
- Skip if offering news (ATM kills bounces)
- Skip if halt triggered (wait for clarity)

---

## Risk Management ($200 Account)

### Position Sizing
- **Per trade risk:** $5 (2.5% of $200)
- **Position size:** ~$50 (allows 10% stop distance)
- **Max positions:** 1 (ONE at a time)
- **Max trades/day:** 3 (prevent revenge trading)

### Stop Loss Rules
- **Always use server-side stops** (if broker allows)
- **Runner VWAP:** Stop at VWAP break
- **FRD Bounce:** Stop at -4% from entry
- **NO moving stops up** until +5% profit (let it breathe)

### Circuit Breakers
- **Daily loss limit:** $15 (3 losses) → STOP TRADING
- **Max drawdown:** 10% ($20) → Review strategy
- **3 consecutive losses:** Take a break, review trades

### Order Execution
- **Always use LIMIT orders** (never market orders in pennies)
- Place limits **0.1% from midpoint** (bid-ask midpoint)
- **NO chasing through halts** (if halted while flat, skip)
- Cancel if not filled in **30 seconds** (re-evaluate)

---

## Penny-Specific Guards

### Halts
- **Skip** tickers halted 2+ times today
- **Wait 15 minutes** after halt resumption
- **Track** halts in `penny_universe.add_halt(ticker)`

### SSR (Short Sale Restriction)
- Triggered when down **-10%+ from prior close**
- **Effect:** Shorts can't hit bid (can squeeze higher)
- **For longs:** SSR + VWAP reclaim = bullish tailwind

### Offerings/Dilution
- **Blacklist 2 days** after ATM/direct offering closes
- **Skip** convertible note filings (dilutes float)
- **Track** shares outstanding increases

### Spread Monitoring
- **Reject** if spread breaches 2% intraday
- **Monitor** bid/ask sizes (≥5k shares required)
- **Wide spread = liquidity drying up** → Exit

---

## Data & Execution

### Current Setup (EOD Approximation)
- **Nightly scanner:** `run_pennyhunter_nightly.py`
- **Data source:** yfinance (EOD bars)
- **Signals:** Approximate Runner/FRD from daily bars

### Future Setup (Intraday Live)
- **Broker:** Questrade (IQ Level 1 feed)
- **Bars:** 1-minute intraday data
- **VWAP:** Real-time calculation via `vwap_engine.py`
- **Signals:** Live Runner VWAP reclaims, FRD bounces

### Telegram Alerts
```
🟢 PennyHunter – Runner VWAP
TMQ  (float ~ 38M)  $1.86  spread 0.7%
Gap +24% | 1m vol 3.1× avg | VWAP reclaim 10:14
Entry 1.87  •  Stop 1.79 (-4.3%)  •  TP 2.02 / 2.15
Guards: no offering news • SSR: off • Halts: none
```

---

## Common Mistakes (Learn from Others)

### ❌ DON'T:
1. **Chase runners above +50%** → Already too extended
2. **Add after halts** → Spread explodes, liquidity vanishes
3. **Use market orders** → You'll get ripped on slippage
4. **Hold through offerings** → ATMs nuke price -30-50%
5. **Trade sub-$0.20 tickers** → Manipulation, no liquidity
6. **Hold overnight in pennies** → Gap risk is HUGE
7. **Risk >$5 per trade** → Account wipeout with 3-4 losses
8. **Trade multiple positions** → Portfolio risk in illiquid names

### ✅ DO:
1. **Wait for VWAP pullback + reclaim** → Let setup mature
2. **Check spread before entry** → If >1.5%, pass
3. **Use limits near midpoint** → Control fill price
4. **Exit immediately if offering news** → No hesitation
5. **Respect time stops** → If no move in 40min/3hr, exit
6. **Take profits at levels** → Don't get greedy in pennies
7. **Track halt history** → Repeat halters = trouble
8. **Journal every trade** → Review wins AND losses

---

## Troubleshooting

### "No signals found"
- **Normal on quiet days** → Pennies are event-driven
- **Try different tickers:** Use `--tickers` flag
- **Check filters:** Some days, nothing passes liquidity/spread

### "Spread too wide"
- **Skip the trade** → Slippage will eat your edge
- **Wait for normalization** → Spread tightens after volatility

### "Halted during entry"
- **If filled:** Hold, assess news when resumed
- **If not filled:** Cancel order, skip trade

### "Scanner found delisted tickers"
- **Update ticker list** → Some sample tickers are old
- **Use screener API** → Finviz, TradingView, ThinkorSwim

### "Signals not matching intraday"
- **EOD approximation** → Nightly scanner uses daily bars
- **Intraday required** → For live signals, need 1-min bars from Questrade

---

## File Structure

```
configs/
  pennyhunter.yaml              # Main config

src/bouncehunter/
  penny_universe.py             # Universe filters
  vwap_engine.py                # VWAP calculation engine
  signals/
    runner_vwap.py              # (Future) Runner VWAP signal
    frd_bounce.py               # (Future) FRD Bounce signal

run_pennyhunter_nightly.py      # EOD scanner (run daily)
```

---

## Configuration Reference

### Universe Settings
```yaml
universe:
  exchanges: [NASDAQ, NYSE, AMEX]
  price_min: 0.20
  price_max: 5.00
  min_avg_dollar_vol: 1500000    # $1.5M/day
  min_avg_volume: 300000          # 300k shares/day
  max_spread_pct: 1.5             # 1.5% max spread
  float_max_millions: 50          # Prefer <50M float
  exclude_otc: true
```

### Signal Settings
```yaml
signals:
  runner_vwap:
    premarket_gap_min_pct: 20
    volume_spike_mult: 2.5
    take_profit_pct: [8, 15]
    time_stop_min: 40

  frd_bounce:
    prior_day_range_mult_atr: 2.5
    rsi2_max: 5
    take_profit_pct: [5, 10]
    time_stop_min: 180
```

### Risk Settings
```yaml
risk:
  per_trade_risk_dollars: 5
  max_concurrent_positions: 1
  max_positions_per_day: 3
  order_type: limit
  daily_loss_limit_dollars: 15
  max_drawdown_pct: 10
```

---

## Next Steps

1. **Run nightly scanner** → Get tonight's watchlist
   ```powershell
   python run_pennyhunter_nightly.py --tickers PLUG,MARA,RIOT,GEVO,SNDL
   ```

2. **Paper trade setups** → Practice entries with paper broker
   ```powershell
   python src/bouncehunter/agentic_cli.py --broker paper --config configs/pennyhunter.yaml
   ```

3. **Resolve Questrade token** → Follow QUESTRADE_QUICKSTART.md
   - Configure callback URL in App Hub
   - Generate fresh token (40-70+ chars)
   - Test with `diagnose_questrade.py`

4. **Go live (small size)** → Once Questrade working
   - Start with $5 risk per trade
   - Track every trade in journal
   - Review after 20 trades minimum

---

## Support & Resources

- **Config:** `configs/pennyhunter.yaml`
- **Questrade Setup:** `QUESTRADE_QUICKSTART.md`
- **Token Issues:** `QUESTRADE_TOKEN_GUIDE.md`
- **General Docs:** `docs/` directory

**Questions?** Review trade logs in `logs/` or check `FEATURE_STATUS.md` for implementation status.

---

## Disclaimer

Penny stocks are **high-risk, high-volatility** instruments. PennyHunter is designed for:
- **Experienced traders** who understand microcap risks
- **Small accounts** starting with $200-500
- **Disciplined execution** (NO revenge trading, NO FOMO)

Past performance ≠ future results. Start small, track everything, and don't risk money you can't afford to lose.

**Discipline beats prediction. Many small wins > one big loss.**
