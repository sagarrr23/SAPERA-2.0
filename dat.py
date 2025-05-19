import oandapyV20
import oandapyV20.endpoints.instruments as instruments
import pandas as pd
from datetime import datetime, timedelta

# Initialize the OANDA API client
client = oandapyV20.API(access_token="bf360920d5432b7f61bd21f12b447aa6-7326b27f0f16ffc655f5b6008326ca0a")

# Parameters
instrument = "EUR_USD"
granularity = "M1"  # 1-minute candles
start_date = "2025-01-01T00:00:00Z"  # Start date
end_date = "2025-12-31T23:59:59Z"    # End date
max_candles_per_request = 5000  # Maximum allowed candles per request
output_file = f"data/{instrument}_historical_data.csv"  # Save path for data

# Ensure the output directory exists
import os
os.makedirs(os.path.dirname(output_file), exist_ok=True)

# Helper function to fetch candles in chunks
def fetch_candles(instrument, start_date, end_date, granularity, max_candles_per_request):
    """
    Fetch historical data from OANDA API in chunks.
    Args:
        instrument: Currency pair (e.g., 'EUR_USD').
        start_date: Start date for fetching data (ISO 8601 format).
        end_date: End date for fetching data (ISO 8601 format).
        granularity: Timeframe for the candles (e.g., 'M1', 'H1').
        max_candles_per_request: Maximum candles to fetch per request.
    Returns:
        DataFrame containing historical data.
    """
    current_date = datetime.strptime(start_date, "%Y-%m-%dT%H:%M:%SZ")
    end_date_obj = datetime.strptime(end_date, "%Y-%m-%dT%H:%M:%SZ")
    all_data = []

    while current_date < end_date_obj:
        params = {
            "from": current_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "granularity": granularity,
            "count": max_candles_per_request
        }
        print(f"Fetching data starting from {params['from']}...")

        try:
            candles = instruments.InstrumentsCandles(instrument=instrument, params=params)
            response = client.request(candles)

            for candle in response.get("candles", []):
                if candle["complete"]:
                    all_data.append({
                        "time": candle["time"],
                        "open": float(candle["mid"]["o"]),
                        "high": float(candle["mid"]["h"]),
                        "low": float(candle["mid"]["l"]),
                        "close": float(candle["mid"]["c"]),
                        "volume": int(candle["volume"])  # Volume for the candle
                    })

            # Move to the next chunk
            if response.get("candles"):
                current_date = datetime.strptime(response["candles"][-1]["time"], "%Y-%m-%dT%H:%M:%SZ") + timedelta(minutes=1)
            else:
                print("No more data available.")
                break

        except Exception as e:
            print(f"Error fetching data: {e}")
            break

    return pd.DataFrame(all_data)

# Fetch and save the data
print(f"Fetching historical data for {instrument}...")
historical_data = fetch_candles(instrument, start_date, end_date, granularity, max_candles_per_request)

if not historical_data.empty:
    historical_data.to_csv(output_file, index=False)
    print(f"Historical data saved to {output_file}")
else:
    print("No data fetched.")
