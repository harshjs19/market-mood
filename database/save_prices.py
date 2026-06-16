from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3

import pandas as pd


# ----------------------------
# CONFIGURATION
# ----------------------------

DB_PATH = Path("db/market.db")
PRICE_DATA_DIR = Path("news_data")
PRICE_FILE_PATTERN = "*_prices.csv"
PRICE_FILE_SUFFIX = "_prices"

REQUIRED_DB_COLUMNS = {
    "symbol",
    "date",
    "close_price",
    "volume",
}

REQUIRED_SOURCE_COLUMNS = {
    "date": "Date",
    "close": "Close",
    "volume": "Volume",
}


@dataclass
class ImportResult:
    """Stores per-file import metrics for the final summary."""

    file_name: str
    symbol: str
    rows_read: int = 0
    invalid_rows: int = 0
    duplicate_rows_in_file: int = 0
    duplicate_rows_in_db: int = 0
    inserted_rows: int = 0
    error: str = ""


# ----------------------------
# FILE DISCOVERY
# ----------------------------

def discover_price_files():
    """Find every local price CSV that follows the *_prices.csv convention."""

    if not PRICE_DATA_DIR.exists():
        raise FileNotFoundError(
            f"Price data directory not found: {PRICE_DATA_DIR}"
        )

    price_files = sorted(
        PRICE_DATA_DIR.glob(PRICE_FILE_PATTERN)
    )

    if not price_files:
        raise FileNotFoundError(
            f"No price files found for pattern: {PRICE_DATA_DIR / PRICE_FILE_PATTERN}"
        )

    return price_files


def detect_symbol_from_filename(file_path):
    """Infer ticker symbol from filenames like aapl_prices.csv -> AAPL."""

    stem = file_path.stem

    if not stem.lower().endswith(PRICE_FILE_SUFFIX):
        raise ValueError(
            f"Price file does not end with '{PRICE_FILE_SUFFIX}': {file_path.name}"
        )

    symbol = stem[:-len(PRICE_FILE_SUFFIX)].upper()

    if not re.fullmatch(r"[A-Z0-9.\-]+", symbol):
        raise ValueError(
            f"Invalid ticker symbol detected from filename: {file_path.name}"
        )

    return symbol


# ----------------------------
# DATABASE VALIDATION
# ----------------------------

def connect_to_database():
    """Open the existing SQLite database without silently creating a new one."""

    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}. Run database/setup_db.py first."
        )

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


