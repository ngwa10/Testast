"""
Core logic for Pocket Option Telegram Trading Bot.
Integrates with telegram_listener.py, executes trades via pyautogui.
Handles timezone conversion for UTC-4 and Cameroon signals to match UTC-3 broker time.
Works with Selenium integration to:
- Confirm asset availability
- Stop martingale on wins
- Skip trades if entry time elapsed
"""

import time
import threading
import logging
from datetime import datetime, timedelta

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
except Exception:
    pyautogui = None

from telegram_listener import client, parse_signal, events
from selenium_integration import PocketOptionSelenium

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
# Timezone Conversion
# =========================
def convert_signal_times(entry_time_str, martingale_times, message_text):
    """
    Convert signal times to broker timezone (UTC-3) based on message signature.
    """
    if message_text.endswith("💥 GET THIS SIGNAL HERE!\n💰 HOW TO START?"):
        offset = timedelta(hours=1)  # UTC-4 → UTC-3
    elif message_text.endswith("💥 TRADE THIS SIGNAL !"):
        offset = timedelta(hours=-2)  # Cameroon → UTC-3
    else:
        offset = timedelta(hours=0)  # Assume already UTC-3

    fmt = "%H:%M"

    entry_dt = datetime.strptime(entry_time_str, fmt)
    entry_dt += offset
    entry_time_converted = entry_dt.strftime(fmt)

    martingale_converted = []
    for mg in martingale_times:
        mg_dt = datetime.strptime(mg, fmt)
        mg_dt += offset
        martingale_converted.append(mg_dt.strftime(fmt))

    return entry_time_converted, martingale_converted

# =========================
# Trade Manager
# =========================
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=2):
        self.trading_active = True  # auto-start
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.martingale_stop_flags = {}  # stop martingale per trade if Selenium detects win
        self.selenium = PocketOptionSelenium(self)
        self.selenium.start_result_monitor()
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

    def handle_signal(self, signal, raw_message=""):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Signal ignored.")
            return

        # Convert timezones
        entry_time, martingale_times = convert_signal_times(
            signal.get("entry_time"),
            signal.get("martingale_times", []),
            raw_message
        )
        signal["entry_time"] = entry_time
        signal["martingale_times"] = martingale_times

        logger.info(f"[📡] Processing signal: {signal}")

        # Set timeframe via Selenium
        self.selenium.set_timeframe(signal["timeframe"])

        # Schedule trades
        self.schedule_trade(entry_time, signal.get("direction", "BUY"), self.base_amount, 0, signal["currency_pair"])

        for i, mg_time in enumerate(signal.get("martingale_times", [])):
            if i + 1 > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {i+1} exceeds max {self.max_martingale}; skipping.")
                break
            mg_amount = self.base_amount * (2 ** (i + 1))
            self.schedule_trade(mg_time, signal.get("direction", "BUY"), mg_amount, i + 1, signal["currency_pair"])

    def schedule_trade(self, entry_time_str, direction, amount, martingale_level, currency_pair):
        logger.info(f"[⚡] Scheduling trade at {entry_time_str} | {direction} | {amount} | level {martingale_level} | {currency_pair}")

        def execute_trade():
            self.wait_until(entry_time_str)

            # Confirm asset and entry time via Selenium
            if not self.selenium.confirm_asset_ready(currency_pair, entry_time_str):
                logger.info(f"[🛑] Trade skipped: Asset '{currency_pair}' not ready or entry time elapsed")
                return

            key = f"{currency_pair}_{martingale_level}_{entry_time_str}"
            if self.martingale_stop_flags.get(key):
                logger.info(f"[🛑] Trade skipped due to win: {key}")
                return

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
            logger.info(f"[✅] Trade hotkey sent: {direction}")
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkeys: {e}")


# =========================
# Main
# =========================
def main():
    trade_manager = TradeManager()

    @client.on(events.NewMessage(chats=-1003033183667))
    async def listener(event):
        try:
            text = event.message.message
            signal = parse_signal(text)
            if signal:
                trade_manager.handle_signal(signal, raw_message=text)
        except Exception as e:
            logger.error(f"[❌] Error processing signal: {e}")

    try:
        logger.info("[⚙️] Connecting to Telegram...")
        client.start(bot_token="8477806088:AAGEXpIAwN5tNQM0hsCGqP-otpLJjPJLmWA")
        logger.info("[✅] Connected. Listening for signals...")
        client.run_until_disconnected()
    except Exception as e:
        logger.error(f"[❌] Telegram listener failed: {e}")


if __name__ == "__main__":
    main()
