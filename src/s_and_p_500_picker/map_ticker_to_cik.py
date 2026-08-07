"""
This module provides functionality to create a mapping between stock tickers and their corresponding CIK (Central Index Key) numbers. 
It uses the current S&P 500 composition as a base, supplements historical (removed) tickers using the SEC file, and fills any remaining 
dead tickers using a local fallback JSON file. The module also checks for any tickers that are still missing CIKs after the fallback process and prints a warning message with the list of those tickers,
indicating that they need to be added.

- Source for company tickers: https://www.sec.gov/files/company_tickers.json
- Source for artificially created fallback CIKs: https://www.sec.gov

NOTE: CIKs fallback JSON file was written manually and verified using Gemini 3.6 Flash and Claude Sonnet 5 (checked manually as well)
"""

import pandas as pd
import json
from s_and_p_500_picker.retrieve_s_and_p_500_companies import retrieve_s_and_p_500_companies

config = json.load(open("config/config.json", "r"))

def map_ticker_to_cik() -> pd.DataFrame:
    """
    Creates a full Ticker to CIK mapping. Uses the current S&P 500 composition as a base,
    supplements historical (removed) tickers using the SEC file, and fills any remaining 
    dead tickers using a local fallback JSON file. It loads artificially created fallback CIKs for historical 
    tickers that are not present in the SEC file. If any tickers are still missing CIKs after this process, 
    they need to be added to the fallback_ciks.json file manually.

    Returns:
        pd.DataFrame: A DataFrame containing mapped Tickers and their corresponding CIKs.
    """
    sec_path = config["paths"]["company_tickers"]
    fallback_path = config["paths"]["fallback_ciks"]
    
    with open(sec_path, "r") as file:
        sec_json = json.load(file)
        
    with open(fallback_path, "r") as file:
        fallback_ciks_raw = json.load(file)

    fallback_ciks = {ticker: data["CIK"] for ticker, data in fallback_ciks_raw.items()}

    # Create a DataFrame from the SEC JSON data and rename columns for consistency
    sec_tickers = pd.DataFrame(sec_json.values())
    sec_tickers = sec_tickers.rename(columns={
        "cik_str": "CIK", 
        "ticker": "Ticker", 
        "title": "Company Name"
    })
    sec_tickers["CIK"] = sec_tickers["CIK"].astype(str).str.zfill(10)

    # Retrieve current S&P 500 companies and historical changes
    current_companies, historical_changes = retrieve_s_and_p_500_companies()
    current_companies = current_companies.rename(columns={
        "Symbol": "Ticker", 
        "Security": "Company Name"
    })
    current_companies["CIK"] = current_companies["CIK"].astype(str).str.zfill(10)
    current_base = current_companies[["Ticker", "CIK", "Company Name"]].copy()

    # Process historical changes to extract removed tickers and their corresponding CIKs
    removed_df = historical_changes[["Removed Ticker", "Removed Company Name"]].copy()
    removed_df = removed_df.dropna(subset=["Removed Ticker"]).drop_duplicates(subset=["Removed Ticker"])
    removed_df = removed_df.rename(columns={
        "Removed Ticker": "Ticker", 
        "Removed Company Name": "Wiki Company Name"
    })
    
    # Filter out any removed tickers that are still present in the current S&P 500 composition
    removed_df = removed_df[~removed_df["Ticker"].isin(current_base["Ticker"])]
    
    # Merge the removed tickers with the SEC tickers to get their CIKs
    removed_base = pd.merge(removed_df, sec_tickers, on="Ticker", how="left")
    
    # Fill in the Company Name for removed tickers using the Wiki Company Name if it's missing in the SEC data
    removed_base["Company Name"] = removed_base["Company Name"].fillna(removed_base["Wiki Company Name"])
    
    # Drop the Wiki Company Name column as it's no longer needed
    removed_base = removed_base.drop(columns=["Wiki Company Name"])
    
    # Concatenate the current and removed tickers to create the final mapping
    final_mapping = pd.concat([current_base, removed_base], ignore_index=True)

    # Fill in any missing CIKs using the flattened fallback CIKs
    mapped_fallback_ciks = final_mapping["Ticker"].map(fallback_ciks)
    final_mapping["CIK"] = final_mapping["CIK"].fillna(mapped_fallback_ciks)

    # Check for any tickers that are still missing CIKs after the fallback process
    missing_ciks_after_fallback = final_mapping[final_mapping["Ticker"].isna() | final_mapping["CIK"].isna() | final_mapping["Company Name"].isna()]
    if not missing_ciks_after_fallback.empty:
        print("WARNING: The following historical tickers are still missing CIKs and need to be added to fallback_ciks.json:")
        print(missing_ciks_after_fallback["Ticker"].tolist())

    return final_mapping

if __name__ == "__main__":
    mapping_df = map_ticker_to_cik()
    print(mapping_df.sample(10))
    print(f"Total unique tickers mapped: {mapping_df['Ticker'].nunique()}")