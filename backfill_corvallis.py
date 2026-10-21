from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import requests

# Exact coordinates
CORVALLIS_LAT, CORVALLIS_LON = 44.5646, -123.2620
WEST_HORIZON_LAT, WEST_HORIZON_LON = 44.6368, -123.8500
TIMEZONE = "America/Los_Angeles"

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Set window for the past 13 days
end_date = datetime.now() - timedelta(days=1)
start_date = end_date - timedelta(days=12)

start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

print(f"Fetching archive data for Corvallis from {start_str} to {end_str}...")

# 1. Fetch Corvallis local metrics
corvallis_params = {
    "latitude": CORVALLIS_LAT,
    "longitude": CORVALLIS_LON,
    "start_date": start_str,
    "end_date": end_str,
    "hourly": "cloud_cover_low,cloud_cover_mid,cloud_cover_high,relative_humidity_2m,precipitation_probability,visibility",
    "daily": "sunset",
    "timezone": TIMEZONE,
}

# 2. Fetch Coast Range / Toledo corridor metrics
west_params = {
    "latitude": WEST_HORIZON_LAT,
    "longitude": WEST_HORIZON_LON,
    "start_date": start_str,
    "end_date": end_str,
    "hourly": "cloud_cover_low",
    "timezone": TIMEZONE,
}

res_corv = requests.get(ARCHIVE_URL, params=corvallis_params, timeout=20)
res_corv.raise_for_status()
data_corv = res_corv.json()

res_west = requests.get(ARCHIVE_URL, params=west_params, timeout=20)
res_west.raise_for_status()
data_west = res_west.json()

rows = []
daily_sunsets = data_corv["daily"]["sunset"]
time_stamps = data_corv["hourly"]["time"]

for day_idx, sunset_iso in enumerate(daily_sunsets):
    sunset_dt = datetime.fromisoformat(sunset_iso)
    date_str = sunset_dt.strftime("%Y-%m-%d")
    sunset_hour = sunset_dt.hour

    # Match hour index in the hourly array
    matching_timestamp = f"{date_str}T{sunset_hour:02d}:00"
    try:
        hour_idx = time_stamps.index(matching_timestamp)
    except ValueError:
        hour_idx = day_idx * 24 + sunset_hour

    low = data_corv["hourly"]["cloud_cover_low"][hour_idx]
    mid = data_corv["hourly"]["cloud_cover_mid"][hour_idx]
    high = data_corv["hourly"]["cloud_cover_high"][hour_idx]
    humidity = data_corv["hourly"]["relative_humidity_2m"][hour_idx]

    precip_raw = data_corv["hourly"].get("precipitation_probability")
    precip_prob = (
        precip_raw[hour_idx]
        if precip_raw and precip_raw[hour_idx] is not None
        else 0
    )

    vis_raw = data_corv["hourly"]["visibility"][hour_idx]
    visibility_km = round(vis_raw / 1000, 1) if vis_raw is not None else 15.0

    west_low = data_west["hourly"]["cloud_cover_low"][hour_idx]

    # Baseline heuristic score
    quality_score = 0
    if precip_prob <= 40 and west_low <= 65:
        if low <= 35:
            quality_score += 30
        if west_low <= 30:
            quality_score += 20
        canvas = max(mid, high)
        if 20 <= canvas <= 80:
            quality_score += 30
        if humidity <= 75 and visibility_km >= 12:
            quality_score += 20
        quality_score = max(0, min(quality_score, 100))

    rows.append({
        "date": date_str,
        "sunset_hour": sunset_hour,
        "low_clouds": low,
        "mid_clouds": mid,
        "high_clouds": high,
        "west_low_clouds": west_low,
        "humidity": humidity,
        "precip_prob": precip_prob,
        "visibility_km": visibility_km,
        "heuristic_score": quality_score,
        "actual_label": "",  # Fill this in using your camera footage!
    })

Path("data").mkdir(exist_ok=True)
csv_path = Path("data/sunset_history.csv")

new_df = pd.DataFrame(rows)

if csv_path.exists():
    existing_df = pd.read_csv(csv_path)
    combined = (
        pd.concat([existing_df, new_df])
        .drop_duplicates(subset=["date"], keep="first")
        .sort_values(by="date")
    )
    combined.to_csv(csv_path, index=False)
else:
    new_df.to_csv(csv_path, index=False)

print(
    f"Successfully backfilled {len(rows)} days for Corvallis into data/sunset_history.csv!"
)
