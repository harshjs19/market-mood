import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

sentiment_df = pd.read_sql(
    "SELECT * FROM sentiment",
    conn
)

print(sentiment_df)

conn.close()