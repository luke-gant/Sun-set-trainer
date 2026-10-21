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

url = "https://api.open-meteo.com/v1/forecast"

corvallis_params = {
    "latitude": CORVALLIS_LAT,
    "longitude": CORVALLIS_LON,
    "hourly": "cloud_cover_low,cloud_cover_mid,cloud_cover_high,relative_humidity_2m,precipitation_probability,visibility",
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
    res = requests.get(url, params=corvallis_params, timeout=15)
    res.raise_for_status()
    data = res.json()

    res_west = requests.get(url, params=west_params, timeout=15)
    res_west.raise_for_status()
    data_west = res_west.json()

    sunset_iso = data["daily"]["sunset"][0]
    sunset_dt = datetime.fromisoformat(sunset_iso)
    sunset_hour = sunset_dt.hour
    date_str = sunset_dt.strftime("%Y-%m-%d")

    low_clouds = data["hourly"]["cloud_cover_low"][sunset_hour]
    mid_clouds = data["hourly"]["cloud_cover_mid"][sunset_hour]
    high_clouds = data["hourly"]["cloud_cover_high"][sunset_hour]
    humidity = data["hourly"]["relative_humidity_2m"][sunset_hour]
    precip_prob = data["hourly"]["precipitation_probability"][sunset_hour]
    visibility_km = round(data["hourly"]["visibility"][sunset_hour] / 1000, 1)
    west_low_clouds = data_west["hourly"]["cloud_cover_low"][sunset_hour]

    # Heuristic scoring
    quality_score = 0
    if precip_prob <= 40 and west_low_clouds <= 65:
        if low_clouds <= 35:
            quality_score += 30
        if west_low_clouds <= 30:
            quality_score += 20
        upper_canvas = max(mid_clouds, high_clouds)
        if 20 <= upper_canvas <= 80:
            quality_score += 30
        if humidity <= 75 and visibility_km >= 12:
            quality_score += 20
        quality_score = max(0, min(quality_score, 100))

    # Append row to CSV
    Path("data").mkdir(exist_ok=True)
    csv_path = Path("data/sunset_history.csv")

    new_row = {
        "date": date_str,
        "sunset_hour": sunset_hour,
        "low_clouds": low_clouds,
        "mid_clouds": mid_clouds,
        "high_clouds": high_clouds,
        "west_low_clouds": west_low_clouds,
        "humidity": humidity,
        "precip_prob": precip_prob,
        "visibility_km": visibility_km,
        "heuristic_score": quality_score,
        "actual_label": "",
    }

    if csv_path.exists():
        df = pd.read_csv(csv_path)
        if date_str not in df["date"].astype(str).values:
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(csv_path, index=False)
    else:
        pd.DataFrame([new_row]).to_csv(csv_path, index=False)

    print(f"Logged atmospheric data for {date_str}. Score: {quality_score}/100")

    # Lowered alert threshold to 35
    if quality_score >= 35:
        message = (
            f"🌅 *Sunset Check ({date_str})*\n"
            f"Sunset Time: *{sunset_dt.strftime('%I:%M %p')}*\n"
            f"Score: *{quality_score}/100*\n\n"
            f"☁️ *Clouds:* L {low_clouds}% | M {mid_clouds}% | H {high_clouds}%\n"
            f"🌄 *West Corridor:* {west_low_clouds}% | 💧 {humidity}%\n\n"
            f"_Was tonight's sunset worth seeing?_"
        )

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown",
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {
                            "text": "🔥 Epic (1)",
                            "callback_data": f"label:{date_str}:1",
                        },
                        {
                            "text": "☁️ Dull / Flat (0)",
                            "callback_data": f"label:{date_str}:0",
                        },
                    ]
                ]
            },
        }

        t_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(t_url, json=payload, timeout=15)
        print("Telegram notification dispatched.")

except Exception as e:
    sys.exit(f"Run failed: {e}")
