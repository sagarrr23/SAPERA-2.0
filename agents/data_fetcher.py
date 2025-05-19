import os
import logging
import time
from datetime import datetime
import pandas as pd
import talib
import oandapyV20
import oandapyV20.endpoints.pricing as pricing
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OANDA_API_KEY, OANDA_ACCOUNT_ID, INSTRUMENTS, FETCH_INTERVAL
# Configure logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "sapera_2_0.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)


class DataFetcher:
    """
    Fetch live market data from OANDA and save session data continuously.
    """
    def __init__(self, api_key, account_id):
        self.api_key = api_key
        self.account_id = account_id
        self.client = oandapyV20.API(access_token=self.api_key)
        logging.info("DataFetcher initialized.")


    def _initialize_session_file(self):
        """Generate a single session-specific file for appending data."""
        session_start_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(DATA_DIR, f"live_data_session_{session_start_time}.csv")
        logging.info(f"Session file initialized: {filename}")
        return filename

    def fetch_live_data(self, instruments="EUR_USD,USD_JPY"):
        """Fetch live data for specified instruments."""
        try:
            logging.info(f"Fetching live data for instruments: {instruments}")
            request = pricing.PricingInfo(accountID=self.account_id, params={"instruments": instruments})
            response = self.client.request(request)

            prices = response.get("prices", [])
            if not prices:
                logging.warning("No price data received.")
                return None

            data = [
                {
                    "instrument": p["instrument"],
                    "time": p["time"],
                    "bid": float(p["bids"][0]["price"]),
                    "ask": float(p["asks"][0]["price"]),
                    "close": (float(p["bids"][0]["price"]) + float(p["asks"][0]["price"])) / 2,  # Derive 'close'
                    "open": (float(p["bids"][0]["price"]) + float(p["asks"][0]["price"])) / 2,  # Use 'close' for simplicity
                    "high": (float(p["bids"][0]["price"]) + float(p["asks"][0]["price"])) / 2,  # Use 'close' for simplicity
                    "low": (float(p["bids"][0]["price"]) + float(p["asks"][0]["price"])) / 2,   # Use 'close' for simplicity
                }
                for p in prices if "bids" in p and "asks" in p
            ]

            df = pd.DataFrame(data)
            logging.info("Live data fetched successfully.")
            return df
        except Exception as e:
            logging.error(f"Error fetching live data: {e}")
            return None


    def calculate_indicators(self, df):
        """Calculate technical indicators."""
        required_columns = ["close", "open", "high", "low"]
        for column in required_columns:
            if column not in df.columns:
                raise ValueError(f"Missing required column: {column}")

        try:
            df["EMA_Fast"] = talib.EMA(df["close"], timeperiod=self.config["ema_fast"])
            df["EMA_Slow"] = talib.EMA(df["close"], timeperiod=self.config["ema_slow"])
            df["RSI"] = talib.RSI(df["close"], timeperiod=self.config["rsi_period"])
            df["ATR"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=self.config["atr_period"])
            df["ADX"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=self.config["adx_period"])
            df["Upper_Band"], df["Middle_Band"], df["Lower_Band"] = talib.BBANDS(
                df["close"], timeperiod=self.config["bollinger_period"], nbdevup=self.config["bollinger_dev"], nbdevdn=self.config["bollinger_dev"]
            )
            logging.info("Indicators calculated successfully.")
            return df
        except Exception as e:
            logging.error(f"Error calculating indicators: {e}")
            return df


    def save_data(self, df):
        """Append data to the session file and manage file rotation."""
        try:
            self._rotate_session_file()
            file_exists = os.path.isfile(self.session_file)
            df.to_csv(self.session_file, mode="a", index=False, header=not file_exists)
            logging.info(f"Data appended to {self.session_file}.")
        except Exception as e:
            logging.error(f"Error saving data: {e}")

    def _rotate_session_file(self):
        """Rotate session file if size exceeds a threshold."""
        max_file_size_mb = 50  # Maximum file size in MB
        if os.path.exists(self.session_file) and os.path.getsize(self.session_file) > max_file_size_mb * 1024 * 1024:
            rotated_file = self.session_file.replace(".csv", f"_{int(time.time())}.csv")
            os.rename(self.session_file, rotated_file)
            logging.info(f"Session file rotated: {rotated_file}")

    def run(self, instruments, interval):
        """Run the fetcher continuously, appending data to the session file."""
        logging.info("Starting DataFetcher for continuous operation...")
        try:
            while True:
                data = self.fetch_live_data(instruments)
                if data is not None:
                    data = self.calculate_indicators(data)
                    if data is not None:
                        self.save_data(data)
                else:
                    logging.warning("No data fetched in this cycle. Retrying...")

                time.sleep(interval)
        except KeyboardInterrupt:
            logging.info("DataFetcher stopped by user.")
        except Exception as e:
            logging.error(f"Unexpected error: {e}. Retrying in 1 minute...")
            time.sleep(60)


if __name__ == "__main__":
    instruments_list = ",".join(INSTRUMENTS)  # Fetch instruments from config
    fetcher = DataFetcher()
    fetcher.run(instruments=instruments_list, interval=FETCH_INTERVAL)
