"""
This module reads the list of missing tickers, fetches missing data from Tiingo,
incorporates a Smart Resume feature to skip already downloaded tickers,
and handles rate limits seamlessly by batching requests with pauses.
"""

import os
import json
import time
import pandas as pd
import requests
from sp500_quantitative_dataset import config


def fetch_tiingo_data(ticker: str, start_date: str, end_date: str, api_key: str):
    """
    Fetches historical daily prices for a given ticker from the Tiingo API.
    Returns a DataFrame on success, or the string "RATE_LIMIT" on HTTP 429.
    """
    headers = {"Content-Type": "application/json", "Authorization": f"Token {api_key}"}

    formatted_ticker = ticker.replace(".", "-")
    url = f"https://api.tiingo.com/tiingo/daily/{formatted_ticker}/prices?startDate={start_date}&endDate={end_date}"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "adjClose": "Adj Close",
                "volume": "Volume",
            }
        )

        df = df[["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]].copy()
        df["Ticker"] = ticker
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
        return df

    elif response.status_code == 429:
        print(f"\n[!] Hourly rate limit hit (429) on {ticker}!")
        return "RATE_LIMIT"
    else:
        print(
            f"Failed to fetch data for {ticker}. HTTP Status Code: {response.status_code}"
        )
        return pd.DataFrame()


def backfill_missing_prices() -> None:
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        print(
            "Error: TIINGO_API_KEY environment variable is not set. Use `export TIINGO_API_KEY='api_key'` command"
        )
        return

    missing_tickers_path = config["paths"].get(
        "missing_tickers", "data/missing_tickers.json"
    )
    prices_output_path = config["paths"].get(
        "historical_prices_csv", "data/s_and_p_500_prices.csv"
    )
    failed_tiingo_path = config["paths"].get(
        "failed_tiingo_log", "data/failed_tiingo.json"
    )
    start_date = config["date_range"]["start_date"]
    end_date = config["date_range"]["end_date"]

    try:
        with open(missing_tickers_path, "r") as file:
            missing_tickers_list = json.load(file)
    except FileNotFoundError:
        print(f"Missing tickers file not found at {missing_tickers_path}.")
        return

    if os.path.exists(prices_output_path):
        existing_data = pd.read_csv(prices_output_path)
        existing_tickers = (
            set(existing_data["Ticker"].unique())
            if "Ticker" in existing_data.columns
            else set()
        )
    else:
        existing_data = pd.DataFrame()
        existing_tickers = set()

    items_to_fetch = [
        item for item in missing_tickers_list if item["Ticker"] not in existing_tickers
    ]

    if not items_to_fetch:
        print("All missing tickers have already been successfully backfilled!")
        return

    print(f"Attempting to fetch {len(items_to_fetch)} remaining tickers from Tiingo...")

    backfilled_dataframes = []
    failed_logs = []

    if os.path.exists(failed_tiingo_path):
        try:
            with open(failed_tiingo_path, "r") as f:
                failed_logs = json.load(f)
        except Exception:
            failed_logs = []

    # === BYPASS 50 API REQUESTS PER HOUR LOGIC ===
    BATCH_SIZE = 45
    SLEEP_DURATION = 3660
    total_items = len(items_to_fetch)

    for i, item in enumerate(items_to_fetch):
        ticker = item["Ticker"]
        cik = item["CIK"]
        print(f"[{i + 1}/{total_items}] Fetching data for {ticker} (CIK: {cik})...")

        df = fetch_tiingo_data(ticker, start_date, end_date, api_key)

        if isinstance(df, str) and df == "RATE_LIMIT":
            print(
                "Rate limit hit unexpectedly. Sleeping for 61 minutes to reset quota..."
            )
            time.sleep(SLEEP_DURATION)
            df = fetch_tiingo_data(ticker, start_date, end_date, api_key)

        if isinstance(df, str) or df.empty:
            failed_logs.append(
                {
                    "Ticker": ticker,
                    "CIK": cik,
                    "Reason": "Tiingo returned 404 or empty data",
                }
            )
        else:
            backfilled_dataframes.append(df)

        if (i + 1) % BATCH_SIZE == 0 and (i + 1) < total_items:
            print(
                f"Reached batch limit ({BATCH_SIZE} requests). Sleeping for 61 minutes..."
            )
            if backfilled_dataframes:
                temp_new_data = pd.concat(backfilled_dataframes, ignore_index=True)
                if os.path.exists(prices_output_path):
                    curr_data = pd.read_csv(prices_output_path)
                    combined = pd.concat(
                        [curr_data, temp_new_data], ignore_index=True
                    ).drop_duplicates(subset=["Date", "Ticker"])
                else:
                    combined = temp_new_data

                # Zabezpieczenie katalogu przed zapisem tymczasowym
                if os.path.dirname(prices_output_path):
                    os.makedirs(os.path.dirname(prices_output_path), exist_ok=True)

                combined.to_csv(prices_output_path, index=False)
                print("Progress saved to disk during sleep.")
                backfilled_dataframes = []
            time.sleep(SLEEP_DURATION)
        else:
            time.sleep(0.1)

    # Zapis logów nieudanych próśb z tworzeniem katalogu
    if failed_logs:
        if os.path.dirname(failed_tiingo_path):
            os.makedirs(os.path.dirname(failed_tiingo_path), exist_ok=True)

        with open(failed_tiingo_path, "w") as f:
            json.dump(failed_logs, f, indent=4)
        print(f"-> Unresolvable tickers logged to {failed_tiingo_path}")

    if not backfilled_dataframes:
        print("No new data was fetched in this run.")
        return

    new_data = pd.concat(backfilled_dataframes, ignore_index=True)
    if not existing_data.empty:
        combined_data = pd.concat(
            [existing_data, new_data], ignore_index=True
        ).drop_duplicates(subset=["Date", "Ticker"])
    else:
        combined_data = new_data

    combined_data = combined_data.sort_values(by=["Date", "Ticker"]).reset_index(
        drop=True
    )

    # Zabezpieczenie katalogu przed końcowym zapisem CSV
    if os.path.dirname(prices_output_path):
        os.makedirs(os.path.dirname(prices_output_path), exist_ok=True)

    combined_data.to_csv(prices_output_path, index=False)
    print(f"Backfill progress saved to {prices_output_path}")


if __name__ == "__main__":
    backfill_missing_prices()
