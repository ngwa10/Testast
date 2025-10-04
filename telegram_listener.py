# core.py
"""
Core trading logic (hotkey-driven, personality logs)
"""

import json
import logging
import threading
import time
import random
import uuid
from datetime import datetime
from typing import Optional
import time 
import os
import shared  # 👈 shared singleton

# Lazy import helper
pyautogui = get_pyautogui()
    import importlib
    if not os.environ.get("DISPLAY"):
        os.environ["DISPLAY"] = ":1"
    # ✅ Wait until DISPLAY socket is available (VNC started)
    for _ in range(20):  # ~20s max
        if os.path.exists("/tmp/.X11-unix/X1"):
            break
        print("[ℹ️] Waiting for X11 display to become ready...")
        time.sleep(1)
    return importlib.import_module("pyautogui")

# Replace this line ↓
# import pyautogui
pyautogui
 = get_pyautogui()

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
EXPIRY_BUFFER_SECONDS = 5
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
# Load personality logs
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
_pending_trades = {}
_active_groups = {}

# ---------------------------
# Utilities
# ---------------------------
def _tf_to_seconds(tf: str) -> int:
    if not tf:
        return 60
    return TIMEFRAME_SECONDS.get(tf.strip().upper(), 60)

def _normalize_currency(pair: str) -> str:
    if not pair:
        return ""
    return pair.replace("/", "").replace(" ", "").upper()

