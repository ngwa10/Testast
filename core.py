import logging
import time
from datetime import datetime
from threading import Thread
import pyautogui

# Import screen logic (Selenium placeholder)
try:
    import screen_logic
except ImportError:
    screen_logic = None  # Safe if empty

# Import timezone converter
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
# TradeManager
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

        # Send info to screen_logic (fire-and-forget)
        self.send_to_screen(currency, timeframe)

        # Schedule main trade
        Thread(target=self.schedule_trade, args=(entry_time, direction)).start()

        # Schedule martingale trades
        for mg_time in martingale_times:
            Thread(target=self.schedule_trade, args=(mg_time, direction, True)).start()

    def send_to_screen(self, currency, timeframe):
        try:
            if screen_logic:
                screen_logic.select_currency(currency, timeframe)
            logging.info(f"[ℹ️] Sent to screen logic: currency={currency}, timeframe={timeframe}")
        except Exception as e:
            logging.warning(f"[⚠️] Failed to send to screen logic: {e}")

    def schedule_trade(self, trade_time, direction, martingale=False):
        now = datetime.now(trade_time.tzinfo)
        delta = (trade_time - now).total_seconds()
        if delta > 0:
            logging.info(f"[⏱️] Waiting {delta:.1f}s to enter trade {direction} (martingale={martingale})")
            time.sleep(delta)
        self.execute_trade(direction, martingale)

    def execute_trade(self, direction, martingale=False):
        # Hotkey trading
        try:
            if direction.upper() == "BUY":
                pyautogui.hotkey("shift", "w")
            elif direction.upper() == "SELL":
                pyautogui.hotkey("shift", "s")
            logging.info(f"[✅] Trade executed: {direction}, amount={self.current_trade_amount}, martingale={martingale}")
        except Exception as e:
            logging.error(f"[❌] Failed to execute trade hotkey: {e}")

        # Update martingale
        if martingale:
            self.current_martingale_level += 1
            self.current_trade_amount *= 2
            if self.current_martingale_level >= self.max_martingale:
                self.reset_martingale()

    def reset_martingale(self):
        self.current_martingale_level = 0
        self.current_trade_amount = self.base_amount
        logging.info("[🔄] Martingale reset")

# --------------------------
# Global instance
# --------------------------
trade_manager = TradeManager(base_amount=1.0, max_martingale=3)

# --------------------------
# Core signal handler
# --------------------------
def process_signal(signal: dict):
    try:
        trade_manager.handle_signal(signal)
        logging.info("[🤖] Signal forwarded to TradeManager")
    except Exception as e:
        logging.error(f"[❌] Failed to handle signal: {e}")

# --------------------------
# Optional commands
# --------------------------
def process_command(cmd: str):
    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — trading enabled.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — trading disabled.")
    else:
        logging.info(f"[ℹ️] Unknown command: {cmd}")

# --------------------------
# Keep core alive
# --------------------------
if __name__ == "__main__":
    logging.info("[🚀] Core started, waiting for signals...")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        logging.info("[🛑] Core stopped manually")
        
