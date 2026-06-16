import sqlite3

conn = sqlite3.connect("db/market.db")

cursor = conn.cursor()

cursor.execute("SELECT COUNT(*) FROM news")
news_count = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM prices")
price_count = cursor.fetchone()[0]

print(f"News rows: {news_count}")
print(f"Price rows: {price_count}")

conn.close()