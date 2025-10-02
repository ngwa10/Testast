# core.py
import logging
import time
import random
from datetime import datetime, timedelta
import pytz
import pyautogui
import json

from selenium_integration import PocketOptionSelenium  # Make sure this exists

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
# Random Log Messages
# =========================
try:
    with open("logs.json", "r", encoding="utf-8") as f:
        LOG_MESSAGES = json.load(f)
except Exception:
    LOG_MESSAGES = [
        "Precision is warming up. Desmond is watching.",
        "Desmond's bot is on duty — targets locked.",
    ]

def random_log():
    return random.choice(LOG_MESSAGES) if LOG_MESSAGES else ""

# =========================
# Timezone Conversion Helper
# =========================
def timezone_convert(entry_time_val, source_tz_str):
    try:
        tz_lower = source_tz_str.lower().strip()
        if tz_lower.startswith("utc"):
            sign = 1 if "+" in tz_lower else -1
            hours = int(tz_lower.split("utc")[1].replace("+", "").replace("-", ""))
            src_tz = pytz.FixedOffset(sign * hours * 60)
        elif tz_lower == "cameroon":
            src_tz = pytz.timezone("Africa/Douala")
        elif tz_lower.startswith("otc-"):
            offset_hours = int(tz_lower.split("-")[1])
            src_tz = pytz.FixedOffset(-offset_hours * 60)
        else:
            try:
                src_tz = pytz.timezone(source_tz_str)
            except:
                src_tz = pytz.UTC

        now_src = datetime.now(pytz.utc).astimezone(src_tz)

        if isinstance(entry_time_val, datetime):
            entry_dt = entry_time_val.astimezone(src_tz) if entry_time_val.tzinfo else src_tz.localize(entry_time_val)
        elif isinstance(entry_time_val, str):
            fmt = "%H:%M"
            entry_time = datetime.strptime(entry_time_val, fmt).time()
            entry_dt = datetime.combine(now_src.date(), entry_time)
            entry_dt = src_tz.localize(entry_dt)
        else:
            return None

        if entry_dt < now_src:
            return None
        return entry_dt
    except Exception as e:
        logger.warning(f"[⚠️] Failed timezone conversion for '{entry_time_val}' ({source_tz_str}): {e}")
        return None

# =========================
# TradeManager
# =========================
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=3, hotkey_mode=True):
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.trading_active = True
        self.pending_trades = []
        self.pending_lock = None
        self.increase_counts = {}
        self.hotkey_mode = hotkey_mode

        pyautogui.FAILSAFE = False

        # Initialize Selenium
        self.selenium = PocketOptionSelenium(self, headless=False)
        logger.info(f"TradeManager initialized | base_amount: {base_amount}, max_martingale: {max_martingale}, hotkey_mode={hotkey_mode}")

    # -----------------
    # Handle commands
    # -----------------
    def handle_command(self, cmd: str):
        cmd = cmd.strip().lower()
        if cmd.startswith("/start"):
            self.trading_active = True
            logger.info("[🚀] Trading started.")
        elif cmd.startswith("/stop"):
            self.trading_active = False
            logger.info("[⏹️] Trading stopped.")
        elif cmd.startswith("/status"):
            logger.info("[ℹ️] Trading status: ACTIVE" if self.trading_active else "[ℹ️] Trading status: PAUSED")
        else:
            logger.info(f"[ℹ️] Unknown command: {cmd}")

    # -----------------
    # Schedule Trade
    # -----------------
    def schedule_trade(self, entry_dt, signal, martingale_level):
        delay = (entry_dt - datetime.now(entry_dt.tzinfo)).total_seconds()
        if delay <= 0:
            logger.info(f"[⏹️] Signal entry time {entry_dt.strftime('%H:%M')} passed. Skipping trade.")
            return
        from threading import Timer
        Timer(delay, self.execute_trade, args=(entry_dt, signal, martingale_level)).start()

    # -----------------
    # Handle Signal
    # -----------------
    def handle_signal(self, signal: dict):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Ignoring signal.")
            return

        logger.info(f"[📡] Received signal: {signal} | {random_log()}")
        source_tz = signal.get("source", "UTC-3")

        entry_dt = timezone_convert(signal.get('entry_time'), source_tz)
        if not entry_dt:
            logger.warning(f"[⚠️] Invalid or passed entry_time: {signal.get('entry_time')}. Skipping signal.")
            return
        signal['entry_time'] = entry_dt

        # Convert martingale times
        mg_times_fixed = []
        for t in signal.get("martingale_times", []):
            t_conv = timezone_convert(t, source_tz)
            if t_conv:
                mg_times_fixed.append(t_conv)
        signal['martingale_times'] = mg_times_fixed

        # Schedule base trade
        self.schedule_trade(entry_dt, signal, 0)

        # Schedule martingale trades
        for i, mg in enumerate(signal['martingale_times']):
            level = i + 1
            if level > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {level} exceeds max {self.max_martingale}. Skipping.")
                break
            self.schedule_trade(mg, signal, level)

    # -----------------
    # Execute Trade
    # -----------------
    def execute_trade(self, entry_dt, signal, martingale_level):
        currency = signal['currency_pair']
        direction = signal.get('direction', 'BUY')
        trade_id = f"{currency}_{entry_dt.strftime('%H%M')}_{martingale_level}_{int(time.time()*1000)}"

        logger.info(f"[🎯] READY to place trade {trade_id} — {direction} level {martingale_level} | {random_log()}")

        # Martingale hotkey
        if self.hotkey_mode and martingale_level > 0:
            try:
                pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
            except Exception as e:
                logger.warning(f"[⚠️] Failed martingale increase hotkey: {e}")

        # Trade hotkeys
        if self.hotkey_mode:
            try:
                if direction.upper() == 'BUY':
                    pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
                else:
                    pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
            except Exception as e:
                logger.error(f"[❌] Hotkey trade failed: {e}")

        # Watch trade with Selenium
        if self.selenium:
            self.selenium.watch_trade_for_result(currency, datetime.now(entry_dt.tzinfo))

# =========================
# Instantiate TradeManager
# =========================
trade_manager = TradeManager()

# =========================
# Telegram Callbacks
# =========================
async def signal_callback(signal: dict, raw_message=None):
    try:
        trade_manager.handle_signal(signal)
        logger.info("[🤖] Signal forwarded to TradeManager.")
    except Exception as e:
        logger.error(f"[❌] Failed to forward signal: {e}")

async def command_callback(cmd: str):
    trade_manager.handle_command(cmd)
    logger.info(f"[💻] Command processed: {cmd}")

# =========================
# Keep bot alive
# =========================
logger.info("[ℹ️] Core bot running and ready for signals.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logger.info("[ℹ️] Bot shutting down.")
