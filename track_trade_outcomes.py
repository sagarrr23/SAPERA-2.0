import os
import time
import json
import logging
import pandas as pd
from datetime import datetime
import oandapyV20
import oandapyV20.endpoints.trades as trades
import oandapyV20.endpoints.transactions as transactions

from config import OANDA_API_KEY, OANDA_ACCOUNT_ID

# Setup logging
os.makedirs("logs", exist_ok=True)
LOG_FILE = "logs/trade_outcome_tracker.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

TRADE_LOG = "logs/trade_log.csv"

class TradeOutcomeTracker:
    def __init__(self, api_key, account_id, trade_log_path):
        self.client = oandapyV20.API(access_token=api_key)
        self.account_id = account_id
        self.trade_log_path = trade_log_path
        logging.info("✅ TradeOutcomeTracker initialized")

    def fetch_closed_trades(self):
        try:
            req = transactions.TransactionList(self.account_id)
            self.client.request(req)
            return req.response.get("transactions", [])
        except Exception as e:
            logging.error(f"❌ Failed to fetch closed trades: {e}")
            return []

    def update_trade_log(self):
        if not os.path.exists(self.trade_log_path):
            logging.warning("⚠️ Trade log file not found.")
            return

        try:
            df = pd.read_csv(self.trade_log_path)
            closed_trades = self.fetch_closed_trades()

            for tx in closed_trades:
                if tx["type"] != "ORDER_FILL":
                    continue

                instrument = tx.get("instrument")
                filled_price = float(tx.get("price", 0))
                units = abs(int(float(tx.get("units", 0))))
                realized_pl = float(tx.get("pl", 0))
                fill_time = tx.get("time")

                if instrument is None or filled_price == 0 or units == 0:
                    continue

                # Match open trades in CSV with 0 profit and same instrument
                match = df[
                    (df["instrument"] == instrument)
                    & (df["profit"] == 0)
                    & (df["trade_size"] == units)
                    & (df["price"].round(4) == round(filled_price, 4))
                ]

                if not match.empty:
                    idx = match.index[0]
                    df.at[idx, "profit"] = round(realized_pl, 2)
                    df.at[idx, "duration"] = 60  # Placeholder (can improve)
                    df.at[idx, "cumulative_profit"] = df["profit"].cumsum().iloc[idx]
                    logging.info(f"✅ Trade closed → {instrument} | Profit: {realized_pl:.2f}")

            df.to_csv(self.trade_log_path, index=False)
        except Exception as e:
            logging.error(f"❌ Error updating trade log: {e}")

if __name__ == "__main__":
    tracker = TradeOutcomeTracker(
        api_key=OANDA_API_KEY,
        account_id=OANDA_ACCOUNT_ID,
        trade_log_path=TRADE_LOG
    )

    while True:
        tracker.update_trade_log()
        time.sleep(60)  # Run every 60 seconds
