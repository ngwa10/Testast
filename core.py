"""
Core logic for Pocket Option Telegram Trading Bot.
Integrates with telegram_listener.py, executes trades using hotkeys via pyautogui.
No Chrome login/credential handling here.
"""

import time
import threading
import logging
from datetime import datetime

# pyautogui for hotkeys
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
except Exception:
    pyautogui = None

# Telegram integration
from telegram_listener import start_telegram_listener  # your working listener

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
# Trade Manager
# =========================
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=2):
        self.trading_active = False
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        logger.info(f"TradeManager initialized | base_amount: {base_amount}, max_martingale: {max_martingale}")

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

    def handle_signal(self, signal):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Signal ignored.")
            return
        logger.info(f"[📡] Processing signal: {signal}")

        # Schedule direct trade
        entry_time = signal.get("entry_time")
        if entry_time:
            self.schedule_trade(entry_time, signal.get("direction", "BUY"), self.base_amount, 0)

        # Schedule martingale trades
        for i, mg_time in enumerate(signal.get("martingale_times", [])):
            if i + 1 > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {i+1} exceeds max {self.max_martingale}; skipping.")
                break
            mg_amount = self.base_amount * (2 ** (i + 1))
            self.schedule_trade(mg_time, signal.get("direction", "BUY"), mg_amount, i + 1)

    def schedule_trade(self, entry_time_str, direction, amount, martingale_level):
        logger.info(f"[⚡] Scheduling trade at {entry_time_str} | {direction} | {amount} | level {martingale_level}")

        def execute_trade():
            self.wait_until(entry_time_str)
            self.place_trade(amount, direction)

        threading.Thread(target=execute_trade, daemon=True).start()

    def wait_until(self, entry_time_str):
        try:
            fmt = "%H:%M:%S" if len(entry_time_str) == 8 else "%H:%M"
            entry_dt = datetime.strptime(entry_time_str, fmt)
            now = datetime.now()
            delay = (entry_dt - now).total_seconds()
            if delay > 0:
                logger.info(f"[⏰] Waiting {delay:.2f}s until trade entry")
                time.sleep(delay)
        except Exception as e:
            logger.warning(f"[⚠️] Could not parse entry_time '{entry_time_str}': {e}")

    def place_trade(self, amount, direction="BUY"):
        logger.info(f"[🎯] Placing trade: {direction} | amount: {amount}")
        if not pyautogui:
            logger.warning("[⚠️] pyautogui not available; cannot send hotkeys")
            return
        try:
            if direction.upper() == "BUY":
                pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
            elif direction.upper() == "SELL":
                pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
            else:
                logger.warning(f"[⚠️] Unknown direction '{direction}'")
            logger.info(f"[✅] Trade hotkey sent: {direction}")
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkeys: {e}")

# =========================
# Main
# =========================
def main():
    trade_manager = TradeManager()

    # Start Telegram listener
    start_telegram_listener(trade_manager.handle_signal, trade_manager.handle_command)

    # Keep bot running
    while True:
        time.sleep(30)
        logger.info("[💓] Bot heartbeat - running...")

if __name__ == "__main__":
    main()
