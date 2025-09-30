"""
Core logic for Pocket Option Telegram Trading Bot.
- Receives parsed signals from Telegram listener.
- Executes trades via pyautogui hotkeys.
- Automatically switches assets (randomized firing 🔥 every 5–9 seconds).
- Handles martingale logic.
- Integrates with Selenium for asset confirmation, timeframe adjustment, and WIN detection.
"""

import time
import threading
import random
from datetime import datetime, timedelta
import logging
import pyautogui
import json
from pytz import timezone
from selenium_integration import PocketOptionSelenium  # 👈 Your Selenium class

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# =========================
# Load Humanized Logs
# =========================
try:
    with open("logs.json", "r") as f:
        LOG_MESSAGES = json.load(f)
except FileNotFoundError:
    LOG_MESSAGES = ["[ℹ️] Precision bot is ready! Waiting for the next signal..."]

# =========================
# Core Trade Manager
# =========================
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=2):
        self.trading_active = True
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.martingale_stop_flags = {}
        self.trade_increments = {}  # track how many times trade amount increased
        self.selenium_integration = PocketOptionSelenium(self)
        self.selenium_integration.start_result_monitor()
        logger.info(f"TradeManager initialized | base_amount: {base_amount}, max_martingale: {max_martingale}")

    # --------------------------
    # Command Handler
    # --------------------------
    def handle_command(self, command):
        cmd = command.strip().lower()
        if cmd.startswith("/start"):
            self.trading_active = True
            logger.info("[🚀] Trading started")
        elif cmd.startswith("/stop"):
            self.trading_active = False
            logger.info("[⏹️] Trading stopped")
        elif cmd.startswith("/status"):
            status = "ACTIVE" if self.trading_active else "PAUSED"
            logger.info(f"[ℹ️] Trading status: {status}")
        else:
            logger.info(f"[ℹ️] Unknown command: {command}")

    # --------------------------
    # Signal Handler
    # --------------------------
    def handle_signal(self, signal):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Signal ignored.")
            return
        logger.info(f"[📡] Processing signal: {signal}")

        # Schedule direct trade
        entry_time = signal.get("entry_time")
        if entry_time:
            threading.Thread(target=self.execute_trade, args=(entry_time, signal, 0), daemon=True).start()

        # Schedule martingale trades
        for i, mg_time in enumerate(signal.get("martingale_times", [])):
            if i + 1 > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {i+1} exceeds max {self.max_martingale}; skipping.")
                break
            threading.Thread(target=self.execute_trade, args=(mg_time, signal, i+1), daemon=True).start()

    # --------------------------
    # Execute a single trade
    # --------------------------
    def execute_trade(self, entry_time_str, signal, martingale_level):
        fmt = "%H:%M"
        try:
            # Convert entry time from signal timezone to Jakarta timezone
            entry_dt = datetime.strptime(entry_time_str, fmt)
            now = datetime.now()
            delay = (entry_dt - now).total_seconds()
            if delay > 0:
                logger.info(f"[⏰] Waiting {delay:.2f}s until trade entry")
                time.sleep(delay)
        except Exception as e:
            logger.warning(f"[⚠️] Could not parse entry_time '{entry_time_str}': {e}")
            return

        asset_name = signal["currency_pair"]
        direction = signal.get("direction", "BUY")
        timeframe = signal.get("timeframe", "M1")

        # Adjust timeframe via Selenium
        self.selenium_integration.set_timeframe(timeframe)

        # Firing currency switching strokes until asset is ready
        logger.info(f"[🔥] Starting asset switch firing for {asset_name}")
        while not self.selenium_integration.confirm_asset_ready(asset_name, entry_time_str):
            if datetime.now() > entry_dt + timedelta(seconds=1):
                logger.info(f"[⏹️] Entry time {entry_time_str} reached, stopping firing. Trade expired.")
                return
            pyautogui.hotkey('shift', 'tab')  # Switch currency
            logger.info(f"[🔥] Firing currency switching stroke for {asset_name}")
            time.sleep(random.randint(5,9))

        logger.info(f"[✅] Asset {asset_name} ready. Placing trade now...")

        # Place trade
        self.place_trade(direction, martingale_level)

    # --------------------------
    # Place trade via pyautogui
    # --------------------------
    def place_trade(self, direction="BUY", martingale_level=0):
        amount = self.base_amount * (2 ** martingale_level)
        logger.info(f"[🎯] Placing trade: {direction} | amount: {amount} | level {martingale_level}")

        # Increase trade amount if martingale
        if martingale_level > 0:
            pyautogui.hotkey('shift', 'd')
            self.trade_increments[direction] = self.trade_increments.get(direction, 0) + 1
            logger.info(f"[🔥] Increased trade amount for martingale level {martingale_level}")

        # Send trade hotkey
        if direction.upper() == "BUY":
            pyautogui.hotkey('shift', 'w')
            logger.info(f"[🔥] Just fired a BUY stroke")
        elif direction.upper() == "SELL":
            pyautogui.hotkey('shift', 's')
            logger.info(f"[🔥] Just fired a SELL stroke")
        else:
            logger.warning(f"[⚠️] Unknown trade direction '{direction}'")

        # Decrease trade amount back to default if WIN or max martingale reached
        def reset_trade_amount():
            increments = self.trade_increments.get(direction, 0)
            if increments > 0:
                for _ in range(increments):
                    pyautogui.hotkey('shift', 'a')
                    logger.info(f"[🔥] Resetting trade amount for {direction}")
                self.trade_increments[direction] = 0

        # Delay slightly to allow Selenium to detect WIN
        threading.Timer(0.5, reset_trade_amount).start()

        # Randomized humanized logs
        logger.info(random.choice(LOG_MESSAGES))

# =========================
# Instantiate Core
# =========================
trade_manager = TradeManager()
            
