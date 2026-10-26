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

# Retain all manual scores you already recorded
score_lookup = dict(
    zip(existing_df["date"].astype(str), existing_df["actual_score"])
)

start_date = str(existing_df["date"].min())
end_date = str(existing_df["date"].max())

print(f"Re-fetching enhanced archive metrics for {start_date} to {end_date}...")

# Archive API supported variables (including radiation and dew point)
corv_params = {
    "latitude": CORVALLIS_LAT,
    "longitude": CORVALLIS_LON,
    "start_date": start_date,
    "end_date": end_date,
    "hourly": (
        "cloud_cover_low,cloud_cover_mid,cloud_cover_high,"
        "temperature_2m,dew_point_2m,relative_humidity_2m,"
        "direct_normal_irradiance,diffuse_radiation,"
        "surface_pressure,wind_speed_10m,wind_direction_10m,precipitation"
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

# 1. Fetch Corvallis archive
res_corv = requests.get(ARCHIVE_URL, params=corv_params, timeout=20)
res_corv.raise_for_status()
data_corv = res_corv.json()

# 2. Fetch Coast Range archive
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

    # Cloud cover
    low = data_corv["hourly"]["cloud_cover_low"][h_idx]
    mid = data_corv["hourly"]["cloud_cover_mid"][h_idx]
    high = data_corv["hourly"]["cloud_cover_high"][h_idx]

    # Moisture and Temperature
    temp = data_corv["hourly"]["temperature_2m"][h_idx]
    dew_point = data_corv["hourly"]["dew_point_2m"][h_idx]
    dew_point_depression = round(temp - dew_point, 1)
    humidity = data_corv["hourly"]["relative_humidity_2m"][h_idx]
    precip = data_corv["hourly"]["precipitation"][h_idx]

    # Solar Radiation (W/m^2)
    dni = round(data_corv["hourly"]["direct_normal_irradiance"][h_idx], 1)
    diffuse = round(data_corv["hourly"]["diffuse_radiation"][h_idx], 1)

    # Dynamics
    pressure = data_corv["hourly"]["surface_pressure"][h_idx]
    wind_spd = data_corv["hourly"]["wind_speed_10m"][h_idx]
    wind_dir = data_corv["hourly"]["wind_direction_10m"][h_idx]

    # Western corridor
    west_low = data_west["hourly"]["cloud_cover_low"][h_idx]
    west_low_prev = data_west["hourly"]["cloud_cover_low"][h_prev_idx]
    west_trend = west_low - west_low_prev

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
        "actual_score": score_lookup.get(date_str, ""),
    })

new_df = pd.DataFrame(rows)
new_df.to_csv(csv_path, index=False)
print(f"Successfully upgraded {len(rows)} historical days with full radiation & moisture data!")
