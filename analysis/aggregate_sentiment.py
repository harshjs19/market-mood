import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

sentiment_df = pd.read_sql(
    "SELECT * FROM sentiment",
    conn
)

sentiment_df = sentiment_df[
    sentiment_df["ticker"] != "UNKNOWN"
].copy()

summary = (
    sentiment_df
    .groupby("ticker")["sentiment_value"]
    .mean()
    .reset_index()
)

print(summary)

conn.close()