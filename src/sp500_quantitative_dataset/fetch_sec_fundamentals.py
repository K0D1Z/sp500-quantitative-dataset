"""
This module fetches fundamental financial data (Income Statement, Balance Sheet,
Cash Flow items) from the SEC EDGAR API for all unique CIKs in the S&P 500 universe,
and exports the processed dataset to both CSV and Parquet formats for Kaggle.
"""

import os
import json
import time
import requests
import pandas as pd

# Load configuration from config.json
with open("config/config.json", "r") as file:
    config = json.load(file)


def get_sec_headers() -> dict:
    """
    Generates required headers for SEC EDGAR API requests.
    SEC requires a custom User-Agent containing user name and email.
    """
    return {
        "User-Agent": "Student student@agh.edu.pl",
        "Accept-Encoding": "gzip, deflate",
        "Host": "data.sec.gov",
    }


def fetch_company_facts(cik: str) -> dict:
    """
    Fetches raw XBRL company facts JSON from the SEC EDGAR API for a given CIK.

    Args:
        cik (str): The company's CIK identifier.

    Returns:
        dict: The JSON response containing financial facts, or an empty dict on failure.
    """
    # SEC expects a 10-digit zero-padded CIK string
    padded_cik = str(cik).zfill(10)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{padded_cik}.json"

    headers = get_sec_headers()
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(
            f"Failed to fetch SEC data for CIK {padded_cik}. Status code: {response.status_code}"
        )
        return {}


def extract_metric_dataframe(
    facts_data: dict, tag_name: str, metric_label: str
) -> pd.DataFrame:
    """
    Extracts a specific US-GAAP financial metric time-series from raw SEC facts data.
    Now supports multiple reporting units: USD, shares, and USD/shares.
    """
    try:
        us_gaap = facts_data.get("facts", {}).get("us-gaap", {})
        tag_data = us_gaap.get(tag_name, {})
        units = tag_data.get("units", {})

        # Determine the correct unit type for the metric
        target_data = []
        if "USD" in units:
            target_data = units["USD"]
        elif "shares" in units:
            target_data = units["shares"]
        elif "USD/shares" in units:
            target_data = units["USD/shares"]

        if not target_data:
            return pd.DataFrame()

        records = []
        for item in target_data:
            form = item.get("form", "")
            if form in ["10-Q", "10-K"]:
                records.append(
                    {
                        "Filing Date": item.get("filed"),
                        "Period End": item.get("end"),
                        "Form": form,
                        metric_label: item.get("val"),
                    }
                )

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = df.dropna(subset=["Filing Date", "Period End"])
        df = df.sort_values(by="Filing Date").drop_duplicates(
            subset=["Period End", "Form"], keep="last"
        )

        return df
    except Exception as e:
        print(f"Error extracting metric {tag_name}: {e}")
        return pd.DataFrame()


def process_company_fundamentals(cik: str, ticker: str) -> pd.DataFrame:
    """
    Aggregates a massive set of key fundamental metrics for a single company into a unified panel.
    Uses a robust fallback system (aliases) for US-GAAP tags to handle reporting variations.
    """
    facts = fetch_company_facts(cik)
    if not facts:
        return pd.DataFrame()

    # THE MEGA DICTIONARY
    metrics_mapping = {
        # --- INCOME STATEMENT (Profitability & Growth) ---
        "Revenue": [
            "Revenues",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
        ],
        "Cost of Revenue": [
            "CostOfGoodsAndServicesSold",
            "CostOfRevenue",
            "CostOfGoodsSold",
        ],
        "Gross Profit": ["GrossProfit"],
        "Operating Expenses": ["OperatingExpenses"],
        "R&D Expenses": [
            "ResearchAndDevelopmentExpense",
            "ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost",
        ],
        "SG&A Expenses": ["SellingGeneralAndAdministrativeExpense"],
        "Operating Income": ["OperatingIncomeLoss"],
        "Net Income": [
            "NetIncomeLoss",
            "ProfitLoss",
            "NetIncomeLossAvailableToCommonStockholdersBasic",
        ],
        "EPS (Basic)": ["EarningsPerShareBasic"],
        "EPS (Diluted)": ["EarningsPerShareDiluted"],
        # --- BALANCE SHEET (Liquidity & Solvency) ---
        "Total Assets": ["Assets"],
        "Current Assets": ["AssetsCurrent"],
        "Cash and Equivalents": [
            "CashAndCashEquivalentsAtCarryingValue",
            "CashAndCashEquivalentsFairValueDisclosure",
        ],
        "Total Liabilities": ["Liabilities"],
        "Current Liabilities": ["LiabilitiesCurrent"],
        "Long-Term Debt": [
            "LongTermDebtNoncurrent",
            "LongTermDebt",
            "LongTermDebtAndCapitalLeaseObligations",
        ],
        "Stockholders Equity": [
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ],
        # --- CASH FLOW (Cash Generation & Return to Shareholders) ---
        "Operating Cash Flow": [
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
            "OperatingCashFlow",
        ],
        "CapEx": [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsToAcquireProductiveAssets",
        ],
        "Dividends Paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
        "Stock Repurchases": [
            "PaymentsForRepurchaseOfCommonStock",
            "PaymentsForRepurchaseOfEquity",
        ],
        # --- SHARE COUNTS (Valuation Multiples Baseline) ---
        "Shares Outstanding (Basic)": [
            "WeightedAverageNumberOfSharesOutstandingBasic",
            "CommonStockSharesOutstanding",
            "EntityCommonStockSharesOutstanding",
        ],
        "Shares Outstanding (Diluted)": [
            "WeightedAverageNumberOfDilutedSharesOutstanding"
        ],
    }

    dfs = []
    for label, tags in metrics_mapping.items():
        metric_df = pd.DataFrame()
        for tag in tags:
            metric_df = extract_metric_dataframe(facts, tag, label)
            if not metric_df.empty:
                break

        if not metric_df.empty:
            dfs.append(metric_df)

    if not dfs:
        return pd.DataFrame()

    base_df = dfs[0]
    for next_df in dfs[1:]:
        base_df = pd.merge(
            base_df, next_df, on=["Filing Date", "Period End", "Form"], how="outer"
        )

    base_df["CIK"] = str(cik).zfill(10)
    base_df["Ticker"] = ticker

    return base_df


