# 🌅 Corvallis Sunset Quality Predictor & Tracker

An automated end-to-end atmospheric data pipeline and predictive modeling engine designed to forecast and log sunset quality in Corvallis, Oregon.

The system combines local microclimate thermodynamics, high-resolution solar radiation, and directional Coast Range cloud deck vectors into an automated daily notification workflow, recording empirical features alongside ground-truth observer ratings.

---

## 🧭 Project Architecture
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
* **`train_model.py`**: Machine learning pipeline that ingests `sunset_history.csv`, extracts feature matrices, trains a regressor/neural network against ground truth labels, and evaluates predictive accuracy.
* **`.github/workflows/sunset.yml`**: Scheduled daily GitHub Actions runner operating with non-shallow Git rebase handling to guarantee seamless dataset persistence.

---

## 🚀 Setup & Local Execution

### 1. Clone & Install Dependencies
```bash
git clone [https://github.com/your-username/Sun-set-trainer.git](https://github.com/your-username/Sun-set-trainer.git)
cd Sun-set-trainer
pip install -r requirements.txt
