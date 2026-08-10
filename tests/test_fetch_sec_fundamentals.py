"""
Unit and integration tests for the SEC EDGAR fundamentals extraction module.
This test suite covers API requesting, JSON parsing, dataframe aggregation,
and the generation of the final CSV/Parquet datasets including failure logs.
"""

import pandas as pd

from sp500_quantitative_dataset.fetch_sec_fundamentals import (
    get_sec_headers,
    fetch_company_facts,
    extract_metric_dataframe,
    process_company_fundamentals,
    generate_fundamentals_dataset,
)

MOCK_CONFIG = {
    "paths": {
        "daily_composition": "fake_composition.csv",
        "fundamentals_csv": "fake_fundamentals.csv",
        "fundamentals_parquet": "fake_fundamentals.parquet",
        "failed_sec_log": "fake_failed_sec.json",
    }
}

MOCK_COMPOSITION = pd.DataFrame(
    {
        "Date": ["2023-01-01", "2023-01-01"],
        "Ticker": ["AAPL", "DEAD"],
        "CIK": ["320193", "9999999999"],
    }
)

MOCK_SEC_JSON = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "units": {
                    "USD": [
                        {
                            "end": "2022-09-24",
                            "val": 394328000000,
                            "accn": "0000320193-22-000108",
                            "fy": 2022,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2022-10-28",
                        }
                    ]
                }
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "end": "2022-09-24",
                            "val": 99803000000,
                            "accn": "0000320193-22-000108",
                            "fy": 2022,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2022-10-28",
                        }
                    ]
                }
            },
        }
    },
}


class MockResponse:
    """Mock object to simulate requests.get responses."""

    def __init__(self, json_data, status_code):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data


# Unit tests


def test_get_sec_headers():
    """Tests if the SEC headers contain the mandatory User-Agent."""
    headers = get_sec_headers()
    assert "User-Agent" in headers
    assert "student@agh.edu.pl" in headers["User-Agent"]


def test_fetch_company_facts_success(mocker):
    """Tests successful data retrieval from the SEC API (Status 200)."""
    mocker.patch("requests.get", return_value=MockResponse(MOCK_SEC_JSON, 200))

    # Passing integer to test if it gets zero-padded correctly
    result = fetch_company_facts("320193")
    assert isinstance(result, dict)
    assert result["cik"] == 320193


def test_fetch_company_facts_failure(mocker):
    """Tests API failure handling (e.g., Status 404 for delisted companies)."""
    mocker.patch("requests.get", return_value=MockResponse({}, 404))

    result = fetch_company_facts("999999")
    assert isinstance(result, dict)
    assert not result  # Dictionary should be empty


def test_extract_metric_dataframe():
    """Tests parsing of the nested SEC XBRL JSON into a clean Pandas DataFrame."""
    df = extract_metric_dataframe(MOCK_SEC_JSON, "Revenues", "Revenue")

    assert not df.empty
    assert "Revenue" in df.columns
    assert "Filing Date" in df.columns
    assert df.iloc[0]["Revenue"] == 394328000000
    assert df.iloc[0]["Form"] == "10-K"


def test_process_company_fundamentals(mocker):
    """Tests aggregating multiple financial metrics into a single panel."""
    mocker.patch(
        "sp500_quantitative_dataset.fetch_sec_fundamentals.fetch_company_facts",
        return_value=MOCK_SEC_JSON,
    )

    df = process_company_fundamentals("320193", "AAPL")

    assert not df.empty
    assert "Revenue" in df.columns
    assert "Net Income" in df.columns
    assert "CIK" in df.columns
    assert "Ticker" in df.columns
    assert df.iloc[0]["Ticker"] == "AAPL"
    assert df.iloc[0]["CIK"] == "0000320193"  # Should be zero-padded


# Integration tests


def test_generate_fundamentals_dataset(mocker):
    """
    Tests the complete pipeline: iterating over tickers, fetching data,
    handling failures (Dead Letter Queue logging), and saving CSV/Parquet outputs.
    """
    # 1. Mock configuration
    mocker.patch(
        "sp500_quantitative_dataset.fetch_sec_fundamentals.config", MOCK_CONFIG
    )
    mocker.patch("os.path.exists", return_value=True)

    # 2. Mock reading composition CSV
    mocker.patch("pandas.read_csv", return_value=MOCK_COMPOSITION)

    # 3. Mock processing fundamentals
    # AAPL returns a valid DataFrame, DEAD returns an empty DataFrame
    valid_df = pd.DataFrame(
        {
            "Filing Date": ["2022-10-28"],
            "Period End": ["2022-09-24"],
            "Form": ["10-K"],
            "Revenue": [1000],
            "CIK": ["0000320193"],
            "Ticker": ["AAPL"],
        }
    )

    def mock_process(cik, ticker):
        if ticker == "AAPL":
            return valid_df
        return pd.DataFrame()

    mocker.patch(
        "sp500_quantitative_dataset.fetch_sec_fundamentals.process_company_fundamentals",
        side_effect=mock_process,
    )

    # 4. Mock file saving (autospec=True required to catch self parameter properly)
    mock_to_csv = mocker.patch("pandas.DataFrame.to_csv", autospec=True)
    mock_to_parquet = mocker.patch("pandas.DataFrame.to_parquet", autospec=True)
    mock_json_dump = mocker.patch("json.dump")
    mocker.patch("builtins.open", mocker.mock_open())
    mocker.patch("time.sleep")  # Prevent test from actually waiting

    # Execute
    generate_fundamentals_dataset()

    # Assert CSV saving
    assert mock_to_csv.called
    saved_csv_df = mock_to_csv.call_args[0][0]
    assert "AAPL" in saved_csv_df["Ticker"].values
    assert "DEAD" not in saved_csv_df["Ticker"].values

    # Assert Parquet saving
    assert mock_to_parquet.called

    # Assert Failure Logging (Dead Letter Queue)
    assert mock_json_dump.called
    failed_logs = mock_json_dump.call_args[0][0]
    assert isinstance(failed_logs, list)
    assert len(failed_logs) == 1
    assert failed_logs[0]["Ticker"] == "DEAD"
    assert "SEC returned 404" in failed_logs[0]["Reason"]