def generate_fundamentals_dataset() -> None:
    """
    Orchestrates the bulk download and merging of fundamental data for all
    unique companies present in the S&P 500 daily composition dataset.
    Saves outputs in both CSV and Parquet formats.
    """
    composition_path = config["paths"].get(
        "daily_composition_csv", "data/s_and_p_500_daily_composition.csv"
    )
    csv_output_path = config["paths"].get(
        "fundamentals_csv", "data/s_and_p_500_fundamentals.csv"
    )
    parquet_output_path = config["paths"].get(
        "fundamentals_parquet", "data/s_and_p_500_fundamentals.parquet"
    )
    failed_sec_path = config["paths"].get(
        "failed_sec_log", "data/failed_sec_fundamentals.json"
    )

    if not os.path.exists(composition_path):
        print(
            f"Composition file not found at {composition_path}. Run daily composition script first."
        )
        return

    df_comp = pd.read_csv(composition_path)
    unique_entities = df_comp[["Ticker", "CIK"]].dropna().drop_duplicates().values

    print(
        f"Starting fundamentals extraction for {len(unique_entities)} unique entities from SEC EDGAR..."
    )

    all_fundamentals = []
    failed_sec_logs = []

    for ticker, cik in unique_entities:
        print(f"Fetching fundamentals for {ticker} (CIK: {cik})...")
        company_df = process_company_fundamentals(cik, ticker)

        if company_df.empty:
            failed_sec_logs.append(
                {
                    "Ticker": ticker,
                    "CIK": str(cik).zfill(10),
                    "Reason": "SEC returned 404 or lacked USD XBRL tags",
                }
            )
        else:
            all_fundamentals.append(company_df)

        time.sleep(0.2)

    if failed_sec_logs:
        if failed_sec_path and os.path.dirname(failed_sec_path):
            os.makedirs(os.path.dirname(failed_sec_path), exist_ok=True)
        with open(failed_sec_path, "w") as f:
            json.dump(failed_sec_logs, f, indent=4)
        print(f"-> Failed SEC fetches logged to {failed_sec_path}")

    if not all_fundamentals:
        print("No fundamental data was successfully retrieved.")
        return

    master_df = pd.concat(all_fundamentals, ignore_index=True)
    master_df = master_df.sort_values(by=["Ticker", "Filing Date"]).reset_index(
        drop=True
    )

    if csv_output_path and os.path.dirname(csv_output_path):
        os.makedirs(os.path.dirname(csv_output_path), exist_ok=True)
    master_df.to_csv(csv_output_path, index=False)
    print(f"-> Fundamentals successfully saved to CSV: {csv_output_path}")

    if parquet_output_path and os.path.dirname(parquet_output_path):
        os.makedirs(os.path.dirname(parquet_output_path), exist_ok=True)
    master_df.to_parquet(parquet_output_path, index=False)
    print(f"-> Fundamentals successfully saved to Parquet: {parquet_output_path}")


if __name__ == "__main__":
    generate_fundamentals_dataset()
