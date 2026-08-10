"""
This module retrieves the list of S&P 500 companies from Wikipedia and returns it as a pandas DataFrame.
It also retrieves historical changes to the S&P 500 index. Data is filtered based on the date range specified in the config.json file.
See the config/config.json file for the date range configuration. Source: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
"""

from io import StringIO
import json
import pandas as pd
import requests


def load_config() -> dict:
    """Safely loads runtime configuration from config.json."""
    with open("config/config.json", "r") as file:
        return json.load(file)


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
    config = load_config()

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
    companies["Date added"] = pd.to_datetime(companies["Date added"], errors="coerce")
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

    # 2. Process historical changes table
    historical_changes_columns = [
        "Date",
        "Added Ticker",
        "Added Company Name",
        "Removed Ticker",
        "Removed Company Name",
        "Change Reason",
    ]

    historical_changes = tables[1].iloc[:, :6].copy()
    historical_changes.columns = historical_changes_columns

    historical_changes["Date"] = pd.to_datetime(
        historical_changes["Date"], errors="coerce"
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
    config = load_config()
    companies, changes = retrieve_companies()

    print(
        f"S&P 500 Companies from {config['date_range']['start_date']} to {config['date_range']['end_date']}:"
    )
    print(companies.head())

    print(
        f"\nHistorical Changes from {config['date_range']['start_date']} to {config['date_range']['end_date']}:"
    )
    print(changes.head())
