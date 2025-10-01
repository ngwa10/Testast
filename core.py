"""
Final core.py — TradeManager and orchestration.

Features:
- Receives parsed signals from Telegram listener.
- Converts sender time -> Jakarta time (uses core_utils.timezone_convert if available).
- Schedules direct and martingale trades.
- Fires keystrokes (hotkeys) using Pocket Option mappings:
    Shift+W : BUY
    Shift+S : SELL
    Shift+D : INCREASE amount (martingale)
    Shift+A : DECREASE amount (reset)
    Shift+TAB : SWITCH ASSET
- Tracks pending trades and martingale increases.
- Waits a short 0.5s before martingale entry to let Selenium detect direct-win.
- Resets trade amounts only when a WIN arrives or max martingale is reached.
- Communicates with selenium_integration.PocketOptionSelenium which calls back on results.
"""

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
    # fallback simple converter
    def convert_signal_time(entry_time_str, source_tz_str):
        fmt = "%H:%M"
        try:
            entry_dt = datetime.strptime(entry_time_str, fmt)
            if source_tz_str.lower() == "cameroon":
                src = pytz.timezone("Africa/Douala")
            elif source_tz_str.lower() == "utc-4":
                src = pytz.FixedOffset(-240)
            elif source_tz_str.lower() == "utc-3":
                src = pytz.FixedOffset(-180)
            else:
                src = pytz.UTC
            today = datetime.now(pytz.utc).date()
            entry_dt = entry_dt.replace(year=today.year, month=today.month, day=today.day)
            entry_dt = src.localize(entry_dt)
            jkt_tz = pytz.timezone("Asia/Jakarta")
            return entry_dt.astimezone(jkt_tz).strftime(fmt)
        except Exception:
            return None

# Import Selenium integration (must exist)
from selenium_integration import PocketOptionSelenium

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Humanized logs
try:
    with open("logs.json", "r", encoding="utf-8") as f:
        LOG_MESSAGES = json.load(f)
except Exception:
    LOG_MESSAGES = [
        "Precision is warming up. Desmond is watching.",
        "Desmond's bot is on duty — targets locked.",
    ]

def random_log():
    if LOG_MESSAGES:
        return random.choice(LOG_MESSAGES)
    return ""

# -------------------------
# TradeManager
# -------------------------
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=2):
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
        entry_time = convert_signal_time(signal.get('entry_time'), source_tz)
        if not entry_time:
            logger.warning(f"[⚠️] Invalid entry_time: {signal.get('entry_time')}. Skipping signal.")
            return
        signal['entry_time'] = entry_time

        # Convert martingale times
        valid_mg_times = []
        for t in signal.get('martingale_times', []):
            t_conv = convert_signal_time(t, source_tz)
            if t_conv:
                valid_mg_times.append(t_conv)
        signal['martingale_times'] = valid_mg_times

        # Schedule direct trade
        threading.Thread(target=self.execute_trade, args=(signal['entry_time'], signal, 0), daemon=True).start()

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
    def execute_trade(self, entry_time_str: str, signal: dict, martingale_level: int):
        fmt = "%H:%M"
        jkt_tz = pytz.timezone("Asia/Jakarta")
        try:
            dt_naive = datetime.strptime(entry_time_str, fmt)
            now_jkt = datetime.now(jkt_tz)
            entry_dt = dt_naive.replace(year=now_jkt.year, month=now_jkt.month, day=now_jkt.day)
            entry_dt = jkt_tz.localize(entry_dt)
        except Exception as e:
            logger.warning(f"[⚠️] Could not parse entry time '{entry_time_str}': {e}")
            return

        delay = (entry_dt - datetime.now(jkt_tz)).total_seconds()
        if delay > 0:
            logger.info(f"[⏰] Waiting {delay:.1f}s until {entry_time_str} (level {martingale_level}) for {signal['currency_pair']}")
            time.sleep(delay)

        currency = signal['currency_pair']
        direction = signal.get('direction', 'BUY')
        timeframe = signal.get('timeframe', 'M1')

        # Martingale checks
        if martingale_level > 0:
            time.sleep(0.5)
            with self.pending_lock:
                for t in self.pending_trades:
                    if t['currency_pair'] == currency and t['level'] == 0 and t['resolved'] and t['result'] == 'WIN':
                        logger.info(f"[⏹️] Base trade WIN — skipping martingale level {martingale_level}.")
                        return

        # Set timeframe
        try:
            self.selenium.set_timeframe(timeframe)
        except Exception as e:
            logger.warning(f"[⚠️] set_timeframe failed: {e}")

        # Switch asset until ready
        logger.info(f"[🔥] Switching asset for {currency} until ready or entry passes.")
        while not self.selenium.confirm_asset_ready(currency, entry_time_str):
            if datetime.now(jkt_tz) > entry_dt + timedelta(seconds=1):
                logger.info(f"[⏹️] Entry time passed for {currency} — aborting.")
                return
            pyautogui.keyDown('shift'); pyautogui.press('tab'); pyautogui.keyUp('shift')
            time.sleep(random.randint(5, 9))

        # Place trade
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

        if martingale_level > 0:
            pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
            with self.pending_lock:
                pending['increase_count'] += 1
                self.increase_counts[currency] = self.increase_counts.get(currency, 0) + 1

        # Fire BUY/SELL
        try:
            if direction.upper() == 'BUY':
                pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
            else:
                pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkey for {trade_id}: {e}")

        with self.pending_lock:
            pending['placed_at'] = datetime.now(jkt_tz)

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
            cutoff = datetime.now(pytz.timezone("Asia/Jakarta")) - timedelta(minutes=30)
            self.pending_trades = [t for t in self.pending_trades if (not t['resolved'] or (t['placed_at'] and t['placed_at'] > cutoff))]

# -----------------
# Global instance
# -----------------
trade_manager = TradeManager()
        
