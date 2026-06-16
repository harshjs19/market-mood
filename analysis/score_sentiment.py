import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

sentiment_df = pd.read_sql(
    "SELECT * FROM sentiment",
    conn
)

def sentiment_value(row):

    label = row["sentiment_label"].lower()
    score = row["sentiment_score"]

    if label == "positive":
        return score

    elif label == "negative":
        return -score

    else:
        return 0


sentiment_df["sentiment_value"] = sentiment_df.apply(
    sentiment_value,
    axis=1
)

print(
    sentiment_df[
        [
            "sentiment_label",
            "sentiment_score",
            "sentiment_value"
        ]
    ]
)

conn.close()