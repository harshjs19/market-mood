import sqlite3
import pandas as pd


def save_news_to_db():

    news_df = pd.read_csv(
        "news_data/news.csv"
    )

    conn = sqlite3.connect(
        "db/market.db"
    )

    existing_df = pd.read_sql(
        "SELECT title FROM news",
        conn
    )

    if not existing_df.empty:

        news_df = news_df[
            ~news_df["title"].isin(
                existing_df["title"]
            )
        ]

    if not news_df.empty:

        news_df.to_sql(
            "news",
            conn,
            if_exists="append",
            index=False
        )

        print(
            f"Inserted {len(news_df)} new rows"
        )

    else:

        print(
            "No new rows to insert"
        )

    conn.close()


save_news_to_db()