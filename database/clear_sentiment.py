import sqlite3

conn = sqlite3.connect("db/market.db")

cursor = conn.cursor()

cursor.execute("DELETE FROM sentiment")

conn.commit()

conn.close()

print("Sentiment table cleared")