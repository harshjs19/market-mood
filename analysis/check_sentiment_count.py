import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

df = pd.read_sql(
    "SELECT COUNT(*) AS total FROM sentiment",
    conn
)

print(df)

conn.close()