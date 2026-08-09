import pytest
import pandas as pd
import json
import os

from s_and_p_500_picker.backfill_missing_prices import (
    fetch_tiingo_data,
    backfill_missing_prices
)

# Unit test for fetching data from Tiingo

class MockResponse:
    """Mock object to simulate requests.get response."""
    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

def test_fetch_tiingo_data_success(mocker):
    """Tests successful data retrieval and column mapping from Tiingo API."""
    mock_api_data = [
        {
            "date": "2023-01-02T00:00:00.000Z",
            "open": 100.0,
            "high": 105.0,
            "low": 98.0,
            "close": 102.5,
            "adjClose": 101.5,
            "volume": 50000
        }
    ]
    
    # Mock requests.get to return status 200 with fake JSON data
    mocker.patch('requests.get', return_value=MockResponse(mock_api_data, 200))

    df = fetch_tiingo_data("FRC", "2023-01-01", "2023-01-03", "fake_api_key")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Date" in df.columns
    assert "Adj Close" in df.columns
    assert "Ticker" in df.columns
    assert df.iloc[0]["Ticker"] == "FRC"
    assert df.iloc[0]["Date"] == "2023-01-02"
    assert df.iloc[0]["Close"] == 102.5
    assert df.iloc[0]["Adj Close"] == 101.5

def test_fetch_tiingo_data_not_found(mocker):
    """Tests handling of a 404 error from Tiingo API for a delisted/missing stock."""
    mocker.patch('requests.get', return_value=MockResponse([], 404))

    df = fetch_tiingo_data("DEAD", "2023-01-01", "2023-01-03", "fake_api_key")

    assert isinstance(df, pd.DataFrame)
    assert df.empty


# Integration test for backfill process

MOCK_CONFIG = {
    "date_range": {
        "start_date": "2023-01-01",
        "end_date": "2023-01-03"
    },
    "paths": {
        "missing_tickers": "fake_missing.json",
        "historical_prices": "fake_prices.csv"
    }
}

MOCK_EXISTING_PRICES = pd.DataFrame({
    "Date": ["2023-01-02", "2023-01-02"],
    "Open": [10.0, 20.0],
    "High": [11.0, 21.0],
    "Low": [9.0, 19.0],
    "Close": [10.5, 20.5],
    "Adj Close": [10.0, 20.0],
    "Volume": [1000, 2000],
    "Ticker": ["AAPL", "MSFT"]
})

def test_backfill_missing_prices_workflow(mocker):
    """
    Tests the complete backfill orchestration: reads missing tickers, 
    fetches data via API, merges with existing CSV, and saves back.
    """
    # 1. Mock environment variable for API key
    mocker.patch.dict(os.environ, {"TIINGO_API_KEY": "test_key"})
    
    # 2. Mock configuration loading
    mocker.patch('s_and_p_500_picker.backfill_missing_prices.config', MOCK_CONFIG)
    
    # 3. Mock file reading (missing tickers JSON)
    mock_file_data = json.dumps([{"Ticker": "FRC", "CIK": "0000000000", "Reason": "Test reason"}])
    mocker.patch('builtins.open', mocker.mock_open(read_data=mock_file_data))
    
    # 4. Mock fetch_tiingo_data to return a fake backfilled dataframe
    fake_backfilled_df = pd.DataFrame({
        "Date": ["2023-01-02"],
        "Open": [50.0],
        "High": [55.0],
        "Low": [45.0],
        "Close": [52.0],
        "Adj Close": [51.0],
        "Volume": [100],
        "Ticker": ["FRC"]
    })
    mocker.patch('s_and_p_500_picker.backfill_missing_prices.fetch_tiingo_data', return_value=fake_backfilled_df)
    
    # 5. Mock reading existing prices CSV (and force os.path.exists to return True)
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('pandas.read_csv', return_value=MOCK_EXISTING_PRICES)
    
    # 6. Mock saving to CSV using autospec=True to catch the dataframe instance
    mock_to_csv = mocker.patch('pandas.DataFrame.to_csv', autospec=True)

    # Execute backfill
    backfill_missing_prices()

    # Assertions
    assert mock_to_csv.called
    saved_df = mock_to_csv.call_args[0][0]  # First argument is the combined DataFrame ("self")
    
    # Check if FRC was successfully merged alongside AAPL and MSFT
    assert "FRC" in saved_df["Ticker"].values
    assert "AAPL" in saved_df["Ticker"].values
    assert len(saved_df) == 3  # 2 existing + 1 backfilled