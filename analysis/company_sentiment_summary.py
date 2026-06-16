import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

df = pd.read_sql(
    """
    SELECT
        ticker,
        COUNT(*) as news_count,
        AVG(sentiment_value) as avg_sentiment
    FROM sentiment
    GROUP BY ticker
    ORDER BY avg_sentiment DESC
    """,
    conn
)

print(df)

conn.close()