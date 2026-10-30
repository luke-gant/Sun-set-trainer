from pathlib import Path
import numpy as np
import pandas as pd
import requests

CORVALLIS_LAT, CORVALLIS_LON = 44.5646, -123.2620
WEST_HORIZON_LAT, WEST_HORIZON_LON = 44.6368, -123.8500
TIMEZONE = "America/Los_Angeles"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

csv_path = Path("data/sunset_history.csv")
if not csv_path.exists():
    raise FileNotFoundError("data/sunset_history.csv not found!")

existing_df = pd.read_csv(csv_path)

# Retain all manual scores you already recorded (ignoring NaN)
score_lookup = {}
if "actual_score" in existing_df.columns:
    valid_scores = existing_df.dropna(subset=["actual_score"])
    score_lookup = dict(
        zip(valid_scores["date"].astype(str), valid_scores["actual_score"])
    )

start_date = str(existing_df["date"].min())
end_date = str(existing_df["date"].max())

print(f"Re-fetching enhanced archive metrics for {start_date} to {end_date}...")

# 1. Fetch Corvallis archive (NOW INCLUDES VISIBILITY)
corv_params = {
    "latitude": CORVALLIS_LAT,
    "longitude": CORVALLIS_LON,
    "start_date": start_date,
    "end_date": end_date,
    "hourly": (
        "cloud_cover_low,cloud_cover_mid,cloud_cover_high,"
        "temperature_2m,dew_point_2m,relative_humidity_2m,"
        "direct_normal_irradiance,diffuse_radiation,"
        "surface_pressure,wind_speed_10m,wind_direction_10m,"
        "precipitation,visibility"
    ),
    "daily": "sunset",
    "timezone": TIMEZONE,
}

west_params = {
    "latitude": WEST_HORIZON_LAT,
    "longitude": WEST_HORIZON_LON,
    "start_date": start_date,
    "end_date": end_date,
    "hourly": "cloud_cover_low",
    "timezone": TIMEZONE,
}

res_corv = requests.get(ARCHIVE_URL, params=corv_params, timeout=25)
res_corv.raise_for_status()
data_corv = res_corv.json()

res_west = requests.get(ARCHIVE_URL, params=west_params, timeout=25)
res_west.raise_for_status()
data_west = res_west.json()

times = data_corv["hourly"]["time"]
sunsets = data_corv["daily"]["sunset"]

rows = []
for day_idx, s_iso in enumerate(sunsets):
    date_str = s_iso.split("T")[0]
    sunset_hour = int(s_iso.split("T")[1].split(":")[0])

    t_str = f"{date_str}T{sunset_hour:02d}:00"
    t_prev_str = f"{date_str}T{(sunset_hour - 1):02d}:00"

    h_idx = (
        times.index(t_str) if t_str in times else (day_idx * 24 + sunset_hour)
    )
    h_prev_idx = (
        times.index(t_prev_str)
        if t_prev_str in times
        else max(0, h_idx - 1)
    )

    # Cloud cover
    low = int(data_corv["hourly"]["cloud_cover_low"][h_idx] or 0)
    mid = int(data_corv["hourly"]["cloud_cover_mid"][h_idx] or 0)
    high = int(data_corv["hourly"]["cloud_cover_high"][h_idx] or 0)

    # Moisture and Temperature
    temp = round(float(data_corv["hourly"]["temperature_2m"][h_idx] or 0.0), 1)
    dew_point = round(float(data_corv["hourly"]["dew_point_2m"][h_idx] or 0.0), 1)
    dew_point_depression = round(temp - dew_point, 1)
    humidity = int(data_corv["hourly"]["relative_humidity_2m"][h_idx] or 0)

    # Handle potentially null/lagged recent precipitation
    raw_precip = data_corv["hourly"]["precipitation"][h_idx]
    precip = round(float(raw_precip), 1) if raw_precip is not None else 0.0

    # Solar Radiation (W/m^2)
    dni = round(float(data_corv["hourly"]["direct_normal_irradiance"][h_idx] or 0.0), 1)
    diffuse = round(float(data_corv["hourly"]["diffuse_radiation"][h_idx] or 0.0), 1)

    # Dynamics
    pressure = round(float(data_corv["hourly"]["surface_pressure"][h_idx] or 0.0), 1)
    wind_spd = round(float(data_corv["hourly"]["wind_speed_10m"][h_idx] or 0.0), 1)
    wind_dir = int(data_corv["hourly"]["wind_direction_10m"][h_idx] or 0)

    # Western corridor
    west_low = int(data_west["hourly"]["cloud_cover_low"][h_idx] or 0)
    west_low_prev = int(data_west["hourly"]["cloud_cover_low"][h_prev_idx] or 0)
    west_trend = west_low - west_low_prev

    # Visibility (convert meters to km)
    raw_vis = data_corv["hourly"]["visibility"][h_idx]
    visibility_km = (
        round(float(raw_vis) / 1000.0, 1) if raw_vis is not None else 15.0
    )

    # Heuristic scoring (1.0 to 5.0 scale)
    h_score = 1.0
    if west_low <= 65 and precip <= 0.1:
        if low <= 30:
            h_score += 0.8
        if west_low <= 25:
            h_score += 0.8
        canvas = max(mid, high)
        if 20 <= canvas <= 80:
            h_score += 1.2
        if dni >= 50:
            h_score += 0.5
        if dew_point_depression >= 3.0:
            h_score += 0.4
        if west_trend < 0:
            h_score += 0.3
    h_score = round(min(5.0, h_score), 1)

    # Preserve recorded manual score, otherwise leave empty string
    actual_val = score_lookup.get(date_str, "")
    if pd.isna(actual_val):
        actual_val = ""

    rows.append({
        "date": date_str,
        "sunset_hour": sunset_hour,
        "low_clouds": low,
        "mid_clouds": mid,
        "high_clouds": high,
        "west_low_clouds": west_low,
        "west_trend": west_trend,
        "temp_c": temp,
        "dew_point_c": dew_point,
        "dew_point_depression_c": dew_point_depression,
        "humidity": humidity,
        "dni_wm2": dni,
        "diffuse_rad_wm2": diffuse,
        "surface_pressure_hpa": pressure,
        "wind_speed_kmh": wind_spd,
        "wind_dir_deg": wind_dir,
        "precipitation_mm": precip,
        "heuristic_score": h_score,
        "actual_score": actual_val,
        "visibility_km": visibility_km,
    })

new_df = pd.DataFrame(rows)
new_df.to_csv(csv_path, index=False)
print(f"Successfully upgraded {len(rows)} historical days with full radiation, moisture, and visibility data!")
