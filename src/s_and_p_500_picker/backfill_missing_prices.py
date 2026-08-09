"""
This module reads the list of missing tickers, fetches missing data from Tiingo, 
incorporates a Smart Resume feature to skip already downloaded tickers, 
and elegantly halts to save progress if a 429 rate limit is hit.
"""

import os
import json
import time
import pandas as pd
import requests

# Load configuration from config.json
with open("config/config.json", "r") as file:
    config = json.load(file)

def fetch_tiingo_data(ticker: str, start_date: str, end_date: str, api_key: str):
    """
    Fetches historical daily prices for a given ticker from the Tiingo API.
    Returns a DataFrame on success, or the string "RATE_LIMIT" on HTTP 429.
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Token {api_key}'
    }
    
    formatted_ticker = ticker.replace(".", "-")
    url = f"https://api.tiingo.com/tiingo/daily/{formatted_ticker}/prices?startDate={start_date}&endDate={end_date}"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df = df.rename(columns={
            'date': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'adjClose': 'Adj Close',
            'volume': 'Volume'
        })
        
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']].copy()
        df['Ticker'] = ticker
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        return df
        
    elif response.status_code == 429:
        print(f"\n[!] Hourly rate limit hit (429) on {ticker}!")
        return "RATE_LIMIT"
    else:
        print(f"Failed to fetch data for {ticker}. HTTP Status Code: {response.status_code}")
        return pd.DataFrame()

def backfill_missing_prices() -> None:
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        print("Error: TIINGO_API_KEY environment variable is not set.")
        return

    missing_tickers_path = config["paths"].get("missing_tickers", "data/missing_tickers.json")
    prices_output_path = config["paths"].get("historical_prices", "data/s_and_p_500_prices.csv")
    start_date = config["date_range"]["start_date"]
    end_date = config["date_range"]["end_date"]

    # 1. Load missing tickers list
    try:
        with open(missing_tickers_path, "r") as file:
            missing_tickers = json.load(file)
    except FileNotFoundError:
        print(f"Missing tickers file not found at {missing_tickers_path}.")
        return

    if not missing_tickers:
        print("No missing tickers to backfill.")
        return

    # 2. Load existing CSV to see what we ALREADY backfilled
    if os.path.exists(prices_output_path):
        existing_data = pd.read_csv(prices_output_path)
        existing_tickers = set(existing_data["Ticker"].unique())
    else:
        existing_data = pd.DataFrame()
        existing_tickers = set()

    # 3. Filter the list to only fetch what's TRULY missing
    tickers_to_fetch = [t for t in missing_tickers if t not in existing_tickers]

    if not tickers_to_fetch:
        print("All missing tickers have already been successfully backfilled!")
        return

    print(f"Attempting to fetch {len(tickers_to_fetch)} remaining tickers from Tiingo...")
    
    backfilled_dataframes = []
    
    for ticker in tickers_to_fetch:
        print(f"Fetching data for {ticker}...")
        df = fetch_tiingo_data(ticker, start_date, end_date, api_key)
        
        # If we hit the rate limit, halt the loop to save what we have
        if isinstance(df, str) and df == "RATE_LIMIT":
            print("Stopping execution to preserve already fetched data.")
            break
            
        if not df.empty:
            backfilled_dataframes.append(df)
        
        time.sleep(0.3)

    if not backfilled_dataframes:
        print("No new data was fetched in this run.")
        return

    # 4. Save and consolidate
    new_data = pd.concat(backfilled_dataframes, ignore_index=True)
    print(f"Successfully fetched {len(new_data)} rows of data.")

    print("Merging with existing historical prices...")
    combined_data = pd.concat([existing_data, new_data], ignore_index=True)
    combined_data = combined_data.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)
    
    combined_data.to_csv(prices_output_path, index=False)
    print(f"Backfill progress saved to {prices_output_path}")

if __name__ == "__main__":
    backfill_missing_prices()