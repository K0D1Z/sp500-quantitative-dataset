"""
A simple script to check the statistics of the resulting csv file.
"""

import pandas as pd
import json

config = json.load(open("config/config.json", "r"))
composition_path = config["paths"].get(
    "daily_features_csv", "data/s_and_p_500_daily_features.csv"
)
df = pd.read_csv(composition_path)
pd.options.display.max_columns = None
pd.options.display.max_rows = None

n_rows = 10
_width = 150
print(f" COLUMNS ".center(_width, "="))
print(df.columns.tolist())
print(f" FIRST {n_rows} ROWS ".center(_width, "="))
print(df.head(n_rows))
print(f"INFO".center(_width, "="))
print(df.info())
print(f"DESCRIPTION".center(_width, "="))
print(df.describe())
