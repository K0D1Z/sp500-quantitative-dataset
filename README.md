# ✦ S&P 500 Quantitative Dataset & PIT Pipeline ✦

> Publicly available data should never be behind a paywall—including public corporate data.

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests: Pytest](https://img.shields.io/badge/Tests-Pytest-0A9EDC.svg?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Data Source: SEC EDGAR](https://img.shields.io/badge/Data_Source-SEC_EDGAR-003366.svg)](https://www.sec.gov/edgar)
[![Data Source: yfinance](https://img.shields.io/badge/Data_Source-yfinance-6001D2.svg?logo=yahoo&logoColor=white)](https://github.com/ranaroussi/yfinance)
[![Data Source: Tiingo API](https://img.shields.io/badge/Data_Source-Tiingo_API-028090.svg)](https://api.tiingo.com/)
[![Documentation: Sphinx](https://img.shields.io/badge/Docs-Sphinx-000000.svg?logo=sphinx&logoColor=white)](#-documentation)

**Survivorship-Bias-Free**, and **Point-in-Time (PIT)** daily financial dataset of the S&P 500 index. This project reverse-engineers the daily historical index constituents, extracts raw US-GAAP XBRL fundamentals directly from SEC EDGAR, computes TTM (Trailing Twelve Months) flow metrics, incorporates split adjustments, and generates machine-learning-ready technical features.

---

![logo](img/logo.png)

## ► Key Highlights & Architecture Features

1. **Survivorship-Bias-Free Universe:** Reverse-engineers daily index composition from 2015 to present using current constituents and historical change logs. Includes delisted, acquired, and bankrupt companies (e.g., First Republic Bank, SVB).
2. **Strict Point-in-Time (PIT) Matching:** Fundamentals are merged with market prices based on the official SEC **`Filing Date`** (via `pd.merge_asof`) rather than reporting period ends, completely eliminating **look-ahead bias** in backtesting.
3. **TTM Normalization:** All income statement and cash flow metrics are aggregated across a rolling 4-quarter window (Trailing Twelve Months) to prevent distorted quarterly seasonality and produce realistic P/E ratios.
4. **Backward Cumulative Split Adjustment:** Computes a time-reversibly adjusted `Cum Split Factor` to dynamically align historical point-in-time share counts and EPS with unadjusted market prices.
5. **Rate-Limit Resilient ETL:** Built-in proactive batching system (45 req/hour) with stateful persistence to bypass Tiingo API free-tier throttling seamlessly.
6. **Containerized & Tested:** Fully dockerized via `Docker Compose`, managed with `uv`, and covered by comprehensive integration and unit test suites using `pytest`.
7. **Everything available for free:** The pipeline uses public APIs and the free plans of data-providing institutions.
8. **Create only one account:** To use the dataset pipeline, you create only one account (Tiingo).

---

## ► Getting Started

### Prerequisites

* **Docker & Docker Compose** OR **Python 3.12+** with **`uv`** installed.
* **Tiingo API Key:** Free account at [Tiingo](https://api.tiingo.com/) for historical delisted price backfilling. If you don't want to use your real email address, simply create an additional one with a service provider like [Tuta](https://tuta.com/) (temporary email addresses may not work).

---

### Option 1: Containerized Execution

1. **Clone the repository:**

```bash
git clone git@github.com:K0D1Z/sp500-quantitative-dataset.git
cd sp500-quantitative-dataset

```

2. **Configure environment variables:**
Create a `.env` file in the root directory:

```env
TIINGO_API_KEY=your_actual_tiingo_api_key_here

```

3. **Build and run the entire pipeline via Docker Compose:**

```bash
docker compose up --build

```

*The processed datasets will be automatically populated into your local `./data` folder via volume mounts.*

---

### Option 2: Local Python Execution with `uv`

1. **Install `uv` (Fast Python package installer):**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

```

2. **Set up virtual environment and install dependencies:**

```bash
uv sync

```

3. **Export your API Key:**

```bash
export TIINGO_API_KEY="your_actual_tiingo_api_key_here"

```

4. **Run the master ETL pipeline:**

```bash
uv run python main.py

```
> [!IMPORTANT]
> Due to Tiingo's API hourly limits, executing a script on the free plan can take 2-3 hours. If you want to speed up your script, consider purchasing a monthly premium plan with Tiingo. Alternatively, you can purchase monthly API access for a more comprehensive dataset. It's up to you :)
> If pipeline Step 1 isn't working correctly, it likely means the external site's structure has changed. Please contact me if this happens, as I'll need to update the link or selectors.

---

## ► Directory Structure

```text
sp500-quantitative-dataset/
├── config/
│   ├── config.json                     # Main pipeline configuration (date ranges, file paths)
│   └── example_config.json             # Backup template configuration
├── data/                               # Local volume directory for generated datasets
│   ├── config/
│   │   ├── company_tickers.json        # SEC company tickers mapping
│   │   └── fallback_ciks.json          # Manual fallback CIK lookup for historical entities
│   ├── datasets/
│   │   ├── daily_composition/          # Reconstructed daily constituent logs (.csv & .parquet)
│   │   ├── daily_features/             # Final PIT merged features (.csv & .parquet)
│   │   ├── events/                     # Categorized corporate events ledger (.csv & .parquet)
│   │   ├── fundamental_data/           # SEC EDGAR XBRL fundamentals (.csv & .parquet)
│   │   └── historical_prices/          # Cleaned market price series (.csv & .parquet)
│   └── missing/
│       ├── missing_example/            # Sample logs for missing data
│       ├── missing_sec_fundamentals.json
│       ├── missing_tickers_tiingo.json
│       └── missing_tickers_yfinance.json
├── docs/                               # Sphinx documentation source files & builds
├── src/
│   └── sp500_quantitative_dataset/
│       ├── __init__.py
│       ├── backfill_missing_prices.py  # Resilient Tiingo API price backfill
│       ├── config_loader.py            # Centralized config path resolver
│       ├── dataset_info.py             # A simple script to check the integrity of the final dataset.
│       ├── download_historical_prices.py # Bulk market price scraper (yfinance)
│       ├── feature_engineering.py     # PIT merge, TTM, valuation & technicals
│       ├── fetch_sec_fundamentals.py  # SEC EDGAR XBRL fundamentals parser
│       ├── generate_corporate_events.py # M&A, spin-off & bankruptcy classifier
│       ├── generate_daily_composition.py # Dynamic daily index reconstruction
│       ├── map_ticker_to_cik.py       # Ticker -> SEC CIK cross-walk resolver
│       └── retrieve_companies.py      # Wikipedia index scraper & changes parser
├── tests/                              # Complete pytest suite with mocks
│   ├── test_backfill_missing_prices.py
│   ├── test_download_historical_prices.py
│   ├── test_feature_engineering.py
│   ├── test_fetch_sec_fundamentals.py
│   ├── test_generate_corporate_events.py
│   ├── test_generate_daily_composition.py
│   ├── test_map_ticker_to_cik.py
│   └── test_retrieve_companies.py
├── .env.example                        # Environment variables template
├── docker-compose.yml                  # Container orchestration setup
├── Dockerfile                          # Hermetic multi-stage build image definition
├── main.py                             # Main execution pipeline entry point
├── pyproject.toml                      # UV / PEP 621 package requirements
└── README.md

```

---

## ► Data Dictionary & Handling Edge Cases

The final dataset (`data/datasets/daily_features/s_and_p_500_daily_features.csv` / `.parquet`) consists of over **1.6+ million rows** and **45+ features**.

> [!IMPORTANT]
> **Downstream Programmatic Handling Required (`NaN` Values)**
> Not all columns in the dataset are 100% populated with non-null values. When writing your trading strategies, backtesting scripts, or machine learning pipelines, **you MUST implement explicit conditional logic and error handling** (e.g., `if pd.notna(...)`, sector-specific feature masking, or forward-filling strategies).
> Reasons for missing data include:
> 1. **Industry-Specific Accounting (US-GAAP):** Financial Institutions & Banks (e.g., JPMorgan, Bank of America) do not report *Cost of Revenue* or *Gross Profit*. Non-tech firms rarely disclose *R&D Expenses*.
> 2. **Unreported Fields:** Certain corporations do not break out operational sub-metrics in their 10-K/10-Q SEC XBRL filings.
> 3. **Market Delistings & Complex Corporate Restructuring:** A small minority of historical companies that bankrupted, rapidly merged, or liquidated prior to modernized XBRL disclosures may lack complete financial or pricing records—even after automated backfilling through Tiingo and SEC EDGAR APIs.

### ► Manual Extensibility for Unresolved Tickers

If specific delisted or historical entities fail automated retrieval via public APIs, the pipeline logs them directly into:

* `data/missing/missing_tickers_tiingo.json` *(for missing historical market price series)*
* `data/missing/missing_sec_fundamentals.json` *(for missing SEC CIKs or financial filings)*

You can manually supply missing historical records by appending custom price rows directly to `data/datasets/historical_prices/s_and_p_500_prices.csv` or mapping custom CIKs inside `data/config/fallback_ciks.json`. The pipeline's merge and feature engineering modules will automatically ingest and process these manual overrides.

> [!NOTE]
> Check out example missing data logs:
> * Missing OHLCV data for tickers after fetching from Yahoo Finance API: [example_missing_tickers_yfinance.json](data/missing/missing_example/example_missing_tickers_yfinance.json)
> * Missing OHLCV data for remaining tickers after fetching from Tiingo API: [example_missing_tickers_tiingo.json](data/missing/missing_example/example_missing_tickers_tiingo.json)
> * Missing SEC fundamental data: [example_missing_sec_fundamentals.json](data/missing/missing_example/example_missing_sec_fundamentals.json)

---

### ► Configuration Files and Hardcoded Data

The project uses a configuration file located at `config/config.json`. You can modify the date range for the search and the paths to generated files within it.
Check it out: [config.json](config/config.json)

> [!TIP]
> After changing the project configuration, you can return to the original configuration using the `example_config.json` file.
> Check it out: [example_config.json](config/example_config.json)

The repository also utilizes [data/config/company_tickers.json](data/config/company_tickers.json) and [data/config/fallback_ciks.json](data/config/fallback_ciks.json) files—the former downloaded from SEC EDGAR, the latter artificially created and verified for historical delisted tickers.

* Source for company tickers: https://www.sec.gov/files/company_tickers.json
* Source for SEC Central Index Keys: https://www.sec.gov

> [!NOTE]
> I used Gemini 3.6 Flash and Claude Sonnet 5 to search the SEC dataset and then manually checked each entry, searching available sources.
> If you encounter any errors, please do not hesitate to contact me or create a Pull Request.

---

### ► Dataset Columns Description

#### 1. Market & Price Features (OHLCV)

| Column Name | Data Type | Description |
| --- | --- | --- |
| `Date` | `str` / `datetime64` | Trading session date (`YYYY-MM-DD`). |
| `Ticker` | `str` | Equity ticker symbol (e.g., `AAPL`, `BRK.B`). |
| `Open` | `float64` | Unadjusted opening price ($). |
| `High` | `float64` | Unadjusted intraday high price ($). |
| `Low` | `float64` | Unadjusted intraday low price ($). |
| `Close` | `float64` | Unadjusted daily closing price ($). |
| `Adj Close` | `float64` | Split and dividend-adjusted closing price ($). |
| `Volume` | `float64` | Number of shares traded during the session. |

#### 2. Corporate Actions & Split Adjustments

| Column Name | Data Type | Description |
| --- | --- | --- |
| `Stock Splits` | `float64` | Split ratio executed on the date (e.g., `4.0` for 4-for-1). |
| `Split Multiplier` | `float64` | Raw split ratio (`1.0` if no split occurred). |
| `Split Shifted` | `float64` | Multiplier shifted backwards by 1 day to handle split-day execution. |
| `Cum Split Factor` | `float64` | Cumulative product of historical split multipliers calculated backwards. |

#### 3. Point-in-Time SEC EDGAR Fundamentals (TTM Aggregated)

| Column Name | Data Type | Description |
| --- | --- | --- |
| `Filing Date` | `str` / `datetime64` | Official date the 10-K or 10-Q form was made public on SEC EDGAR. |
| `Period End` | `str` / `datetime64` | Fiscal period end date covered by the filing. |
| `Form` | `str` | SEC form identifier (`10-K` for annual, `10-Q` for quarterly). |
| `Revenue` | `float64` | Trailing Twelve Months (TTM) total revenues ($). |
| `Cost of Revenue` | `float64` | TTM cost of goods and services sold ($). |
| `Gross Profit` | `float64` | TTM gross profit ($). |
| `Operating Expenses` | `float64` | TTM total operating expenses ($). |
| `R&D Expenses` | `float64` | TTM research and development expenditures ($). |
| `SG&A Expenses` | `float64` | TTM selling, general, and administrative expenses ($). |
| `Operating Income` | `float64` | TTM operating income / EBIT ($). |
| `Net Income` | `float64` | TTM net income available to common shareholders ($). |
| `EPS (Basic)` | `float64` | TTM basic earnings per share ($). |
| `EPS (Diluted)` | `float64` | TTM diluted earnings per share ($). |
| `Total Assets` | `float64` | Carrying value of total balance sheet assets ($). |
| `Current Assets` | `float64` | Total current assets ($). |
| `Cash and Equivalents` | `float64` | Cash, cash equivalents, and short-term investments ($). |
| `Total Liabilities` | `float64` | Total balance sheet liabilities ($). |
| `Current Liabilities` | `float64` | Total current liabilities ($). |
| `Long-Term Debt` | `float64` | Non-current debt obligations ($). |
| `Stockholders Equity` | `float64` | Total shareholder equity / book value ($). |
| `Operating Cash Flow` | `float64` | TTM cash generated from operating activities ($). |
| `CapEx` | `float64` | TTM capital expenditures ($). |
| `Dividends Paid` | `float64` | TTM cash dividends paid out ($). |
| `Stock Repurchases` | `float64` | TTM payments for share buybacks ($). |
| `Shares Outstanding (Basic)` | `float64` | Weighted average basic share count. |
| `Shares Outstanding (Diluted)` | `float64` | Weighted average diluted share count. |

#### 4. Valuation Multiples & Technical Indicators

| Column Name | Data Type | Description |
| --- | --- | --- |
| `Market Cap` | `float64` | Market Capitalization (`Close * Adjusted Shares`). |
| `P/E Ratio` | `float64` | Normalized Price-to-Earnings Ratio using TTM Diluted EPS. |
| `P/B Ratio` | `float64` | Price-to-Book Ratio (`Close / Book Value Per Share`). |
| `SMA_50` | `float64` | 50-day Simple Moving Average of unadjusted close prices. |
| `SMA_200` | `float64` | 200-day Simple Moving Average of unadjusted close prices. |
| `Volatility_30D` | `float64` | 30-day rolling standard deviation of daily percent returns. |
| `RSI_14` | `float64` | 14-day Relative Strength Index oscillator (0-100). |
| `GICS Sector` | `str` | Global Industry Classification Standard sector. |
| `GICS Sub-Industry` | `str` | GICS detailed sub-industry group. |
| `CIK` | `str` | SEC Central Index Key identifier (10-digit zero-padded). |

---

## ► Running Unit & Integration Tests

The project uses `pytest` alongside `pytest-mock` to verify Point-in-Time logic, forward-fill mechanics, TTM rolling sum correctness, and rate-limit handling without firing external API calls.

Run tests locally:

```bash
uv run pytest

```

---

## ► Documentation

Detailed code-level documentation, module API specifications, and architecture workflow diagrams are built using **Sphinx**.

The documentation source files are housed under the `docs/` directory.

To build and view the HTML documentation locally:

```bash
# Generate HTML build using uv
uv run sphinx-build -b html docs docs/_build/html

```

Then open `docs/_build/html/index.html` in any web browser, or serve it locally using Python:

```bash
uv run python -m http.server --directory docs/_build/html 8000

```

---

## ► Quick Code Usage Example

Loading the dataset using **Pandas** or **Polars** to analyze historical valuation multiples with conditional filtering:

```python
import pandas as pd

# Load final parquet file
df = pd.read_parquet("data/datasets/daily_features/s_and_p_500_daily_features.parquet")

# Filter for Apple Inc. (AAPL) in 2023
aapl = df[(df["Ticker"] == "AAPL") & (df["Date"] >= "2023-01-01")]

# Example of handling potential NaNs in downstream algorithms
valid_pe_mask = aapl["P/E Ratio"].notna()
clean_aapl = aapl[valid_pe_mask]

# Display Valuation & Technical Features
print(
    clean_aapl[
        ["Date", "Close", "Market Cap", "P/E Ratio", "RSI_14", "Volatility_30D"]
    ].head()
)
```

---

## 🛡 License

Distributed under the **MIT License**. See `LICENSE` for more information.

## ► Logo Attribution
<a href="https://www.flaticon.com/free-icons/bear-market" title="bear market icons">Bear market icons created by heisenberg_jr - Flaticon</a>

<a href="https://www.flaticon.com/free-icons/bull-market" title="bull market icons">Bull market icons created by heisenberg_jr - Flaticon</a>
