import os
import time
import json
import logging
import pandas as pd
from datetime import datetime
import oandapyV20
import oandapyV20.endpoints.trades as trades

from config import OANDA_API_KEY, OANDA_ACCOUNT_ID

# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    filename="logs/trade_tracker.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

TRADE_LOG = "logs/trade_log.csv"

class TradeOutcomeTracker:
    def __init__(self):
        self.client = oandapyV20.API(access_token=OANDA_API_KEY)

    def fetch_closed_trades(self):
        try:
            r = trades.TradesList(OANDA_ACCOUNT_ID)
            self.client.request(r)
            return r.response.get("trades", [])
        except Exception as e:
            logging.error(f"Failed to fetch trades: {e}")
            return []

    def update_trade_log(self):
        if not os.path.exists(TRADE_LOG):
            logging.warning("Trade log not found.")
            return

        try:
            df = pd.read_csv(TRADE_LOG)
            closed_trades = self.fetch_closed_trades()

            for trade in closed_trades:
                if trade.get("state") != "CLOSED":
                    continue

                instrument = trade["instrument"]
                units = abs(int(trade["initialUnits"]))
                realized_pl = float(trade.get("realizedPL", 0))
                open_time = pd.to_datetime(trade["openTime"])
                close_time = pd.to_datetime(trade["closeTime"])
                duration = (close_time - open_time).total_seconds() / 60

                match_idx = df[
                    (df["instrument"] == instrument) &
                    (df["profit"] == 0) &
                    (df["trade_size"] == units)
                ].index

                if not match_idx.empty:
                    idx = match_idx[0]
                    df.at[idx, "profit"] = realized_pl
                    df.at[idx, "duration"] = round(duration, 2)
                    df["cumulative_profit"] = df["profit"].cumsum()
                    logging.info(f"Updated trade {instrument} with P&L: {realized_pl:.2f}")

            df.to_csv(TRADE_LOG, index=False)
        except Exception as e:
            logging.error(f"Failed to update trade log: {e}")


if __name__ == "__main__":
    tracker = TradeOutcomeTracker()
    while True:
        tracker.update_trade_log()
        time.sleep(60)  # run every minute
