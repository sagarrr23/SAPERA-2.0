import os
import joblib
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
from tensorflow.keras.callbacks import ModelCheckpoint

# === Configuration ===
HISTORICAL_DATA_PATH = "data/historical_data.csv"
MODEL_PATH = "models/lstm_model.keras"
SCALER_PATH = MODEL_PATH.replace(".keras", "_scaler.save")
LOOK_BACK = 50
EPOCHS = 10
BATCH_SIZE = 32

# === Step 1: Load Historical Data ===
print("📥 Loading historical data...")
if not os.path.exists(HISTORICAL_DATA_PATH):
    raise FileNotFoundError(f"❌ Data not found: {HISTORICAL_DATA_PATH}")

df = pd.read_csv(HISTORICAL_DATA_PATH)
required_cols = ["open", "high", "low", "close", "volume"]
if not set(required_cols).issubset(df.columns):
    raise ValueError(f"❌ Missing columns: {set(required_cols) - set(df.columns)}")

data = df[required_cols].values
print(f"✅ Loaded {len(data)} rows of market data.")

# === Step 2: Normalize the Dataset ===
scaler = MinMaxScaler()
scaled_data = scaler.fit_transform(data)

# Save fitted scaler for later prediction use
os.makedirs(os.path.dirname(SCALER_PATH), exist_ok=True)
joblib.dump(scaler, SCALER_PATH)
print(f"✅ Scaler saved → {SCALER_PATH}")

# === Step 3: Create Time-Series Sequences ===
def create_sequences(dataset, look_back):
    X, y = [], []
    for i in range(len(dataset) - look_back):
        X.append(dataset[i:i + look_back])
        y.append(dataset[i + look_back][3])  # Predict "close" price
    return np.array(X), np.array(y)

X, y = create_sequences(scaled_data, LOOK_BACK)
print(f"✅ Created {X.shape[0]} sequences | Input shape: {X.shape[1:]}")

# === Step 4: Build the LSTM Model ===
model = Sequential([
    LSTM(64, input_shape=(LOOK_BACK, X.shape[2]), activation='tanh'),
    Dense(1)
])
model.compile(optimizer="adam", loss="mse")

# === Step 5: Train & Save Model ===
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
checkpoint_cb = ModelCheckpoint(
    MODEL_PATH, monitor="loss", mode="min", save_best_only=True, verbose=1
)

print("🚀 Training LSTM model...")
model.fit(X, y, epochs=EPOCHS, batch_size=BATCH_SIZE, callbacks=[checkpoint_cb], verbose=1)
print(f"✅ Model trained and saved → {MODEL_PATH}")

# === Step 6: Evaluate Performance ===
print("🔍 Predicting on last 100 samples...")
X_eval, y_true = X[-100:], y[-100:]
predictions = model.predict(X_eval)

print("🔢 Sample Predictions vs Actual Close Prices:")
for i in range(5):
    actual = scaler.inverse_transform([[0, 0, 0, y_true[i], 0]])[0][3]
    predicted = scaler.inverse_transform([[0, 0, 0, predictions[i][0], 0]])[0][3]
    print(f" → Actual: {actual:.5f} | Predicted: {predicted:.5f}")
