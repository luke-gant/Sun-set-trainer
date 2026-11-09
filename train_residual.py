from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, root_mean_squared_error
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler

csv_path = Path("data/sunset_history.csv")
df = pd.read_csv(csv_path)

df["actual_score"] = pd.to_numeric(df["actual_score"], errors="coerce")
df = df.dropna(subset=["actual_score"]).copy()

# Core optical features
FEATURE_COLS = [
    "west_low_clouds",
    "high_clouds",
    "mid_clouds",
    "low_clouds",
    "dew_point_depression_c",
    "dni_wm2",
]

X = df[FEATURE_COLS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
y = df["actual_score"].values
heuristic = df["heuristic_score"].values
y_residual = y - heuristic

kf = KFold(n_splits=5, shuffle=True, random_state=42)

residual_cv_mae = []
residual_cv_rmse = []

for train_idx, test_idx in kf.split(X):
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_res_train = y_residual[train_idx]
    y_test = y[test_idx]
    heur_test = heuristic[test_idx]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # Ridge regularized linear regression (cannot explode)
    model = Ridge(alpha=2.0)
    model.fit(X_train_scaled, y_res_train)

    # Reconstruct final score
    predicted_residual = model.predict(X_test_scaled)
    final_pred = np.clip(heur_test + predicted_residual, 1.0, 5.0)

    residual_cv_mae.append(mean_absolute_error(y_test, final_pred))
    residual_cv_rmse.append(root_mean_squared_error(y_test, final_pred))

baseline_mae = mean_absolute_error(y, heuristic)

print("-" * 55)
print(f"Baseline Heuristic Rule MAE   : {baseline_mae:.3f}")
print(f"5-Fold Residual Ridge CV MAE : {np.mean(residual_cv_mae):.3f}")
print(f"5-Fold Residual Ridge CV RMSE: {np.mean(residual_cv_rmse):.3f}")
print("-" * 55)

if np.mean(residual_cv_mae) < baseline_mae:
    print(
        f"Result: Residual Ridge BEATS heuristic by {baseline_mae - np.mean(residual_cv_mae):.3f} points!"
    )
else:
    print(
        "Result: Heuristic is still superior. Stick to heuristic until N >= 60-80."
    )
