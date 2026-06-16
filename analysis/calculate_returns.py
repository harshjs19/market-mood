import pandas as pd

tickers = [
    "nvda",
    "msft",
    "aapl",
    "tsla"
]

for ticker in tickers:

    try:

        df = pd.read_csv(
            f"news_data/{ticker}_prices.csv"
        )

        first_price = df["Close"].iloc[0]
        last_price = df["Close"].iloc[-1]

        pct_return = (
            (last_price - first_price)
            / first_price
        ) * 100

        print(
            f"{ticker.upper()} : "
            f"{pct_return:.2f}%"
        )

    except Exception as e:

        print(
            f"{ticker.upper()} : {e}"
        )