import sqlite3
from datetime import datetime

import pandas as pd
from transformers import pipeline


# --------------------------------
# FINBERT MODEL
# --------------------------------

sentiment_model = pipeline(
    "sentiment-analysis",
    model="ProsusAI/finbert"
)


# --------------------------------
# COMPANY MAPPING
# --------------------------------

company_map = {

    "Nvidia": "NVDA",
    "NVDA": "NVDA",
    "Jensen Huang": "NVDA",
    "CUDA": "NVDA",
    "RTX": "NVDA",
    "GeForce": "NVDA",

    "Microsoft": "MSFT",
    "MSFT": "MSFT",
    "Windows": "MSFT",
    "Xbox": "MSFT",
    "Azure": "MSFT",
    "Copilot": "MSFT",
    "Satya Nadella": "MSFT",

    "Apple": "AAPL",
    "AAPL": "AAPL",
    "iPhone": "AAPL",
    "iPad": "AAPL",
    "MacBook": "AAPL",
    "Safari": "AAPL",
    "Siri": "AAPL",
    "Tim Cook": "AAPL",

    "Tesla": "TSLA",
    "TSLA": "TSLA",
    "Elon Musk": "TSLA",
    "Cybertruck": "TSLA",
    "Model Y": "TSLA",
    "Model 3": "TSLA",
    "Autopilot": "TSLA",
    "FSD": "TSLA",
}


def detect_company(title, description):

    text = f"{title} {description}".lower()

    for keyword, ticker in company_map.items():

        if keyword.lower() in text:
            return ticker

    return "UNKNOWN"


# --------------------------------
# SENTIMENT VALUE
# --------------------------------

def calculate_sentiment_value(label, score):

    label = label.lower()

    if label == "positive":
        return score

    elif label == "negative":
        return -score

    return 0


# --------------------------------
# LOAD DATA
# --------------------------------

conn = sqlite3.connect("db/market.db")

news_df = pd.read_sql(
    """
    SELECT
        title,
        description
    FROM news
    """,
    conn
)

existing_sentiments = pd.read_sql(
    """
    SELECT title
    FROM sentiment
    """,
    conn
)

existing_titles = set(
    existing_sentiments["title"]
)

sentiment_rows = []


# --------------------------------
# ANALYZE NEWS
# --------------------------------

for _, row in news_df.iterrows():

    title = str(row["title"])
    description = str(
        row.get("description", "")
    )

    if title in existing_titles:
        continue

    result = sentiment_model(title)[0]

    ticker = detect_company(
        title,
        description
    )

    sentiment_value = calculate_sentiment_value(
        result["label"],
        result["score"]
    )

    sentiment_rows.append(
        {
            "ticker": ticker,
            "title": title,
            "sentiment_label": result["label"],
            "sentiment_score": result["score"],
            "sentiment_value": sentiment_value,
            "analyzed_at": datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        }
    )


# --------------------------------
# SAVE RESULTS
# --------------------------------

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

    print("\nTicker Counts:\n")
    print(
        sentiment_df["ticker"]
        .value_counts()
    )

else:

    print(
        "No new headlines to analyze"
    )

conn.close()