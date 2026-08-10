"""
This module contains unit tests for the `retrieve_companies` function in the
`sp500_quantitative_dataset.retrieve_companies` module. The tests use the `pytest`
framework and the `mocker` fixture to mock HTTP requests and responses.
"""

import pytest
import pandas as pd
from requests.exceptions import HTTPError
from sp500_quantitative_dataset.retrieve_companies import (
    retrieve_companies,
)

MOCK_HTML = """
<html>
  <body>
    <table>
      <tr>
        <th>Symbol</th><th>Security</th><th>SEC filings</th><th>GICS Sector</th><th>GICS Sub-Industry</th><th>Headquarters Location</th><th>Date added</th><th>CIK</th><th>Founded</th>
      </tr>
      <tr>
        <td>AAPL</td><td>Apple Inc.</td><td>reports</td><td>Information Technology</td><td>Technology Hardware</td><td>Cupertino, CA</td><td>1982-11-30</td><td>0000320193</td><td>1977</td>
      </tr>
    </table>

    <table>
      <tr>
        <th>Date</th><th>Added</th><th>Added</th><th>Removed</th><th>Removed</th><th>Reason</th>
      </tr>
      <tr>
        <th>Date</th><th>Ticker</th><th>Security</th><th>Ticker</th><th>Security</th><th>Reason</th>
      </tr>
      <tr>
        <td>January 1, 2020</td><td>TSLA</td><td>Tesla</td><td>AIV</td><td>Apartment Inv</td><td>Market Cap</td>
      </tr>
    </table>
  </body>
</html>
"""


def test_retrieve_companies(mocker):
    """
    Test the retrieve_companies function with a mock HTTP response.
    """
    mock_response = mocker.Mock()
    mock_response.text = MOCK_HTML
    mock_response.raise_for_status.return_value = None

    mocker.patch(
        "sp500_quantitative_dataset.retrieve_companies.requests.get",
        return_value=mock_response,
    )

    companies, changes = retrieve_companies()

    assert isinstance(companies, pd.DataFrame)
    assert isinstance(changes, pd.DataFrame)

    assert "Ticker" in companies.columns
    assert companies.iloc[0]["Ticker"] == "AAPL"

    assert "Added Ticker" in changes.columns
    assert changes.iloc[0]["Added Ticker"] == "TSLA"


def test_http_error(mocker):
    """
    Test that the retrieve_companies function raises an HTTPError when the HTTP request fails.
    """
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = HTTPError("HTTP Error")

    mocker.patch(
        "sp500_quantitative_dataset.retrieve_companies.requests.get",
        return_value=mock_response,
    )

    with pytest.raises(HTTPError):
        retrieve_companies()
