import time
import threading
import random
import logging
import json
from datetime import datetime, timedelta
import pytz
import pyautogui

from selenium_integration import PocketOptionSelenium

# -------------------------
# Logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

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

# -------------------------
# Timezone conversion helper
# -------------------------
def convert_signal_time(entry_time_val, source_tz_str):
    if isinstance(entry_time_val, datetime):
        return entry_time_val
    fmt = "%H:%M"
    try:
        entry_dt_naive = datetime.strptime(entry_time_val, fmt)
        tz_lower = source_tz_str.lower().strip()
        if tz_lower == "cameroon":
            src = pytz.timezone("Africa/Douala")
        elif tz_lower == "utc-4":
            src = pytz.FixedOffset(-240)
        elif tz_lower == "utc-3":
            src = pytz.FixedOffset(-180)
        else:
            try:
                src = pytz.timezone(source_tz_str)
            except:
                src = pytz.UTC
        now_src = datetime.now(pytz.utc).astimezone(src)
        entry_dt = datetime.combine(now_src.date(), entry_dt_naive.time())
        entry_dt = src.localize(entry_dt) if entry_dt.tzinfo is None else entry_dt
        if entry_dt < now_src:
            return None
        return entry_dt
    except Exception:
        return None

# -------------------------
# TradeManager
# -------------------------
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=3, hotkey_mode=True):
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.trading_active = True
        self.pending_trades = []
        self.pending_lock = threading.Lock()
        self.increase_counts = {}
        self.hotkey_mode = hotkey_mode

        pyautogui.FAILSAFE = False if hotkey_mode else True

        self.selenium = PocketOptionSelenium(self, headless=not hotkey_mode)
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
    # Schedule trade
    # -----------------
    def schedule_trade(self, entry_dt, signal, martingale_level):
        delay = (entry_dt - datetime.now(entry_dt.tzinfo)).total_seconds()
        if delay <= 0:
            logger.info(f"[⏹️] Signal entry time {entry_dt.strftime('%H:%M')} passed. Skipping trade.")
            return
        threading.Timer(delay, self.execute_trade, args=(entry_dt, signal, martingale_level)).start()

    # -----------------
    # Signal entrypoint
    # -----------------
    def handle_signal(self, signal: dict):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Ignoring signal.")
            return

        logger.info(f"[📡] Received signal: {signal} | {random_log()}")
        source_tz = signal.get("source", "UTC-3")

        # Convert entry time
        entry_dt = convert_signal_time(signal.get('entry_time'), source_tz)
        if not entry_dt:
            logger.warning(f"[⚠️] Invalid or passed entry_time: {signal.get('entry_time')}. Skipping signal.")
            return
        signal['entry_time'] = entry_dt

        # Convert martingale times
        valid_mg_times = []
        for t in signal.get('martingale_times', []):
            t_conv = convert_signal_time(t, source_tz)
            if t_conv:
                valid_mg_times.append(t_conv)
        signal['martingale_times'] = valid_mg_times

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
    # Execute a single trade
    # -----------------
    def execute_trade(self, entry_dt, signal, martingale_level):
        currency = signal['currency_pair']
        direction = signal.get('direction', 'BUY')
        timeframe = signal.get('timeframe', 'M1')

        # Martingale check
        if martingale_level > 0:
            with self.pending_lock:
                for t in self.pending_trades:
                    if t['currency_pair'] == currency and t['level'] == 0 and t['resolved'] and t['result'] == 'WIN':
                        logger.info(f"[⏹️] Base trade WIN — skipping martingale level {martingale_level}.")
                        return

        # Selenium readiness (with retry)
        ready_info = {"ready": False}
        for _ in range(3):
            try:
                ready_info = self.selenium.confirm_asset_ready(currency, entry_dt, timeframe)
                if ready_info['ready']:
                    break
            except Exception as e:
                logger.warning(f"[⚠️] Selenium readiness check failed: {e}")
                time.sleep(0.5)
        if not ready_info['ready']:
            logger.warning(f"[⚠️] Signal missed or asset not ready for {currency} at {entry_dt.strftime('%H:%M')}. Skipping trade.")
            return

        # Prepare pending trade
        trade_id = f"{currency}_{entry_dt.strftime('%H%M')}_{martingale_level}_{int(time.time()*1000)}"
        logger.info(f"[🎯] READY to place trade {trade_id} — {direction} level {martingale_level}")

        with self.pending_lock:
            pending = {
                'id': trade_id,
                'currency_pair': currency,
                'entry_dt': entry_dt,
                'level': martingale_level,
                'placed_at': None,
                'resolved': False,
                'result': None,
                'increase_count': 0
            }
            self.pending_trades.append(pending)

        # Execute trade via hotkeys if enabled
        if self.hotkey_mode:
            try:
                # Martingale increase
                if martingale_level > 0:
                    pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
                    with self.pending_lock:
                        pending['increase_count'] += 1
                        self.increase_counts[currency] = self.increase_counts.get(currency, 0) + 1

                # Trade hotkey
                if direction.upper() == 'BUY':
                    pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
                else:
                    pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
            except Exception as e:
                logger.error(f"[❌] Hotkey execution failed for {trade_id}: {e}")

        with self.pending_lock:
            pending['placed_at'] = datetime.now(entry_dt.tzinfo)

        # Watch trade result via Selenium
        self.selenium.watch_trade_for_result(currency, pending['placed_at'])
        logger.info(f"[📝] Trade placed: {trade_id} — awaiting result. {random_log()}")

    # -----------------
    # Trade result callback
    # -----------------
    def on_trade_result(self, currency_pair: str, result: str):
        logger.info(f"[📣] Result callback: {currency_pair} -> {result}")
        with self.pending_lock:
            pending = None
            for t in sorted(self.pending_trades, key=lambda x: x['placed_at'] or datetime.max):
                if t['currency_pair'] == currency_pair and not t['resolved'] and t['placed_at']:
                    pending = t
                    break
            if not pending:
                logger.info(f"[ℹ️] No pending trade matched for {currency_pair}")
                return
            pending['resolved'] = True
            pending['result'] = result

        # Handle WIN / LOSS
        if result == 'WIN' and self.hotkey_mode:
            with self.pending_lock:
                incs = self.increase_counts.get(currency_pair, 0)
                for _ in range(incs):
                    try:
                        pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift'); time.sleep(0.05)
                    except:
                        pass
                self.increase_counts[currency_pair] = 0
                # Mark unresolved trades as skipped after win
                for t in self.pending_trades:
                    if t['currency_pair'] == currency_pair and not t['resolved']:
                        t['resolved'] = True
                        t['result'] = 'SKIPPED_AFTER_WIN'
        elif result == 'LOSS' and self.hotkey_mode:
            with self.pending_lock:
                increases_done = self.increase_counts.get(currency_pair, 0)
            if increases_done >= self.max_martingale:
                with self.pending_lock:
                    incs = self.increase_counts.get(currency_pair, 0)
                    for _ in range(incs):
                        try:
                            pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift'); time.sleep(0.05)
                        except:
                            pass
                    self.increase_counts[currency_pair] = 0

# -------------------------
# Instantiate global TradeManager
# -------------------------
trade_manager = TradeManager(hotkey_mode=True)
        
