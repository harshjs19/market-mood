import sqlite3

conn = sqlite3.connect("db/market.db")
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", c.fetchall())

for table in ["news", "prices", "sentiment"]:
    c.execute(f"PRAGMA table_info({table})")
    print(f"\n{table} schema:")
    for row in c.fetchall():
        print(f"  {row}")

c.execute("SELECT name, sql FROM sqlite_master WHERE type='index'")
print("\nIndexes:")
for row in c.fetchall():
    print(f"  {row}")

for table in ["news", "prices", "sentiment"]:
    c.execute(f"SELECT COUNT(*) FROM {table}")
    print(f"\n{table} rows: {c.fetchone()[0]}")

# Sample rows
for table in ["news", "prices", "sentiment"]:
    c.execute(f"SELECT * FROM {table} LIMIT 3")
    rows = c.fetchall()
    print(f"\n{table} sample:")
    for row in rows:
        print(f"  {row}")

conn.close()
