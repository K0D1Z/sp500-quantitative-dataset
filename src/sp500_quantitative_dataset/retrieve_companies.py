"""
This module retrieves the list of S&P 500 companies from Wikipedia and returns it as a pandas DataFrame.
It also retrieves historical changes to the S&P 500 index. Data is filtered based on the date range specified in the config.json file.
See the config/config.json file for the date range configuration. Source: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
"""

from io import StringIO
import pandas as pd
import requests
from sp500_quantitative_dataset import config


def retrieve_companies() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retrieves the list of S&P 500 companies from Wikipedia.

    Returns:
        tuple: A tuple containing two pandas DataFrames:
            - companies: DataFrame containing current S&P 500 companies.
            - historical_changes: DataFrame containing historical index changes.
    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
    """
    # URL of the Wikipedia page containing the list of S&P 500 companies
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    # Custom User-Agent header required by Wikimedia policy
    headers = {"User-Agent": "S&P 500 Quant/1.0 (student@gmail.com)"}

    # HTTP GET request
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    # Parse HTML tables
    html_data = StringIO(response.text)
    tables = pd.read_html(html_data)

    # 1. Process current companies table
    companies_columns = [
        "CIK",
        "Symbol",
        "GICS Sector",
        "GICS Sub-Industry",
        "Security",
        "Date added",
    ]
    companies = tables[0][companies_columns].copy()
    companies["Date added"] = pd.to_datetime(companies["Date added"], errors="coerce", )
    companies = companies.sort_values(by="Date added", ascending=True).reset_index(
        drop=True
    )

    companies = companies.rename(
        columns={
            "CIK": "CIK",
            "Symbol": "Ticker",
            "Security": "Company Name",
            "GICS Sector": "GICS Sector",
            "GICS Sub-Industry": "GICS Sub-Industry",
            "Date added": "Date Added",
        }
    )

    # 2. Process historical changes table (with safety check for column count & multi-index)
    historical_changes = tables[1].copy()
    
    if isinstance(historical_changes.columns, pd.MultiIndex):
        historical_changes.columns = ['_'.join(str(c) for c in col).strip() for col in historical_changes.columns.values]

    historical_changes_columns = [
        "Date",
        "Added Ticker",
        "Added Company Name",
        "Removed Ticker",
        "Removed Company Name",
        "Change Reason",
    ]

    # Dynamically match available columns to avoid length mismatch
    n_cols = min(len(historical_changes.columns), len(historical_changes_columns))
    historical_changes = historical_changes.iloc[:, :n_cols].copy()
    historical_changes.columns = historical_changes_columns[:n_cols]

    historical_changes["Date"] = pd.to_datetime(
        historical_changes["Date"], errors="coerce", format="mixed"
    )

    # Drop any parsing artifacts/unparsed header rows
    historical_changes = historical_changes.dropna(subset=["Date"])

    # Filter based on configured date range
    start_date = pd.to_datetime(config["date_range"]["start_date"])
    end_date = pd.to_datetime(config["date_range"]["end_date"])

    mask_historical_changes = (historical_changes["Date"] >= start_date) & (
        historical_changes["Date"] <= end_date
    )
    historical_changes = historical_changes[mask_historical_changes]

    # Sort chronologically from oldest to newest
    historical_changes = historical_changes.sort_values(
        by="Date", ascending=True
    ).reset_index(drop=True)

    return companies, historical_changes


if __name__ == "__main__":
    companies, changes = retrieve_companies()

    print(
        f"S&P 500 Companies from {config['date_range']['start_date']} to {config['date_range']['end_date']}:"
    )
    print(companies.head())

    print(
        f"\nHistorical Changes from {config['date_range']['start_date']} to {config['date_range']['end_date']}:"
    )
    print(changes.head())