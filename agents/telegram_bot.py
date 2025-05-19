import os
import sys
import time
import logging
import asyncio
import pandas as pd
import talib
from datetime import datetime
from telegram import Bot
import oandapyV20
import oandapyV20.endpoints.orders as orders

# === Load Configs ===
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# === Logging Setup ===
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "sapera_step1.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

LIVE_DATA_FILE = "data/live_data_session.csv"

# === Wallet Manager ===
class WalletManager:
    def __init__(self, total_balance):
        self.total_balance = total_balance
        self.session_balance = 0

    def allocate_balance(self, amount):
        if amount > self.total_balance:
            logging.error("Insufficient funds.")
            return False
        self.session_balance = amount
        self.total_balance -= amount
        logging.info(f"Allocated ${amount}. Remaining: ${self.total_balance}")
        return True

    def update_balance(self, profit_or_loss):
        self.total_balance += self.session_balance + profit_or_loss
        logging.info(f"Wallet updated. Total balance: ${self.total_balance:.2f}")
        self.session_balance = 0

# === Telegram Notifier ===
class TelegramNotifier:
    def __init__(self, token, chat_id):
        self.bot = Bot(token)
        self.chat_id = chat_id

    def send(self, msg):
        try:
            asyncio.run(self.bot.send_message(chat_id=self.chat_id, text=msg))
            logging.info(f"Telegram sent: {msg}")
        except Exception as e:
            logging.error(f"Telegram error: {e}")

# === Strategy Analyzer ===
class StrategyAnalyzer:
    def __init__(self):
        self.config = {
            "ema_fast": 10,
            "ema_slow": 20,
            "rsi_period": 14,
            "rsi_overbought": 70,
            "rsi_oversold": 30,
            "atr_period": 14,
        }

    def analyze(self, df):
        try:
            df["EMA_Fast"] = talib.EMA(df["bid"], timeperiod=self.config["ema_fast"])
            df["EMA_Slow"] = talib.EMA(df["bid"], timeperiod=self.config["ema_slow"])
            df["RSI"] = talib.RSI(df["bid"], timeperiod=self.config["rsi_period"])
            df["ATR"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=self.config["atr_period"])
            df["signal"] = "Hold"

            buy = (df["RSI"] < self.config["rsi_oversold"]) & (df["EMA_Fast"] > df["EMA_Slow"])
            sell = (df["RSI"] > self.config["rsi_overbought"]) & (df["EMA_Fast"] < df["EMA_Slow"])

            df.loc[buy, "signal"] = "Buy"
            df.loc[sell, "signal"] = "Sell"

            return df
        except Exception as e:
            logging.error(f"Strategy error: {e}")
            return None

# === Trading Bot ===
class TradingBot:
    def __init__(self, risk=1.0, tp_mult=2.5):
        self.client = oandapyV20.API(access_token=OANDA_API_KEY)
        self.risk = risk
        self.tp_mult = tp_mult

    def place_order(self, instrument, signal, price, atr, wallet):
        try:
            pip_value = 0.0001 if "JPY" not in instrument else 0.01
            trade_size = round(wallet.session_balance / (pip_value * atr), 2)

            stop = price - (atr * pip_value) if signal == "Buy" else price + (atr * pip_value)
            tp = price + (atr * self.tp_mult * pip_value) if signal == "Buy" else price - (atr * self.tp_mult * pip_value)

            order_data = {
                "order": {
                    "instrument": instrument,
                    "units": str(trade_size if signal == "Buy" else -trade_size),
                    "type": "MARKET",
                    "positionFill": "DEFAULT",
                    "stopLossOnFill": {"price": f"{stop:.5f}"},
                    "takeProfitOnFill": {"price": f"{tp:.5f}"},
                }
            }

            request = orders.OrderCreate(accountID=OANDA_ACCOUNT_ID, data=order_data)
            res = self.client.request(request)
            logging.info(f"Order placed: {res}")
            return True
        except Exception as e:
            logging.error(f"Trade failed: {e}")
            return False

# === Main Loop ===
if __name__ == "__main__":
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    wallet = WalletManager(total_balance=1000)
    analyzer = StrategyAnalyzer()
    bot = TradingBot()

    session_capital = 500
    if not wallet.allocate_balance(session_capital):
        notifier.send("❌ Not enough wallet balance to start session.")
        sys.exit(1)

    notifier.send(f"✅ Session started with ${session_capital} allocated.")

    while True:
        try:
            if not os.path.exists(LIVE_DATA_FILE):
                logging.warning("Live data missing. Retrying in 60s...")
                time.sleep(60)
                continue

            df = pd.read_csv(LIVE_DATA_FILE)
            if df.empty:
                logging.warning("Live data empty. Retrying in 60s...")
                time.sleep(60)
                continue

            analyzed = analyzer.analyze(df)

            for _, row in analyzed.iterrows():
                if row["signal"] in ["Buy", "Sell"]:
                    notifier.send(f"📊 {row['signal']} signal for {row['instrument']} at {row['bid']:.5f}")
                    success = bot.place_order(
                        instrument=row["instrument"],
                        signal=row["signal"],
                        price=row["bid"],
                        atr=row["ATR"],
                        wallet=wallet
                    )

            time.sleep(60)

        except KeyboardInterrupt:
            notifier.send("🔌 Session manually stopped.")
            wallet.update_balance(0)
            break
        except Exception as e:
            logging.error(f"Loop error: {e}")
            time.sleep(60)
