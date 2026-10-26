from pathlib import Path
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

# Map existing manual scores so no labeling work is lost
score_lookup = dict(
    zip(existing_df["date"].astype(str), existing_df["actual_score"])
)

start_date = str(existing_df["date"].min())
end_date = str(existing_df["date"].max())

print(f"Re-fetching enhanced metrics for {start_date} to {end_date}...")

# 1. Fetch Corvallis local metrics
corv_params = {
    "latitude": CORVALLIS_LAT,
    "longitude": CORVALLIS_LON,
    "start_date": start_date,
    "end_date": end_date,
    "hourly": "cloud_cover_low,cloud_cover_mid,cloud_cover_high,cloud_base_height,relative_humidity_2m,precipitation,visibility,surface_pressure,wind_speed_10m",
    "daily": "sunset",
    "timezone": TIMEZONE,
}

# 2. Fetch Coast Range corridor metrics
west_params = {
    "latitude": WEST_HORIZON_LAT,
    "longitude": WEST_HORIZON_LON,
    "start_date": start_date,
    "end_date": end_date,
    "hourly": "cloud_cover_low",
    "timezone": TIMEZONE,
}

res_corv = requests.get(ARCHIVE_URL, params=corv_params, timeout=20)
res_corv.raise_for_status()
data_corv = res_corv.json()

res_west = requests.get(ARCHIVE_URL, params=west_params, timeout=20)
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

    low = data_corv["hourly"]["cloud_cover_low"][h_idx]
    mid = data_corv["hourly"]["cloud_cover_mid"][h_idx]
    high = data_corv["hourly"]["cloud_cover_high"][h_idx]

    # Cloud base height (defaults to 10,000m if sky is clear)
    cbh_raw = data_corv["hourly"].get("cloud_base_height")
    cloud_base_m = (
        cbh_raw[h_idx] if cbh_raw and cbh_raw[h_idx] is not None else 10000
    )

    humidity = data_corv["hourly"]["relative_humidity_2m"][h_idx]
    pressure = data_corv["hourly"]["surface_pressure"][h_idx]
    wind = data_corv["hourly"]["wind_speed_10m"][h_idx]

    vis_raw = data_corv["hourly"]["visibility"][h_idx]
    vis_km = round(vis_raw / 1000, 1) if vis_raw is not None else 15.0

    west_low = data_west["hourly"]["cloud_cover_low"][h_idx]
    west_low_prev = data_west["hourly"]["cloud_cover_low"][h_prev_idx]

    # Horizon Clearing Trend: negative means horizon is clearing up right before sunset
    west_trend = west_low - west_low_prev

    # Calculate unified 1.0 - 5.0 heuristic score
    h_score = 1.0
    if west_low <= 65:
        if low <= 35:
            h_score += 1.0
        if west_low <= 30:
            h_score += 0.8
        canvas = max(mid, high)
        if 20 <= canvas <= 80:
            h_score += 1.2
        if humidity <= 75 and vis_km >= 12:
            h_score += 0.5
        if west_trend < 0:
            h_score += 0.5  # Clearing horizon bonus
    h_score = round(min(5.0, h_score), 1)

    rows.append({
        "date": date_str,
        "sunset_hour": sunset_hour,
        "low_clouds": low,
        "mid_clouds": mid,
        "high_clouds": high,
        "cloud_base_m": cloud_base_m,
        "west_low_clouds": west_low,
        "west_trend": west_trend,
        "humidity": humidity,
        "surface_pressure_hpa": pressure,
        "wind_speed_kmh": wind,
        "visibility_km": vis_km,
        "heuristic_score": h_score,
        "actual_score": score_lookup.get(date_str, ""),
    })

new_df = pd.DataFrame(rows)
new_df.to_csv(csv_path, index=False)
print("Updated data/sunset_history.csv with enhanced atmospheric metrics!")
