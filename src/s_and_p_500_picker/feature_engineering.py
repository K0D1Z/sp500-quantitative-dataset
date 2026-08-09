"""
This module merges historical daily prices with SEC fundamental data
using a Point-in-Time approach (merge_asof based on Filing Date).
It calculates key financial ratios such as Market Cap, P/E, and P/B.
"""

import os
import json
import pandas as pd
import numpy as np

# Load configuration
with open("config/config.json", "r") as file:
    config = json.load(file)

def load_and_clean_fundamentals(filepath: str) -> pd.DataFrame:
    """
    Loads fundamental data, compresses multiple rows per filing date,
    and forward-fills missing metrics per ticker.
    """
    if not os.path.exists(filepath):
        print(f"Fundamentals file not found at {filepath}")
        return pd.DataFrame()

    df = pd.read_csv(filepath)
    
    # Ensure datetime formats
    df["Filing Date"] = pd.to_datetime(df["Filing Date"])
    df = df.sort_values(by=["Ticker", "Filing Date", "Period End"])
    
    # Group by Ticker and Filing Date, taking the last non-null value for each column
    df_daily = df.groupby(["Ticker", "Filing Date"]).last().reset_index()
    
    # Forward fill remaining missing values per ticker (carry forward from previous quarters)
    df_daily = df_daily.sort_values(["Ticker", "Filing Date"])
    
    cols_to_fill = df_daily.columns.drop(["Ticker", "Filing Date"])
    df_daily[cols_to_fill] = df_daily.groupby("Ticker")[cols_to_fill].ffill()
    
    return df_daily

def load_and_clean_prices(filepath: str) -> pd.DataFrame:
    """
    Loads the historical price data and calculates the Cumulative Split Factor
    to adjust historical point-in-time fundamentals.
    """
    if not os.path.exists(filepath):
        print(f"Prices file not found at {filepath}")
        return pd.DataFrame()

    df = pd.read_csv(filepath)
    df["Date"] = pd.to_datetime(df["Date"])
    
    # Manage splits(Cumulative Split Factor)
    if "Stock Splits" not in df.columns:
        df["Stock Splits"] = 0.0
        
    df["Stock Splits"] = df["Stock Splits"].fillna(0.0)
    df["Split Multiplier"] = df["Stock Splits"].replace(0.0, 1.0)
    
    # Sort from newest to oldest date to calculate the split backwards
    df = df.sort_values(by=["Ticker", "Date"], ascending=[True, False])
    
    # Move the multiplier back 1 day (on the split day the price is already adjusted)
    df["Split Shifted"] = df.groupby("Ticker")["Split Multiplier"].shift(1).fillna(1.0)
    
    # Cumulative product for all previous days
    df["Cum Split Factor"] = df.groupby("Ticker")["Split Shifted"].cumprod()
    
    # Go back to normal chronological sorting
    df = df.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)
    
    return df

def calculate_financial_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates key financial multiples based on merged price and fundamental data,
    adjusting historical shares and EPS using the Cumulative Split Factor.
    """
    # Market Capitalization (Price * Shares Outstanding)
    # Prefer Diluted shares, fallback to Basic
    raw_shares = df["Shares Outstanding (Diluted)"].fillna(df["Shares Outstanding (Basic)"])
    adjusted_shares = raw_shares * df["Cum Split Factor"]
    df["Market Cap"] = df["Close"] * adjusted_shares

    # Price-to-Earnings (P/E) Ratio
    # Using EPS Diluted directly if available
    adjusted_eps = df["EPS (Diluted)"] / df["Cum Split Factor"]
    df["P/E Ratio"] = np.where(
        (adjusted_eps.notna()) & (adjusted_eps > 0),
        df["Close"] / adjusted_eps,
        np.nan
    )

    # Price-to-Book (P/B) Ratio
    # Book Value Per Share = Stockholders Equity / Shares Outstanding
    book_value_per_share = df["Stockholders Equity"] / adjusted_shares
    df["P/B Ratio"] = np.where(
        (book_value_per_share.notna()) & (book_value_per_share > 0),
        df["Close"] / book_value_per_share,
        np.nan
    )
    return df

def generate_features() -> None:
    """
    Orchestrates the Point-in-Time merge of prices and fundamentals,
    calculates metrics, and exports the final Kaggle-ready datasets.
    """
    prices_path = config["paths"].get("historical_prices", "data/s_and_p_500_prices.csv")
    fundamentals_path = config["paths"].get("fundamentals_csv", "data/s_and_p_500_fundamentals.csv")
    output_csv = config["paths"].get("daily_features_csv", "data/s_and_p_500_daily_features.csv")
    output_parquet = config["paths"].get("daily_features_parquet", "data/s_and_p_500_daily_features.parquet")

    print("Loading and cleaning fundamentals...")
    fund_df = load_and_clean_fundamentals(fundamentals_path)
    if fund_df.empty:
        return

    print("Loading and cleaning prices...")
    prices_df = load_and_clean_prices(prices_path)
    if prices_df.empty:
        return

    print("Performing Point-in-Time merge (asof)...")
    # merge_asof requires both dataframes to be sorted by the merge key
    prices_df = prices_df.sort_values("Date")
    fund_df = fund_df.sort_values("Filing Date")

    # Match each daily price with the most recent fundamental filing up to that date
    merged_df = pd.merge_asof(
        prices_df,
        fund_df,
        left_on="Date",
        right_on="Filing Date",
        by="Ticker",
        direction="backward"
    )

    print("Calculating financial ratios (P/E, P/B, Market Cap)...")
    final_df = calculate_financial_ratios(merged_df)

    # Sort and clean up columns
    final_df = final_df.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)
    
    print(f"Exporting final dataset ({len(final_df)} rows)...")
    final_df.to_csv(output_csv, index=False)
    final_df.to_parquet(output_parquet, index=False)
    
    print(f"-> Final CSV saved to: {output_csv}")
    print(f"-> Final Parquet saved to: {output_parquet}")

if __name__ == "__main__":
    generate_features()