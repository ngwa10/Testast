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

# Try to import timezone helper from core_utils if available
try:
    from core_utils import convert_signal_time
except Exception:
    # fallback simple converter (expects "UTC-3","UTC-4","Cameroon")
    def convert_signal_time(entry_time_str, source_tz_str, target_tz_str="Asia/Jakarta"):
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
                # treat as UTC by default
                src = pytz.UTC
            target = pytz.timezone(target_tz_str)
            now = datetime.now(target)
            entry_dt = entry_dt.replace(year=now.year, month=now.month, day=now.day)
            entry_dt = src.localize(entry_dt)
            entry_dt_tz = entry_dt.astimezone(target)
            return entry_dt_tz.strftime(fmt)
        except Exception:
            return entry_time_str

# Import Selenium integration (must exist in same folder)
from selenium_integration import PocketOptionSelenium

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load humanized logs
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

        # Pending trades list: each is dict with keys:
        # id, currency_pair, entry_dt (Jakarta-aware), level, placed_at, resolved(bool), result(str or None), increases(int)
        self.pending_trades = []
        self.pending_lock = threading.Lock()

        # Track how many times we increased amounts per currency (for resets)
        self.increase_counts = {}

        # Selenium integration instance (starts result monitor on init)
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
        """
        Expected signal keys: currency_pair, direction (BUY/SELL), entry_time (HH:MM),
        timeframe (M1/M5), martingale_times (list of HH:MM), source (UTC-3/UTC-4/Cameroon)
        """
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Ignoring signal.")
            return

        logger.info(f"[📡] Received signal: {signal} | {random_log()}")

        # Convert times from sender tz to Jakarta
        source_tz = signal.get("source", "UTC-3")
        try:
            signal['entry_time'] = convert_signal_time(signal['entry_time'], source_tz)
            signal['martingale_times'] = [convert_signal_time(t, source_tz) for t in signal.get('martingale_times', [])]
        except Exception as e:
            logger.warning(f"[⚠️] Time conversion error: {e}")

        # Schedule trades: direct + martingale entries (these run in background)
        entry_time = signal.get('entry_time')
        if entry_time:
            threading.Thread(target=self.execute_trade, args=(entry_time, signal, 0), daemon=True).start()

        for i, mg in enumerate(signal.get('martingale_times', [])):
            level = i + 1
            if level > self.max_martingale:
                logger.warning(f"[⚠️] Signal provided martingale level {level} but max allowed is {self.max_martingale}. Skipping further levels.")
                break
            threading.Thread(target=self.execute_trade, args=(mg, signal, level), daemon=True).start()

    # -----------------
    # Execute single trade (either direct or martingale level)
    # -----------------
    def execute_trade(self, entry_time_str: str, signal: dict, martingale_level: int):
        # Convert entry_time_str (already converted to Jakarta string) to datetime in Jakarta tz
        fmt = "%H:%M"
        try:
            jkt_tz = pytz.timezone("Asia/Jakarta")
            entry_dt_naive = datetime.strptime(entry_time_str, fmt)
            now_jkt = datetime.now(jkt_tz)
            entry_dt = entry_dt_naive.replace(year=now_jkt.year, month=now_jkt.month, day=now_jkt.day)
            entry_dt = jkt_tz.localize(entry_dt)
        except Exception as e:
            logger.warning(f"[⚠️] Could not parse entry time '{entry_time_str}': {e}")
            return

        # Wait until entry time
        delay = (entry_dt - datetime.now(pytz.timezone("Asia/Jakarta"))).total_seconds()
        if delay > 0:
            logger.info(f"[⏰] Waiting {delay:.1f}s until {entry_time_str} (level {martingale_level}) for {signal['currency_pair']}")
            time.sleep(delay)

        currency = signal['currency_pair']
        direction = signal.get('direction', 'BUY')
        timeframe = signal.get('timeframe', 'M1')

        # If this is a martingale level > 0, before sending anything, check if earlier trade was won
        base_trade_key = f"{currency}_{signal.get('entry_time')}"
        if martingale_level > 0:
            # short wait to let Selenium catch up — 0.5s as requested
            time.sleep(0.5)
            # if any pending base trade for this currency+base time has result == 'WIN' then skip
            with self.pending_lock:
                for t in self.pending_trades:
                    if (t['currency_pair'] == currency and t['level'] == 0 and not t['resolved']):
                        # base trade still unresolved -> proceed with martingale
                        break
                    if (t['currency_pair'] == currency and t['level'] == 0 and t['resolved'] and t['result'] == 'WIN'):
                        logger.info(f"[⏹️] Base trade for {currency} was WIN — skipping martingale level {martingale_level}.")
                        return

        # Ensure timeframe set
        try:
            self.selenium.set_timeframe(timeframe)
        except Exception as e:
            logger.warning(f"[⚠️] set_timeframe failed: {e}")

        # Start asset switching until selenium confirms asset ready (or entry time passes)
        logger.info(f"[🔥] Starting asset switching (firing) for {currency} until asset is ready or entry passes.")
        while not self.selenium.confirm_asset_ready(currency, entry_time_str):
            # if entry time passed already
            if datetime.now(pytz.timezone("Asia/Jakarta")) > entry_dt + timedelta(seconds=1):
                logger.info(f"[⏹️] Entry time passed for {currency} — aborting this entry (expired).")
                return
            # Fire switching stroke: Shift+TAB
            pyautogui.keyDown('shift'); pyautogui.press('tab'); pyautogui.keyUp('shift')
            logger.info(f"[🔥] Firing currency switching stroke for {currency} ...")
            time.sleep(random.randint(5, 9))

        # Place trade: if martingale, increase amount first
        trade_id = f"{currency}_{entry_dt.strftime('%H%M')}_{martingale_level}_{int(time.time()*1000)}"
        logger.info(f"[🎯] READY to place trade {trade_id} — {direction} level {martingale_level}")

        # Register pending trade before placing (so selenium watch can match results in time)
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

        # If martingale_level > 0 => increase amount first (Shift+D)
        if martingale_level > 0:
            pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
            with self.pending_lock:
                pending['increase_count'] += 1
                # track global increase counts by currency so we can reset later
                self.increase_counts[currency] = self.increase_counts.get(currency, 0) + 1
            logger.info(f"[🔥] Increased trade amount for martingale level {martingale_level} (trade {trade_id})")

        # Now send BUY/SELL hotkey
        try:
            if direction.upper() == 'BUY':
                pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
                logger.info(f"[🔥] Just fired BUY stroke for {trade_id}")
            else:
                pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
                logger.info(f"[🔥] Just fired SELL stroke for {trade_id}")
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkey for {trade_id}: {e}")

        # Mark placed_at
        with self.pending_lock:
            pending['placed_at'] = datetime.now(pytz.timezone("Asia/Jakarta"))

        # Ask Selenium to watch for this trade result (it will call back on_trade_result)
        try:
            self.selenium.watch_trade_for_result(currency, pending['placed_at'])
        except Exception:
            # Even if this watch fails, core will still continue - result monitoring runs globally too.
            pass

        # Log and exit (the result handling happens in on_trade_result)
        logger.info(f"[📝] Trade placed and registered: {trade_id} — awaiting result. {random_log()}")

    # -----------------
    # Called by Selenium when it detects WIN/LOSS.
    # Selenium will pass currency_pair and the detected result.
    # -----------------
    def on_trade_result(self, currency_pair: str, result: str):
        """
        Called from Selenium monitor thread when a WIN or LOSS is detected.
        We map that to the earliest unresolved pending trade for that currency and apply logic.
        """
        logger.info(f"[📣] Result callback from Selenium: {currency_pair} -> {result}")

        with self.pending_lock:
            # find earliest unresolved pending trade for this currency
            pending = None
            for t in sorted(self.pending_trades, key=lambda x: x['placed_at'] or datetime.max):
                if t['currency_pair'] == currency_pair and not t['resolved'] and t['placed_at'] is not None:
                    pending = t
                    break

            if not pending:
                logger.info(f"[ℹ️] No pending trade matched for {currency_pair}; ignoring result.")
                return

            # mark resolved
            pending['resolved'] = True
            pending['result'] = result

        # If WIN -> reset increases for this currency and prevent further martingale
        if result == 'WIN':
            logger.info(f"[✅] Trade WIN detected for {currency_pair}. Resetting increases and stopping martingale.")
            # reset global increase counts for this currency by decrementing accordingly
            with self.pending_lock:
                incs = self.increase_counts.get(currency_pair, 0)
                if incs > 0:
                    # send Shift+A incs times to decrease amount back to base
                    for _ in range(incs):
                        pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                        logger.info(f"[↩️] Decreased trade amount for {currency_pair} (reset).")
                        time.sleep(0.05)  # small gap
                    self.increase_counts[currency_pair] = 0

            # stop martingale behavior for any pending entries of this currency
            # mark any unresolved pending trades for same currency as 'skipped' (so we won't place)
            with self.pending_lock:
                for t in self.pending_trades:
                    if t['currency_pair'] == currency_pair and not t['resolved']:
                        t['resolved'] = True
                        t['result'] = 'SKIPPED_AFTER_WIN'
            return

        # If LOSS -> see if we reached max martingale (for the base trade)
        if result == 'LOSS':
            logger.info(f"[❌] Trade LOSS detected for {currency_pair}.")
            # find base trade (level 0) that matches and check how many levels already tried
            with self.pending_lock:
                base_levels = [t for t in self.pending_trades if t['currency_pair'] == currency_pair and t['level'] == 0]
                # determine how many martingale levels already placed for this base signal
                # count resolved levels where level > 0 and placed recently
                # simple approach: count increases we executed
                increases_done = self.increase_counts.get(currency_pair, 0)

            # If increases_done >= max_martingale -> reset and mark stop
            if increases_done >= self.max_martingale:
                logger.info(f"[⚠️] Reached max martingale for {currency_pair}. Resetting amounts and stopping further martingales.")
                with self.pending_lock:
                    incs = self.increase_counts.get(currency_pair, 0)
                    if incs > 0:
                        for _ in range(incs):
                            pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                            logger.info(f"[↩️] Decreased trade amount for {currency_pair} (reset after max).")
                            time.sleep(0.05)
                        self.increase_counts[currency_pair] = 0

                # mark pending unresolved trades for this currency as resolved to avoid further placing
                with self.pending_lock:
                    for t in self.pending_trades:
                        if t['currency_pair'] == currency_pair and not t['resolved']:
                            t['resolved'] = True
                            t['result'] = 'ABORTED_MAX_MARTINGALE'
                return

            # else: do nothing here — the next martingale execute_trade thread (scheduled from signal) will run at its scheduled time and place the next trade (increase + buy/sell)
            logger.info(f"[ℹ️] Martingale available for {currency_pair}. Next martingale entry (if scheduled) will attempt to place trade.")

    # -----------------
    # Utility: cleanup old resolved pending trades to prevent memory growth
    # -----------------
    def _cleanup_pending(self):
        with self.pending_lock:
            cutoff = datetime.now(pytz.timezone("Asia/Jakarta")) - timedelta(minutes=30)
            self.pending_trades = [t for t in self.pending_trades if (not t['resolved'] or (t['placed_at'] and t['placed_at'] > cutoff))]

