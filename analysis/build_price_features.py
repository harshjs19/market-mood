from pathlib import Path
import sqlite3

import pandas as pd


# ----------------------------
# CONFIGURATION
# ----------------------------

DB_PATH = Path("db/market.db")
PRICES_TABLE = "prices"

REQUIRED_COLUMNS = {
    "symbol",
    "date",
    "close_price",
    "volume",
}

VOLUME_AVERAGE_WINDOW = 5
VOLATILITY_WINDOW = 10


# ----------------------------
# DATABASE LOADING
# ----------------------------

def connect_to_database():
    """Open the existing SQLite database without silently creating a new file."""

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}. Run database/setup_db.py first."
        )

    return sqlite3.connect(DB_PATH)


def validate_prices_table(conn):
    """Confirm the prices table exists and contains the expected schema."""

    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (PRICES_TABLE,),
    ).fetchone()

    if not table_exists:
        raise RuntimeError(
            f"Missing table: {PRICES_TABLE}. Run database/setup_db.py first."
        )

    table_columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({PRICES_TABLE})")
    }

    missing_columns = REQUIRED_COLUMNS - table_columns

    if missing_columns:
        raise RuntimeError(
            f"{PRICES_TABLE} table is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )


def load_prices(conn):
    """Read all ticker price rows from SQLite."""

    validate_prices_table(conn)

    return pd.read_sql_query(
        """
        SELECT
            symbol,
            date,
            close_price,
            volume
        FROM prices
        ORDER BY symbol, date
        """,
        conn,
    )


# ----------------------------
# DATA CLEANING
# ----------------------------

def normalize_prices(price_df):
    """Clean raw SQLite rows and prepare a stable ticker/date time series."""

    if price_df.empty:
        raise ValueError(
            "No price rows found in the prices table."
        )

    normalized_df = price_df.copy()

    # Normalize text keys before validation and grouping.
    normalized_df["symbol"] = (
        normalized_df["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    normalized_df["date"] = pd.to_datetime(
        normalized_df["date"],
        errors="coerce",
        utc=True,
    )

    normalized_df["close_price"] = pd.to_numeric(
        normalized_df["close_price"],
        errors="coerce",
    )

    normalized_df["volume"] = pd.to_numeric(
        normalized_df["volume"],
        errors="coerce",
    )

    invalid_rows = (
        normalized_df["symbol"].eq("")
        | normalized_df["symbol"].eq("NAN")
        | normalized_df["date"].isna()
        | normalized_df["close_price"].isna()
        | normalized_df["volume"].isna()
        | normalized_df["close_price"].le(0)
        | normalized_df["volume"].lt(0)
    )

    dropped_rows = int(invalid_rows.sum())

    if dropped_rows:
        print(
            f"Warning: dropped {dropped_rows} invalid price rows."
        )

    normalized_df = normalized_df.loc[
        ~invalid_rows,
        ["symbol", "date", "close_price", "volume"],
    ].copy()

    if normalized_df.empty:
        raise ValueError(
            "No valid price rows remain after cleaning."
        )

    before_dedupe = len(normalized_df)

    # Keep the latest observed value if a ticker/date is duplicated.
    normalized_df = normalized_df.drop_duplicates(
        subset=["symbol", "date"],
        keep="last",
    )

    duplicate_rows = before_dedupe - len(normalized_df)

    if duplicate_rows:
        print(
            f"Warning: removed {duplicate_rows} duplicate symbol/date rows."
        )

    normalized_df["volume"] = normalized_df["volume"].astype("int64")

    normalized_df = normalized_df.sort_values(
        ["symbol", "date"],
        kind="mergesort",
    ).reset_index(drop=True)

    return normalized_df


# ----------------------------
# FEATURE ENGINEERING
# ----------------------------

def calculate_return_pct(close_prices, periods):
    """Calculate percentage return over a ticker-local lookback window."""

    prior_close = close_prices.shift(periods)

    return (
        (close_prices / prior_close) - 1
    ) * 100


def add_price_features(price_df):
    """Create return, volume, and volatility features for every ticker."""

    feature_df = price_df.copy()
    grouped = feature_df.groupby("symbol", group_keys=False)

    # Close-to-close daily return.
    feature_df["daily_return_pct"] = grouped["close_price"].transform(
        lambda series: calculate_return_pct(series, periods=1)
    )

    # Medium-horizon returns for price-impact analysis.
    feature_df["return_5d_pct"] = grouped["close_price"].transform(
        lambda series: calculate_return_pct(series, periods=5)
    )

    feature_df["return_10d_pct"] = grouped["close_price"].transform(
        lambda series: calculate_return_pct(series, periods=10)
    )

    # Compare current volume against the prior 5 trading days to avoid lookahead.
    feature_df["rolling_volume_avg"] = grouped["volume"].transform(
        lambda series: (
            series
            .shift(1)
            .rolling(
                window=VOLUME_AVERAGE_WINDOW,
                min_periods=1,
            )
            .mean()
        )
    )

    feature_df["volume_ratio"] = (
        feature_df["volume"] / feature_df["rolling_volume_avg"]
    )

    feature_df.loc[
        feature_df["rolling_volume_avg"].le(0),
        "volume_ratio",
    ] = pd.NA

    # Rolling volatility is the trailing standard deviation of daily returns.
    feature_df["rolling_volatility"] = grouped["daily_return_pct"].transform(
        lambda series: (
            series
            .rolling(
                window=VOLATILITY_WINDOW,
                min_periods=2,
            )
            .std()
        )
    )

    return feature_df


def build_price_features():
    """
    Build a pandas DataFrame with AlphaLens price features.

    Returns:
        pandas.DataFrame with one row per ticker/date and engineered features.
    """

    with connect_to_database() as conn:
        raw_prices = load_prices(conn)

    normalized_prices = normalize_prices(raw_prices)

    return add_price_features(normalized_prices)


# ----------------------------
# SUMMARY REPORTING
# ----------------------------

def print_ticker_summary(feature_df):
    """Print coverage and latest feature values for each ticker."""

    print("\nPrice feature summary")
    print("-" * 118)
    print(
        f"{'symbol':<8}"
        f"{'rows':>8}"
        f"{'first_date':>14}"
        f"{'last_date':>14}"
        f"{'last_close':>14}"
        f"{'daily %':>12}"
        f"{'5d %':>12}"
        f"{'10d %':>12}"
        f"{'vol ratio':>12}"
        f"{'volatility':>12}"
    )
    print("-" * 118)

    for symbol, ticker_df in feature_df.groupby("symbol", sort=True):
        ticker_df = ticker_df.sort_values("date")
        latest_row = ticker_df.iloc[-1]

        print(
            f"{symbol:<8}"
            f"{len(ticker_df):>8}"
            f"{ticker_df['date'].iloc[0].date().isoformat():>14}"
            f"{latest_row['date'].date().isoformat():>14}"
            f"{latest_row['close_price']:>14.2f}"
            f"{latest_row['daily_return_pct']:>12.2f}"
            f"{latest_row['return_5d_pct']:>12.2f}"
            f"{latest_row['return_10d_pct']:>12.2f}"
            f"{latest_row['volume_ratio']:>12.2f}"
            f"{latest_row['rolling_volatility']:>12.2f}"
        )

    print("-" * 118)
    print(
        f"Generated {len(feature_df)} feature rows "
        f"for {feature_df['symbol'].nunique()} tickers."
    )


def main():
    """Build features and print an analyst-friendly summary."""

    feature_df = build_price_features()
    print_ticker_summary(feature_df)

    return feature_df


if __name__ == "__main__":
    main()
