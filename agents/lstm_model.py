import os
import numpy as np
import pandas as pd
import joblib
import logging
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.callbacks import ModelCheckpoint

# === Logging Setup ===
LOG_FILE = "logs/lstm_model.log"
os.makedirs("logs", exist_ok=True)

def safe_log(msg):
    try:
        logging.info(msg)
    except UnicodeEncodeError:
        logging.info(msg.encode("ascii", "ignore").decode())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)

class LSTMModel:
    """
    LSTM-based classification model to predict direction (Buy/Sell/Hold)
    using OHLCV features.
    """
    def __init__(self, model_path="models/lstm_model.keras", look_back=50):
        self.look_back = look_back
        self.model_path = model_path
        self.scaler_path = model_path.replace(".keras", "_scaler.save")
        self.scaler = MinMaxScaler()
        self.model = self.build_model()
        self.load_model()
        self.load_scaler()

    def build_model(self):
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=(self.look_back, 5)),
            Dropout(0.3),
            LSTM(64),
            Dropout(0.3),
            Dense(3, activation="softmax")  # [Hold, Buy, Sell]
        ])
        model.compile(optimizer="adam", loss="categorical_crossentropy", metrics=["accuracy"])
        safe_log("✅ LSTM classification model built.")
        return model

    def preprocess_data(self, data):
        scaled = self.scaler.fit_transform(data)
        X, y = [], []
        for i in range(self.look_back, len(scaled) - 1):
            X.append(scaled[i - self.look_back:i])
            delta = scaled[i + 1, 3] - scaled[i, 3]  # change in close
            if delta > 0.002:
                label = [0, 1, 0]  # Buy
            elif delta < -0.002:
                label = [0, 0, 1]  # Sell
            else:
                label = [1, 0, 0]  # Hold
            y.append(label)
        return np.array(X), np.array(y)

    def train_model(self, data, epochs=10, batch_size=32):
        X, y = self.preprocess_data(data)
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        checkpoint_cb = ModelCheckpoint(
            self.model_path, monitor="loss", mode="min", save_best_only=True, verbose=1
        )
        self.model.fit(X, y, epochs=epochs, batch_size=batch_size, callbacks=[checkpoint_cb])
        self.save_model()
        self.save_scaler()

    def predict(self, data):
        if not hasattr(self.scaler, "min_"):
            raise RuntimeError("Scaler not loaded or fitted.")

        if data.ndim == 3:
            # Already reshaped input for a single sequence
            scaled = self.scaler.transform(data.reshape(-1, data.shape[2]))  # Flatten for scaling
            scaled = scaled.reshape(data.shape)  # Reshape back to (1, LOOK_BACK, 5)
        else:
            scaled = self.scaler.transform(data)

        X = []
        if scaled.shape[0] >= self.look_back:
            X.append(scaled[-self.look_back:])
        else:
            raise ValueError("Not enough data to make prediction.")

        X = np.array(X)
        predictions = self.model.predict(X)
        return np.argmax(predictions, axis=1)

    def evaluate_model(self, data):
        X, y_true = self.preprocess_data(data)
        y_pred = self.model.predict(X)
        y_true_labels = np.argmax(y_true, axis=1)
        y_pred_labels = np.argmax(y_pred, axis=1)
        acc = np.mean(y_true_labels == y_pred_labels)
        safe_log(f"📊 Classification Accuracy: {acc * 100:.2f}%")
        print(f"📊 Classification Accuracy: {acc * 100:.2f}%")

    def save_model(self):
        self.model.save(self.model_path)
        safe_log(f"✅ Model saved → {self.model_path}")

    def load_model(self):
        if os.path.exists(self.model_path):
            self.model = load_model(self.model_path)
            safe_log(f"📦 Model loaded → {self.model_path}")
        else:
            safe_log("⚠️ No saved model found. Starting fresh.")

    def save_scaler(self):
        joblib.dump(self.scaler, self.scaler_path)
        safe_log(f"✅ Scaler saved → {self.scaler_path}")

    def load_scaler(self):
        if os.path.exists(self.scaler_path):
            self.scaler = joblib.load(self.scaler_path)
            safe_log(f"📦 Scaler loaded → {self.scaler_path}")
        else:
            safe_log("⚠️ Scaler not found. Make sure to train the model first.")


# === Standalone Entry Point for Training and Evaluation ===
if __name__ == "__main__":
    HISTORICAL_DATA_PATH = "data/EUR_USD_historical_data.csv"
    MODEL_PATH = "models/lstm_model.keras"

    if not os.path.exists(HISTORICAL_DATA_PATH):
        raise FileNotFoundError(f"❌ Historical data not found at: {HISTORICAL_DATA_PATH}")

    print("📥 Loading historical data...")
    df = pd.read_csv(HISTORICAL_DATA_PATH)
    df = df[["open", "high", "low", "close", "volume"]]
    print(f"✅ Loaded {len(df)} rows.")

    lstm = LSTMModel(model_path=MODEL_PATH, look_back=50)

    print("🚀 Training LSTM model...")
    lstm.train_model(df.values, epochs=10, batch_size=32)

    print("🧠 Evaluating model...")
    lstm.evaluate_model(df.values)
