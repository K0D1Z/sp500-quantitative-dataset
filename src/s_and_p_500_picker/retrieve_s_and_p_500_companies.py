"""
This module retrieves the list of S&P 500 companies from Wikipedia and returns it as a pandas DataFrame.
It also retrieves historical changes to the S&P 500 index. Data is filtered based on the date range specified in the config.json file.
See the config/config.json file for the date range configuration. Source: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
"""

from io import StringIO
import pandas as pd
import requests
import json

# Load configuration from config.json
config = json.load(open("config/config.json", "r"))


def retrieve_s_and_p_500_companies() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retrieves the list of S&P 500 companies from Wikipedia.

    Returns:
        tuple: A tuple containing two pandas DataFrames:
            - companies: DataFrame containing S&P 500 companies.
            - historical_changes: DataFrame containing the historical changes to the S&P 500 index.

            companies DataFrame columns:
                - CIK: The Central Index Key (CIK) of the company.
                - Ticker: The stock ticker symbol of the company.
                - Company Name: The name of the company.
                - Date Added: The date the company was added to the S&P 500 index.

            historical_changes DataFrame columns:
                - Date: The date of the change in the S&P 500 index.
                - Added Ticker: The stock ticker symbol of the company added to the index.
                - Added Company Name: The name of the company added to the index.
                - Removed Ticker: The stock ticker symbol of the company removed from the index.
                - Removed Company Name: The name of the company removed from the index.
                - Change Reason: The reason for the change in the index (e.g., merger, acquisition, etc.).
    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request to Wikipedia.
    """

    # URL of the Wikipedia page containing the list of S&P 500 companies
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    # Set a custom User-Agent header to avoid potential blocking by Wikipedia
    headers = {"User-Agent": "S&P 500 Picker/1.0 (kodiz2005@gmail.com)"}

    # Make an HTTP GET request to the Wikipedia page
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    # Use StringIO to read the HTML content into pandas
    html_data = StringIO(response.text)
    tables = pd.read_html(html_data)

    # Extract the companies and historical changes tables from the list of tables
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
    # Sort the companies by the "Date added" column in ascending order and reset the index
    companies = companies.sort_values(by="Date added", ascending=True).reset_index(
        drop=True
    )
    companies.rename(
        columns={
            "CIK": "CIK",
            "Symbol": "Ticker",
            "Security": "Company Name",
            "GICS Sector": "GICS Sector",
            "GICS Sub-Industry": "GICS Sub-Industry",
            "Date added": "Date Added",
        },
        inplace=True,
    )

    historical_changes_columns = [
        "Date",
        "Added_Ticker",
        "Added_Security",
        "Removed_Ticker",
        "Removed_Security",
        "Reason",
    ]
    historical_changes = tables[1]
    historical_changes = historical_changes.iloc[:, :6]
    historical_changes.columns = historical_changes_columns
    historical_changes["Date"] = pd.to_datetime(
        historical_changes["Date"], errors="coerce"
    )

    # Filter the historical changes based on the date range specified in the config.json file
    mask_historical_changes = (
        historical_changes["Date"] >= pd.to_datetime(config["date_range"]["start_date"])
    ) & (historical_changes["Date"] <= pd.to_datetime(config["date_range"]["end_date"]))
    historical_changes = historical_changes[mask_historical_changes]

    # Sort the historical changes by the "Date" column in ascending order and reset the index
    historical_changes = historical_changes.sort_values(
        by="Date", ascending=True
    ).reset_index(drop=True)
    historical_changes.rename(
        columns={
            "Date": "Date",
            "Added_Ticker": "Added Ticker",
            "Added_Security": "Added Company Name",
            "Removed_Ticker": "Removed Ticker",
            "Removed_Security": "Removed Company Name",
            "Reason": "Change Reason",
        },
        inplace=True,
    )

    return companies, historical_changes


if __name__ == "__main__":
    companies, changes = retrieve_s_and_p_500_companies()
    print(
        f"S&P 500 Companies from {config['date_range']['start_date']} to {config['date_range']['end_date']}:"
    )
    print(companies.head())
    print(
        f"Historical Changes from {config['date_range']['start_date']} to {config['date_range']['end_date']}:"
    )
    print(changes.head())
