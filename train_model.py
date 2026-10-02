import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold, cross_val_score
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

CSV_PATH = "eugene_sunset_last_100_days.csv"
MODEL_PATH = "sunset_model.joblib"

df = pd.read_csv(CSV_PATH)

# Keep only rows where you entered a score
df_clean = df.dropna(subset=["sunset_score_1_to_10"]).copy()
df_clean = df_clean[df_clean["sunset_score_1_to_10"].astype(str).str.strip() != ""]

if len(df_clean) < 15:
    raise ValueError(f"Need at least 15 scored days to train reliably. Found {len(df_clean)}.")

feature_cols = [c for c in df_clean.columns if c.startswith("eugene_") or c.startswith("coast_gap_")]
X = df_clean[feature_cols].astype(float)
y = df_clean["sunset_score_1_to_10"].astype(float)

# Neural network pipeline with standardization and L2 regularization (alpha=0.05) to avoid overfitting small sample sizes
pipeline = Pipeline([
    ("scaler", StandardScaler()),
    ("mlp", MLPRegressor(
        hidden_layer_sizes=(16, 8),
        activation="relu",
        solver="adam",
        alpha=0.05,
        max_iter=1000,
        random_state=42
    ))
])

# 5-fold cross validation score
cv = KFold(n_splits=min(5, len(df_clean)), shuffle=True, random_state=42)
scores = cross_val_score(pipeline, X, y, cv=cv, scoring="neg_root_mean_squared_error")
print(f"Average RMSE across folds: {-scores.mean():.2f} rating points")

# Train final model on full rated dataset
pipeline.fit(X, y)
joblib.dump(pipeline, MODEL_PATH)
print(f"Model saved to {MODEL_PATH} based on {len(df_clean)} scored days.")
