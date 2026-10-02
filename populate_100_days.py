import os
import requests
import pandas as pd

CSV_PATH = "eugene_sunset_last_100_days.csv"

if not os.path.exists(CSV_PATH):
    raise FileNotFoundError(f"Could not find {CSV_PATH} in root directory.")

df = pd.read_csv(CSV_PATH)

start_date = df["date"].min()
end_date = df["date"].max()

points = {
    "eugene": {"lat": 44.0521, "lon": -123.0868, "prefix": "eugene_"},
    "coast_gap": {"lat": 44.0000, "lon": -123.9500, "prefix": "coast_gap_"}
}

vars_map = {
    "cloud_cover": "cloud_cover_pct",
    "cloud_cover_low": "cloud_low_pct",
    "cloud_cover_mid": "cloud_mid_pct",
    "cloud_cover_high": "cloud_high_pct",
    "relative_humidity_2m": "humidity_pct",
    "visibility": "visibility_m",
    "precipitation": "precipitation_mm"
}

archive_url = "https://archive-api.open-meteo.com/v1/archive"

for key, p in points.items():
    print(f"Fetching historical data for {key}...")
    params = {
        "latitude": p["lat"],
        "longitude": p["lon"],
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(vars_map.keys()),
        "timezone": "America/Los_Angeles"
    }
    
    response = requests.get(archive_url, params=params)
    response.raise_for_status()
    data = response.json()

    hourly = pd.DataFrame(data["hourly"])
    hourly["time"] = pd.to_datetime(hourly["time"])

    for idx, row in df.iterrows():
        sunset_dt = pd.to_datetime(f"{row['date']} {row['sunset_time_pdt']}")
        closest_idx = (hourly["time"] - sunset_dt).abs().idxmin()
        weather = hourly.iloc[closest_idx]

        for api_var, col_suffix in vars_map.items():
            df.at[idx, f"{p['prefix']}{col_suffix}"] = weather[api_var]

df.to_csv(CSV_PATH, index=False)
print(f"Successfully populated weather data across {len(df)} days.")
