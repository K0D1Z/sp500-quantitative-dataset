"""
This module generates a daily composition of the S&P 500 index over a specified date range.
It uses the current composition and historically logged changes to reverse-engineer the
index constituents day by day, mapping each ticker to its exact CIK.
"""

import os
import pandas as pd
from sp500_quantitative_dataset import config
from sp500_quantitative_dataset.retrieve_companies import (
    retrieve_companies,
)
from sp500_quantitative_dataset.map_ticker_to_cik import map_ticker_to_cik


def generate_daily_composition() -> pd.DataFrame:
    """
    Generates a DataFrame containing the daily composition of the S&P 500 index.
    The algorithm iterates backwards from the end date to the start date, reverting
    historical changes to reconstruct the index for each day.

    Returns:
        pd.DataFrame: A DataFrame with columns ['Date', 'Ticker', 'CIK'].
    """
    current_companies, historical_changes = retrieve_companies()
    historical_changes["Date"] = pd.to_datetime(historical_changes["Date"])

    cik_mapping_df = map_ticker_to_cik()

    # Create a fast lookup dictionary for O(1) CIK retrieval
    ticker_to_cik = dict(zip(cik_mapping_df["Ticker"], cik_mapping_df["CIK"]))

    start_date = pd.to_datetime(config["date_range"]["start_date"])
    end_date = pd.to_datetime(config["date_range"]["end_date"])

    # Create a descending date range for the backward iteration
    date_range = pd.date_range(start=start_date, end=end_date, freq="D")[::-1]

    # Initialize the active set of tickers with the current S&P 500 composition
    active_tickers = set(current_companies["Ticker"].tolist())

    # Group historical changes by date to optimize lookup speed
    changes_by_date = historical_changes.groupby("Date")

    daily_records = []

    # Iterate backwards day by day
    for current_date in date_range:
        # 1. Snapshot the current state for this specific date
        for ticker in active_tickers:
            daily_records.append(
                {
                    "Date": current_date,
                    "Ticker": ticker,
                    "CIK": ticker_to_cik.get(ticker, None),
                }
            )

        # 2. Revert the changes that took effect on this date to prepare the set for the day BEFORE
        if current_date in changes_by_date.groups:
            day_changes = changes_by_date.get_group(current_date)

            for _, row in day_changes.iterrows():
                added = row.get("Added Ticker")
                removed = row.get("Removed Ticker")

                # If a company was added on this day, it was NOT in the index the day before
                if pd.notna(added) and added in active_tickers:
                    active_tickers.remove(added)

                # If a company was removed on this day, it WAS in the index the day before
                if pd.notna(removed):
                    active_tickers.add(removed)

    # Convert the records list into a DataFrame and sort chronologically
    daily_composition_df = pd.DataFrame(daily_records)
    daily_composition_df = daily_composition_df.sort_values(
        by=["Date", "Ticker"]
    ).reset_index(drop=True)

    # Save output to CSV
    output_path_csv = config["paths"].get(
        "daily_composition_csv", "data/s_and_p_500_daily_composition.csv"
    )
    if output_path_csv and os.path.dirname(output_path_csv):
        os.makedirs(os.path.dirname(output_path_csv), exist_ok=True)
    daily_composition_df.to_csv(output_path_csv, index=False)

    # Save output to Parquet
    output_path_parquet = config["paths"].get(
        "daily_composition_parquet", "data/s_and_p_500_daily_composition.parquet"
    )
    if output_path_parquet and os.path.dirname(output_path_parquet):
        os.makedirs(os.path.dirname(output_path_parquet), exist_ok=True)
    daily_composition_df.to_parquet(output_path_parquet, index=False)

    return daily_composition_df


if __name__ == "__main__":
    daily_composition = generate_daily_composition()

    print(daily_composition.head())
    print(f"Total rows generated: {len(daily_composition)}")
