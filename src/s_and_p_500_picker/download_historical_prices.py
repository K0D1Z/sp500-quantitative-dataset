"""
This module downloads historical OHLCV price data for all unique tickers
identified in the S&P 500 daily composition using Yahoo Finance.
It logs any missing or delisted tickers for future backfilling.
"""

import pandas as pd
import yfinance as yf
import json
import os

# Load configuration
with open("config/config.json", "r") as file:
    config = json.load(file)

def format_ticker_for_yahoo(ticker: str) -> str:
    """
    Converts standard tickers to Yahoo Finance format (e.g., BRK.B to BRK-B).
    """
    if pd.isna(ticker):
        return ""
    return str(ticker).replace(".", "-")

def download_historical_prices() -> None:
    """
    Downloads historical data, flattens the multi-index DataFrame, 
    saves it to CSV, and logs completely missing tickers.
    """
    # 1. Setup paths
    composition_path = config["paths"].get("daily_composition", "data/s_and_p_500_daily_composition.csv")
    prices_output_path = config["paths"].get("historical_prices", "data/s_and_p_500_prices.csv")
    missing_tickers_path = config["paths"].get("missing_tickers", "data/missing_tickers.json")

    # 2. Extract unique universe of tickers
    df_composition = pd.read_csv(composition_path)
    raw_tickers = df_composition["Ticker"].dropna().unique().tolist()
    
    # Map to Yahoo format
    yahoo_tickers = [format_ticker_for_yahoo(t) for t in raw_tickers if t]
    
    start_date = config["date_range"]["start_date"]
    
    # yfinance 'end' date is exclusive, so we add 1 day to capture the final day
    end_date = pd.to_datetime(config["date_range"]["end_date"]) + pd.Timedelta(days=1)
    end_date_str = end_date.strftime("%Y-%m-%d")

    print(f"Downloading data for {len(yahoo_tickers)} tickers from {start_date} to {end_date_str}...")
    
    # 3. Download Data
    # auto_adjust=False keeps standard Close and Adj Close separate.
    data = yf.download(
        yahoo_tickers, 
        start=start_date, 
        end=end_date_str, 
        auto_adjust=False,
        progress=True
    )

    if data.empty:
        print("No data downloaded!")
        return

    # 4. Identify missing tickers (delisted / bankrupt)
    missing_tickers = []
    
    # Check which tickers actually returned columns/data
    if isinstance(data.columns, pd.MultiIndex):
        available_tickers = data.columns.get_level_values('Ticker').unique().tolist()
        
        for ticker in yahoo_tickers:
            if ticker not in available_tickers:
                missing_tickers.append(ticker)
            else:
                # If ticker is in columns but all 'Close' prices are NaN, it's virtually missing
                if data['Close'][ticker].isna().all():
                    missing_tickers.append(ticker)
    
    print(f"\nSuccessfully downloaded data for: {len(yahoo_tickers) - len(missing_tickers)} tickers.")
    print(f"Missing (delisted) tickers to backfill later: {len(missing_tickers)}")

    # 5. Flatten the data for easier use in backtesting
    print("\nFlattening and structuring data...")
    # stack(level=1) moves Tickers from columns to rows, automatically dropping days with NaNs
    # stack(level=1) moves Tickers from columns to rows, automatically dropping days with NaNs
    flat_data = data.stack(level=1).rename_axis(['Date', 'Ticker']).reset_index()

    # Directly remove rows without Close Price (clean dead companies)
    if "Close" in flat_data.columns:
        flat_data = flat_data.dropna(subset=["Close"])  
    
    # Revert Yahoo ticker format back to original (e.g., BRK-B to BRK.B)
    if "Ticker" in flat_data.columns:
        flat_data["Ticker"] = flat_data["Ticker"].str.replace("-", ".")
    
    # Sort chronologically and by Ticker
    flat_data = flat_data.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)

    # 6. Save outputs
    flat_data.to_csv(prices_output_path, index=False)
    print(f"-> Historical prices saved to: {prices_output_path}")

    # Save missing tickers to JSON for our next steps
    original_missing = [t.replace("-", ".") for t in missing_tickers]
    with open(missing_tickers_path, "w") as f:
        json.dump(original_missing, f, indent=4)
    print(f"-> Missing tickers log saved to: {missing_tickers_path}")


if __name__ == "__main__":
    download_historical_prices()