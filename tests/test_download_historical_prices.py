""" """

import pandas as pd
import numpy as np

from sp500_quantitative_dataset.download_historical_prices import (
    format_ticker_for_yahoo,
    download_historical_prices,
)

# Unit tests


def test_format_ticker_for_yahoo():
    """Tests if standard tickers are correctly converted to Yahoo format."""
    assert format_ticker_for_yahoo("AAPL") == "AAPL"
    assert format_ticker_for_yahoo("BRK.B") == "BRK-B"
    assert format_ticker_for_yahoo("BF.B") == "BF-B"
    assert format_ticker_for_yahoo(np.nan) == ""


# Integration tests

MOCK_CONFIG = {
    "date_range": {"start_date": "2023-01-01", "end_date": "2023-01-02"},
    "paths": {
        "daily_composition_csv": "fake_composition.csv",
        "daily_composition_parquet": "fake_composition.csv",
        "historical_prices_csv": "fake_prices.csv",
        "historical_prices_parquet": "fake_prices.parquet",
        "missing_tickers": "fake_missing.json",
    },
}

# Mocking the daily composition CSV
MOCK_COMPOSITION = pd.DataFrame(
    {
        "Date": ["2023-01-01", "2023-01-01", "2023-01-01"],
        "Ticker": ["AAPL", "BRK.B", "DEAD"],
        "CIK": ["123", "456", "789"],
    }
)

# Mocking yfinance response (MultiIndex DataFrame)
# AAPL and BRK-B have data, DEAD returns NaNs (simulating a delisted stock)
columns = pd.MultiIndex.from_tuples(
    [
        ("Close", "AAPL"),
        ("Close", "BRK-B"),
        ("Close", "DEAD"),
        ("Open", "AAPL"),
        ("Open", "BRK-B"),
        ("Open", "DEAD"),
    ],
    names=["Price", "Ticker"],
)

MOCK_YF_DATA = pd.DataFrame(
    [
        [150.0, 300.0, np.nan, 149.0, 299.0, np.nan],
        [151.0, 301.0, np.nan, 150.0, 300.0, np.nan],
    ],
    index=pd.to_datetime(["2023-01-01", "2023-01-02"]),
    columns=columns,
)


def test_download_historical_prices(mocker):
    """
    Tests the download, flattening, and missing ticker identification process.
    """
    mocker.patch(
        "sp500_quantitative_dataset.download_historical_prices.config", MOCK_CONFIG
    )

    # Mock reading the CSV composition
    mocker.patch("pandas.read_csv", return_value=MOCK_COMPOSITION)

    # Mock yfinance download
    mocker.patch("yfinance.download", return_value=MOCK_YF_DATA)

    # Mock file saving
    mock_to_csv = mocker.patch.object(pd.DataFrame, "to_csv", autospec=True)
    mock_to_parquet = mocker.patch.object(pd.DataFrame, "to_parquet", autospec=True)

    mock_json_dump = mocker.patch("json.dump")
    mocker.patch("builtins.open", mocker.mock_open())

    # Execute
    download_historical_prices()

    # Assertions for CSV Saving (Flattened Data)
    assert mock_to_csv.called
    assert mock_to_parquet.called
    saved_df = mock_to_csv.call_args[0][
        0
    ]  # Get the DataFrame that was about to be saved

    # Check if the dot was restored in BRK.B
    assert "BRK.B" in saved_df["Ticker"].values
    assert "BRK-B" not in saved_df["Ticker"].values

    # Check if DEAD was correctly dropped from the flattened structure
    assert "DEAD" not in saved_df["Ticker"].values

    # Assertions for JSON Saving (Missing Tickers)
    assert mock_json_dump.called
    missing_list_saved = mock_json_dump.call_args[0][0]

    # DEAD should be recorded as missing
    assert any(item.get("Ticker") == "DEAD" for item in missing_list_saved)
