"""
This module merges historical daily prices with SEC fundamental data using a Point-in-Time approach.
It calculates TTM (Trailing Twelve Months) metrics, technical indicators (SMA, RSI, Volatility),
and core financial ratios (Market Cap, P/E, P/B).
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
    calculates TTM (Trailing Twelve Months) for flow metrics, and forward-fills values.
    """
    if not os.path.exists(filepath):
        print(f"Fundamentals file not found at {filepath}")
        return pd.DataFrame()

    df = pd.read_csv(filepath)

    # Ensure datetime formats
    df["Filing Date"] = pd.to_datetime(df["Filing Date"])
    df["Period End"] = pd.to_datetime(df["Period End"])
    df = df.sort_values(by=["Ticker", "Period End"])

    # Compress multiple filings per period/date
    df_clean = df.groupby(["Ticker", "Period End"]).last().reset_index()

    # Define flow metrics that need TTM (sum over last 4 quarters / approx 1 year)
    flow_metrics = [
        "Revenue",
        "Cost of Revenue",
        "Gross Profit",
        "R&D Expenses",
        "SG&A Expenses",
        "Operating Income",
        "Net Income",
        "Operating Cash Flow",
        "CapEx",
        "Dividends Paid",
        "Stock Repurchases",
    ]

    # Calculate TTM for flow metrics using a rolling window of 4 quarters per ticker
    for metric in flow_metrics:
        if metric in df_clean.columns:
            df_clean[metric] = df_clean.groupby("Ticker")[metric].transform(
                lambda x: x.rolling(window=4, min_periods=1).sum()
            )

    # Sort back by filing date for point-in-time merge alignment
    df_clean = df_clean.sort_values(by=["Ticker", "Filing Date", "Period End"])
    df_daily = df_clean.groupby(["Ticker", "Filing Date"]).last().reset_index()

    df_daily = df_daily.sort_values(["Ticker", "Filing Date"])
    cols_to_fill = df_daily.columns.drop(
        ["Ticker", "Filing Date", "Period End", "Form"], errors="ignore"
    )
    df_daily[cols_to_fill] = df_daily.groupby("Ticker")[cols_to_fill].ffill()

    return df_daily


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates technical analysis features (SMA 50, SMA 200, Volatility, RSI).
    """
    print("Calculating technical indicators...")
    df = df.sort_values(by=["Ticker", "Date"])

    # Moving Averages
    df["SMA_50"] = df.groupby("Ticker")["Close"].transform(
        lambda x: x.rolling(window=50, min_periods=10).mean()
    )
    df["SMA_200"] = df.groupby("Ticker")["Close"].transform(
        lambda x: x.rolling(window=200, min_periods=30).mean()
    )

    # 30-Day Rolling Volatility (Standard Deviation of daily returns)
    daily_returns = df.groupby("Ticker")["Close"].pct_change()
    df["Volatility_30D"] = daily_returns.groupby(df["Ticker"]).transform(
        lambda x: x.rolling(window=30, min_periods=10).std()
    )

    # 14-Day RSI (Relative Strength Index)
    def calculate_rsi(series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    df["RSI_14"] = df.groupby("Ticker")["Close"].transform(lambda x: calculate_rsi(x))

    return df


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

    # Add technical indicators
    df = add_technical_indicators(df)

    return df


def calculate_financial_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates key financial multiples based on merged price and fundamental data,
    adjusting historical shares and EPS using the Cumulative Split Factor.
    """
    # Market Capitalization (Price * Shares Outstanding)
    raw_shares = df["Shares Outstanding (Diluted)"].fillna(
        df["Shares Outstanding (Basic)"]
    )
    adjusted_shares = raw_shares * df["Cum Split Factor"]
    df["Market Cap"] = df["Close"] * adjusted_shares

    # TTM EPS Adjusted for Splits
    adjusted_eps = df["EPS (Diluted)"] / df["Cum Split Factor"]
    df["P/E Ratio"] = (
        df["Close"]
        .div(adjusted_eps)
        .where((adjusted_eps.notna()) & (adjusted_eps > 0), np.nan)
    )

    # Price-to-Book (P/B) Ratio
    book_value_per_share = df["Stockholders Equity"] / adjusted_shares
    df["P/B Ratio"] = (
        df["Close"]
        .div(book_value_per_share)
        .where((book_value_per_share.notna()) & (book_value_per_share > 0), np.nan)
    )
    return df


def generate_features() -> None:
    """
    Orchestrates the Point-in-Time merge of prices and fundamentals,
    calculates metrics, and exports the final Kaggle-ready datasets.
    """
    prices_path = config["paths"].get(
        "historical_prices_csv", "data/s_and_p_500_prices.csv"
    )
    fundamentals_path = config["paths"].get(
        "fundamentals_csv", "data/s_and_p_500_fundamentals.csv"
    )
    output_csv = config["paths"].get(
        "daily_features_csv", "data/s_and_p_500_daily_features.csv"
    )
    output_parquet = config["paths"].get(
        "daily_features_parquet", "data/s_and_p_500_daily_features.parquet"
    )

    print("Loading and cleaning fundamentals...")
    fund_df = load_and_clean_fundamentals(fundamentals_path)
    if fund_df.empty:
        return

    print("Loading and cleaning prices...")
    prices_df = load_and_clean_prices(prices_path)
    if prices_df.empty:
        return

    print("Performing Point-in-Time merge (asof)...")
    prices_df = prices_df.sort_values("Date")
    fund_df = fund_df.sort_values("Filing Date")

    merged_df = pd.merge_asof(
        prices_df,
        fund_df,
        left_on="Date",
        right_on="Filing Date",
        by="Ticker",
        direction="backward",
    )

    print("Calculating financial ratios (P/E, P/B, Market Cap)...")
    final_df = calculate_financial_ratios(merged_df)

    final_df = final_df.sort_values(by=["Date", "Ticker"]).reset_index(drop=True)

    print(f"Exporting final dataset ({len(final_df)} rows)...")
    if output_csv and os.path.dirname(output_csv):
        os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    final_df.to_csv(output_csv, index=False)
    print(f"-> Final CSV saved to: {output_csv}")

    if output_parquet and os.path.dirname(output_parquet):
        os.makedirs(os.path.dirname(output_parquet), exist_ok=True)
    final_df.to_parquet(output_parquet, index=False)
    print(f"-> Final Parquet saved to: {output_parquet}")


if __name__ == "__main__":
    generate_features()
