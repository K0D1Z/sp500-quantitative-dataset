"""
This module extracts historical changes from the S&P 500 composition,
analyzes the unstructured text reasons, and categorizes them into 
standardized corporate events (M&A, MARKET_CAP, SPIN_OFF, BANKRUPTCY, OTHER).
"""

import pandas as pd
import json
from s_and_p_500_picker.retrieve_s_and_p_500_companies import retrieve_s_and_p_500_companies

with open("config/config.json", "r") as file:
    config = json.load(file)

def categorize_reason(reason_text: str) -> str:
    """
    Maps an unstructured reason string to a standardized event tag.
    """
    if not isinstance(reason_text, str):
        return "OTHER"
    
    reason_lower = reason_text.lower()
    
    # Mergers and Acquisitions (M&A): catch "acquire", "acquired", "merger", "merging", "merged", "bought", "takeover", "purchased"
    if any(word in reason_lower for word in ["acquir", "merg", "bought", "takeover", "taken over", "purchased"]):
        return "ACQUISITION"
    
    # Changes in capitalization and rotation (the most common reason): catch "market cap", "capitalization", "size", "valuation" etc.
    if any(word in reason_lower for word in ["market cap", "capitalization", "size", "valuation"]):
        return "MARKET_CAP"
    
    # Spin-offs: catch "spin-off", "spinoff", "spins off", "spinning off", "split", "separated" etc.
    if any(word in reason_lower for word in ["spin", "split", "separat", "spun"]):
        return "SPIN_OFF"
    
    # Bankruptcy / Insolvency: catch "bankruptcy", "chapter 11", "liquidated", "insolvency", "receivership" etc.
    if any(word in reason_lower for word in ["bankruptcy", "chapter 11", "liquidat", "insolven", "receivership"]):
        return "BANKRUPTCY"
    
    return "OTHER"

def generate_corporate_events() -> pd.DataFrame:
    """
    Generates a structured ledger of corporate events affecting S&P 500 constituents.
    """
    _, historical_changes = retrieve_s_and_p_500_companies()
    

    events = historical_changes[["Date", "Removed Ticker", "Removed Company Name", "Added Ticker", "Change Reason"]].copy()
    
    # We focus mainly on removal events because they trigger actions in the portfolio
    events = events.dropna(subset=["Removed Ticker", "Change Reason"])
    
    events["Date"] = pd.to_datetime(events["Date"])
    
    # Categorize
    events["Event Type"] = events["Change Reason"].apply(categorize_reason)
    
    # Cleaning and sorting chronologically from oldest to newest
    events = events.sort_values(by="Date", ascending=True).reset_index(drop=True)
    
    return events

if __name__ == "__main__":
    events_df = generate_corporate_events()
    
    output_path = config["paths"].get("events_ledger", "data/s_and_p_500_events.csv")
    events_df.to_csv(output_path, index=False)
    
    print("Categorized events sample: ")
    print(events_df[["Date", "Removed Ticker", "Event Type", "Change Reason"]].sample(10))
    
    print("\nStatistics in the period under review: ")
    print(events_df["Event Type"].value_counts())