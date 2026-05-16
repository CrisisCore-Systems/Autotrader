# AutoTrader Validation Report v1

## Scope
Strategy: BounceHunter Agentic (backtest validation from agentic_backtest_results)
Mode: Backtest validation artifact
Framing: Validation Report v1 is a reproducible backtest validation artifact. It does not replace Phase 2 paper-trading validation. Live capital remains blocked until paper-trade sample validation is complete.
Capital: $100,000.00
Date range: 2019-01-01 to 2025-10-18
Trade sample size: 8

## Executive Verdict
Fail for live-capital eligibility.

## Core Metrics
- Total trades: 8
- Wins: 6
- Losses: 2
- Win rate: 75.00%
- Win rate confidence interval: [40.93%, 92.85%] (Wilson 95%)
- Average win: 10.00%
- Average loss: -5.00%
- Profit factor: 6.000
- Sharpe ratio: 0.977
- Max drawdown: 0.05%
- Average return per trade: 6.25%

## Loss Analysis
- Largest loss: COMP on 2021-08-10 (-5.00%)
- Repeated failure patterns: {'STOP': 2}
- Tickers responsible for losses: {'COMP': 1, 'INTR': 1}
- Regime during losses: {'normal': 2}
- Slippage or liquidity notes: No explicit slippage/liquidity loss note in source trades; investigate separately.

## Regime Breakdown
- Normal regime: 8
- High VIX regime: 0
- SPY stress regime: 0
- Unknown regime: 0

## Memory / Auto-Ejector Review
- Before memory hooks: win rate 46.88% over 32 samples
- After memory hooks: win rate 75.00% over 8 samples
- Ejection candidates: {'ADT': 5}
- Whether ejection logic behaved sensibly: Sensible based on repeated low-win-rate ejection notes

## Live Capital Gate
Decision: Fail
Required evidence before live use:
- Increase completed paper trade sample to >= 30
- Sustain positive profit factor and stable drawdown across regimes
- Demonstrate memory/ejector impact over a larger sample
- Provide slippage/liquidity stress checks
Hard stop conditions:
- Disable live capital if max drawdown exceeds 10%
- Disable live capital if 95% CI lower bound for win rate falls below 0.50
- Disable live capital on repeated unresolved broker/execution errors


## Conclusion
Validation artifacts generated from reports\agentic_backtest_results.json. Current sample supports a Fail verdict; expand sample size and regime coverage before any live-capital claim.

Validation Report v1 is a reproducible backtest validation artifact. It does not replace Phase 2 paper-trading validation. Live capital remains blocked until paper-trade sample validation is complete.
