import sqlite3
import pandas as pd

conn = sqlite3.connect("db/market.db")

news_df = pd.read_sql(
    "SELECT * FROM news",
    conn
)

COMPANY_KEYWORDS = {

    "AAPL": [
        "apple",
        "iphone",
        "ipad",
        "macbook",
        "ios",
        "safari",
        "tim cook",
        "vision pro"
    ],

    "MSFT": [
        "microsoft",
        "windows",
        "azure",
        "xbox",
        "office",
        "copilot",
        "satya nadella",
        "surface"
    ],

    "NVDA": [
        "nvidia",
        "rtx",
        "geforce",
        "cuda",
        "gpu",
        "jensen huang"
    ],

    "TSLA": [
        "tesla",
        "elon musk",
        "cybertruck",
        "model y",
        "model 3",
        "autopilot",
        "fsd"
    ]
}


def detect_company(title):

    title = str(title).lower()

    for ticker, keywords in COMPANY_KEYWORDS.items():

        for keyword in keywords:

            if keyword.lower() in title:
                return ticker

    return "UNKNOWN"


news_df["ticker"] = news_df["title"].apply(
    detect_company
)

print(
    news_df[
        ["title", "ticker"]
    ]
)

print("\nTicker Counts:\n")
print(news_df["ticker"].value_counts())

conn.close()