"""
This module reads the list of missing tickers (delisted or bankrupt companies),
fetches their historical OHLCV data using the Tiingo API with rate-limiting, 
and appends it to the existing historical prices dataset.
"""

import os
import json
import time
import pandas as pd
import requests

# Load configuration from config.json
with open("config/config.json", "r") as file:
    config = json.load(file)

def fetch_tiingo_data(ticker: str, start_date: str, end_date: str, api_key: str) -> pd.DataFrame:
    """
    Fetches historical daily prices for a given ticker from the Tiingo API.
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
        print(f"Rate limit hit (429) for {ticker}. Sleeping for 5 seconds...")
        time.sleep(5) # Give the API a moment to breathe
        return pd.DataFrame()
    else:
        print(f"Failed to fetch data for {ticker}. HTTP Status Code: {response.status_code}")
        return pd.DataFrame()

def backfill_missing_prices() -> None:
    """
    Reads missing tickers from the JSON log, fetches missing data from Tiingo 
    with a small delay to respect rate limits, and merges it with existing prices.
    """
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        print("Error: TIINGO_API_KEY environment variable is not set.")
        return

    missing_tickers_path = config["paths"].get("missing_tickers", "data/missing_tickers.json")
    prices_output_path = config["paths"].get("historical_prices", "data/s_and_p_500_prices.csv")
    start_date = config["date_range"]["start_date"]
    end_date = config["date_range"]["end_date"]

    try:
        with open(missing_tickers_path, "r") as file:
            missing_tickers = json.load(file)
    except FileNotFoundError:
        print(f"Missing tickers file not found at {missing_tickers_path}.")
        return

    if not missing_tickers:
        print("No missing tickers to backfill.")
        return

    print(f"Attempting to backfill {len(missing_tickers)} tickers from Tiingo safely...")
    
    backfilled_dataframes = []
    
    for ticker in missing_tickers:
        print(f"Fetching data for {ticker}...")
        df = fetch_tiingo_data(ticker, start_date, end_date, api_key)
        if not df.empty:
            backfilled_dataframes.append(df)
        
        # Polite delay to prevent HTTP 429 Rate Limit
        time.sleep(0.3)

    if not backfilled_dataframes:
        print("No new data was fetched.")
        return

    new_data = pd.concat(backfilled_dataframes, ignore_index=True)
    print(f"Successfully fetched {len(new_data)} rows of data for delisted companies.")

    print("Merging with existing historical prices...")
    existing_data = pd.read_csv(prices_output_path)
    
    combined_data = pd.concat([existing_data, new_data], ignore_index=True)
    combined_data = combined_data.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)
    
    combined_data.to_csv(prices_output_path, index=False)
    print(f"Backfill complete. Consolidated data saved to {prices_output_path}")

if __name__ == "__main__":
    backfill_missing_prices()