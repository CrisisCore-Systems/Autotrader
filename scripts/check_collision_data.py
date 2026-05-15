#!/usr/bin/env python3
import pandas as pd

btc = pd.read_parquet('reports/crypto/collision_test/collision_data/kraken_BTC_USD_15m_features.parquet')
eth = pd.read_parquet('reports/crypto/collision_test/collision_data/kraken_ETH_USD_15m_features.parquet')

collision_ts = pd.Timestamp('2026-05-14 20:30:00+00:00')
btc_collision = btc[btc['timestamp'] == collision_ts].iloc[0]
eth_collision = eth[eth['timestamp'] == collision_ts].iloc[0]

print(f'BTC at {collision_ts}:')
print(f'  signal_candidate={btc_collision["signal_candidate"]:.0f}')
print(f'  tradeable_long={btc_collision["tradeable_long"]:.0f}')
print(f'  corr_regime={btc_collision["corr_regime"]}')
print(f'  mean_correlation={btc_collision["mean_correlation"]:.4f}')

print()
print(f'ETH at {collision_ts}:')
print(f'  signal_candidate={eth_collision["signal_candidate"]:.0f}')
print(f'  tradeable_long={eth_collision["tradeable_long"]:.0f}')
print(f'  corr_regime={eth_collision["corr_regime"]}')
print(f'  mean_correlation={eth_collision["mean_correlation"]:.4f}')
