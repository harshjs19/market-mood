import sqlite3

conn = sqlite3.connect("db/market.db")

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    source TEXT,
    published_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT,
    date TEXT,
    close_price REAL,
    volume INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sentiment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT,
    title TEXT,
    sentiment_label TEXT,
    sentiment_score REAL,
    sentiment_value REAL,
    analyzed_at TEXT
)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_news_title
ON news(title)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_sentiment_ticker
ON sentiment(ticker)
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_prices_symbol
ON prices(symbol)
""")

conn.commit()

conn.close()

print("Database ready")