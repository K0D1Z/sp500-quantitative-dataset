"""
Unit and integration tests for the feature engineering module.
Tests the point-in-time merge logic, data cleaning (forward-filling), 
and the accurate calculation of financial ratios (P/E, P/B, Market Cap).
"""

import pytest
import pandas as pd
import numpy as np
import os

from s_and_p_500_picker.feature_engineering import (
    load_and_clean_fundamentals,
    load_and_clean_prices,
    calculate_financial_ratios,
    generate_features
)


MOCK_CONFIG = {
    "paths": {
        "historical_prices": "fake_prices.csv",
        "fundamentals_csv": "fake_fundamentals.csv",
        "daily_features_csv": "fake_daily_features.csv",
        "daily_features_parquet": "fake_daily_features.parquet"
    }
}

def test_load_and_clean_fundamentals(mocker):
    """
    Tests if multiple filings on the same day are compressed properly,
    and if missing values are correctly forward-filled over time.
    """
    mock_fund_data = pd.DataFrame({
        "Ticker": ["AAPL", "AAPL", "AAPL"],
        "Filing Date": ["2023-01-01", "2023-01-01", "2023-04-01"],
        "Period End": ["2022-09-30", "2022-12-31", "2023-03-31"],
        "Revenue": [1000, 1500, np.nan],  # Revenue is missing in Q2
        "Net Income": [100, 150, 200]
    })
    
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('pandas.read_csv', return_value=mock_fund_data)
    
    df = load_and_clean_fundamentals("fake_path.csv")
    
    # 3 rows should be compressed to 2 unique Filing Dates for AAPL
    assert len(df) == 2
    
    # Check if the last period end was kept for the first date
    first_date_row = df[df["Filing Date"] == pd.to_datetime("2023-01-01")].iloc[0]
    assert first_date_row["Revenue"] == 1500
    
    # Check if forward-fill worked for the missing Revenue on 2023-04-01
    second_date_row = df[df["Filing Date"] == pd.to_datetime("2023-04-01")].iloc[0]
    assert second_date_row["Revenue"] == 1500  # Carried forward from previous quarter
    assert second_date_row["Net Income"] == 200 # Own value kept

def test_load_and_clean_prices(mocker):
    """Tests if prices are loaded and dates are properly parsed and sorted."""
    mock_prices_data = pd.DataFrame({
        "Ticker": ["AAPL", "AAPL"],
        "Date": ["2023-01-02", "2023-01-01"],
        "Close": [150.0, 145.0],
        "Stock Splits": [0.0, 0.0]
    })
    
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('pandas.read_csv', return_value=mock_prices_data)
    
    df = load_and_clean_prices("fake_path.csv")
    
    assert len(df) == 2
    # Ensure it's sorted chronologically
    assert df.iloc[0]["Date"] == pd.to_datetime("2023-01-01")

def test_calculate_financial_ratios():
    """
    Tests the mathematical accuracy of P/E, P/B, and Market Cap.
    Also tests edge cases like missing diluted shares, negative earnings, and zero equity.
    """
    test_df = pd.DataFrame({
        "Ticker": ["A", "B", "C"],
        "Close": [100.0, 50.0, 10.0],
        "Shares Outstanding (Diluted)": [10.0, np.nan, 5.0],
        "Shares Outstanding (Basic)": [10.0, 20.0, 5.0],  # B should fallback to Basic
        "EPS (Diluted)": [5.0, -2.0, 2.0],                # B has negative EPS (P/E should be NaN)
        "Stockholders Equity": [500.0, 1000.0, 0.0],       # C has zero equity (P/B should be NaN)
        "Cum Split Factor": [1.0, 1.0, 1.0]               # Added Cum Split Factor
    })
    
    result_df = calculate_financial_ratios(test_df)
    
    # Market Cap = Close * Shares * Split Factor
    assert result_df.loc[0, "Market Cap"] == 1000.0  # 100 * 10 * 1.0
    assert result_df.loc[1, "Market Cap"] == 1000.0  # 50 * 20 * 1.0 (fallback to basic shares)
    
    # P/E Ratio = Close / (EPS / Split Factor)
    assert result_df.loc[0, "P/E Ratio"] == 20.0     # 100 / 5
    assert pd.isna(result_df.loc[1, "P/E Ratio"])    # Negative EPS -> NaN
    
    # P/B Ratio = Close / (Equity / Adjusted Shares)
    # Book value per share for A = 500 / 10 = 50. P/B = 100 / 50 = 2.0
    assert result_df.loc[0, "P/B Ratio"] == 2.0
    assert pd.isna(result_df.loc[2, "P/B Ratio"])    # Zero equity -> NaN

def test_generate_features_workflow(mocker):
    """
    Tests the full orchestrator: loading, merging asof (Point-in-Time), 
    calculating metrics, and saving files.
    """
    mocker.patch('s_and_p_500_picker.feature_engineering.config', MOCK_CONFIG)
    
    mock_fund_clean = pd.DataFrame({
        "Ticker": ["AAPL"],
        "Filing Date": [pd.to_datetime("2023-01-01")],
        "EPS (Diluted)": [5.0],
        "Shares Outstanding (Diluted)": [10.0],
        "Shares Outstanding (Basic)": [10.0],
        "Stockholders Equity": [500.0]
    })
    
    mock_prices_clean = pd.DataFrame({
        "Ticker": ["AAPL", "AAPL"],
        "Date": [pd.to_datetime("2023-01-02"), pd.to_datetime("2023-01-03")],
        "Close": [100.0, 110.0],
        "Cum Split Factor": [1.0, 1.0]
    })
    
    mocker.patch('s_and_p_500_picker.feature_engineering.load_and_clean_fundamentals', return_value=mock_fund_clean)
    mocker.patch('s_and_p_500_picker.feature_engineering.load_and_clean_prices', return_value=mock_prices_clean)
    
    # Mock exports
    mock_to_csv = mocker.patch('pandas.DataFrame.to_csv', autospec=True)
    mock_to_parquet = mocker.patch('pandas.DataFrame.to_parquet', autospec=True)
    
    # Execute
    generate_features()
    
    # Assert saving methods were called
    assert mock_to_csv.called
    assert mock_to_parquet.called
    
    # Inspect the final dataframe being saved
    final_df = mock_to_csv.call_args[0][0]
    
    assert len(final_df) == 2
    assert "P/E Ratio" in final_df.columns
    assert "Market Cap" in final_df.columns
    
    # Check if point-in-time merge worked
    assert final_df.iloc[0]["Market Cap"] == 1000.0  # 100.0 * 10.0 * 1.0
    assert final_df.iloc[1]["Market Cap"] == 1100.0  # 110.0 * 10.0 * 1.0