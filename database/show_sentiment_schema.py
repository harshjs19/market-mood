import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

schema = pd.read_sql(
    "PRAGMA table_info(sentiment)",
    conn
)

print(schema)

conn.close()