import yfinance as yf


def get_prices(symbol):

    ticker = yf.Ticker(symbol)

    price_df = ticker.history(period="30d")

    file_name = f"news_data/{symbol.lower()}_prices.csv"

    price_df.to_csv(file_name)

    print(f"Saved {len(price_df)} rows for {symbol}")


symbols = [
    "TSLA",
    "NVDA",
    "MSFT",
    "AAPL"
]

for symbol in symbols:

    get_prices(symbol)