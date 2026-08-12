"""
This module retrieves the list of S&P 500 companies and historical changes from Wikipedia
and returns them as pandas DataFrames.
Data is filtered based on the date range specified in the config.json file.
See the config/config.json file for the date range configuration.

Sources:
- Current Constituents: https://en.wikipedia.org/wiki/List_of_S%26P_500_companies
- Historical Changes: https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500
"""

from io import StringIO
import pandas as pd
import requests
from sp500_quantitative_dataset import config


def _flatten_columns(df: pd.DataFrame) -> list[str]:
    """
    Returns lowercase, flattened column name strings for a DataFrame, handling both
    regular and MultiIndex columns. Wikipedia sometimes renders grouped headers
    (e.g. 'Added'/'Removed' with 'Ticker'/'Security' sub-columns), which pandas reads
    as a MultiIndex.
    """
    if isinstance(df.columns, pd.MultiIndex):
        return [
            " ".join(str(c) for c in col if str(c) != "nan").strip().lower()
            for col in df.columns.values
        ]
    return [str(c).strip().lower() for c in df.columns]


def _find_table(
    tables: list[pd.DataFrame], required_keyword_groups: list[list[str]]
) -> pd.DataFrame:
    """
    Scans a list of tables (as returned by pd.read_html) and returns the first one
    whose columns satisfy every keyword group. Each group is a list of alternative
    substrings; a column matching ANY substring in a group satisfies that group.
    """
    for df in tables:
        flat_cols = _flatten_columns(df)
        if all(
            any(keyword in col for col in flat_cols for keyword in group)
            for group in required_keyword_groups
        ):
            return df
    raise ValueError(
        "Could not locate an expected table on the Wikipedia page. "
        "The page layout may have changed further - inspect pd.read_html(...) output manually."
    )


def retrieve_companies() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Retrieves current S&P 500 companies and historical changes from Wikipedia.

    Returns:
        tuple: A tuple containing two pandas DataFrames:
            - companies: DataFrame containing current S&P 500 companies.
            - historical_changes: DataFrame containing historical index changes.
    Raises:
        requests.exceptions.RequestException: If there is an issue with the HTTP request.
        ValueError: If the expected tables cannot be located on the pages.
    """
    headers = {"User-Agent": "S&P 500 Quant/1.0 (student@gmail.com)"}

    # -------------------------------------------------------------------------
    # 1. Fetch Current S&P 500 Companies
    # -------------------------------------------------------------------------
    url_constituents = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    response_constituents = requests.get(url_constituents, headers=headers)
    response_constituents.raise_for_status()

    html_constituents = StringIO(response_constituents.text)
    tables_constituents = pd.read_html(html_constituents)

    companies_raw = _find_table(
        tables_constituents,
        required_keyword_groups=[
            ["symbol", "ticker"],
            ["security", "company"],
            ["cik"],
            ["date added", "date"],
        ],
    )

    companies_col_mapping = {}
    for col in companies_raw.columns:
        col_str = str(col).strip().lower()
        if col_str == "cik":
            companies_col_mapping[col] = "CIK"
        elif col_str in ("symbol", "ticker"):
            companies_col_mapping[col] = "Ticker"
        elif col_str in ("security", "company"):
            companies_col_mapping[col] = "Company Name"
        elif "gics sector" in col_str and "sub" not in col_str:
            companies_col_mapping[col] = "GICS Sector"
        elif "gics sub" in col_str:
            companies_col_mapping[col] = "GICS Sub-Industry"
        elif "date added" in col_str or col_str == "date":
            companies_col_mapping[col] = "Date Added"

    companies = companies_raw.rename(columns=companies_col_mapping)
    required_company_cols = [
        "CIK",
        "Ticker",
        "GICS Sector",
        "GICS Sub-Industry",
        "Company Name",
        "Date Added",
    ]
    for rc in required_company_cols:
        if rc not in companies.columns:
            companies[rc] = None
    companies = companies[required_company_cols].copy()

    companies["Date Added"] = pd.to_datetime(companies["Date Added"], errors="coerce")
    companies = companies.sort_values(by="Date Added", ascending=True).reset_index(
        drop=True
    )

    # -------------------------------------------------------------------------
    # 2. Fetch Historical S&P 500 Index Changes
    # -------------------------------------------------------------------------
    url_changes = "https://en.wikipedia.org/wiki/Historical_components_of_the_S%26P_500"
    response_changes = requests.get(url_changes, headers=headers)
    response_changes.raise_for_status()

    html_changes = StringIO(response_changes.text)
    tables_changes = pd.read_html(html_changes)

    changes_raw = _find_table(
        tables_changes,
        required_keyword_groups=[["date"], ["ticker", "symbol"], ["removed"]],
    )

    changes_raw = changes_raw.copy()
    if isinstance(changes_raw.columns, pd.MultiIndex):
        changes_raw.columns = [
            "_".join(str(c) for c in col if str(c) != "nan").strip()
            for col in changes_raw.columns.values
        ]
    else:
        changes_raw.columns = [str(c).strip() for c in changes_raw.columns]

    # Map column headers to standard expected names
    col_mapping = {}
    for col in changes_raw.columns:
        col_str = str(col).lower()
        if "date" in col_str:
            col_mapping[col] = "Date"
        elif ("add" in col_str) and ("ticker" in col_str or "symbol" in col_str):
            col_mapping[col] = "Added Ticker"
        elif ("add" in col_str) and (
            "compan" in col_str or "name" in col_str or "security" in col_str
        ):
            col_mapping[col] = "Added Company Name"
        elif ("rem" in col_str) and ("ticker" in col_str or "symbol" in col_str):
            col_mapping[col] = "Removed Ticker"
        elif ("rem" in col_str) and (
            "compan" in col_str or "name" in col_str or "security" in col_str
        ):
            col_mapping[col] = "Removed Company Name"
        elif "reas" in col_str or "note" in col_str or "cause" in col_str:
            col_mapping[col] = "Change Reason"

    historical_changes = changes_raw.rename(columns=col_mapping)

    required_change_cols = [
        "Date",
        "Added Ticker",
        "Added Company Name",
        "Removed Ticker",
        "Removed Company Name",
        "Change Reason",
    ]
    for rc in required_change_cols:
        if rc not in historical_changes.columns:
            historical_changes[rc] = None
    historical_changes = historical_changes[required_change_cols].copy()

    historical_changes["Date"] = pd.to_datetime(
        historical_changes["Date"], errors="coerce"
    )

    # Drop parsing artifacts / unparsed header rows
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
