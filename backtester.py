import os
import pandas as pd
import numpy as np
import talib
import logging
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split

# Configure logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "backtester.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

class WalletManager:
    def __init__(self, total_balance):
        self.total_balance = total_balance
        self.session_balance = 0

    def allocate_balance(self, amount):
        if amount > self.total_balance:
            logging.error("Insufficient wallet balance.")
            return False
        self.session_balance = amount
        self.total_balance -= amount
        logging.info(f"Allocated ${amount} to session. Remaining: ${self.total_balance}")
        return True

    def update_balance(self, profit_or_loss):
        self.session_balance += profit_or_loss
        self.total_balance += self.session_balance
        logging.info(f"Wallet updated. New total: ${self.total_balance:.2f}")

class Backtester:
    def __init__(self, data_path, wallet_manager, config=None):
        self.data_path = data_path
        self.wallet_manager = wallet_manager
        self.initial_balance = wallet_manager.session_balance
        self.current_balance = self.initial_balance
        self.trades = []
        self.config = config or self.default_config()
        self.scaler = StandardScaler()
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        logging.info("Backtester initialized.")

    @staticmethod
    def default_config():
        return {
            "ema_fast": 10,
            "ema_slow": 50,
            "rsi_period": 14,
            "atr_multiplier": 1.2,
            "take_profit_multiplier": 2.5,
            "rsi_overbought": 75,
            "rsi_oversold": 25,
            "bollinger_period": 20,
            "bollinger_dev": 2,
            "adx_threshold": 20,
        }

    def load_data(self):
        try:
            df = pd.read_csv(self.data_path, parse_dates=["time"])
            df.set_index("time", inplace=True)
            logging.info(f"Loaded {len(df)} records from {self.data_path}.")
            return df
        except Exception as e:
            logging.error(f"Error loading data: {e}")
            return None

    def calculate_indicators(self, df):
        try:
            df["EMA_Fast"] = talib.EMA(df["close"], timeperiod=self.config["ema_fast"])
            df["EMA_Slow"] = talib.EMA(df["close"], timeperiod=self.config["ema_slow"])
            df["RSI"] = talib.RSI(df["close"], timeperiod=self.config["rsi_period"])
            df["ATR"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=14)
            df["Upper_Band"], _, df["Lower_Band"] = talib.BBANDS(
                df["close"],
                timeperiod=self.config["bollinger_period"],
                nbdevup=self.config["bollinger_dev"],
                nbdevdn=self.config["bollinger_dev"],
            )
            df["ADX"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=14)
            return df
        except Exception as e:
            logging.error(f"Indicator calculation failed: {e}")
            return df

    def apply_strategy(self, df):
        try:
            df["signal"] = "Hold"
            buy = (
                (df["EMA_Fast"] > df["EMA_Slow"]) &
                (df["RSI"] < self.config["rsi_oversold"]) &
                (df["ADX"] > self.config["adx_threshold"])
            )
            sell = (
                (df["EMA_Fast"] < df["EMA_Slow"]) &
                (df["RSI"] > self.config["rsi_overbought"]) &
                (df["ADX"] > self.config["adx_threshold"])
            )
            df.loc[buy, "signal"] = "Buy"
            df.loc[sell, "signal"] = "Sell"

            df.dropna(inplace=True)
            X = df[["EMA_Fast", "EMA_Slow", "RSI", "ATR", "ADX"]]
            y = (df["signal"] == "Buy").astype(int)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)
            self.model.fit(self.scaler.fit_transform(X_train), y_train)
            df["ml_signal"] = self.model.predict(self.scaler.transform(X))
            return df
        except Exception as e:
            logging.error(f"Strategy application failed: {e}")
            return df

    def simulate_trades(self, df):
        try:
            for _, row in df.iterrows():
                if row["signal"] == "Buy":
                    pnl = row["ATR"] * self.config["take_profit_multiplier"]
                    self.trades.append({"type": "Buy", "pnl": pnl})
                    self.current_balance += pnl
                elif row["signal"] == "Sell":
                    pnl = row["ATR"] * self.config["take_profit_multiplier"]
                    self.trades.append({"type": "Sell", "pnl": pnl})
                    self.current_balance += pnl
        except Exception as e:
            logging.error(f"Trade simulation failed: {e}")

    def calculate_metrics(self):
        wins = [t for t in self.trades if t["pnl"] > 0]
        roi = (self.current_balance - self.initial_balance) / self.initial_balance * 100
        return {
            "Total Trades": len(self.trades),
            "Win Rate": len(wins) / len(self.trades) * 100 if self.trades else 0,
            "ROI (%)": roi,
            "Final Balance": self.current_balance
        }

    def run(self):
        df = self.load_data()
        if df is not None:
            df = self.calculate_indicators(df)
            df = self.apply_strategy(df)
            self.simulate_trades(df)
            metrics = self.calculate_metrics()
            logging.info("Backtest completed.")
            return metrics


if __name__ == "__main__":
    wallet = WalletManager(total_balance=10000)
    wallet.allocate_balance(5000)
    backtester = Backtester(data_path="EUR_USD_historical_data.csv", wallet_manager=wallet)
    results = backtester.run()
    if results:
        print("Backtest Results:")
        print(results)
