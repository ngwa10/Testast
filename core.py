import time
import threading
import random
import logging
import json
from datetime import datetime, timedelta
import pyautogui
import pytz

# -------------------------
# Timezone conversion import
# -------------------------
try:
    from core_utils import timezone_convert as convert_signal_time
except Exception:
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
                except Exception:
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
# Selenium integration
# -------------------------
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
# TradeManager
# -------------------------
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=3):
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.trading_active = True
        self.pending_trades = []
        self.pending_lock = threading.Lock()
        self.increase_counts = {}
        self.selenium = PocketOptionSelenium(self, headless=False)
        logger.info(f"TradeManager initialized | base_amount: {base_amount}, max_martingale: {max_martingale}")

    # -----------------
    # Commands
    # -----------------
    def handle_command(self, cmd: str):
        cmd = cmd.strip().lower()
        if cmd.startswith("/start"):
            self.trading_active = True
            logger.info("[🚀] Trading started — Precision firing.")
        elif cmd.startswith("/stop"):
            self.trading_active = False
            logger.info("[⏹️] Trading stopped — taking a break.")
        elif cmd.startswith("/status"):
            logger.info("[ℹ️] Trading status: ACTIVE" if self.trading_active else "[ℹ️] Trading status: PAUSED")
        else:
            logger.info(f"[ℹ️] Unknown command: {cmd}")

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
        threading.Thread(target=self.execute_trade, args=(entry_dt, signal, 0), daemon=True).start()

        # Schedule martingale trades
        for i, mg in enumerate(signal['martingale_times']):
            level = i + 1
            if level > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {level} exceeds max {self.max_martingale}. Skipping.")
                break
            threading.Thread(target=self.execute_trade, args=(mg, signal, level), daemon=True).start()

    # -----------------
    # Execute single trade
    # -----------------
    def execute_trade(self, entry_dt, signal, martingale_level):
        currency = signal['currency_pair']
        direction = signal.get('direction', 'BUY')
        timeframe = signal.get('timeframe', 'M1')

        # Wait until entry time minus 20 seconds
        now = datetime.now(entry_dt.tzinfo)
        wait_until = entry_dt - timedelta(seconds=20)
        delay = (wait_until - now).total_seconds()
        if delay > 0:
            fmt = "%H:%M:%S"
            logger.info(f"[⏰] Waiting {delay:.1f}s until {wait_until.strftime(fmt)} for {currency} (level {martingale_level})")
            time.sleep(delay)

        # Try to confirm asset readiness until 20 seconds before entry time
        ready = None
        while datetime.now(entry_dt.tzinfo) < entry_dt - timedelta(seconds=20):
            try:
                ready = self.selenium.confirm_asset_ready(currency, entry_dt, timeframe)
                if ready.get("ready"):
                    break
            except Exception as e:
                logger.warning(f"[⚠️] Selenium confirm_asset_ready failed: {e}")
            time.sleep(0.5)  # retry every 0.5s

        # If still not ready, log as missed
        if not ready or not ready.get("ready"):
            logger.warning(f"[❌] Signal missed: Asset {currency} was not ready before entry time {entry_dt.strftime('%H:%M:%S')}")
            return

        # Martingale check
        if martingale_level > 0:
            with self.pending_lock:
                for t in self.pending_trades:
                    if t['currency_pair'] == currency and t['level'] == 0 and t['resolved'] and t['result'] == 'WIN':
                        logger.info(f"[⏹️] Base trade WIN — skipping martingale level {martingale_level}.")
                        return

        # Prepare pending trade entry
        trade_id = f"{currency}_{entry_dt.strftime('%H%M')}_{martingale_level}_{int(time.time()*1000)}"
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

        # Martingale increase
        if martingale_level > 0:
            pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
            with self.pending_lock:
                pending['increase_count'] += 1
                self.increase_counts[currency] = self.increase_counts.get(currency, 0) + 1

        # Fire trade hotkey
        try:
            if direction.upper() == 'BUY':
                pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
            else:
                pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkey for {trade_id}: {e}")

        with self.pending_lock:
            pending['placed_at'] = datetime.now(entry_dt.tzinfo)

        # Watch trade result via Selenium
        try:
            self.selenium.watch_trade_for_result(currency, pending['placed_at'])
        except Exception:
            pass

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
        if result == 'WIN':
            with self.pending_lock:
                incs = self.increase_counts.get(currency_pair, 0)
                for _ in range(incs):
                    pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                    time.sleep(0.05)
                self.increase_counts[currency_pair] = 0
                for t in self.pending_trades:
                    if t['currency_pair'] == currency_pair and not t['resolved']:
                        t['resolved'] = True
                        t['result'] = 'SKIPPED_AFTER_WIN'
        elif result == 'LOSS':
            with self.pending_lock:
                increases_done = self.increase_counts.get(currency_pair, 0)
            if increases_done >= self.max_martingale:
                with self.pending_lock:
                    incs = self.increase_counts.get(currency_pair, 0)
                    for _ in range(incs):
                        pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                        time.sleep(0.05)
                    self.increase_counts[currency_pair] = 0
                    for t in self.pending_trades:
                        if t['currency_pair'] == currency_pair and not t['resolved']:
                            t['resolved'] = True
                            t['result'] = 'ABORTED_MAX_MARTINGALE'

    # -----------------
    # Cleanup old trades
    # -----------------
    def _cleanup_pending(self):
        with self.pending_lock:
            cutoff = datetime.now(pytz.utc) - timedelta(minutes=30)
            self.pending_trades = [
                t for t in self.pending_trades
                if (not t['resolved'] or (t['placed_at'] and t['placed_at'] > cutoff))
            ]

# -----------------
# Global instance
# -----------------
trade_manager = TradeManager()
                    
