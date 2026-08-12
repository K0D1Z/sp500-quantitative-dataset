"""
This module extracts historical changes from the S&P 500 composition,
analyzes the unstructured text reasons, and categorizes them into
standardized corporate events (M&A, MARKET_CAP, SPIN_OFF, BANKRUPTCY, OTHER).
"""

import os
import pandas as pd
from sp500_quantitative_dataset import config
from sp500_quantitative_dataset.retrieve_companies import (
    retrieve_companies,
)


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

    if historical_changes is None or historical_changes.empty:
        print("Warning: Retrieved historical changes data is empty.")
        return pd.DataFrame(
            columns=[
                "Date",
                "Removed Ticker",
                "Removed Company Name",
                "Added Ticker",
                "Change Reason",
                "Event Type",
            ]
        )

    # Handle MultiIndex columns if returned by pd.read_html from Wikipedia
    if isinstance(historical_changes.columns, pd.MultiIndex):
        historical_changes.columns = [
            "_".join([str(c) for c in col if str(c) != "nan"]).strip()
            for col in historical_changes.columns.values
        ]
    else:
        historical_changes.columns = [
            str(c).strip() for c in historical_changes.columns
        ]

    col_mapping = {}
    for col in historical_changes.columns:
        col_str = str(col).lower()
        if "date" in col_str:
            col_mapping[col] = "Date"
        elif ("add" in col_str) and ("ticker" in col_str or "symbol" in col_str):
            col_mapping[col] = "Added Ticker"
        elif ("rem" in col_str) and ("ticker" in col_str or "symbol" in col_str):
            col_mapping[col] = "Removed Ticker"
        elif ("rem" in col_str) and (
            "company" in col_str or "name" in col_str or "security" in col_str
        ):
            col_mapping[col] = "Removed Company Name"
        elif "reas" in col_str or "change" in col_str or "note" in col_str:
            col_mapping[col] = "Change Reason"

    historical_changes = historical_changes.rename(columns=col_mapping)

    required_cols = [
        "Date",
        "Removed Ticker",
        "Removed Company Name",
        "Added Ticker",
        "Change Reason",
    ]
    for rc in required_cols:
        if rc not in historical_changes.columns:
            historical_changes[rc] = None

    events = historical_changes[required_cols].copy()

    # We focus mainly on removal events because they trigger actions in the portfolio
    events = events.dropna(subset=["Removed Ticker", "Change Reason"])

    # Safe date conversion ignoring invalid strings
    events["Date"] = pd.to_datetime(events["Date"], errors="coerce")
    events = events.dropna(subset=["Date"])

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

    if not events_df.empty:
        print("Categorized events sample: ")
        print(
            events_df[["Date", "Removed Ticker", "Event Type", "Change Reason"]].sample(
                min(10, len(events_df))
            )
        )

        print("\nStatistics in the period under review: ")
        print(events_df["Event Type"].value_counts())
    else:
        print("Events dataframe is empty.")
