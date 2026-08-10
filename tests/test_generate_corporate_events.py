import pandas as pd

from sp500_quantitative_dataset.generate_corporate_events import (
    categorize_reason,
    generate_corporate_events,
)


# Catogerization logic
def test_categorize_reason():
    """
    Tests the string matching rules for categorizing corporate events.
    Ensures all edge cases (like 'spun' vs 'spin') are handled correctly.
    """

    # M&A (Acquisitions & Mergers)
    assert categorize_reason("Acquired by Microsoft") == "ACQUISITION"
    assert categorize_reason("Merger with Dow Chemical") == "ACQUISITION"
    assert categorize_reason("Pall taken over") == "ACQUISITION"
    assert categorize_reason("L3 purchased by Harris") == "ACQUISITION"

    # Market Capitalization
    assert categorize_reason("Market capitalization changes") == "MARKET_CAP"
    assert categorize_reason("Market cap too low") == "MARKET_CAP"

    # Spin-offs (Checking both 'spin' and 'spun')
    assert categorize_reason("Spun-off into a separate entity") == "SPIN_OFF"
    assert categorize_reason("DOW spun off from DWDP") == "SPIN_OFF"
    assert categorize_reason("HPQ spins off HPE") == "SPIN_OFF"
    assert categorize_reason("Company was split") == "SPIN_OFF"

    # Bankruptcies
    assert categorize_reason("Filing for Chapter 11 bankruptcy") == "BANKRUPTCY"
    assert categorize_reason("The company was liquidated") == "BANKRUPTCY"

    # Other or missing reasons
    assert categorize_reason("Ticker symbol change") == "OTHER"
    assert categorize_reason("CFG replaces PCP") == "OTHER"
    assert categorize_reason(None) == "OTHER"


# Integration test for the main module

# Mock configuration matching the expected structure
MOCK_CONFIG = {
    "paths": {
        "events_ledger_csv": "fake_path_events.csv",
        "events_ledger_parquet": "fake_path_events.parquet",
    }
}

# Mock historical changes designed to test filtering and sorting logic
MOCK_HISTORICAL_CHANGES = pd.DataFrame(
    {
        "Date": ["2023-02-01", "2023-01-01", "2023-03-01"],
        "Removed Ticker": [
            "A",
            "B",
            pd.NA,
        ],  # The last row has NaN in Removed Ticker (addition only)
        "Removed Company Name": ["Company A", "Company B", pd.NA],
        "Added Ticker": ["C", "D", "E"],
        "Change Reason": [
            "Filing for bankruptcy protection",
            "DOW spun off from DWDP",
            "Market cap changes",
        ],
    }
)

# The current composition is not used in this module, so it can be empty
MOCK_CURRENT = pd.DataFrame()


def test_generate_corporate_events(mocker):
    """
    Tests the extraction, cleaning, and categorization of the Corporate Events Ledger.
    """
    # Mock file operations and configuration loading
    mocker.patch("builtins.open", mocker.mock_open())

    # Mock the data retrieval function to return our predefined DataFrames
    mocker.patch(
        "sp500_quantitative_dataset.generate_corporate_events.retrieve_companies",
        return_value=(MOCK_CURRENT, MOCK_HISTORICAL_CHANGES),
    )

    mocker.patch("os.makedirs")
    mocker.patch.object(pd.DataFrame, "to_csv")
    mocker.patch.object(pd.DataFrame, "to_parquet")

    result_df = generate_corporate_events()

    assert isinstance(result_df, pd.DataFrame)

    # Expect exactly 2 rows. The third row (index 2) had pd.NA in "Removed Ticker" and should be dropped.
    assert len(result_df) == 2

    # Check if the DataFrame is sorted chronologically
    # The oldest event in our mock is January (Ticker B), which should appear first
    assert result_df.iloc[0]["Removed Ticker"] == "B"
    assert result_df.iloc[1]["Removed Ticker"] == "A"

    # Verify that categorization was applied successfully
    assert "Event Type" in result_df.columns
    assert (
        result_df.iloc[0]["Event Type"] == "SPIN_OFF"
    )  # Map from "DOW spun off from DWDP"
    assert (
        result_df.iloc[1]["Event Type"] == "BANKRUPTCY"
    )  # Map from "Filing for bankruptcy protection"