# ---------------------------
# Trade Manager
# ---------------------------
class TradeManager:
    def __init__(self, max_martingale: int = 3):
        self.max_martingale = max_martingale
        pyautogui.FAILSAFE = False
        logger.info("[ℹ️] TradeManager initialized.")
        logger.info(_random_log("idle_logs"))

    def handle_signal(self, signal: dict):
        try:
            currency_raw = signal.get("currency_pair")
            direction = (signal.get("direction") or "BUY").upper()
            entry_time = signal.get("entry_time")
            mg_times = signal.get("martingale_times", []) or []
            timeframe = (signal.get("timeframe") or "M1").upper()

            if not currency_raw or not isinstance(entry_time, datetime) or entry_time.tzinfo is None:
                logger.warning("[⚠️] Invalid signal: missing currency or timezone-aware entry_time.")
                return

            currency = _normalize_currency(currency_raw)
            group_id = f"{currency}_{entry_time.isoformat()}_{uuid.uuid4().hex[:8]}"

            with _registry_lock:
                _active_groups[group_id] = {"stopped": False, "signal": signal}

            logger.info(f"[📩] Signal received for {currency_raw} ({direction}) at {entry_time.strftime('%H:%M:%S')} — scheduling (group={group_id})")
            logger.info(_random_log("pre_trade_logs"))

            # Fire-and-forget screen logic
            try:
                import screen_logic
                try:
                    screen_logic.select_currency(currency, timeframe)
                except TypeError:
                    screen_logic.select_currency(currency)
                logger.info(f"[🛰️] Instructed screen_logic to select {currency}/{timeframe}")
            except Exception:
                logger.info(f"[🛰️] screen_logic not available; continuing.")

            # Schedule base trade
            self._schedule_trade(entry_time, currency, direction, timeframe, group_id, martingale_level=0)

            # Schedule martingales
            for idx, mg_time in enumerate(mg_times):
                level = idx + 1
                if level > self.max_martingale:
                    logger.warning(f"[⚠️] Martingale time at level {level} exceeds max; skipping.")
                    break
                self._schedule_trade(mg_time, currency, direction, timeframe, group_id, martingale_level=level)

        except Exception as e:
            logger.exception(f"[❌] handle_signal unexpected error: {e}")

    # ---- schedule trade ----
    def _schedule_trade(self, when, currency, direction, timeframe, group_id, martingale_level):
        trade_id = f"{currency}_{when.strftime('%H%M%S')}_{martingale_level}_{uuid.uuid4().hex[:6]}"
        thread = threading.Thread(target=self._trade_worker,
                                  args=(trade_id, when, currency, direction, timeframe, group_id, martingale_level),
                                  daemon=True)
        thread.start()
        logger.info(f"[🗓️] Scheduled trade id={trade_id} level={martingale_level} at {when.strftime('%H:%M:%S')} (group={group_id})")

    # ---- worker ----
    def _trade_worker(self, trade_id, when, currency, direction, timeframe, group_id, martingale_level):
        try:
            now = datetime.now(when.tzinfo)
            delay = (when - now).total_seconds()
            if delay > 0:
                logger.info(f"[⏱️] Trade {trade_id}: waiting {delay:.1f}s until entry (level={martingale_level})")
                time.sleep(delay)
        except Exception:
            pass

        with _registry_lock:
            grp = _active_groups.get(group_id)
            if not grp or grp.get("stopped"):
                logger.info(f"[⏹️] Trade {trade_id}: group stopped before entry; skipping.")
                return

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

        logger.info(_random_log("firing_logs"))

        # send hotkey
        try:
            if direction.upper() == "BUY":
                pyautogui.hotkey("shift", "w")
            else:
                pyautogui.hotkey("shift", "s")
            logger.info(f"[🎯] Trade {trade_id}: main-hotkey sent ({direction}) at {placed_at.strftime('%H:%M:%S')} level={martingale_level}")
        except Exception as e:
            logger.error(f"[❌] Trade {trade_id}: failed main-hotkey: {e}")

        # increase trade amount ONCE
        if martingale_level <= self.max_martingale:
            inc_delay = random.randint(2, 40)
            logger.info(f"[⌛] Trade {trade_id}: waiting {inc_delay}s before increase-hotkey (level={martingale_level})")
            time.sleep(inc_delay)
            try:
                logger.info(_random_log("martingale_logs"))
                pyautogui.hotkey("shift", "d")
                logger.info(f"[📈] Trade {trade_id}: increase-hotkey sent (level={martingale_level})")
            except Exception as e:
                logger.error(f"[❌] Trade {trade_id}: failed increase-hotkey: {e}")

        # wait for result
        expiry_seconds = _tf_to_seconds(timeframe)
        wait_timeout = expiry_seconds + 5
        got_result = event.wait(timeout=wait_timeout)

        if got_result:
            with _registry_lock:
                info = _pending_trades.get(trade_id)
            result_text = info.get("result") if info else None
            logger.info(f"[📣] Trade {trade_id}: result received -> {result_text}")
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
                logger.info(_random_log("loss_logs"))
                logger.info(f"[↪️] Trade {trade_id} LOSS/OTHER — continuing to next martingale.")
                with _registry_lock:
                    _pending_trades.pop(trade_id, None)
                return
        else:
            logger.warning(f"[❌] Trade {trade_id}: NO RESULT received within expiry. Stopping group {group_id}.")
            logger.info(_random_log("loss_logs"))
            with _registry_lock:
                grp = _active_groups.get(group_id)
                if grp:
                    grp["stopped"] = True
                _pending_trades.pop(trade_id, None)
            return

    # ---- result API ----
    def _set_result_for_id(self, trade_id: str, result_text: str):
        with _registry_lock:
            info = _pending_trades.get(trade_id)
            if not info:
                logger.info(f"[ℹ️] Received result for unknown trade_id={trade_id}: {result_text}")
                return False
            info["result"] = result_text
            info["event"].set()
            return True

    def trade_result_received(self, trade_id: Optional[str], result_text: str):
        try:
            rt = (result_text or "").strip()
            logger.info(f"[🛰️] trade_result_received called -> {trade_id=} {rt}")
            if trade_id:
                ok = self._set_result_for_id(trade_id, rt)
                if ok:
                    return
            with _registry_lock:
                if not _pending_trades:
                    return
                latest_id = max(_pending_trades, key=lambda k: _pending_trades[k]["placed_at"])
            self._set_result_for_id(latest_id, rt)
        except Exception as e:
            logger.exception(f"[❌] trade_result_received error: {e}")

    def handle_trade_result(self, status: str, amount: Optional[float] = None, trade_id: Optional[str] = None):
        try:
            txt = status
            if amount is not None:
                txt = f"{status} {amount:+g}"
            self.trade_result_received(trade_id, txt)
        except Exception as e:
            logger.exception(f"[❌] handle_trade_result error: {e}")

    # ---- handle Telegram /start and /stop ----
    def handle_command(self, cmd: str):
        """
        Handles commands like /start and /stop without breaking the core logic.
        """
        try:
            if cmd.startswith("/start"):
                logger.info("[✅] Trading started (command received)")
                # Optional: self.enabled = True
            elif cmd.startswith("/stop"):
                logger.info("[🛑] Trading stopped (command received)")
                # Optional: self.enabled = False
            else:
                logger.info(f"[ℹ️] Unknown command received: {cmd}")
        except Exception as e:
            logger.exception(f"[❌] handle_command error: {e}")

# ---------------------------
# Create singleton in shared
# ---------------------------
shared.trade_manager = TradeManager(max_martingale=3)

# ---------------------------
# Public API
# ---------------------------
def signal_callback(signal: dict):
    shared.trade_manager.handle_signal(signal)

def trade_result_received(trade_id: Optional[str], result_text: str):
    shared.trade_manager.trade_result_received(trade_id, result_text)

def handle_trade_result(status: str, amount: Optional[float] = None, trade_id: Optional[str] = None):
    shared.trade_manager.handle_trade_result(status, amount, trade_id)

# ---------------------------
# Keep ali
ve
# ---------------------------
if __name__ == "__main__":
    logger.info("[🚀] Core started (hotkey mode). Waiting for signals...")
    try:
        while True:
            time.sleep(30)
            logger.info(_random_log("idle_logs"))
    except KeyboardInterrupt:
        logger.info("[🛑] Core stopped by KeyboardInterrupt")
