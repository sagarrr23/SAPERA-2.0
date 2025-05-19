# scripts/run_forever.py

import os
import time
import subprocess
import logging
from datetime import datetime

# Configuration
INTERVAL_MINUTES = 5  # How often to run main.py
MAIN_SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'main.py'))

# Logging
os.makedirs("logs", exist_ok=True)
LOG_FILE = "logs/run_forever.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def run_main():
    PYTHON_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'venv310', 'Scripts', 'python.exe'))
    try:
        logging.info("🟢 Running main.py")
        result = subprocess.run([PYTHON_PATH, MAIN_SCRIPT_PATH], capture_output=True, text=True)
        logging.info(f"✅ main.py completed with return code {result.returncode}")
        if result.stdout:
            logging.info("STDOUT:\n" + result.stdout.strip())
        if result.stderr:
            logging.warning("STDERR:\n" + result.stderr.strip())
    except Exception as e:
        logging.error(f"❌ Failed to run main.py: {e}")


def main_loop():
    logging.info("🔁 Starting SAPERA 2.0 auto-run loop.")
    while True:
        run_main()
        logging.info(f"⏳ Waiting {INTERVAL_MINUTES} minutes until next run...")
        time.sleep(INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logging.info("🛑 Auto-run loop terminated manually.")
