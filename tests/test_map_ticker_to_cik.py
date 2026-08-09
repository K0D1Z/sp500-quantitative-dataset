"""
This module contains unit tests for the `map_ticker_to_cik` function in the `s_and_p_500_picker.map_ticker_to_cik` module.
The tests use the `pytest` framework and the `mocker` fixture to mock the retrieval of S&P 500 companies and historical changes,
as well as the loading of SEC and fallback JSON data. The tests verify that the function correctly maps tickers to CIKs,
including current and historical tickers, and that it prints a warning for any tickers that are still missing CIKs after the
fallback process.
"""

import pytest
import pandas as pd
from s_and_p_500_picker.map_ticker_to_cik import map_ticker_to_cik


MOCK_CURRENT_COMPANIES = pd.DataFrame(
    {
        "Ticker": ["AAPL", "MSFT"],
        "Company Name": ["Apple Inc.", "Microsoft Corp."],
        "CIK": [
            "320193",
            "789019",
        ],  # Celowo bez zer na początku, żeby sprawdzić zfill(10)
    }
)

MOCK_HISTORICAL_CHANGES = pd.DataFrame(
    {
        "Date": ["2015-01-01", "2018-01-01"],
        "Removed Ticker": ["SWY", "PETM"],
        "Removed Company Name": ["Safeway", "PetSmart"],
    }
)

MOCK_SEC_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corp."},
    "2": {"cik_str": 909954, "ticker": "PETM", "title": "PetSmart Inc."},
}

MOCK_FALLBACK_JSON = {
    "SWY": {
        "CIK": "0000086144",
        "Company Name": "Safeway Inc.",
        "Status": "correct",
        "Sources": ["https://fake-link.sec.gov"],
    }
}


def test_map_ticker_to_cik_success(mocker):
    """
    Test the map_ticker_to_cik function to ensure it correctly maps tickers to CIKs, including current and historical tickers.
    """
    mocker.patch(
        "s_and_p_500_picker.map_ticker_to_cik.retrieve_s_and_p_500_companies",
        return_value=(MOCK_CURRENT_COMPANIES, MOCK_HISTORICAL_CHANGES),
    )

    mocker.patch("builtins.open", mocker.mock_open())

    mocker.patch(
        "s_and_p_500_picker.map_ticker_to_cik.json.load",
        side_effect=[MOCK_SEC_JSON, MOCK_FALLBACK_JSON],
    )

    result_df = map_ticker_to_cik()

    assert isinstance(result_df, pd.DataFrame)
    assert len(result_df) == 4  # AAPL, MSFT (Current) + SWY, PETM (Removed)

    assert result_df.loc[result_df["Ticker"] == "AAPL", "CIK"].iloc[0] == "0000320193"

    petm_row = result_df[result_df["Ticker"] == "PETM"].iloc[0]
    assert petm_row["CIK"] == "0000909954"
    assert petm_row["Company Name"] == "PetSmart Inc."

    swy_row = result_df[result_df["Ticker"] == "SWY"].iloc[0]
    assert swy_row["CIK"] == "0000086144"
    assert swy_row["Company Name"] == "Safeway"


def test_map_ticker_to_cik_missing_warning(mocker, capsys):
    """
    Test the map_ticker_to_cik function to ensure it prints a warning for tickers that are still missing CIKs after the fallback process.
    """
    mocker.patch(
        "s_and_p_500_picker.map_ticker_to_cik.retrieve_s_and_p_500_companies",
        return_value=(MOCK_CURRENT_COMPANIES, MOCK_HISTORICAL_CHANGES),
    )

    mocker.patch("builtins.open", mocker.mock_open())

    mocker.patch(
        "s_and_p_500_picker.map_ticker_to_cik.json.load",
        side_effect=[MOCK_SEC_JSON, {}],
    )

    result_df = map_ticker_to_cik()

    swy_row = result_df[result_df["Ticker"] == "SWY"].iloc[0]
    assert pd.isna(swy_row["CIK"])

    captured = capsys.readouterr()
    assert (
        "WARNING: The following historical tickers are still missing CIKs"
        in captured.out
    )
    assert "SWY" in captured.out
