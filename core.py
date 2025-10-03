# core.py
"""
Core trading logic (hotkey-driven, personality logs)

- Loads logs.json at startup and uses random messages for personality lines.
- Exposes signal_callback(signal) to schedule trades.
- Exposes trade_result_received(trade_id, result_text) and handle_trade_result(status, amount, trade_id)
  to accept results reported by screen_logic.py.
- Uses pyautogui to send hotkeys:
    Shift+W -> BUY
    Shift+S -> SELL
    Shift+D -> Increase trade amount (martingale)
- Stops martingale chain if no result is reported within expiry.
"""

import json
import logging
import threading
import time
import random
import uuid
from datetime import datetime, timedelta
from typing import Optional

import pyautogui

# ---------------------------
# Configuration
# ---------------------------
TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 300,
    "M15": 900,
    "M30": 1800,
    "H1": 3600
}
# Small buffer to allow detection latency
EXPIRY_BUFFER_SECONDS = 5

# pyautogui safety
pyautogui.FAILSAFE = False

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("core")

# ---------------------------
# Load personality logs (logs.json) at startup
# ---------------------------
try:
    with open("logs.json", "r", encoding="utf-8") as f:
        LOG_BUCKETS = json.load(f)
except Exception as e:
    logger.warning(f"[⚠️] Failed to load logs.json: {e}. Using minimal defaults.")
    LOG_BUCKETS = {
        "idle_logs": ["Precision is idling."],
        "pre_trade_logs": ["Precision preparing trade."],
        "firing_logs": ["Precision firing."],
        "martingale_logs": ["Martingale engaged."],
        "win_logs": ["Win!"],
        "loss_logs": ["Loss."],
        "praise_desmond": ["Desmond is great."],
        "roast_others": ["Look at others."],
        "questions": ["What's next?"]
    }

def _random_log(category: str) -> str:
    bucket = LOG_BUCKETS.get(category, None)
    if not bucket:
        return ""
    return random.choice(bucket)

# ---------------------------
# Thread-safe registries
# ---------------------------
_registry_lock = threading.RLock()
_pending_trades = {}   # trade_id -> trade_info dict
_active_groups = {}    # group_id -> {"stopped": bool, "signal": <signal dict>}

# ---------------------------
# Utilities
# ---------------------------
def _tf_to_seconds(tf: str) -> int:
    if not tf:
        return 60
    tfu = tf.strip().upper()
    return TIMEFRAME_SECONDS.get(tfu, 60)

def _normalize_currency(pair: str) -> str:
    if not pair:
        return ""
    return pair.replace("/", "").replace(" ", "").upper()

