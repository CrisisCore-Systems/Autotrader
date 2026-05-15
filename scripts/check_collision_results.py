#!/usr/bin/env python3
import json
manifest = json.load(open('reports/crypto/collision_test/backtest_results_stressed/manifest_backtest_strategy.json'))
pr = manifest.get('portfolio_run', {})
print('=== PORTFOLIO RUN (WITH STRESS TEST - max_simultaneous_assets=1) ===')
print(f'portfolio_run_id: {pr.get("portfolio_run_id")}')
print(f'coordination_mode: {pr.get("coordination_mode")}')
print(f'total_trades: {pr.get("total_trades")}')
print(f'gated_signals_count: {pr.get("gated_signals_count")}')
print(f'portfolio_net_pnl: ${pr.get("portfolio_net_pnl"):.4f}')
print(f'portfolio_profit_factor: {pr.get("portfolio_profit_factor"):.4f}')
print(f'max_simultaneous_assets: {pr.get("max_simultaneous_assets")}')
