import os
import requests
import pandas as pd
from datetime import datetime

POINTS = {
    "eugene_valley": {"lat": 44.0521, "lon": -123.0868},
    "eugene_coast_gap": {"lat": 44.0000, "lon": -123.9500}
}

URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_VARS = [
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "relative_humidity_2m",
    "visibility",
    "precipitation"
]

CSV_FILE = "eugene_sunset_history.csv"
today_str = datetime.now().strftime("%Y-%m-%d")

extracted_features = {"date": today_str}

for point_name, coords in POINTS.items():
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "hourly": ",".join(HOURLY_VARS),
        "daily": "sunset",
        "timezone": "America/Los_Angeles",
        "forecast_days": 1
    }
    
    res = requests.get(URL, params=params).json()
    sunset_dt = pd.to_datetime(res["daily"]["sunset"][0])
    extracted_features["sunset_time"] = sunset_dt.strftime("%H:%M")
    
    df_hourly = pd.DataFrame(res["hourly"])
    df_hourly["time"] = pd.to_datetime(df_hourly["time"])
    
    # Pick the hour directly preceding sunset
    idx = (df_hourly["time"] - sunset_dt).abs().idxmin()
    closest_hour_data = df_hourly.iloc[idx]
    
    for var in HOURLY_VARS:
        extracted_features[f"{point_name}_{var}"] = closest_hour_data[var]

# Initialize empty manual score column
extracted_features["score_1_to_10"] = ""

new_df = pd.DataFrame([extracted_features])

# Append to existing history or create new file
if os.path.exists(CSV_FILE):
    existing_df = pd.read_csv(CSV_FILE)
    if today_str not in existing_df["date"].astype(str).values:
        updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        updated_df.to_csv(CSV_FILE, index=False)
        print(f"Appended entry for {today_str}.")
    else:
        print(f"Entry for {today_str} already recorded. Skipping.")
else:
    new_df.to_csv(CSV_FILE, index=False)
    print(f"Created {CSV_FILE} with initial entry for {today_str}.")
