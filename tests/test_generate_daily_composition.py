"""
This module contains unit test for `generate_daily_composition` function in the function in the
`sp500_quantitative_dataset.generate_daily_composition` module.
"""

import pandas as pd
from sp500_quantitative_dataset.generate_daily_composition import (
    generate_daily_composition,
)


MOCK_CONFIG = {
    "date_range": {"start_date": "2023-01-01", "end_date": "2023-01-03"},
    "paths": {
        "daily_composition_csv": "fake_composition.csv",
        "daily_composition_parquet": "fake_composition.parquet",
    },
}

MOCK_CURRENT_COMPANIES = pd.DataFrame(
    {"Ticker": ["AAPL", "TSLA"], "Company Name": ["Apple", "Tesla"]}
)

# Historical change: 2nd January TSLA replaces F
MOCK_HISTORICAL_CHANGES = pd.DataFrame(
    {
        "Date": ["2023-01-02"],
        "Added Ticker": ["TSLA"],
        "Added Company Name": ["Tesla"],
        "Removed Ticker": ["F"],
        "Removed Company Name": ["Ford"],
        "Reason": ["Market cap"],
    }
)

# CIK mapping (map_ticker_to_cik return DataFrame)
MOCK_CIK_MAPPING = pd.DataFrame(
    {
        "Ticker": ["AAPL", "TSLA", "F"],
        "CIK": ["0000320193", "0001318605", "0000037996"],
        "Company Name": ["Apple", "Tesla", "Ford"],
    }
)


def test_generate_daily_composition(mocker):
    """
    Checks whether generate_daily_composition module correctly
    rolls back index changes traversing backwards from end_date to start_date.
    """
    mocker.patch(
        "sp500_quantitative_dataset.generate_daily_composition.config", MOCK_CONFIG
    )

    mocker.patch(
        "sp500_quantitative_dataset.generate_daily_composition.retrieve_companies",
        return_value=(MOCK_CURRENT_COMPANIES, MOCK_HISTORICAL_CHANGES),
    )

    mocker.patch(
        "sp500_quantitative_dataset.generate_daily_composition.map_ticker_to_cik",
        return_value=MOCK_CIK_MAPPING,
    )

    mocker.patch("os.makedirs")
    mocker.patch.object(pd.DataFrame, "to_csv")
    mocker.patch.object(pd.DataFrame, "to_parquet")
    
    result_df = generate_daily_composition()

    assert isinstance(result_df, pd.DataFrame)

    # Expected 3 days (01.01, 02.01, 03.01) for each exactly 2 firms
    assert len(result_df) == 6

    # 3rd January (End Date) ->  AAPL & TSLA should be there
    jan_3 = result_df[result_df["Date"] == pd.to_datetime("2023-01-03")]
    tickers_jan_3 = set(jan_3["Ticker"].tolist())
    assert tickers_jan_3 == {"AAPL", "TSLA"}

    # 1st January (Start Date) -> Returning BEFORE the change. TSLA should be gone, F comes back.
    jan_1 = result_df[result_df["Date"] == pd.to_datetime("2023-01-01")]
    tickers_jan_1 = set(jan_1["Ticker"].tolist())
    assert tickers_jan_1 == {"AAPL", "F"}

    # Had CIKs been properly mapped
    f_row = jan_1[jan_1["Ticker"] == "F"].iloc[0]
    assert f_row["CIK"] == "0000037996"
