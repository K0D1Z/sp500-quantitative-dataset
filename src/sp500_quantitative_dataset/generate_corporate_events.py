"""
This module extracts historical changes from the S&P 500 composition,
analyzes the unstructured text reasons, and categorizes them into
standardized corporate events (M&A, MARKET_CAP, SPIN_OFF, BANKRUPTCY, OTHER).
"""

import os
import pandas as pd
import json
from sp500_quantitative_dataset.retrieve_companies import (
    retrieve_companies,
)

with open("config/config.json", "r") as file:
    config = json.load(file)


def categorize_reason(reason_text: str) -> str:
    """
    Maps an unstructured reason string to a standardized event tag.
    """
    if not isinstance(reason_text, str):
        return "OTHER"

    reason_lower = reason_text.lower()

    # Mergers and Acquisitions (M&A)
    if any(
        word in reason_lower
        for word in ["acquir", "merg", "bought", "takeover", "taken over", "purchased"]
    ):
        return "ACQUISITION"

    # Changes in capitalization and rotation
    if any(
        word in reason_lower
        for word in ["market cap", "capitalization", "size", "valuation"]
    ):
        return "MARKET_CAP"

    # Spin-offs
    if any(word in reason_lower for word in ["spin", "split", "separat", "spun"]):
        return "SPIN_OFF"

    # Bankruptcy / Insolvency
    if any(
        word in reason_lower
        for word in ["bankruptcy", "chapter 11", "liquidat", "insolven", "receivership"]
    ):
        return "BANKRUPTCY"

    return "OTHER"


def generate_corporate_events() -> pd.DataFrame:
    """
    Generates a structured ledger of corporate events affecting S&P 500 constituents.
    """
    print("Generating corporate events...")
    _, historical_changes = retrieve_companies()

    events = historical_changes[
        [
            "Date",
            "Removed Ticker",
            "Removed Company Name",
            "Added Ticker",
            "Change Reason",
        ]
    ].copy()

    # We focus mainly on removal events because they trigger actions in the portfolio
    events = events.dropna(subset=["Removed Ticker", "Change Reason"])

    events["Date"] = pd.to_datetime(events["Date"])

    # Categorize
    print("Categorizing corporate events...")
    events["Event Type"] = events["Change Reason"].apply(categorize_reason)

    # Cleaning and sorting chronologically from oldest to newest
    print("Cleaning corporate events...")
    events = events.sort_values(by="Date", ascending=True).reset_index(drop=True)

    print("Saving corporate events...")

    # Save to CSV
    output_path_csv = config["paths"].get(
        "events_ledger_csv", "data/s_and_p_500_events.csv"
    )
    if output_path_csv and os.path.dirname(output_path_csv):
        os.makedirs(os.path.dirname(output_path_csv), exist_ok=True)
    events.to_csv(output_path_csv, index=False)

    # Save to Parquet
    output_path_parquet = config["paths"].get(
        "events_ledger_parquet", "data/s_and_p_500_events.parquet"
    )
    if output_path_parquet and os.path.dirname(output_path_parquet):
        os.makedirs(os.path.dirname(output_path_parquet), exist_ok=True)
    events.to_parquet(output_path_parquet, index=False)

    print("Success!")

    return events


if __name__ == "__main__":
    events_df = generate_corporate_events()

    print("Categorized events sample: ")
    print(
        events_df[["Date", "Removed Ticker", "Event Type", "Change Reason"]].sample(10)
    )

    print("\nStatistics in the period under review: ")
    print(events_df["Event Type"].value_counts())
