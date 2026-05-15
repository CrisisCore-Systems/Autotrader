#!/usr/bin/env python3
import sqlite3, json

db = sqlite3.connect('reports/crypto/crypto_experiments_collision_test.db')
cur = db.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print('Tables:', tables)
for t in tables:
    cur.execute(f'PRAGMA table_info({t})')
    cols = cur.fetchall()
    print(f'\n=== {t} ===')
    for c in cols:
        print(f'  {c[1]:40s} {c[2]}')
    # Print a sample row
    cur.execute(f'SELECT * FROM {t} LIMIT 1')
    row = cur.fetchone()
    if row:
        colnames = [d[0] for d in cur.description]
        print(f'  --- Sample row ---')
        for k, v in zip(colnames, row):
            print(f'  {k:40s} = {repr(v)[:80]}')
db.close()
