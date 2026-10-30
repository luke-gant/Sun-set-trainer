from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import requests

CORVALLIS_LAT, CORVALLIS_LON = 44.5646, -123.2620
WEST_HORIZON_LAT, WEST_HORIZON_LON = 44.6368, -123.8500
TIMEZONE = "America/Los_Angeles"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

# Set backfill window (e.g. Oct 8 to Oct 25, 2026)
start_date = datetime(2026, 10, 8)
end_date = datetime(2026, 10, 25)

start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

print(f"Fetching archive data for Corvallis from {start_str} to {end_str}...")

# 1. Corvallis local weather & solar parameters
corvallis_params = {
    "latitude": CORVALLIS_LAT,
    "longitude": CORVALLIS_LON,
    "start_date": start_str,
    "end_date": end_str,
    "hourly": [
        "cloud_cover_low",
        "cloud_cover_mid",
        "cloud_cover_high",
        "temperature_2m",
        "dew_point_2m",
        "relative_humidity_2m",
        "direct_normal_irradiance",
        "diffuse_radiation",
        "surface_pressure",
        "wind_speed_10m",
        "wind_direction_10m",
        "precipitation",
        "visibility",
    ],
    "daily": "sunset",
    "timezone": TIMEZONE,
}

# 2. West corridor parameters (Coast Range low clouds)
west_params = {
    "latitude": WEST_HORIZON_LAT,
    "longitude": WEST_HORIZON_LON,
    "start_date": start_str,
    "end_date": end_str,
    "hourly": ["cloud_cover_low"],
    "timezone": TIMEZONE,
}

res_corv = requests.get(ARCHIVE_URL, params=corvallis_params, timeout=25)
res_corv.raise_for_status()
data_corv = res_corv.json()

res_west = requests.get(ARCHIVE_URL, params=west_params, timeout=25)
res_west.raise_for_status()
data_west = res_west.json()

rows = []
daily_sunsets = data_corv["daily"]["sunset"]
time_stamps = data_corv["hourly"]["time"]
h_corv = data_corv["hourly"]
h_west = data_west["hourly"]

for day_idx, sunset_iso in enumerate(daily_sunsets):
    sunset_dt = datetime.fromisoformat(sunset_iso)
    date_str = sunset_dt.strftime("%Y-%m-%d")
    sunset_hour = sunset_dt.hour

    matching_timestamp = f"{date_str}T{sunset_hour:02d}:00"
    try:
        hour_idx = time_stamps.index(matching_timestamp)
    except ValueError:
        hour_idx = day_idx * 24 + sunset_hour

    # Local Cloud Metrics
    low = int(h_corv["cloud_cover_low"][hour_idx] or 0)
    mid = int(h_corv["cloud_cover_mid"][hour_idx] or 0)
    high = int(h_corv["cloud_cover_high"][hour_idx] or 0)
