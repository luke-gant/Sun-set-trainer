import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

df = pd.read_csv("data/sunset_history.csv")

# Filter only days you manually scored 1-5
df = df.dropna(subset=["actual_score"])
df = df[df["actual_score"] != ""]
df["actual_score"] = df["actual_score"].astype(float)

if len(df) < 15:
    print(f"Need at least 15 scored days to train. Currently have: {len(df)}")
    exit()

features = [
    "low_clouds",
    "mid_clouds",
    "high_clouds",
    "west_low_clouds",
    "humidity",
    "precip_prob",
    "visibility_km",
]
X = df[features]
y = df["actual_score"]

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)
model = RandomForestRegressor(n_estimators=100, max_depth=4, random_state=42)
model.fit(X_train, y_train)

if len(X_test) > 0:
    preds = model.predict(X_test)
    print(f"Mean Absolute Error: {mean_absolute_error(y_test, preds):.2f} stars")
    print(f"R² Score: {r2_score(y_test, preds):.2f}")

print("\n--- Learned Feature Weights ---")
for feat, imp in zip(features, model.feature_importances_):
    print(f"{feat:18s}: {imp * 100:.1f}%")

joblib.dump(model, "models/sunset_model.joblib")
print("\nSaved regressor model to models/sunset_model.joblib")