def validate_prices_table(conn):
    """Ensure the current prices table has the columns this importer requires."""

    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'prices'
        """
    ).fetchone()

    if not table_exists:
        raise RuntimeError(
            "Missing table: prices. Run database/setup_db.py first."
        )

    table_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(prices)")
    }

    missing_columns = REQUIRED_DB_COLUMNS - table_columns

    if missing_columns:
        raise RuntimeError(
            "prices table is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )


def load_existing_price_keys(conn):
    """Read existing symbol/date pairs so repeated imports stay idempotent."""

    return {
        (symbol, date)
        for symbol, date in conn.execute(
            "SELECT symbol, date FROM prices"
        )
    }


# ----------------------------
# CSV NORMALIZATION
# ----------------------------

def normalize_price_file(file_path, symbol):
    """
    Convert a yfinance CSV into the current prices schema.

    Current schema target:
        symbol, date, close_price, volume
    """

    raw_df = pd.read_csv(file_path)

    result = ImportResult(
        file_name=file_path.name,
        symbol=symbol,
        rows_read=len(raw_df),
    )

    column_lookup = {
        str(column).strip().lower(): column
        for column in raw_df.columns
    }

    missing_columns = [
        source_column
        for canonical_name, source_column in REQUIRED_SOURCE_COLUMNS.items()
        if canonical_name not in column_lookup
    ]

    if missing_columns:
        result.error = (
            "Missing required CSV columns: "
            + ", ".join(missing_columns)
        )
        return pd.DataFrame(), result

    price_df = pd.DataFrame({
        "symbol": symbol,
        "date": raw_df[column_lookup["date"]].astype(str).str.strip(),
        "close_price": pd.to_numeric(
            raw_df[column_lookup["close"]],
            errors="coerce",
        ),
        "volume": pd.to_numeric(
            raw_df[column_lookup["volume"]],
            errors="coerce",
        ),
    })

    invalid_rows = (
        price_df["date"].eq("")
        | price_df["date"].str.lower().eq("nan")
        | price_df["close_price"].isna()
        | price_df["volume"].isna()
    )

    result.invalid_rows = int(invalid_rows.sum())

    price_df = price_df.loc[
        ~invalid_rows,
        ["symbol", "date", "close_price", "volume"],
    ].copy()

    before_dedupe = len(price_df)

    price_df = price_df.drop_duplicates(
        subset=["symbol", "date"],
        keep="last",
    )

    result.duplicate_rows_in_file = before_dedupe - len(price_df)

    if not price_df.empty:
        price_df["close_price"] = price_df["close_price"].astype(float)
        price_df["volume"] = price_df["volume"].astype("int64")

    return price_df.reset_index(drop=True), result


def filter_new_price_rows(price_df, existing_keys):
    """Remove rows already present in SQLite using the current schema keys."""

    row_keys = list(
        zip(
            price_df["symbol"],
            price_df["date"],
        )
    )

    new_row_mask = [
        row_key not in existing_keys
        for row_key in row_keys
    ]

    duplicate_count = len(price_df) - sum(new_row_mask)

    return price_df.loc[new_row_mask].copy(), duplicate_count


# ----------------------------
# DATABASE INSERT
# ----------------------------

def insert_price_rows(conn, price_df):
    """Insert normalized rows into prices without relying on pandas to_sql."""

    records = [
        (
            str(row.symbol),
            str(row.date),
            float(row.close_price),
            int(row.volume),
        )
        for row in price_df.itertuples(index=False)
    ]

    if not records:
        return 0

    conn.executemany(
        """
        INSERT INTO prices (
            symbol,
            date,
            close_price,
            volume
        )
        VALUES (?, ?, ?, ?)
        """,
        records,
    )

    return len(records)


# ----------------------------
# POST-IMPORT VALIDATION
# ----------------------------

def validate_database_coverage(conn, expected_symbols):
    """Check imported ticker coverage and detect duplicate symbol/date rows."""

    coverage_rows = conn.execute(
        """
        SELECT
            symbol,
            COUNT(*) AS row_count,
            MIN(date) AS first_date,
            MAX(date) AS last_date
        FROM prices
        GROUP BY symbol
        ORDER BY symbol
        """
    ).fetchall()

    duplicate_rows = conn.execute(
        """
        SELECT
            symbol,
            date,
            COUNT(*) AS duplicate_count
        FROM prices
        GROUP BY symbol, date
        HAVING COUNT(*) > 1
        ORDER BY symbol, date
        """
    ).fetchall()

    imported_symbols = {
        symbol
        for symbol, *_ in coverage_rows
    }

    missing_symbols = sorted(
        expected_symbols - imported_symbols
    )

    return coverage_rows, duplicate_rows, missing_symbols


# ----------------------------
# REPORTING
# ----------------------------

def print_import_summary(results, coverage_rows, duplicate_rows, missing_symbols):
    """Print a concise operational summary for the ingestion run."""

    print("\nPrice import summary")
    print("-" * 96)
    print(
        f"{'file':<24}"
        f"{'symbol':<8}"
        f"{'read':>8}"
        f"{'invalid':>10}"
        f"{'file dup':>10}"
        f"{'db dup':>10}"
        f"{'inserted':>12}"
    )
    print("-" * 96)

    for result in results:
        print(
            f"{result.file_name:<24}"
            f"{result.symbol:<8}"
            f"{result.rows_read:>8}"
            f"{result.invalid_rows:>10}"
            f"{result.duplicate_rows_in_file:>10}"
            f"{result.duplicate_rows_in_db:>10}"
            f"{result.inserted_rows:>12}"
        )

        if result.error:
            print(f"  error: {result.error}")

    print("-" * 96)
    print(
        "Total inserted rows: "
        f"{sum(result.inserted_rows for result in results)}"
    )

    print("\nDatabase coverage")
    print("-" * 72)
    print(
        f"{'symbol':<8}"
        f"{'rows':>8}"
        f"{'first_date':>28}"
        f"{'last_date':>28}"
    )
    print("-" * 72)

    for symbol, row_count, first_date, last_date in coverage_rows:
        print(
            f"{symbol:<8}"
            f"{row_count:>8}"
            f"{first_date:>28}"
            f"{last_date:>28}"
        )

    if missing_symbols:
        print(
            "\nWarning: no rows found in prices for expected symbols: "
            + ", ".join(missing_symbols)
        )

    if duplicate_rows:
        print(
            "\nWarning: duplicate symbol/date rows already exist in prices. "
            "Current schema has no UNIQUE constraint."
        )

        for symbol, date, duplicate_count in duplicate_rows[:10]:
            print(
                f"  {symbol} {date}: {duplicate_count} rows"
            )

        if len(duplicate_rows) > 10:
            print(
                f"  ...and {len(duplicate_rows) - 10} more duplicate keys"
            )


# ----------------------------
# MAIN IMPORT FLOW
# ----------------------------

def main():
    """Import every available local price CSV into SQLite."""

    price_files = discover_price_files()
    expected_symbols = set()
    normalized_batches = []
    results = []

    print(
        f"Scanning {PRICE_DATA_DIR} for {PRICE_FILE_PATTERN}"
    )

    # Validate and normalize every file before opening a write transaction.
    for file_path in price_files:
        symbol = detect_symbol_from_filename(file_path)
        expected_symbols.add(symbol)

        price_df, result = normalize_price_file(
            file_path,
            symbol,
        )

        normalized_batches.append(price_df)
        results.append(result)

    file_errors = [
        result.error
        for result in results
        if result.error
    ]

    if file_errors:
        print_import_summary(
            results=results,
            coverage_rows=[],
            duplicate_rows=[],
            missing_symbols=[],
        )
        raise SystemExit(
            "Price import aborted because one or more CSV files are invalid."
        )

    with connect_to_database() as conn:
        validate_prices_table(conn)

        existing_keys = load_existing_price_keys(conn)

        # Insert all new rows in one SQLite transaction.
        with conn:
            for index, price_df in enumerate(normalized_batches):
                new_price_df, duplicate_rows_in_db = filter_new_price_rows(
                    price_df,
                    existing_keys,
                )

                results[index].duplicate_rows_in_db = duplicate_rows_in_db
                results[index].inserted_rows = insert_price_rows(
                    conn,
                    new_price_df,
                )

                existing_keys.update(
                    zip(
                        new_price_df["symbol"],
                        new_price_df["date"],
                    )
                )

        coverage_rows, duplicate_rows, missing_symbols = validate_database_coverage(
            conn,
            expected_symbols,
        )

    print_import_summary(
        results=results,
        coverage_rows=coverage_rows,
        duplicate_rows=duplicate_rows,
        missing_symbols=missing_symbols,
    )


if __name__ == "__main__":
    main()
