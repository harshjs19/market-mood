import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

df = pd.read_sql(
    """
    SELECT title
    FROM sentiment
    WHERE ticker = 'UNKNOWN'
    """,
    conn
)

print(df)

conn.close()