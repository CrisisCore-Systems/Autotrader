#!/usr/bin/env python3
import json, pathlib, sys

report = pathlib.Path('reports/crypto/collision_test/backtest_results/crypto_BTC_USD_4h_3184bf835461.json')
if not report.exists():
    # Find any crypto_* report
    reports = sorted(pathlib.Path('reports/crypto').rglob('crypto_*_*.json'))
    if not reports:
        print('No report files found')
        sys.exit(1)
    report = reports[0]

print(f'Reading: {report}')
data = json.loads(report.read_text())
print(json.dumps(data, indent=2))
