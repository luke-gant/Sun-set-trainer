from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import KFold
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

csv_path = Path("data/sunset_history.csv")
if not csv_path.exists():
    raise FileNotFoundError("data/sunset_history.csv not found!")

df = pd.read_csv(csv_path)

# 1. Filter out unrated days
df["actual_score"] = pd.to_numeric(df["actual_score"], errors="coerce")
df = df.dropna(subset=["actual_score"]).copy()

print(f"Loaded {len(df)} scored days for neural network training.")

# 2. Complete 17-feature input vector matching your CSV schema
FEATURE_COLS = [
    "low_clouds",
    "mid_clouds",
    "high_clouds",
    "west_low_clouds",
    "west_trend",
    "temp_c",
    "dew_point_c",
    "dew_point_depression_c",
    "humidity",
    "dni_wm2",
    "diffuse_rad_wm2",
    "surface_pressure_hpa",
    "wind_speed_kmh",
    "wind_dir_deg",
    "precipitation_mm",
    "visibility_km",
    "heuristic_score",
]

# Verify all columns exist; if visibility_km has blanks from earlier backfills, fill with 15.0 km
if "visibility_km" in df.columns:
    df["visibility_km"] = df["visibility_km"].fillna(15.0)

# Check for presence of all features
missing_from_csv = [col for col in FEATURE_COLS if col not in df.columns]
if missing_from_csv:
    raise ValueError(f"Missing expected columns in CSV: {missing_from_csv}")

X = df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
y = df["actual_score"].values

# 3. 5-Fold Cross-Validation Evaluation
kf = KFold(n_splits=5, shuffle=True, random_state=42)
cv_mae = []
cv_rmse = []

for fold, (train_idx, test_idx) in enumerate(kf.split(X), 1):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    # Fit scaler strictly on training partition
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Compact MLP constrained for small sample size (N=32)
    nn = MLPRegressor(
        hidden_layer_sizes=(8, 4),
        activation="relu",
        solver="lbfgs",
        alpha=0.1,  # Ridge penalty to dampen overfitting
        max_iter=1000,
        random_state=42,
    )
    nn.fit(X_train_scaled, y_train)

    preds = nn.predict(X_test_scaled)
    preds = np.clip(preds, 1.0, 5.0)

    cv_mae.append(mean_absolute_error(y_test, preds))
    cv_rmse.append(root_mean_squared_error(y_test, preds))

print("-" * 55)
print(f"5-Fold Cross-Validation MAE : {np.mean(cv_mae):.3f} (Avg score error)")
print(f"5-Fold Cross-Validation RMSE: {np.mean(cv_rmse):.3f}")
print("-" * 55)

# Benchmark against hardcoded heuristic baseline
heuristic_mae = mean_absolute_error(y, df["heuristic_score"])
print(f"Baseline Heuristic Rule MAE: {heuristic_mae:.3f}")

# 4. Train final production model on all 32 days & serialize
final_scaler = StandardScaler()
X_final_scaled = final_scaler.fit_transform(X)

final_nn = MLPRegressor(
    hidden_layer_sizes=(8, 4),
    activation="relu",
    solver="lbfgs",
    alpha=0.1,
    max_iter=1000,
    random_state=42,
)
final_nn.fit(X_final_scaled, y)

# 5. Export models and feature metadata
model_dir = Path("models")
model_dir.mkdir(exist_ok=True)

joblib.dump(final_nn, model_dir / "sunset_nn_model.pkl")
joblib.dump(final_scaler, model_dir / "scaler.pkl")
joblib.dump(FEATURE_COLS, model_dir / "features.pkl")

print("Successfully serialized model, scaler, and features to models/")
