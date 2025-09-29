"""
Core logic for Pocket Option Telegram Trading Bot.
Integrates with telegram_listener.py, executes trades using hotkeys via pyautogui.
Prepared to integrate with selenium_integration.py for currency detection and trade results.
"""

import time
import threading
import logging
import random
from datetime import datetime, timedelta

# pyautogui for hotkeys
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
except Exception:
    pyautogui = None

# Telegram integration
from telegram_listener import start_telegram_listener  # your working listener

# Selenium integration (to be implemented)
try:
    import selenium_integration
except Exception:
    selenium_integration = None
    print("[⚠️] selenium_integration.py not found — asset switch and win detection disabled.")

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
    def __init__(self, base_amount=1.0, max_martingale=2, switch_interval=(5, 8)):
        self.trading_active = False
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.switch_interval = switch_interval  # Seconds between Shift+TAB
        self.lock = threading.Lock()
        # Track which currencies are currently being switched
        self.switching_assets = {}
        logger.info(f"TradeManager initialized | base_amount: {base_amount}, max_martingale: {max_martingale}")

    # -------------------------
    # Command handler (sync)
    # -------------------------
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

    # -------------------------
    # Signal handler (sync)
    # -------------------------
    def handle_signal(self, signal):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Signal ignored.")
            return

        currency_pair = signal.get("currency_pair")
        direction = signal.get("direction", "BUY")
        entry_time_str = signal.get("entry_time")
        martingale_times = signal.get("martingale_times", [])

        logger.info(f"[📡] Processing signal: {signal}")
        now = datetime.now()

        # -------------------------
        # Start asset switching loop
        # -------------------------
        if currency_pair:
            with self.lock:
                if currency_pair not in self.switching_assets:
                    self.switching_assets[currency_pair] = True
                    threading.Thread(target=self._switch_asset_loop, args=(currency_pair,), daemon=True).start()

        # -------------------------
        # Schedule main trade
        # -------------------------
        if entry_time_str:
            entry_dt = self._parse_entry_time(entry_time_str)
            if entry_dt and entry_dt > now:
                self.schedule_trade(entry_time_str, direction, self.base_amount, 0, currency_pair)
            else:
                logger.warning(f"[⏱️] Entry time {entry_time_str} has passed — skipping signal.")

        # -------------------------
        # Schedule martingale trades
        # -------------------------
        for i, mg_time in enumerate(martingale_times):
            if i + 1 > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {i+1} exceeds max {self.max_martingale}; skipping.")
                break
            mg_dt = self._parse_entry_time(mg_time)
            if mg_dt and mg_dt > now:
                mg_amount = self.base_amount * (2 ** (i + 1))
                self.schedule_trade(mg_time, direction, mg_amount, i + 1, currency_pair)
            else:
                logger.warning(f"[⏱️] Martingale time {mg_time} has passed — skipping this level.")

    # -------------------------
    # Asset switching loop
    # -------------------------
    def _switch_asset_loop(self, currency_pair):
        logger.info(f"[🔁] Starting asset switch loop for {currency_pair}")
        while self.switching_assets.get(currency_pair, False) and self.trading_active:
            if selenium_integration and selenium_integration.is_currency_active(currency_pair):
                logger.info(f"[✅] Currency {currency_pair} detected — stopping switch loop")
                with self.lock:
                    self.switching_assets[currency_pair] = False
                break

            if pyautogui:
                pyautogui.keyDown('shift')
                pyautogui.press('tab')
                pyautogui.keyUp('shift')
                logger.info(f"[🎯] Sent Shift+TAB to switch asset ({currency_pair})")
            time.sleep(random.randint(*self.switch_interval))

    # -------------------------
    # Helper: parse entry time into today's datetime
    # -------------------------
    def _parse_entry_time(self, entry_time_str):
        try:
            fmt = "%H:%M:%S" if len(entry_time_str) == 8 else "%H:%M"
            today = datetime.now().date()
            parsed = datetime.strptime(entry_time_str, fmt)
            return parsed.replace(year=today.year, month=today.month, day=today.day)
        except Exception as e:
            logger.warning(f"[⚠️] Failed to parse entry time '{entry_time_str}': {e}")
            return None

    # -------------------------
    # Scheduling (threading)
    # -------------------------
    def schedule_trade(self, entry_time_str, direction, amount, martingale_level, currency_pair):
        logger.info(f"[⚡] Scheduling trade at {entry_time_str} | {direction} | {amount} | level {martingale_level}")

        def execute_trade():
            self.wait_until(entry_time_str)
            # Stop martingale if win detected
            if martingale_level > 0 and selenium_integration:
                result = selenium_integration.check_trade_result(currency_pair, martingale_level)
                if result == "WIN":
                    logger.info(f"[🏆] Win detected at level {martingale_level} — skipping trade hotkey")
                    return
            self.place_trade(amount, direction)

        threading.Thread(target=execute_trade, daemon=True).start()

    # -------------------------
    # Wait until the specific clock time today
    # -------------------------
    def wait_until(self, entry_time_str):
        try:
            fmt = "%H:%M:%S" if len(entry_time_str) == 8 else "%H:%M"
            today = datetime.now().date()
            entry_dt = datetime.strptime(entry_time_str, fmt).replace(year=today.year, month=today.month, day=today.day)
            now = datetime.now()
            delay = (entry_dt - now).total_seconds()
            if delay > 0:
                logger.info(f"[⏰] Waiting {delay:.2f}s until trade entry ({entry_dt})")
                time.sleep(delay)
            else:
                logger.warning(f"[⚱️] wait_until: target time {entry_dt} is past; skipping trade")
        except Exception as e:
            logger.warning(f"[⚠️] Could not parse entry_time '{entry_time_str}' in wait_until: {e}")

    # -------------------------
    # Place trade hotkey
    # -------------------------
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
            logger.info(f"[✅] Trade hotkey sent: {direction}")
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkeys: {e}")

# =========================
# Main
# =========================
def main():
    trade_manager = TradeManager()

    # Start Telegram listener in a separate thread
    threading.Thread(target=lambda: start_telegram_listener(
        trade_manager.handle_signal,
        trade_manager.handle_command
    ), daemon=True).start()

    # Auto-start trading
    trade_manager.handle_command("/start")

    # Keep bot running
    try:
        while True:
            time.sleep(30)
            logger.info("[💓] Bot heartbeat - running...")
    except KeyboardInterrupt:
        logger.info("[🛑] Bot stopped by KeyboardInterrupt")

if __name__ == "__main__":
    main()
