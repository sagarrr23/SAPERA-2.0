import os
import sys
import json
import time
import logging
import asyncio
from datetime import datetime
import pandas as pd

import oandapyV20
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.accounts as accounts
from telegram import Bot

# Config and Credentials
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Setup Logging
os.makedirs("logs", exist_ok=True)
TRADE_LOG = "logs/trade_log.csv"
logging.basicConfig(
    filename="logs/trading_bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ==========================
# WALLET MANAGER
# ==========================
class WalletManager:
    def __init__(self, wallet_file="wallet.json"):
        self.wallet_file = wallet_file
        self.wallet_balance = self._load_balance()

    def _load_balance(self):
        try:
            with open(self.wallet_file, "r") as f:
                return json.load(f).get("wallet_balance", 1000.0)
        except FileNotFoundError:
            logging.info("No wallet file found. Starting with $1000.")
            return 1000.0

    def _save_balance(self):
        with open(self.wallet_file, "w") as f:
            json.dump({"wallet_balance": self.wallet_balance}, f)

    def initialize_session(self, amount):
        if amount > self.wallet_balance:
            logging.error("Insufficient wallet balance.")
            return None
        self.wallet_balance -= amount
        self._save_balance()
        logging.info(f"Session started with ${amount:.2f}. Wallet remaining: ${self.wallet_balance:.2f}")
        return amount

    def update_balance(self, profit_or_loss):
        self.wallet_balance += profit_or_loss
        self._save_balance()
        logging.info(f"Wallet updated. New balance: ${self.wallet_balance:.2f}")

    class TelegramNotifier:
        def __init__(self, token, chat_id):
            self.bot = Bot(token=token)
            self.chat_id = chat_id

        def send_message(self, message):
            try:
                self.bot.send_message(chat_id=self.chat_id, text=message)
                logging.info(f"Telegram alert sent: {message}")
            except Exception as e:
                logging.error(f"Telegram failed: {e}")

# ==========================
# TRADING BOT
# ==========================
class EnhancedTradingBot:
    def __init__(self, wallet_manager, notifier, risk_pct=1.0, tp_multiplier=2.5, retries=3):
        self.client = oandapyV20.API(access_token=OANDA_API_KEY)
        self.wallet = wallet_manager
        self.notifier = notifier
        self.risk_pct = risk_pct
        self.tp_multiplier = tp_multiplier
        self.retries = retries
        logging.info("✅ EnhancedTradingBot initialized")

    def get_account_balance(self):
        for attempt in range(self.retries):
            try:
                req = accounts.AccountDetails(OANDA_ACCOUNT_ID)
                res = self.client.request(req)
                return float(res["account"]["balance"])
            except Exception as e:
                logging.warning(f"Attempt {attempt+1} - Balance fetch failed: {e}")
        raise Exception("Unable to fetch OANDA account balance.")

    def calculate_trade_size(self, capital, atr, instrument):
        try:
            pip_value = 0.0001 if "JPY" not in instrument else 0.01
            units = round((capital * (self.risk_pct / 100)) / (atr * pip_value))
            return min(units, 1_000_000)
        except Exception as e:
            logging.error(f"Trade size calculation error: {e}")
            return 0

    # Inside EnhancedTradingBot class

    def log_trade(self, trade_id, instrument, signal, price, stop_loss, take_profit, units, lstm_prediction, correct_prediction):
        entry = {
            "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "client_trade_id": trade_id,
            "instrument": instrument,
            "signal": signal,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "trade_size": units,
            "lstm_prediction": round(lstm_prediction, 5),
            "correct_prediction": correct_prediction,
            "profit": 0,
            "cumulative_profit": 0,
            "duration": 0
        }
        df = pd.DataFrame([entry])
        if not os.path.exists(TRADE_LOG):
            df.to_csv(TRADE_LOG, index=False)
        else:
            df.to_csv(TRADE_LOG, mode="a", header=False, index=False)
        logging.info(f"Trade logged with LSTM: {trade_id}")

    def place_order(self, instrument, signal, price, atr, capital, lstm_prediction):
        units = self.calculate_trade_size(capital, atr, instrument)
        if units == 0:
            return

        stop_loss = price - atr if signal == "Buy" else price + atr
        take_profit = price + atr * self.tp_multiplier if signal == "Buy" else price - atr * self.tp_multiplier
        client_trade_id = f"{instrument}_{datetime.utcnow().strftime('%H%M%S')}"

        correct_prediction = (
            lstm_prediction > price if signal == "Buy" else lstm_prediction < price
        )

        order_data = {
            "order": {
                "instrument": instrument,
                "units": str(units if signal == "Buy" else -units),
                "type": "MARKET",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {"price": f"{stop_loss:.5f}"},
                "takeProfitOnFill": {"price": f"{take_profit:.5f}"},
                "clientExtensions": {"id": client_trade_id}
            }
        }

        for attempt in range(self.retries):
            try:
                req = orders.OrderCreate(OANDA_ACCOUNT_ID, data=order_data)
                res = self.client.request(req)
                if res.get("orderFillTransaction"):
                    self.notifier.send_message(
                        f"Trade ✅\n{instrument} | {signal}\nEntry: {price:.5f}\nSL: {stop_loss:.5f} | TP: {take_profit:.5f}"
                    )
                    self.log_trade(
                        trade_id=client_trade_id,
                        instrument=instrument,
                        signal=signal,
                        price=price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        units=units,
                        lstm_prediction=lstm_prediction,
                        correct_prediction=correct_prediction
                    )
                    return
            except Exception as e:
                logging.error(f"Order attempt {attempt+1} failed: {e}")
        logging.error("❌ Order placement failed after max retries")

# ==========================
# DEMO ENTRY POINT
# ==========================
if __name__ == "__main__":
    wallet = WalletManager()
    notifier = WalletManager.TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    bot = EnhancedTradingBot(wallet, notifier)

    capital = wallet.initialize_session(500)
    if capital:
        bot.place_order("EUR_USD", "Buy", 1.10500, 0.0025, capital)
        wallet.update_balance(+50)  # Simulate profit update
