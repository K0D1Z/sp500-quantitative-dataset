"""
This module reads the list of missing tickers (delisted or bankrupt companies),
fetches their historical OHLCV data using the Tiingo API, and appends it 
to the existing historical prices dataset.
"""

import os
import json
import pandas as pd
import requests

# Load configuration from config.json
with open("config/config.json", "r") as file:
    config = json.load(file)

def fetch_tiingo_data(ticker: str, start_date: str, end_date: str, api_key: str) -> pd.DataFrame:
    """
    Fetches historical daily prices for a given ticker from the Tiingo API.
    
    Args:
        ticker (str): The stock ticker symbol.
        start_date (str): Start date in YYYY-MM-DD format.
        end_date (str): End date in YYYY-MM-DD format.
        api_key (str): Tiingo API authentication token.
        
    Returns:
        pd.DataFrame: A DataFrame containing the OHLCV data, or an empty DataFrame if the request fails.
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Token {api_key}'
    }
    
    # Tiingo typically uses hyphens instead of dots for multiple share classes
    formatted_ticker = ticker.replace(".", "-")
    
    url = f"https://api.tiingo.com/tiingo/daily/{formatted_ticker}/prices?startDate={start_date}&endDate={end_date}"
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        
        # Map Tiingo response columns to the standard format used in the project
        df = df.rename(columns={
            'date': 'Date',
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'adjClose': 'Adj Close',
            'volume': 'Volume'
        })
        
        # Select and order the required columns
        df = df[['Date', 'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']].copy()
        df['Ticker'] = ticker
        
        # Format Date column to remove timezone information (e.g., '2015-01-02T00:00:00.000Z' -> '2015-01-02')
        df['Date'] = pd.to_datetime(df['Date']).dt.strftime('%Y-%m-%d')
        
        return df
    else:
        print(f"Failed to fetch data for {ticker}. HTTP Status Code: {response.status_code}")
        return pd.DataFrame()

def backfill_missing_prices() -> None:
    """
    Reads missing tickers from the JSON log, fetches missing data from Tiingo, 
    and merges it with the existing historical prices dataset.
    """
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        print("Error: TIINGO_API_KEY environment variable is not set.")
        print("Please set it using: export TIINGO_API_KEY='your_api_key'")
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

    print(f"Attempting to backfill {len(missing_tickers)} tickers from Tiingo...")
    
    backfilled_dataframes = []
    
    # Iterate over missing tickers and fetch data
    for ticker in missing_tickers:
        print(f"Fetching data for {ticker}...")
        df = fetch_tiingo_data(ticker, start_date, end_date, api_key)
        if not df.empty:
            backfilled_dataframes.append(df)

    if not backfilled_dataframes:
        print("No new data was fetched.")
        return

    # Combine all newly fetched data into a single DataFrame
    new_data = pd.concat(backfilled_dataframes, ignore_index=True)
    print(f"Successfully fetched {len(new_data)} rows of data for delisted companies.")

    # Load existing historical prices and merge
    print("Merging with existing historical prices...")
    existing_data = pd.read_csv(prices_output_path)
    
    combined_data = pd.concat([existing_data, new_data], ignore_index=True)
    
    # Sort chronologically and by Ticker to maintain deterministic order
    combined_data = combined_data.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)
    
    # Save the consolidated dataset back to CSV
    combined_data.to_csv(prices_output_path, index=False)
    print(f"Backfill complete. Consolidated data saved to {prices_output_path}")

if __name__ == "__main__":
    backfill_missing_prices()