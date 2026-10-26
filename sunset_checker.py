from datetime import datetime
import os
from pathlib import Path
import sys
import pandas as pd
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

CORVALLIS_LAT, CORVALLIS_LON = 44.5646, -123.2620
WEST_HORIZON_LAT, WEST_HORIZON_LON = 44.6368, -123.8500
TIMEZONE = "America/Los_Angeles"

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Extended atmospheric and radiation parameters
corv_params = {
    "latitude": CORVALLIS_LAT,
    "longitude": CORVALLIS_LON,
    "hourly": (
        "cloud_cover_low,cloud_cover_mid,cloud_cover_high,"
        "relative_humidity_2m,temperature_2m,dew_point_2m,"
        "direct_normal_irradiance,diffuse_radiation,"
        "surface_pressure,wind_speed_10m,wind_direction_10m,visibility"
    ),
    "daily": "sunset",
    "timezone": TIMEZONE,
    "forecast_days": 1,
}

west_params = {
    "latitude": WEST_HORIZON_LAT,
    "longitude": WEST_HORIZON_LON,
    "hourly": "cloud_cover_low",
    "timezone": TIMEZONE,
    "forecast_days": 1,
}

try:
    # 1. Fetch Corvallis and Western horizon forecast data
    res = requests.get(FORECAST_URL, params=corv_params, timeout=15)
    res.raise_for_status()
    data = res.json()

    res_west = requests.get(FORECAST_URL, params=west_params, timeout=15)
    res_west.raise_for_status()
    data_west = res_west.json()

    sunset_iso = data["daily"]["sunset"][0]
    sunset_dt = datetime.fromisoformat(sunset_iso)
    sunset_hour = sunset_dt.hour
    prev_hour = max(0, sunset_hour - 1)
    date_str = sunset_dt.strftime("%Y-%m-%d")

    # Cloud decks
    low = data["hourly"]["cloud_cover_low"][sunset_hour]
    mid = data["hourly"]["cloud_cover_mid"][sunset_hour]
    high = data["hourly"]["cloud_cover_high"][sunset_hour]

    # Temperatures & Moisture
    temp = data["hourly"]["temperature_2m"][sunset_hour]
    dew_point = data["hourly"]["dew_point_2m"][sunset_hour]
    dew_point_depression = round(temp - dew_point, 1)
    humidity = data["hourly"]["relative_humidity_2m"][sunset_hour]

    # Solar Radiation (W/m^2)
    dni = round(data["hourly"]["direct_normal_irradiance"][sunset_hour], 1)
    diffuse = round(data["hourly"]["diffuse_radiation"][sunset_hour], 1)

    # Dynamics & Horizon
    pressure = data["hourly"]["surface_pressure"][sunset_hour]
    wind_spd = data["hourly"]["wind_speed_10m"][sunset_hour]
    wind_dir = data["hourly"]["wind_direction_10m"][sunset_hour]
    vis_km = round(data["hourly"]["visibility"][sunset_hour] / 1000, 1)

    west_low = data_west["hourly"]["cloud_cover_low"][sunset_hour]
    west_prev = data_west["hourly"]["cloud_cover_low"][prev_hour]
    west_trend = west_low - west_prev

    # 2. Refined Heuristic Score (1.0 to 5.0) incorporating DNI and moisture
    h_score = 1.0

    # Western corridor openness
    if west_low <= 65:
        if low <= 30:
            h_score += 0.8
        if west_low <= 25:
            h_score += 0.8

        # Canvas reflection (mid/high clouds)
        canvas = max(mid, high)
        if 20 <= canvas <= 80:
            h_score += 1.2

        # Solar penetration confirmation
        if dni >= 50:
            h_score += 0.5

        # Atmospheric clarity (dew point depression and visibility)
        if dew_point_depression >= 3.0 and vis_km >= 15:
            h_score += 0.4

        # Clearing horizon bonus
        if west_trend < 0:
            h_score += 0.3

    h_score = round(min(5.0, h_score), 1)

    # 3. Append to CSV
    Path("data").mkdir(exist_ok=True)
    csv_path = Path("data/sunset_history.csv")

    new_row = {
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
        "visibility_km": vis_km,
        "heuristic_score": h_score,
        "actual_score": "",
    }

    if csv_path.exists():
        df = pd.read_csv(csv_path)
        if date_str not in df["date"].astype(str).values:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(csv_path, index=False)
    else:
        pd.DataFrame([new_row]).to_csv(csv_path, index=False)

    print(f"Logged atmospheric data for {date_str}. Score: {h_score}/5.0")

    # 4. Telegram Notification
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        trend_str = "📉 Clearing" if west_trend < 0 else ("📈 Thickening" if west_trend > 0 else "➡️ Steady")
        haze_str = "⚠️ Fog/Haze Risk" if dew_point_depression < 2.0 else "✨ Clean Air"

        msg = (
            f"🌅 *Sunset Check ({date_str})*\n"
            f"Sunset: *{sunset_dt.strftime('%I:%M %p')}* | Rating: *{h_score} / 5.0*\n\n"
            f"☁️ *Clouds:* L {low}% | M {mid}% | H {high}%\n"
            f"🌄 *Coast Range:* {west_low}% ({trend_str})\n"
            f"☀️ *DNI:* {dni} W/m² | 🌫️ *Spread:* {dew_point_depression}°C ({haze_str})\n"
            f"💧 *Humidity:* {humidity}% | 👁️ *Vis:* {vis_km} km\n\n"
            f"_Score tonight's sunset (1-5):_"
        )

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "1 ☁️", "callback_data": f"rate:{date_str}:1"},
                        {"text": "2 🌫️", "callback_data": f"rate:{date_str}:2"},
                        {"text": "3 🌤️", "callback_data": f"rate:{date_str}:3"},
                        {"text": "4 🌇", "callback_data": f"rate:{date_str}:4"},
                        {"text": "5 🔥", "callback_data": f"rate:{date_str}:5"},
                    ]
                ]
            },
        }

        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=15,
        )
        print("Telegram alert sent.")

except Exception as e:
    sys.exit(f"Run failed: {e}")
