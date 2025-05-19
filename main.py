import os
import sys
import logging
import pandas as pd

# === Project Path Setup ===
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

# === Internal Module Imports ===
from agents.strategy import StrategyAnalyzer
from agents.data_fetcher import DataFetcher
from agents.trade_executor import EnhancedTradingBot, WalletManager
from agents.lstm_model import LSTMModel
from config import (
    OANDA_API_KEY,
    OANDA_ACCOUNT_ID,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    USE_BACKTEST,
)

# === Configuration ===
HISTORICAL_DATA_FILE = "data/historical_data.csv"
MODEL_PATH = "models/lstm_model.keras"
SESSION_CAPITAL = 1000
LOOK_BACK = 50
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "sapera_main.log")

# === Logging Setup (Safe for Windows console) ===
os.makedirs(LOG_DIR, exist_ok=True)

def safe_log(msg):
    try:
        logging.info(msg.encode("ascii", "ignore").decode())
    except Exception:
        logging.info("Logging failed")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

# === Load Historical Data ===
def load_historical_data():
    try:
        df = pd.read_csv(HISTORICAL_DATA_FILE)
        if df.empty:
            raise ValueError("Historical dataset is empty.")
        return df
    except Exception as e:
        logging.error(f"[FATAL] Could not load historical data: {e}")
        sys.exit(1)

# === Initialize Core Modules ===
def initialize():
    notifier = WalletManager.TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    wallet = WalletManager(wallet_file="wallet.json")
    strategy = StrategyAnalyzer()
    bot = EnhancedTradingBot(wallet_manager=wallet, notifier=notifier)
    fetcher = DataFetcher(api_key=OANDA_API_KEY, account_id=OANDA_ACCOUNT_ID)
    lstm = LSTMModel(model_path=MODEL_PATH, look_back=LOOK_BACK)
    return notifier, wallet, strategy, bot, fetcher, lstm

# === Main Execution ===
def main():
    notifier, wallet, strategy, bot, fetcher, lstm = initialize()

    if not wallet.initialize_session(SESSION_CAPITAL):
        notifier.send_message("Wallet has insufficient funds to start session.")
        return

    # === Load Data ===
    if USE_BACKTEST:
        safe_log("Loading historical data for backtesting...")
        df = load_historical_data()
    else:
        safe_log("Fetching live market data...")
        df = fetcher.fetch_live_data(instruments="EUR_USD,USD_JPY")
        if df is None or df.empty or len(df) < LOOK_BACK:
            fallback_msg = f"Live data invalid or too short (required: {LOOK_BACK}, got: {len(df)}). Falling back to historical."
            logging.warning(fallback_msg)
            notifier.send_message(fallback_msg)
            df = load_historical_data()

    # Add volume column if missing
    if "volume" not in df.columns:
        df["volume"] = 1000

    try:
        safe_log("Applying strategy indicators...")
        df = strategy.calculate_indicators(df)
        df = strategy.generate_signals(df)

        safe_log("Running LSTM price prediction...")
        features = df[["open", "high", "low", "close", "volume"]].values

        if len(features) < LOOK_BACK:
            msg = f"Not enough data for LSTM prediction. Required: {LOOK_BACK}, Found: {len(features)}"
            logging.warning(msg)
            notifier.send_message(msg)
            return

        # ✅ Let the model handle reshaping internally
        lstm_direction = lstm.predict(features)[-1]
        lstm_label = ["Hold", "Buy", "Sell"][lstm_direction]

        safe_log(f"LSTM prediction: {lstm_label}")
        safe_log("Scanning strategy signals...")

        for _, row in df.iterrows():
            signal = row.get("signal")
            if signal not in ["Buy", "Sell"]:
                continue

            price = row["close"]
            matched = signal == lstm_label

            if matched:
                bot.place_order(
                    instrument=row.get("instrument", "EUR_USD"),
                    signal=signal,
                    price=price,
                    atr=row.get("ATR", 0.001),
                    capital=SESSION_CAPITAL,
                    lstm_prediction=lstm_label,
                    correct_prediction=True,
                )
            else:
                safe_log(f"Trade Rejected → {row.get('instrument', 'EUR_USD')} | Signal: {signal} | LSTM: {lstm_label}")

        notifier.send_message("Trading session completed successfully.")

    except Exception as e:
        logging.error(f"Fatal runtime error: {e}")
        try:
            notifier.send_message(f"Session failed: {e}")
        except Exception:
            logging.warning("Telegram notification failed.")

# === Start Script ===
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.info("SAPERA 2.0 manually stopped.")
    except Exception as e:
        logging.error(f"Startup crash: {e}")
