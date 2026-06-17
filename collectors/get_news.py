import os
from datetime import datetime, timedelta, UTC

import pandas as pd
import requests
from dotenv import load_dotenv


# --------------------------------
# CONFIG
# --------------------------------

QUERIES = [
    "Microsoft",
    "Apple",
    "Nvidia",
    "Tesla"
]

load_dotenv()

api_key = os.getenv("NEWS_API_KEY")

if not api_key:
    raise ValueError("NEWS_API_KEY not found")


# --------------------------------
# NEWS FETCH
# --------------------------------

def get_news():

    url = "https://newsapi.org/v2/everything"

    from_date = (
        datetime.now(UTC) - timedelta(days=7)
    ).strftime("%Y-%m-%d")

    all_articles = []

    for query in QUERIES:

        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 25,
            "from": from_date,
            "apiKey": api_key,
        }

        response = requests.get(
            url,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        print(
            f"{query}: "
            f"{len(data.get('articles', []))} articles"
        )

        all_articles.extend(
            data.get("articles", [])
        )

    return all_articles


# --------------------------------
# PROCESS ARTICLES
# --------------------------------

articles = get_news()

news_list = []

for item in articles:

    news_list.append(
        {
            "title": item.get("title"),
            "description": item.get("description"),
            "source": item.get("source", {}).get("name"),
            "published_at": item.get("publishedAt"),
        }
    )

news_df = pd.DataFrame(news_list)

news_df = news_df.drop_duplicates(
    subset=["title"]
)

news_df.to_csv(
    "news_data/news.csv",
    index=False,
)

print(f"Saved {len(news_df)} articles")
print(
    "Latest article date:",
    news_df["published_at"].max()
)