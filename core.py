"""
core.py — TradeManager & Core logic (patched with robust error handling)

Notes:
- Exposes async signal_callback(signal) and command_callback(cmd) for your external telegram_listener.
- Expects signals to include tz-aware datetimes for entry_time and martingale_times.
- Instantiates PocketOptionSelenium (starts Chrome). Make sure chromedriver path in selenium_integration.py is correct.
- hotkey_mode toggles pyautogui usage (requires Xvfb/VNC/display).
"""

import logging
import time
import random
import threading
import json
from datetime import datetime, timedelta
import pytz
import pyautogui

from selenium_integration import PocketOptionSelenium

# --------------------
# Logging
# --------------------
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s: %(message)s',
                    datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)

# --------------------
# Hotkey behavior
# --------------------
pyautogui.FAILSAFE = False

# --------------------
# Read logs.json messages (optional)
# --------------------
try:
    with open("logs.json", "r", encoding="utf-8") as f:
        LOG_MESSAGES = json.load(f)
except Exception:
    LOG_MESSAGES = ["Precision is warming up.", "Desmond's bot is on duty — targets locked."]

def random_log():
    return random.choice(LOG_MESSAGES) if LOG_MESSAGES else ""

# --------------------
# TradeManager
# --------------------
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=3, hotkey_mode=True):
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.hotkey_mode = hotkey_mode

        self.trading_active = True
        self.pending_trades = []            # list of trade dicts
        self._pending_lock = threading.Lock()
        self.increase_counts = {}          # currency -> number of increases applied for this "position"

        # initialize selenium integration (starts Chrome & monitors)
        self.selenium = PocketOptionSelenium(self, headless=False, hotkey_mode=hotkey_mode)
        logger.info("[ℹ️] TradeManager initialized | base_amount: %.2f, max_martingale: %d, hotkey_mode=%s" %
                    (self.base_amount, self.max_martingale, self.hotkey_mode))

    # -----------------
    # context manager for pending lock
    # -----------------
    def pending_lock(self):
        class _Ctx:
            def __init__(self, lock):
                self.lock = lock
            def __enter__(self):
                self.lock.acquire()
                return self.lock
            def __exit__(self, exc_type, exc, tb):
                self.lock.release()
        return _Ctx(self._pending_lock)

    # -----------------
    # called by telegram command
    # -----------------
    def handle_command(self, cmd: str):
        try:
            cmd = cmd.strip().lower()
            if cmd.startswith("/start"):
                self.trading_active = True
                logger.info("[🚀] Trading started.")
            elif cmd.startswith("/stop"):
                self.trading_active = False
                logger.info("[⏹️] Trading stopped.")
            elif cmd.startswith("/status"):
                logger.info("[ℹ️] Trading: ACTIVE" if self.trading_active else "[ℹ️] Trading: PAUSED")
            else:
                logger.info(f"[ℹ️] Unknown command: {cmd}")
        except Exception as e:
            logger.error(f"[❌] Error handling command '{cmd}': {e}")

    # -----------------
    # schedule trade
    # -----------------
    def schedule_trade(self, entry_dt, signal, martingale_level):
        try:
            now = datetime.now(entry_dt.tzinfo)
            delay = (entry_dt - now).total_seconds()
            if delay <= 0:
                logger.info(f"[⏹️] Signal entry time {entry_dt.strftime('%H:%M:%S')} passed. Skipping.")
                return
            t = threading.Timer(delay, self.execute_trade, args=(entry_dt, signal, martingale_level))
            t.daemon = True
            t.start()
            logger.info(f"[🗓️] Scheduled trade {signal['currency_pair']} level {martingale_level} at {entry_dt.strftime('%H:%M:%S')}")
        except Exception as e:
            logger.error(f"[❌] Error scheduling trade for {signal.get('currency_pair')} level {martingale_level}: {e}")

    # -----------------
    # handle incoming signal
    # -----------------
    def handle_signal(self, signal: dict):
        try:
            if not self.trading_active:
                logger.info("[⏸️] Trading paused. Ignoring signal.")
                return

            logger.info(f"[📡] Received signal: {signal} | {random_log()}")

            entry_val = signal.get("entry_time")
            if not entry_val or not isinstance(entry_val, datetime):
                logger.warning("[⚠️] signal.entry_time must be a timezone-aware datetime. Skipping.")
                return

            entry_dt = entry_val
            signal['entry_time'] = entry_dt

            # normalize martingale times
            mg_times = signal.get("martingale_times", []) or []
            signal['martingale_times'] = mg_times

            # Normalize currency format: remove slash if present and uppercase
            raw_pair = signal.get('currency_pair', "")
            norm_pair = raw_pair.replace("/", "").replace(" ", "").upper()
            signal['currency_pair'] = norm_pair

            timeframe = signal.get('timeframe', 'M1').upper()

            # Inform selenium to prepare for base and martingale entries (blocking prepare)
            logger.info(f"[🛰️] Asking Selenium to prepare asset/timeframe for base and martingales for {norm_pair}")
            prepared_base = self.selenium.prepare_for_trade(norm_pair, entry_dt, timeframe)
            if not prepared_base:
                logger.warning(f"[⚠️] Selenium failed to fully prepare for base trade {norm_pair}/{timeframe}. (Proceeding anyway)")

            # Prepare martingales as well (fire-and-forget prepares)
            for mg_dt in signal['martingale_times']:
                try:
                    self.selenium.prepare_for_trade(norm_pair, mg_dt, timeframe)
                except Exception as e:
                    logger.warning(f"[⚠️] Selenium prepare_for_trade failed for martingale time {mg_dt}: {e}")

            # Schedule base and martingale trades
            self.schedule_trade(entry_dt, signal, 0)
            for idx, mg_dt in enumerate(signal['martingale_times']):
                level = idx + 1
                if level > self.max_martingale:
                    logger.warning(f"[⚠️] Skipping martingale level {level} (exceeds max).")
                    break
                self.schedule_trade(mg_dt, signal, level)

        except Exception as e:
            logger.error(f"[❌] Error handling signal: {e}")

    # -----------------
    # Execute trade (base or martingale)
    # -----------------
    def execute_trade(self, entry_dt, signal, martingale_level):
        try:
            currency = signal['currency_pair']
            direction = signal.get('direction', 'BUY')
            timeframe = signal.get('timeframe', 'M1')
            trade_id = f"{currency}_{entry_dt.strftime('%H%M%S')}_{martingale_level}_{int(time.time()*1000)}"
            logger.info(f"[🎯] READY to place trade {trade_id} — {direction} level {martingale_level}")

            if martingale_level > 0:
                time.sleep(0.5)
                quick = self.selenium.detect_trade_result()
                if quick == "WIN":
                    logger.info(f"[✔️] Selenium reported WIN during 0.5s check - skipping martingale level {martingale_level} for {currency}.")
                    return

            with self.pending_lock():
                pending = {
                    "id": trade_id,
                    "currency_pair": currency,
                    "level": martingale_level,
                    "entry_dt": entry_dt,
                    "placed_at": None,
                    "resolved": False,
                    "result": None,
                    "increase_count": 0
                }
                self.pending_trades.append(pending)

            if self.hotkey_mode and martingale_level > 0:
                try:
                    pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
                    with self.pending_lock():
                        pending['increase_count'] += 1
                        self.increase_counts[currency] = self.increase_counts.get(currency, 0) + 1
                    logger.info(f"[⬆️] Martingale increase applied for {currency} (level {martingale_level})")
                except Exception as e:
                    logger.warning(f"[⚠️] Failed to send martingale increase hotkey: {e}")

            try:
                if self.hotkey_mode:
                    if direction.upper() == 'BUY':
                        pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
                    else:
                        pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
                    logger.info(f"[⌨️] Sent trade hotkey for {currency} ({direction})")
                else:
                    logger.info("[ℹ️] Hotkey mode disabled; skipping hotkey press.")
            except Exception as e:
                logger.error(f"[❌] Error sending trade hotkey: {e}")

            with self.pending_lock():
                pending['placed_at'] = datetime.now(entry_dt.tzinfo)

            if self.hotkey_mode and martingale_level == 0:
                def delayed_increase():
                    try:
                        wait_sec = random.uniform(10, 30)
                        time.sleep(wait_sec)
                        with self.pending_lock():
                            still_pending = (not pending['resolved'])
                        if still_pending:
                            pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
                            with self.pending_lock():
                                pending['increase_count'] += 1
                                self.increase_counts[currency] = self.increase_counts.get(currency, 0) + 1
                            logger.info(f"[⬆️] Delayed increase applied for {currency} after {int(wait_sec)}s")
                    except Exception as e:
                        logger.warning(f"[⚠️] Failed delayed increase: {e}")
                threading.Thread(target=delayed_increase, daemon=True).start()

            try:
                self.selenium.watch_trade_for_result(currency, pending['placed_at'], timeframe=timeframe, timeout=90)
                logger.info(f"[👀] Selenium instructed to watch trade {trade_id}")
            except Exception as e:
                logger.warning(f"[⚠️] Selenium watch_trade_for_result failed: {e}")

        except Exception as e:
            logger.error(f"[❌] Error executing trade: {e}")

    # -----------------
    # Called by Selenium when a result is detected
    # -----------------
    def on_trade_result(self, currency_pair, result):
        try:
            logger.info(f"[📣] Result callback: {currency_pair} -> {result}")
            with self.pending_lock():
                pending = None
                sorted_trades = sorted([t for t in self.pending_trades if t.get('placed_at')],
                                       key=lambda x: x['placed_at'] or datetime.max, reverse=True)
                for t in sorted_trades:
                    if t['currency_pair'] == currency_pair and not t['resolved']:
                        pending = t
                        break
                if not pending:
                    logger.info(f"[ℹ️] No pending trade matched for {currency_pair}")
                    return
                pending['resolved'] = True
                pending['result'] = result
                increases = self.increase_counts.get(currency_pair, 0)

            if result == "WIN":
                if increases > 0 and self.hotkey_mode:
                    logger.info(f"[↩️] WIN detected — reverting {increases} increases for {currency_pair}")
                    for _ in range(increases):
                        try:
                            pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                            time.sleep(0.05)
                        except Exception:
                            pass
                with self.pending_lock():
                    self.increase_counts[currency_pair] = 0
                    for t in self.pending_trades:
                        if t['currency_pair'] == currency_pair and not t['resolved']:
                            t['resolved'] = True
                            t['result'] = "SKIPPED_AFTER_WIN"
                logger.info(f"[✅] Trade {currency_pair} WIN handled — martingale reset.")
                return

            if result == "LOSS":
                increases_done = increases
                if increases_done >= self.max_martingale:
                    logger.info(f"[⚠️] LOSS at max martingale for {currency_pair}. Resetting increases.")
                    if self.hotkey_mode:
                        for _ in range(increases_done):
                            try:
                                pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                                time.sleep(0.05)
                            except Exception:
                                pass
                    with self.pending_lock():
                        self.increase_counts[currency_pair] = 0
                    logger.info(f"[🔁] Reset after reaching max martingale for {currency_pair}")
                    return
                else:
                    logger.info(f"[↪️] LOSS detected for {currency_pair}. Waiting for scheduled martingale (if any).")
                    return

        except Exception as e:
            logger.error(f"[❌] Error handling trade result for {currency_pair}: {e}")

# --------------------
# instantiate global trade_manager
# --------------------
trade_manager = TradeManager()

# --------------------
# Exposed async callbacks for external Telegram listener
# --------------------
async def signal_callback(signal: dict, raw_message=None):
    try:
        trade_manager.handle_signal(signal)
        logger.info("[🤖] Signal forwarded to TradeManager for execution.")
    except Exception as e:
        logger.error(f"[❌] Failed to forward signal to TradeManager: {e}")

async def command_callback(cmd: str):
    try:
        trade_manager.handle_command(cmd)
        logger.info("[💻] Command forwarded to TradeManager.")
    except Exception as e:
        logger.error(f"[❌] Failed to forward command to TradeManager: {e}")

# --------------------
# main keep-alive if run directly
# --------------------
if __name__ == "__main__":
    logger.info("[ℹ️] Core running, TradeManager and Selenium started. Waiting for signals.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("[ℹ️] Shutting down.")
