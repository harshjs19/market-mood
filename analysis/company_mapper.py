import sqlite3
import pandas as pd


conn = sqlite3.connect("db/market.db")

news_df = pd.read_sql(
    "SELECT * FROM news",
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

print(
    news_df[
        ["title", "ticker"]
    ]
)

conn.close()