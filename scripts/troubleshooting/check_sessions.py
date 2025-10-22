import json

# Load cumulative history
with open('reports/pennyhunter_cumulative_history.json', 'r') as f:
    h = json.load(f)

print('Total sessions:', h['total_sessions'])
print('First trade:', h['first_trade_date'])
print('Last updated:', h['last_updated'])
print('\nSession markers:')
for t in h['trades']:
    if t.get('type') == 'session_marker':
        print(f"  Session {t['session_id']}: {t['date']}")
