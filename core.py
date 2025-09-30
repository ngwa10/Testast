"""
Core logic for Pocket Option Telegram Trading Bot.
- Receives parsed signals from Telegram listener.
- Executes trades via pyautogui hotkeys.
- Handles martingale logic.
- Integrates with Selenium (external file).
- Randomized currency switching strokes.
- Interactive logging from logs.json.
"""

import time
import threading
import random
from datetime import datetime, timedelta
import logging
import pyautogui
import json
from core_utils import timezone_convert, get_random_log_message

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load interactive logs
try:
    with open("logs.json", "r", encoding="utf-8") as f:
        LOG_MESSAGES = json.load(f)
except FileNotFoundError:
    LOG_MESSAGES = []
    logger.warning("[⚠️] logs.json not found. Interactive logs disabled.")

# =========================
# Core Trade Manager
# =========================
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=2):
        self.trading_active = True
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.martingale_stop_flags = {}
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

        # Convert entry_time to local (Jakarta) time
        signal["entry_time_jakarta"] = timezone_convert(signal["entry_time"], signal["source"])
        logger.info(f"[📡] Processing signal: {signal}")

        # Schedule direct trade
        threading.Thread(target=self.execute_trade, args=(signal["entry_time_jakarta"], signal, 0), daemon=True).start()

        # Schedule martingale trades
        for i, mg_time in enumerate(signal.get("martingale_times", [])):
            if i + 1 > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {i+1} exceeds max {self.max_martingale}; skipping.")
                break
            mg_time_jakarta = timezone_convert(mg_time, signal["source"])
            threading.Thread(target=self.execute_trade, args=(mg_time_jakarta, signal, i+1), daemon=True).start()

    # --------------------------
    # Execute a single trade
    # --------------------------
    def execute_trade(self, entry_time_str, signal, martingale_level):
        fmt = "%H:%M"
        try:
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

        # Random interactive logs
        if LOG_MESSAGES:
            logger.info(get_random_log_message(LOG_MESSAGES))

        # ------------------------
        # Fire currency switching strokes until Selenium confirms asset ready
        # ------------------------
        logger.info(f"[🔥] Starting asset switch firing for {asset_name}")
        start_fire = datetime.now()
        while not selenium_integration.confirm_asset_ready(asset_name, signal["timeframe"], entry_time_str):
            if datetime.now() > entry_dt + timedelta(seconds=1):
                logger.info(f"[⏹️] Entry time {entry_time_str} reached, stopping firing. Trade expired.")
                return
            pyautogui.keyDown('shift'); pyautogui.press('tab'); pyautogui.keyUp('shift')
            logger.info(f"[🔥] Firing currency switching stroke for {asset_name}")
            time.sleep(random.randint(5, 9))

        logger.info(f"[✅] Asset {asset_name} ready. Placing trade...")
        self.place_trade(direction, martingale_level)

    # --------------------------
    # Place trade via pyautogui
    # --------------------------
    def place_trade(self, direction="BUY", martingale_level=0):
        amount = self.base_amount * (2 ** martingale_level)
        logger.info(f"[🎯] Placing trade: {direction} | amount: {amount} | level {martingale_level}")
        try:
            if direction.upper() == "BUY":
                pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
                logger.info(f"[🔥] Just fired a BUY stroke")
            elif direction.upper() == "SELL":
                pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
                logger.info(f"[🔥] Just fired a SELL stroke")
            else:
                logger.warning(f"[⚠️] Unknown direction '{direction}'")
            logger.info(f"[✅] Trade hotkey sent: {direction}")
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkeys: {e}")

# =========================
# Instantiate Core
# =========================
trade_manager = TradeManager()
    
