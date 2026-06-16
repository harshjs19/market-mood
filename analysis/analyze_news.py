import sqlite3
import pandas as pd

from transformers import pipeline
from datetime import datetime

sentiment_model = pipeline(
    "sentiment-analysis",
    model="ProsusAI/finbert"
)

company_map = {
    "Nvidia": "NVDA",
    "Microsoft": "MSFT",
    "Windows": "MSFT",
    "Xbox": "MSFT",

    "Apple": "AAPL",
    "iPhone": "AAPL",
    "MacBook": "AAPL",
    "Jony Ive": "AAPL",

    "Tesla": "TSLA",
    "Elon Musk": "TSLA"
}


def detect_company(title):

    for company, ticker in company_map.items():

        if company.lower() in title.lower():
            return ticker

    return "UNKNOWN"


def calculate_sentiment_value(label, score):

    label = label.lower()

    if label == "positive":
        return score

    elif label == "negative":
        return -score

    else:
        return 0


conn = sqlite3.connect("db/market.db")

news_df = pd.read_sql(
    "SELECT title FROM news",
    conn
)

existing_sentiments = pd.read_sql(
    "SELECT title FROM sentiment",
    conn
)

existing_titles = set(
    existing_sentiments["title"]
)

sentiment_rows = []

for title in news_df["title"]:

    if title in existing_titles:
        continue

    result = sentiment_model(title)[0]

    ticker = detect_company(title)

    sentiment_value = calculate_sentiment_value(
        result["label"],
        result["score"]
    )

    sentiment_rows.append({
        "ticker": ticker,
        "title": title,
        "sentiment_label": result["label"],
        "sentiment_score": result["score"],
        "sentiment_value": sentiment_value,
        "analyzed_at": datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    })

if sentiment_rows:

    sentiment_df = pd.DataFrame(
        sentiment_rows
    )

    sentiment_df.to_sql(
        "sentiment",
        conn,
        if_exists="append",
        index=False
    )

    print(
        f"Inserted {len(sentiment_df)} sentiment rows"
    )

else:

    print(
        "No new headlines to analyze"
    )

conn.close()