# single global instance
trade_manager = TradeManager()
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

# Try to import timezone helper from core_utils if available
try:
    from core_utils import convert_signal_time
except Exception:
    # fallback simple converter (expects "UTC-3","UTC-4","Cameroon")
    def convert_signal_time(entry_time_str, source_tz_str, target_tz_str="Asia/Jakarta"):
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
                # treat as UTC by default
                src = pytz.UTC
            target = pytz.timezone(target_tz_str)
            now = datetime.now(target)
            entry_dt = entry_dt.replace(year=now.year, month=now.month, day=now.day)
            entry_dt = src.localize(entry_dt)
            entry_dt_tz = entry_dt.astimezone(target)
            return entry_dt_tz.strftime(fmt)
        except Exception:
            return entry_time_str

# Import Selenium integration (must exist in same folder)
from selenium_integration import PocketOptionSelenium

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load humanized logs
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

        # Pending trades list: each is dict with keys:
        # id, currency_pair, entry_dt (Jakarta-aware), level, placed_at, resolved(bool), result(str or None), increases(int)
        self.pending_trades = []
        self.pending_lock = threading.Lock()

        # Track how many times we increased amounts per currency (for resets)
        self.increase_counts = {}

        # Selenium integration instance (starts result monitor on init)
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
        """
        Expected signal keys: currency_pair, direction (BUY/SELL), entry_time (HH:MM),
        timeframe (M1/M5), martingale_times (list of HH:MM), source (UTC-3/UTC-4/Cameroon)
        """
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Ignoring signal.")
            return

        logger.info(f"[📡] Received signal: {signal} | {random_log()}")

        # Convert times from sender tz to Jakarta
        source_tz = signal.get("source", "UTC-3")
        try:
            signal['entry_time'] = convert_signal_time(signal['entry_time'], source_tz)
            signal['martingale_times'] = [convert_signal_time(t, source_tz) for t in signal.get('martingale_times', [])]
        except Exception as e:
            logger.warning(f"[⚠️] Time conversion error: {e}")

        # Schedule trades: direct + martingale entries (these run in background)
        entry_time = signal.get('entry_time')
        if entry_time:
            threading.Thread(target=self.execute_trade, args=(entry_time, signal, 0), daemon=True).start()

        for i, mg in enumerate(signal.get('martingale_times', [])):
            level = i + 1
            if level > self.max_martingale:
                logger.warning(f"[⚠️] Signal provided martingale level {level} but max allowed is {self.max_martingale}. Skipping further levels.")
                break
            threading.Thread(target=self.execute_trade, args=(mg, signal, level), daemon=True).start()

    # -----------------
    # Execute single trade (either direct or martingale level)
    # -----------------
    def execute_trade(self, entry_time_str: str, signal: dict, martingale_level: int):
        # Convert entry_time_str (already converted to Jakarta string) to datetime in Jakarta tz
        fmt = "%H:%M"
        try:
            jkt_tz = pytz.timezone("Asia/Jakarta")
            entry_dt_naive = datetime.strptime(entry_time_str, fmt)
            now_jkt = datetime.now(jkt_tz)
            entry_dt = entry_dt_naive.replace(year=now_jkt.year, month=now_jkt.month, day=now_jkt.day)
            entry_dt = jkt_tz.localize(entry_dt)
        except Exception as e:
            logger.warning(f"[⚠️] Could not parse entry time '{entry_time_str}': {e}")
            return

        # Wait until entry time
        delay = (entry_dt - datetime.now(pytz.timezone("Asia/Jakarta"))).total_seconds()
        if delay > 0:
            logger.info(f"[⏰] Waiting {delay:.1f}s until {entry_time_str} (level {martingale_level}) for {signal['currency_pair']}")
            time.sleep(delay)

        currency = signal['currency_pair']
        direction = signal.get('direction', 'BUY')
        timeframe = signal.get('timeframe', 'M1')

        # If this is a martingale level > 0, before sending anything, check if earlier trade was won
        base_trade_key = f"{currency}_{signal.get('entry_time')}"
        if martingale_level > 0:
            # short wait to let Selenium catch up — 0.5s as requested
            time.sleep(0.5)
            # if any pending base trade for this currency+base time has result == 'WIN' then skip
            with self.pending_lock:
                for t in self.pending_trades:
                    if (t['currency_pair'] == currency and t['level'] == 0 and not t['resolved']):
                        # base trade still unresolved -> proceed with martingale
                        break
                    if (t['currency_pair'] == currency and t['level'] == 0 and t['resolved'] and t['result'] == 'WIN'):
                        logger.info(f"[⏹️] Base trade for {currency} was WIN — skipping martingale level {martingale_level}.")
                        return

        # Ensure timeframe set
        try:
            self.selenium.set_timeframe(timeframe)
        except Exception as e:
            logger.warning(f"[⚠️] set_timeframe failed: {e}")

        # Start asset switching until selenium confirms asset ready (or entry time passes)
        logger.info(f"[🔥] Starting asset switching (firing) for {currency} until asset is ready or entry passes.")
        while not self.selenium.confirm_asset_ready(currency, entry_time_str):
            # if entry time passed already
            if datetime.now(pytz.timezone("Asia/Jakarta")) > entry_dt + timedelta(seconds=1):
                logger.info(f"[⏹️] Entry time passed for {currency} — aborting this entry (expired).")
                return
            # Fire switching stroke: Shift+TAB
            pyautogui.keyDown('shift'); pyautogui.press('tab'); pyautogui.keyUp('shift')
            logger.info(f"[🔥] Firing currency switching stroke for {currency} ...")
            time.sleep(random.randint(5, 9))

        # Place trade: if martingale, increase amount first
        trade_id = f"{currency}_{entry_dt.strftime('%H%M')}_{martingale_level}_{int(time.time()*1000)}"
        logger.info(f"[🎯] READY to place trade {trade_id} — {direction} level {martingale_level}")

        # Register pending trade before placing (so selenium watch can match results in time)
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

        # If martingale_level > 0 => increase amount first (Shift+D)
        if martingale_level > 0:
            pyautogui.keyDown('shift'); pyautogui.press('d'); pyautogui.keyUp('shift')
            with self.pending_lock:
                pending['increase_count'] += 1
                # track global increase counts by currency so we can reset later
                self.increase_counts[currency] = self.increase_counts.get(currency, 0) + 1
            logger.info(f"[🔥] Increased trade amount for martingale level {martingale_level} (trade {trade_id})")

        # Now send BUY/SELL hotkey
        try:
            if direction.upper() == 'BUY':
                pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
                logger.info(f"[🔥] Just fired BUY stroke for {trade_id}")
            else:
                pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
                logger.info(f"[🔥] Just fired SELL stroke for {trade_id}")
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkey for {trade_id}: {e}")

        # Mark placed_at
        with self.pending_lock:
            pending['placed_at'] = datetime.now(pytz.timezone("Asia/Jakarta"))

        # Ask Selenium to watch for this trade result (it will call back on_trade_result)
        try:
            self.selenium.watch_trade_for_result(currency, pending['placed_at'])
        except Exception:
            # Even if this watch fails, core will still continue - result monitoring runs globally too.
            pass

        # Log and exit (the result handling happens in on_trade_result)
        logger.info(f"[📝] Trade placed and registered: {trade_id} — awaiting result. {random_log()}")

    # -----------------
    # Called by Selenium when it detects WIN/LOSS.
    # Selenium will pass currency_pair and the detected result.
    # -----------------
    def on_trade_result(self, currency_pair: str, result: str):
        """
        Called from Selenium monitor thread when a WIN or LOSS is detected.
        We map that to the earliest unresolved pending trade for that currency and apply logic.
        """
        logger.info(f"[📣] Result callback from Selenium: {currency_pair} -> {result}")

        with self.pending_lock:
            # find earliest unresolved pending trade for this currency
            pending = None
            for t in sorted(self.pending_trades, key=lambda x: x['placed_at'] or datetime.max):
                if t['currency_pair'] == currency_pair and not t['resolved'] and t['placed_at'] is not None:
                    pending = t
                    break

            if not pending:
                logger.info(f"[ℹ️] No pending trade matched for {currency_pair}; ignoring result.")
                return

            # mark resolved
            pending['resolved'] = True
            pending['result'] = result

        # If WIN -> reset increases for this currency and prevent further martingale
        if result == 'WIN':
            logger.info(f"[✅] Trade WIN detected for {currency_pair}. Resetting increases and stopping martingale.")
            # reset global increase counts for this currency by decrementing accordingly
            with self.pending_lock:
                incs = self.increase_counts.get(currency_pair, 0)
                if incs > 0:
                    # send Shift+A incs times to decrease amount back to base
                    for _ in range(incs):
                        pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                        logger.info(f"[↩️] Decreased trade amount for {currency_pair} (reset).")
                        time.sleep(0.05)  # small gap
                    self.increase_counts[currency_pair] = 0

            # stop martingale behavior for any pending entries of this currency
            # mark any unresolved pending trades for same currency as 'skipped' (so we won't place)
            with self.pending_lock:
                for t in self.pending_trades:
                    if t['currency_pair'] == currency_pair and not t['resolved']:
                        t['resolved'] = True
                        t['result'] = 'SKIPPED_AFTER_WIN'
            return

        # If LOSS -> see if we reached max martingale (for the base trade)
        if result == 'LOSS':
            logger.info(f"[❌] Trade LOSS detected for {currency_pair}.")
            # find base trade (level 0) that matches and check how many levels already tried
            with self.pending_lock:
                base_levels = [t for t in self.pending_trades if t['currency_pair'] == currency_pair and t['level'] == 0]
                # determine how many martingale levels already placed for this base signal
                # count resolved levels where level > 0 and placed recently
                # simple approach: count increases we executed
                increases_done = self.increase_counts.get(currency_pair, 0)

            # If increases_done >= max_martingale -> reset and mark stop
            if increases_done >= self.max_martingale:
                logger.info(f"[⚠️] Reached max martingale for {currency_pair}. Resetting amounts and stopping further martingales.")
                with self.pending_lock:
                    incs = self.increase_counts.get(currency_pair, 0)
                    if incs > 0:
                        for _ in range(incs):
                            pyautogui.keyDown('shift'); pyautogui.press('a'); pyautogui.keyUp('shift')
                            logger.info(f"[↩️] Decreased trade amount for {currency_pair} (reset after max).")
                            time.sleep(0.05)
                        self.increase_counts[currency_pair] = 0

                # mark pending unresolved trades for this currency as resolved to avoid further placing
                with self.pending_lock:
                    for t in self.pending_trades:
                        if t['currency_pair'] == currency_pair and not t['resolved']:
                            t['resolved'] = True
                            t['result'] = 'ABORTED_MAX_MARTINGALE'
                return

            # else: do nothing here — the next martingale execute_trade thread (scheduled from signal) will run at its scheduled time and place the next trade (increase + buy/sell)
            logger.info(f"[ℹ️] Martingale available for {currency_pair}. Next martingale entry (if scheduled) will attempt to place trade.")

    # -----------------
    # Utility: cleanup old resolved pending trades to prevent memory growth
    # -----------------
    def _cleanup_pending(self):
        with self.pending_lock:
            cutoff = datetime.now(pytz.timezone("Asia/Jakarta")) - timedelta(minutes=30)
            self.pending_trades = [t for t in self.pending_trades if (not t['resolved'] or (t['placed_at'] and t['placed_at'] > cutoff))]

# single global instance
trade_manager = TradeManager()
                
