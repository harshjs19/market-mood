import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

news_df = pd.read_sql(
    "SELECT * FROM news",
    conn
)

sentiment_df = pd.read_sql(
    "SELECT * FROM sentiment",
    conn
)

company_map = {
    "Nvidia": "NVDA",
    "Microsoft": "MSFT",
    "Apple": "AAPL",
    "Tesla": "TSLA"
}


def detect_company(title):

    for company, ticker in company_map.items():

        if company.lower() in title.lower():
            return ticker

    return "UNKNOWN"


news_df["ticker"] = news_df["title"].apply(
    detect_company
)

merged_df = news_df.merge(
    sentiment_df,
    on="title"
)

print(
    merged_df[
        [
            "ticker",
            "title",
            "sentiment_label",
            "sentiment_score"
        ]
    ]
)

conn.close()