```markdown
# 🌅 Corvallis Sunset Quality Predictor & Tracker

An automated end-to-end atmospheric data pipeline and predictive modeling engine designed to forecast and log sunset quality in Corvallis, Oregon.

The system combines local microclimate thermodynamics, high-resolution solar radiation, and directional Coast Range cloud deck vectors into an automated daily notification workflow, recording empirical features alongside ground-truth observer ratings.

---

## 🧭 Project Architecture


```

```
                   ┌───────────────────────────────┐
                   │  Open-Meteo Weather APIs       │
                   │  (Forecast & Historical ERA5) │
                   └──────────────┬────────────────┘
                                  │
             ┌────────────────────┴────────────────────┐
             ▼                                         ▼

```

[ Corvallis Local Station ]               [ Coast Range Corridor ]

* Low / Mid / High Clouds                 - Toledo/Cascade Ridge Low Clouds
* DNI & Diffuse Radiation                 - 1-Hour Cloud Density Delta
* Dew Point Depression / Spread           - Western Window Geometry
│                                         │
└────────────────────┬────────────────────┘
▼
┌───────────────────────────┐
│    Feature Pipeline       │
│    (20-Metric Schema)     │
└─────────────┬─────────────┘
│
┌───────────────┴───────────────┐
▼                               ▼
[ GitHub Actions Cron ]             [ Telegram Bot Service ]
* Daily auto-ingest                 - Live pre-sunset forecast
* Rebase & commit sync              - 1–5 Inline rating callbacks
* Appends to dataset                - Observer ground-truth capture
│                               │
└───────────────┬───────────────┘
▼
┌───────────────────────────┐
│ data/sunset_history.csv   │
│ (Primary Training Set)    │
└─────────────┬─────────────┘
▼
┌───────────────────────────┐
│  Neural Network Trainer   │
│  (Heuristic vs. Ground)   │
└───────────────────────────┘



```

---

## 📊 Feature Dataset Schema (`data/sunset_history.csv`)

Each daily observation logs 20 atmospheric, optical, and heuristic metrics sampled at the local sunset hour:

| Column | Type | Unit / Range | Description |
| :--- | :--- | :--- | :--- |
| `date` | `string` | `YYYY-MM-DD` | Date of observation (primary key). |
| `sunset_hour` | `int` | `0–23` | Local hour closest to astronomical sunset. |
| `low_clouds` | `int` | `0–100 %` | Local low cloud cover (< 2 km). |
| `mid_clouds` | `int` | `0–100 %` | Local altocumulus / altostratus reflection canvas. |
| `high_clouds` | `int` | `0–100 %` | Cirrus deck density for high-altitude scatter. |
| `west_low_clouds` | `int` | `0–100 %` | Low cloud density in the Coast Range horizon corridor. |
| `west_trend` | `int` | `% delta` | Rate of change in western low clouds over the prior hour. |
| `temp_c` | `float` | `°C` | Ambient 2-meter air temperature. |
| `dew_point_c` | `float` | `°C` | 2-meter dew point. |
| `dew_point_depression_c` | `float` | `°C` | Spread (`temp - dew_point`); indicates haze/fog threshold. |
| `humidity` | `int` | `0–100 %` | Relative humidity. |
| `dni_wm2` | `float` | `W/m²` | Direct Normal Irradiance (unobstructed beam strength). |
| `diffuse_rad_wm2` | `float` | `W/m²` | Diffuse horizontal radiation from cloud scattering. |
| `surface_pressure_hpa` | `float` | `hPa` | Local barometric pressure. |
| `wind_speed_kmh` | `float` | `km/h` | Surface wind speed at 10 meters. |
| `wind_dir_deg` | `int` | `0–360°` | Wind direction azimuth. |
| `precipitation_mm` | `float` | `mm` | Liquid precipitation depth at sample hour. |
| `heuristic_score` | `float` | `1.0–5.0` | Algorithmic baseline score based on optical rules. |
| `actual_score` | `float` | `1.0–5.0` | Manual observer ground-truth rating. |
| `visibility_km` | `float` | `km` | Horizontal optical atmospheric visibility. |

---

## ⚙️ Core Components

* **`sunset_checker.py`**: Queries the live Open-Meteo forecast models for both Corvallis (`44.5646, -123.2620`) and the Coast Range gap (`44.6368, -123.8500`). Calculates thermodynamic spread, evaluates optical scatter criteria, sends an alert with inline buttons to Telegram, and appends the daily row to the CSV.
* **`upgrade_dataset.py`**: Idempotent archive backfill utility. Pulls historical reanalysis data from Open-Meteo across matching coordinate pairs while preserving any existing manual ratings.
* **`train_model.py`**: Machine learning pipeline that ingests `sunset_history.csv`, extracts feature matrices, trains a regressor or neural network against ground truth labels, and evaluates predictive accuracy.
* **`.github/workflows/sunset.yml`**: Scheduled daily GitHub Actions runner operating with non-shallow Git rebase handling to guarantee seamless dataset persistence.

---

## 🚀 Setup & Local Execution

### 1. Clone & Install Dependencies
```bash
git clone [https://github.com/luke-gant/Sun-set-trainer.git](https://github.com/luke-gant/Sun-set-trainer.git)
cd Sun-set-trainer
pip install requests pandas numpy scikit-learn

```

### 2. Environment Variables

For Telegram notifications, set your environment variables (or add them to GitHub Repository Secrets):

```bash
export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="your_chat_id"

```

### 3. Run Daily Collector Manually

```bash
python sunset_checker.py

```

---

## 📐 Heuristic Scoring Baseline

The heuristic baseline score estimates vibrancy on a 1.0 to 5.0 scale using empirical rules:

1. **Horizon Optical Clearance**: If western low clouds exceed 65% or active precipitation occurs (`> 0.1 mm`), the score is clamped low (blocked western light path / no under-lighting).
2. **Reflective Canvas**: Mid- and high-level clouds between 20% and 80% provide projection surfaces without acting as an overcast blanket.
3. **Solar Penetration**: `dni_wm2 >= 50` confirms direct-beam sunlight reaches the western gap.
4. **Atmospheric Clarity**: High dew point depression (`>= 3.0°C`) indicates low boundary-layer haze risk, maximizing clean Rayleigh and Mie scattering.

```

<FollowUp label="Want to inspect train_model.py to make sure it loads all 20 columns properly?" query="Can you check train_model.py to make sure it loads all 20 columns properly?"/>

```
