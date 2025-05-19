# ui/dashboard.py

import os
import json
import streamlit as st
import pandas as pd
from datetime import datetime

# Paths
WALLET_FILE = "wallet.json"
TRADE_LOG = "logs/trade_log.csv"
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

# Page setup
st.set_page_config(page_title="SAPERA 2.0 Dashboard", layout="wide")
st.title("📊 SAPERA 2.0 Trading Bot Dashboard")

# =========================
# Section: Wallet Overview
# =========================
st.header("💼 Wallet Balance")

if os.path.exists(WALLET_FILE):
    with open(WALLET_FILE, "r") as f:
        wallet_data = json.load(f)
        balance = wallet_data.get("wallet_balance", 0.0)
        st.metric("Available Wallet Balance (USD)", f"${balance:,.2f}")
else:
    st.warning("wallet.json not found.")

# =========================
# Section: Trade Log
# =========================
st.header("📜 Trade Log")

if os.path.exists(TRADE_LOG):
    trades_df = pd.read_csv(TRADE_LOG)

    # Format time column
    if "time" in trades_df.columns:
        trades_df["time"] = pd.to_datetime(trades_df["time"])

    st.dataframe(trades_df.sort_values("time", ascending=False), use_container_width=True)
else:
    st.warning("Trade log not found.")

# =========================
# Section: Performance Metrics
# =========================
st.header("📈 Performance Summary")

if os.path.exists(TRADE_LOG) and not trades_df.empty:
    total = len(trades_df)
    wins = len(trades_df[trades_df["profit"] > 0])
    losses = len(trades_df[trades_df["profit"] <= 0])
    win_rate = (wins / total * 100) if total else 0
    net_profit = trades_df["profit"].sum()
    avg_duration = trades_df["duration"].mean() if "duration" in trades_df.columns else 0

    # Drawdown
    trades_df["cumulative_profit"] = trades_df["profit"].cumsum()
    equity_curve = trades_df["cumulative_profit"]
    peak = equity_curve.cummax()
    drawdown = ((equity_curve - peak) / peak).min() * 100 if not equity_curve.empty else 0

    # Metrics Display
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Trades", total)
    col2.metric("Win Rate", f"{win_rate:.2f}%")
    col3.metric("Net Profit", f"${net_profit:.2f}")

    col4, col5 = st.columns(2)
    col4.metric("Avg Duration (mins)", f"{avg_duration:.1f}")
    col5.metric("Max Drawdown", f"{drawdown:.2f}%")

    # Export session summary
    if st.button("📥 Export Session Report"):
        now = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{RESULTS_DIR}/session_report_{now}.csv"
        trades_df.to_csv(filename, index=False)
        st.success(f"Report saved to: {filename}")
else:
    st.info("No trades to calculate performance yet.")
