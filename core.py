import logging
import time
from datetime import datetime
from threading import Thread
import pyautogui

# Import stub for screen interactions
try:
    import screen_logic
except ImportError:
    screen_logic = None
    logging.warning("[⚠️] screen_logic not available, Selenium commands will be ignored.")

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

        # Send instruction to screen_logic (fire-and-forget)
        self.send_to_screen_logic(currency, timeframe)

        # Schedule main trade
        Thread(target=self.schedule_trade, args=(entry_time, direction)).start()

        # Schedule martingale trades
        for mg_time in martingale_times:
            Thread(target=self.schedule_trade, args=(mg_time, direction, True)).start()

    def send_to_screen_logic(self, currency, timeframe):
        if screen_logic:
            try:
                screen_logic.select_currency(currency)
                screen_logic.select_timeframe(timeframe)
                logging.info(f"[ℹ️] Sent currency={currency} and timeframe={timeframe} to screen_logic")
            except Exception as e:
                logging.error(f"[❌] Failed to send to screen_logic: {e}")
        else:
            logging.info(f"[ℹ️] screen_logic not available — ignoring currency={currency}, timeframe={timeframe}")

    def schedule_trade(self, trade_time, direction, martingale=False):
        now = datetime.now(trade_time.tzinfo)
        delta = (trade_time - now).total_seconds()
        if delta > 0:
            logging.info(f"[⏱️] Waiting {delta:.1f}s to enter trade {direction} (martingale={martingale})")
            time.sleep(delta)
        self.execute_trade(direction, martingale)

    def execute_trade(self, direction, martingale=False):
        # Execute trade using hotkeys
        hotkey_map = {"BUY": "shift+w", "SELL": "shift+s"}
        if direction in hotkey_map:
            self.press_hotkey(hotkey_map[direction])

        logging.info(f"[✅] Trade executed: direction={direction}, amount={self.current_trade_amount}, martingale={martingale}")

        # Update martingale
        if martingale:
            self.current_martingale_level += 1
            self.current_trade_amount *= 2  # Double trade amount for next level
            if self.current_martingale_level > self.max_martingale:
                self.reset_martingale()

    def press_hotkey(self, hotkey):
        try:
            pyautogui.hotkey(*hotkey.split("+"))
            logging.info(f"[⌨️] Hotkey pressed: {hotkey}")
        except Exception as e:
            logging.error(f"[❌] Failed to press hotkey {hotkey}: {e}")

    def reset_martingale(self):
        self.current_martingale_level = 0
        self.current_trade_amount = self.base_amount
        logging.info("[🔄] Martingale reset")


# Global instance
trade_manager = TradeManager(base_amount=1.0, max_martingale=3)
                
