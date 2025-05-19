# File: wallet_manager.py
import json
import logging
import os
import asyncio
from telegram import Bot

class TelegramNotifier:
    """
    Wrapper around Telegram Bot to send messages asynchronously.
    """
    def __init__(self, token: str, chat_id: str):
        self.bot = Bot(token=token)
        self.chat_id = chat_id

    def send_message(self, message: str) -> None:
        try:
            asyncio.run(self.bot.send_message(chat_id=self.chat_id, text=message))
            logging.info(f"Telegram alert sent: {message}")
        except Exception as e:
            logging.error(f"Telegram failed: {e}")


class WalletManager:
    """
    Manages wallet balance, session allocation, and P&L updates.
    """
    def __init__(self, wallet_file: str = "wallet.json", initial_balance: float = 1000.0):
        self.wallet_file = wallet_file
        self.wallet_balance = self._load_balance(initial_balance)
        self.session_balance = 0.0

    def _load_balance(self, initial_balance: float) -> float:
        if not os.path.exists(self.wallet_file):
            logging.info("Wallet file not found. Initializing with default balance.")
            return initial_balance
        try:
            with open(self.wallet_file, "r") as f:
                data = json.load(f)
                return data.get("wallet_balance", initial_balance)
        except Exception as e:
            logging.error(f"Error reading wallet file: {e}")
            return initial_balance

    def _save_balance(self) -> None:
        try:
            with open(self.wallet_file, "w") as f:
                json.dump({"wallet_balance": self.wallet_balance}, f)
            logging.info(f"Wallet balance saved: ${self.wallet_balance:.2f}")
        except Exception as e:
            logging.error(f"Error saving wallet file: {e}")

    def initialize_session(self, amount: float) -> float:
        """
        Deducts `amount` from wallet and starts a session with that capital.
        Returns the allocated amount if successful, else None.
        """
        if amount <= 0 or amount > self.wallet_balance:
            logging.error("Invalid or insufficient funds for session allocation.")
            return None
        self.wallet_balance -= amount
        self.session_balance = amount
        self._save_balance()
        logging.info(f"Session started with ${amount:.2f}. Remaining wallet: ${self.wallet_balance:.2f}")
        return amount

    def update_balance(self, pnl: float) -> None:
        """
        After session ends, adds back session capital + P&L to the wallet.
        """
        total_return = self.session_balance + pnl
        self.wallet_balance += total_return
        logging.info(f"Session P&L: ${pnl:.2f}. Total returned: ${total_return:.2f}")
        self.session_balance = 0.0
        self._save_balance()
