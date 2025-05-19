import os
import logging
import pandas as pd
import talib
from datetime import datetime
import json
import sys
import asyncio
from telegram import Bot
import oandapyV20
import oandapyV20.endpoints.orders as orders

# Add project root to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Configure logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "sapera_strategy.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

LIVE_DATA_FILE = "data/live_data_session.csv"


class WalletManager:
    def __init__(self, wallet_file="wallet.json", initial_balance=1000):
        self.wallet_file = wallet_file
        self.wallet_balance = self.load_wallet_balance(initial_balance)
        self.session_balance = 0

    def load_wallet_balance(self, initial_balance):
        try:
            with open(self.wallet_file, "r") as file:
                data = json.load(file)
                return data.get("wallet_balance", initial_balance)
        except FileNotFoundError:
            logging.info("Wallet file not found. Using initial balance.")
            return initial_balance

    def save_wallet_balance(self):
        with open(self.wallet_file, "w") as file:
            json.dump({"wallet_balance": self.wallet_balance}, file)

    def allocate_balance(self, amount):
        if amount <= 0 or amount > self.wallet_balance:
            logging.error("Invalid allocation amount.")
            return False
        self.wallet_balance -= amount
        self.session_balance = amount
        self.save_wallet_balance()
        logging.info(f"Allocated ${amount:.2f} for the session.")
        return True

    def update_balance(self, pnl):
        self.wallet_balance += (self.session_balance + pnl)
        self.session_balance = 0
        self.save_wallet_balance()
        logging.info(f"Updated wallet balance: ${self.wallet_balance:.2f}")

    class TelegramNotifier:
        def __init__(self, token, chat_id):
            self.bot = Bot(token=token)
            self.chat_id = chat_id

        def send_message(self, message):
            try:
                asyncio.run(self.bot.send_message(chat_id=self.chat_id, text=message))
                logging.info(f"Telegram: {message}")
            except Exception as e:
                logging.error(f"Telegram error: {e}")


class StrategyAnalyzer:
    def __init__(self, config=None):
        self.config = config or self.default_config()
        logging.info(f"Strategy config: {self.config}")

    @staticmethod
    def default_config():
        return {
            "ema_fast": 10,
            "ema_slow": 50,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "atr_period": 14,
            "adx_period": 14,
            "bollinger_period": 20,
            "bollinger_dev": 2,
            "volatility_filter": 0.001,
        }

    def calculate_indicators(self, df):
        try:
            df["EMA_Fast"] = talib.EMA(df["close"], timeperiod=self.config["ema_fast"])
            df["EMA_Slow"] = talib.EMA(df["close"], timeperiod=self.config["ema_slow"])
            df["RSI"] = talib.RSI(df["close"], timeperiod=self.config["rsi_period"])
            df["ATR"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=self.config["atr_period"])
            df["ADX"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=self.config["adx_period"])
            df["Upper_Band"], _, df["Lower_Band"] = talib.BBANDS(df["close"], timeperiod=self.config["bollinger_period"], nbdevup=self.config["bollinger_dev"], nbdevdn=self.config["bollinger_dev"])
        except Exception as e:
            logging.error(f"Indicator error: {e}")
        return df

    def generate_signals(self, df):
        df["signal"] = "Hold"
        try:
            buy = (
                (df["EMA_Fast"] > df["EMA_Slow"]) &
                (df["RSI"] < self.config["rsi_oversold"]) &
                (df["ADX"] > 20)
            )
            sell = (
                (df["EMA_Fast"] < df["EMA_Slow"]) &
                (df["RSI"] > self.config["rsi_overbought"]) &
                (df["ADX"] > 20)
            )
            df.loc[buy, "signal"] = "Buy"
            df.loc[sell, "signal"] = "Sell"
        except Exception as e:
            logging.error(f"Signal error: {e}")
        return df


class TradingBot:
    def __init__(self, wallet_manager, notifier, risk_percentage=1, tp_multiplier=2.5):
        self.client = oandapyV20.API(access_token=OANDA_API_KEY)
        self.wallet_manager = wallet_manager
        self.notifier = notifier
        self.risk_percentage = risk_percentage
        self.tp_multiplier = tp_multiplier

    def place_order(self, instrument, signal, price, atr):
        balance = self.wallet_manager.session_balance
        pip = 0.0001 if "JPY" not in instrument else 0.01
        size = round(balance / (pip * atr), 2)

        stop_loss = price - (atr * pip) if signal == "Buy" else price + (atr * pip)
        take_profit = price + (self.tp_multiplier * atr * pip) if signal == "Buy" else price - (self.tp_multiplier * atr * pip)

        message = (
            f"Order: {instrument}\nSignal: {signal}\nPrice: {price:.4f}\nSL: {stop_loss:.4f}\nTP: {take_profit:.4f}\nSize: {size}"
        )
        logging.info(message)
        self.notifier.send_message(message)


if __name__ == "__main__":
    notifier = WalletManager.TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    wallet = WalletManager(initial_balance=1000)
    analyzer = StrategyAnalyzer()
    bot = TradingBot(wallet, notifier)

    session_amount = 500
    if not wallet.allocate_balance(session_amount):
        notifier.send_message("Insufficient wallet balance.")
        sys.exit()

    try:
        data = pd.read_csv(LIVE_DATA_FILE)
        if data.empty:
            raise ValueError("Data file is empty.")

        data = analyzer.calculate_indicators(data)
        analyzed = analyzer.generate_signals(data)

        for _, row in analyzed.iterrows():
            if row["signal"] in ["Buy", "Sell"]:
                bot.place_order(row["instrument"], row["signal"], row["close"], row["ATR"])
    except Exception as e:
        logging.error(f"Execution failed: {e}")
