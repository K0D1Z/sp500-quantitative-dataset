import pandas as pd
import json

config = json.load(open("config/config.json", "r"))
composition_path = config["paths"].get("daily_features_csv", "data/s_and_p_500_daily_features.csv")
df = pd.read_csv(composition_path)
pd.options.display.max_columns = None
pd.options.display.max_rows = None
print(df.head(10))
print("===================================================")
print(df.columns.tolist())