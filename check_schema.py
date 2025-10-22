import sqlite3

conn = sqlite3.connect('bouncehunter_memory.db')
cursor = conn.cursor()

# Check if table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ticker_performance'")
exists = cursor.fetchone()

if exists:
    print("✅ ticker_performance table exists")
    print("\nTable schema:")
    cursor.execute("PRAGMA table_info(ticker_performance)")
    for row in cursor.fetchall():
        print(f"  - {row[1]} ({row[2]})")
    
    print("\nTable creation SQL:")
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ticker_performance'")
    print(cursor.fetchone()[0])
else:
    print("❌ ticker_performance table does NOT exist")

conn.close()
