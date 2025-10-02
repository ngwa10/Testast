import logging
import time
from datetime import datetime
from threading import Thread
import pytz
import pyautogui

# Import the timezone conversion utility
from core_utils import timezone_convert

# --------------------------
# Logging setup
# --------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

# --------------------------
# TradeManager class
# --------------------------
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=3):
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.current_trade_amount = base_amount
        self.current_martingale_level = 0

    def handle_signal(self, signal: dict):
        currency = signal['currency_pair']
        timeframe = signal['timeframe']
        direction = signal['direction']
        entry_time = signal['entry_time']
        martingale_times = signal.get('martingale_times', [])

        # Send instruction to Selenium (fire-and-forget)
        self.send_to_selenium(currency, timeframe)

        # Schedule main trade
        Thread(target=self.schedule_trade, args=(entry_time, direction)).start()

        # Schedule martingale trades
        for mg_time in martingale_times:
            Thread(target=self.schedule_trade, args=(mg_time, direction, True)).start()

    def send_to_selenium(self, currency, timeframe):
        # Fire-and-forget Selenium instruction
        logging.info(f"[ℹ️] Sending to Selenium: currency={currency}, timeframe={timeframe}")

    def schedule_trade(self, trade_time, direction, martingale=False):
        # Wait until the scheduled trade time
        now = datetime.now(trade_time.tzinfo)
        delta = (trade_time - now).total_seconds()
        if delta > 0:
            logging.info(f"[⏱️] Waiting {delta:.1f}s to enter trade {direction} (martingale={martingale})")
            time.sleep(delta)
        self.execute_trade(direction, martingale)

    def execute_trade(self, direction, martingale=False):
        # Execute trade using hotkeys
        if direction == "BUY":
            self.press_hotkey("shift+w")
        elif direction == "SELL":
            self.press_hotkey("shift+s")

        logging.info(f"[✅] Trade executed: direction={direction}, amount={self.current_trade_amount}, martingale={martingale}")

        # Update martingale
        if martingale:
            self.current_martingale_level += 1
            self.current_trade_amount *= 2  # Double trade amount for next level
            if self.current_martingale_level > self.max_martingale:
                self.reset_martingale()

    def press_hotkey(self, hotkey):
        # Use pyautogui to press hotkeys
        try:
            pyautogui.hotkey(*hotkey.split("+"))
            logging.info(f"[⌨️] Hotkey pressed: {hotkey}")
        except Exception as e:
            logging.error(f"[❌] Failed to press hotkey {hotkey}: {e}")

    def reset_martingale(self):
        self.current_martingale_level = 0
        self.current_trade_amount = self.base_amount
        logging.info("[🔄] Martingale reset")

# --------------------------
# Global TradeManager instance
# --------------------------
trade_manager = TradeManager(base_amount=1.0, max_martingale=3)

# --------------------------
# Core signal handler (called by telegram_callbacks.py)
# --------------------------
def process_signal(signal: dict):
    """
    signal = {
        "currency_pair": "EUR/USD",
        "direction": "BUY",
        "entry_time": datetime object (tz-aware),
        "timeframe": "M1",
        "martingale_times": [datetime1, datetime2, ...]
    }
    """
    try:
        trade_manager.handle_signal(signal)
        logging.info("[🤖] Signal forwarded to TradeManager for execution.")
    except Exception as e:
        logging.error(f"[❌] Failed to handle signal: {e}")

# --------------------------
# Command handler (optional)
# --------------------------
def process_command(cmd: str):
    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — trading enabled.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — trading disabled.")
    else:
        logging.info(f"[ℹ️] Unknown command received: {cmd}")