# ---------------------------
# Core manager
# ---------------------------
class TradeManager:
    def __init__(self, max_martingale: int = 3):
        self.max_martingale = max_martingale
        # ensure pyautogui ready
        pyautogui.FAILSAFE = False
        logger.info("[ℹ️] TradeManager initialized.")
        logger.info(_random_log("idle_logs"))

    # ---- Public: handle incoming signal ----
    def handle_signal(self, signal: dict):
        """
        signal expected keys:
          - currency_pair (e.g. "EUR/USD")
          - direction ("BUY" or "SELL")
          - entry_time (tz-aware datetime)
          - martingale_times (list of tz-aware datetimes) - optional
          - timeframe ("M1", "M5", etc.)
        """
        try:
            if not isinstance(signal, dict):
                logger.warning("[⚠️] handle_signal expects a dict. Ignoring.")
                return

            currency_raw = signal.get("currency_pair")
            direction = (signal.get("direction") or "BUY").upper()
            entry_time = signal.get("entry_time")
            mg_times = signal.get("martingale_times", []) or []
            timeframe = (signal.get("timeframe") or "M1").upper()

            # basic validation
            if not currency_raw or not isinstance(entry_time, datetime) or entry_time.tzinfo is None:
                logger.warning("[⚠️] Invalid signal: missing currency or timezone-aware entry_time.")
                return

            currency = _normalize_currency(currency_raw)

            # group id binds the base and martingales
            group_id = f"{currency}_{entry_time.isoformat()}_{uuid.uuid4().hex[:8]}"

            with _registry_lock:
                _active_groups[group_id] = {"stopped": False, "signal": signal}

            logger.info(f"[📩] Signal received for {currency_raw} ({direction}) at {entry_time.strftime('%H:%M:%S')} — scheduling (group={group_id})")
            logger.info(_random_log("pre_trade_logs"))

            # Fire-and-forget: send select instruction to screen_logic if present
            try:
                import screen_logic  # local module - may be a stub
                # prefer select_currency(currency, timeframe) but accept single-arg stub
                try:
                    screen_logic.select_currency(currency, timeframe)
                except TypeError:
                    screen_logic.select_currency(currency)
                logger.info(f"[🛰️] Instructed screen_logic to select {currency}/{timeframe}")
            except Exception:
                logger.info(f"[🛰️] screen_logic not available or failed; continuing (no crash).")

            # schedule base trade
            self._schedule_trade(entry_time, currency, direction, timeframe, group_id, martingale_level=0)

            # schedule provided martingale times
            for idx, mg_time in enumerate(mg_times):
                level = idx + 1
                if level > self.max_martingale:
                    logger.warning(f"[⚠️] Provided martingale time at level {level} exceeds max_martingale; skipping.")
                    break
                self._schedule_trade(mg_time, currency, direction, timeframe, group_id, martingale_level=level)

        except Exception as e:
            logger.exception(f"[❌] handle_signal unexpected error: {e}")

    # ---- schedule ----
    def _schedule_trade(self, when: datetime, currency: str, direction: str, timeframe: str, group_id: str, martingale_level: int):
        trade_id = f"{currency}_{when.strftime('%H%M%S')}_{martingale_level}_{uuid.uuid4().hex[:6]}"
        thread = threading.Thread(target=self._trade_worker, args=(trade_id, when, currency, direction, timeframe, group_id, martingale_level), daemon=True)
        thread.start()
        logger.info(f"[🗓️] Scheduled trade id={trade_id} level={martingale_level} at {when.strftime('%H:%M:%S')} (group={group_id})")

    # ---- trade worker ----
    def _trade_worker(self, trade_id: str, when: datetime, currency: str, direction: str, timeframe: str, group_id: str, martingale_level: int):
        # wait until scheduled time
        try:
            now = datetime.now(when.tzinfo)
            delay = (when - now).total_seconds()
            if delay > 0:
                logger.info(f"[⏱️] Trade {trade_id}: waiting {delay:.1f}s until entry (level={martingale_level})")
                time.sleep(delay)
        except Exception:
            logger.warning(f"[⚠️] Trade {trade_id}: timezone/now computation failed; proceeding.")

        # check group stopped flag
        with _registry_lock:
            grp = _active_groups.get(group_id)
            if not grp or grp.get("stopped"):
                logger.info(f"[⏹️] Trade {trade_id}: group stopped before entry; skipping.")
                return

        # create pending trade entry
        event = threading.Event()
        placed_at = datetime.now(when.tzinfo)
        trade_info = {
            "id": trade_id,
            "currency": currency,
            "direction": direction,
            "timeframe": timeframe,
            "group_id": group_id,
            "martingale_level": martingale_level,
            "placed_at": placed_at,
            "result": None,
            "event": event
        }
        with _registry_lock:
            _pending_trades[trade_id] = trade_info

        # log pre-fire personality line
        logger.info(_random_log("firing_logs"))

        # send main trade hotkey (only)
        try:
            if direction.upper() == "BUY":
                pyautogui.hotkey("shift", "w")
            else:
                pyautogui.hotkey("shift", "s")
            logger.info(f"[🎯] Trade {trade_id}: main-hotkey sent ({direction}) at {placed_at.strftime('%H:%M:%S')} level={martingale_level}")
        except Exception as e:
            logger.error(f"[❌] Trade {trade_id}: failed to send main-hotkey: {e}")

        # after placing: wait 2-40s and send increase-hotkey ONCE
        # only send increase if martingale_level is <= max_martingale (we still send on base level as "prepare")
        if martingale_level <= self.max_martingale:
            inc_delay = random.randint(2, 40)
            logger.info(f"[⌛] Trade {trade_id}: waiting {inc_delay}s before increase-hotkey (level={martingale_level})")
            time.sleep(inc_delay)
            try:
                logger.info(_random_log("martingale_logs"))
                pyautogui.hotkey("shift", "d")
                logger.info(f"[📈] Trade {trade_id}: increase-hotkey sent (level={martingale_level})")
            except Exception as e:
                logger.error(f"[❌] Trade {trade_id}: failed to send increase-hotkey: {e}")

        # Wait for expiry time for this trade's timeframe (plus buffer)
        expiry_seconds = _tf_to_seconds(timeframe)
        wait_timeout = expiry_seconds + EXPIRY_BUFFER_SECONDS
        logger.info(f"[⏳] Trade {trade_id}: waiting up to {wait_timeout}s for result (timeframe={timeframe})")

        got_result = event.wait(timeout=wait_timeout)

        if got_result:
            # process result
            with _registry_lock:
                info = _pending_trades.get(trade_id)
            result_text = info.get("result") if info else None
            logger.info(f"[📣] Trade {trade_id}: result received -> {result_text}")
            # Win handling: stop group
            if result_text and result_text.strip().upper().startswith("WIN"):
                logger.info(_random_log("win_logs"))
                logger.info(f"[✅] Trade {trade_id} WIN — stopping martingale chain for group {group_id}")
                with _registry_lock:
                    grp = _active_groups.get(group_id)
                    if grp is not None:
                        grp["stopped"] = True
                    _pending_trades.pop(trade_id, None)
                return
            else:
                # LOSS or other - continue if next martingale scheduled
                logger.info(_random_log("loss_logs"))
                logger.info(f"[↪️] Trade {trade_id} LOSS/OTHER — continuing to next scheduled martingale (if any).")
                with _registry_lock:
                    _pending_trades.pop(trade_id, None)
                return
        else:
            # No result received within expiry => stop group and log
            logger.warning(f"[❌] Trade {trade_id}: NO RESULT received from screen_logic within expiry. Stopping martingale chain for group {group_id}.")
            logger.info(_random_log("loss_logs"))
            with _registry_lock:
                grp = _active_groups.get(group_id)
                if grp is not None:
                    grp["stopped"] = True
                _pending_trades.pop(trade_id, None)
            return

    # ---- results API ----
    def _set_result_for_id(self, trade_id: str, result_text: str):
        with _registry_lock:
            info = _pending_trades.get(trade_id)
            if not info:
                logger.info(f"[ℹ️] Received result for unknown/cleared trade_id={trade_id}: {result_text}")
                return False
            info["result"] = result_text
            info["event"].set()
            return True

    def trade_result_received(self, trade_id: Optional[str], result_text: str):
        """
        Accepts a result_text like "WIN +$1.23" or "LOSS" etc.
        If trade_id provided, we match exactly. Otherwise we match the most recent pending trade.
        """
        try:
            rt = (result_text or "").strip()
            logger.info(f"[🛰️] trade_result_received called -> {trade_id=} {rt}")
            if trade_id:
                ok = self._set_result_for_id(trade_id, rt)
                if ok:
                    logger.debug(f"[ℹ️] Matched result by id {trade_id}")
                    return
            # No id or not found: match most recent pending trade
            with _registry_lock:
                if not _pending_trades:
                    logger.info(f"[ℹ️] No pending trades to match result: {rt}")
                    return
                # pick most recent placed_at
                latest_id = None
                latest_time = None
                for tid, tinfo in _pending_trades.items():
                    pat = tinfo.get("placed_at")
                    if not latest_time or (pat and pat > latest_time):
                        latest_id = tid
                        latest_time = pat
                if latest_id:
                    self._set_result_for_id(latest_id, rt)
                    logger.debug(f"[ℹ️] Matched result to most recent pending id {latest_id}")
                    return
        except Exception as e:
            logger.exception(f"[❌] trade_result_received error: {e}")

    def handle_trade_result(self, status: str, amount: Optional[float] = None, trade_id: Optional[str] = None):
        """
        Alternate structured API: screen_logic can call this like:
            core.handle_trade_result(status='WIN', amount=+1.23, trade_id='...') 
        """
        try:
            s = (status or "").strip()
            txt = s
            if amount is not None:
                # format amount if numeric
                try:
                    txt = f"{s} {amount:+g}"
                except Exception:
                    txt = f"{s} {amount}"
            self.trade_result_received(trade_id, txt)
        except Exception as e:
            logger.exception(f"[❌] handle_trade_result error: {e}")

# single manager instance
_manager = TradeManager(max_martingale=3)

# ---------------------------
# Public API
# ---------------------------
def signal_callback(signal: dict):
    """
    External entrypoint: non-blocking. Use to submit parsed signals from telegram listener.
    """
    _manager.handle_signal(signal)

def trade_result_received(trade_id: Optional[str], result_text: str):
    """
    Backwards-compatible alias: screen_logic may call this to report results.
    """
    _manager.trade_result_received(trade_id, result_text)

def handle_trade_result(status: str, amount: Optional[float] = None, trade_id: Optional[str] = None):
    """
    Structured result API: screen_logic may call this.
    """
    _manager.handle_trade_result(status, amount, trade_id)

# Keep the process alive when run directly
if __name__ == "__main__":
    logger.info("[🚀] Core started (hotkey mode). Waiting for signals...")
    try:
        while True:
            # emit occasional idle personality logs during long waits
            time.sleep(30)
            logger.info(_random_log("idle_logs"))
    except KeyboardInterrupt:
        logger.info("[🛑] Core stopped by KeyboardInterrupt")
