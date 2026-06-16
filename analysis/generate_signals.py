import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

df = pd.read_sql("""
SELECT
    ticker,
    COUNT(*) as news_count,
    AVG(sentiment_value) as avg_sentiment
FROM sentiment
WHERE ticker != 'UNKNOWN'
GROUP BY ticker
""", conn)


def generate_signal(score):

    if score >= 0.15:
        return "BUY"

    elif score <= -0.15:
        return "SELL"

    else:
        return "HOLD"


df["signal"] = df["avg_sentiment"].apply(
    generate_signal
)

print(
    df[
        [
            "ticker",
            "news_count",
            "avg_sentiment",
            "signal"
        ]
    ]
)

conn.close()