import os
import requests
import pandas as pd

SEARCH_QUERY = "Tesla OR Apple OR Nvidia OR Microsoft"

from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("NEWS_API_KEY")
if not api_key:
    raise ValueError("NEWS_API_KEY not found")


def get_news():

    url = "https://newsapi.org/v2/everything"

    params = {
        "q": SEARCH_QUERY,
        "language": "en",
        "pageSize": 10,
        "apiKey": api_key
    }

    response = requests.get(url, params=params)

    data = response.json()

    return data["articles"]


articles = get_news()

news_list = []

for item in articles:

    news_list.append({
        "title": item["title"],
        "source": item["source"]["name"],
        "published_at": item["publishedAt"]
    })

news_df = pd.DataFrame(news_list)

news_df.to_csv(
    "news_data/news.csv",
    index=False
)

print(f"Saved {len(news_df)} articles")