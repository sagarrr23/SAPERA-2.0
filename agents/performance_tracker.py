import os
import logging
import pandas as pd
from datetime import datetime

# Setup logging
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "performance_tracker.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

class PerformanceTracker:
    """
    Tracks trading session results and saves summary performance reports.
    """
    def __init__(self, trade_log_path="logs/trade_log.csv"):
        self.trade_log_path = trade_log_path
        logging.info(f"PerformanceTracker initialized with trade log: {self.trade_log_path}")

    def load_trades(self):
        if not os.path.exists(self.trade_log_path):
            logging.warning("Trade log not found.")
            return None
        try:
            df = pd.read_csv(self.trade_log_path)
            df["cumulative_profit"] = df["profit"].cumsum()
            logging.info(f"Loaded {len(df)} trades.")
            return df
        except Exception as e:
            logging.error(f"Failed to read trade log: {e}")
            return None

    def compute_metrics(self, df):
        try:
            total = len(df)
            wins = len(df[df["profit"] > 0])
            losses = len(df[df["profit"] <= 0])
            win_rate = (wins / total * 100) if total else 0
            net_profit = df["profit"].sum()
            avg_duration = df["duration"].mean() if "duration" in df.columns else 0
            drawdown = self.calculate_drawdown(df["cumulative_profit"])

            return {
                "total_trades": total,
                "winning_trades": wins,
                "losing_trades": losses,
                "win_rate (%)": round(win_rate, 2),
                "net_profit": round(net_profit, 2),
                "average_duration": round(avg_duration, 2),
                "max_drawdown (%)": round(drawdown * 100, 2) if drawdown is not None else None
            }
        except Exception as e:
            logging.error(f"Metric calculation failed: {e}")
            return None

    def calculate_drawdown(self, equity_curve):
        try:
            peak = equity_curve.cummax()
            dd = (equity_curve - peak) / peak
            return dd.min()
        except Exception as e:
            logging.error(f"Drawdown calculation failed: {e}")
            return None

    def save_report(self, metrics):
        try:
            os.makedirs("results", exist_ok=True)
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"results/session_report_{now}.csv"
            pd.DataFrame([metrics]).to_csv(path, index=False)
            logging.info(f"Saved report to {path}")
        except Exception as e:
            logging.error(f"Report save failed: {e}")

    def run(self):
        df = self.load_trades()
        if df is not None:
            metrics = self.compute_metrics(df)
            if metrics:
                self.save_report(metrics)
                return metrics
        return None


if __name__ == "__main__":
    tracker = PerformanceTracker()
    result = tracker.run()
    if result:
        print("Session Metrics:")
        for k, v in result.items():
            print(f"{k}: {v}")
    else:
        print("No performance report generated.")
