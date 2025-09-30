"""
core.py - Precision trading core

- Treats signal entry_time as coming from the sender's timezone (signal['source'])
  then converts it to Jakarta time (Asia/Jakarta) and schedules execution accordingly.
- Uses MAX_FUTURE_MINUTES to ignore signals that are too far ahead.
- Fires currency-switch strokes randomly every 5-9 seconds until Selenium confirms asset/timeframe.
- If entry time arrives before confirmation, trade is expired.
- Martingale scheduling supported.
- Personality engine reads logs.json and prints randomized hype messages (idle + event-driven).
"""

import json
import os
import random
import threading
import time
from datetime import datetime, timedelta, timezone
import logging

import pyautogui
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Try zoneinfo (stdlib) first; fall back to pytz
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# =========================
# Configuration
# =========================
MAX_FUTURE_MINUTES = 10  # ignore signals more than this many minutes in future
SWITCH_FIRE_MIN = 5
SWITCH_FIRE_MAX = 9
IDLE_LOG_MIN = 30  # seconds (Option A: 30–60s)
IDLE_LOG_MAX = 60
LOGS_JSON = os.path.join(os.path.dirname(__file__), "logs.json")
JAKARTA_TZ_NAME = "Asia/Jakarta"
# Map signal source string to tz names
SOURCE_TZ_MAP = {
    "UTC-4": "Etc/GMT+4" if not ZoneInfo else "America/New_York",
    "UTC-3": "Etc/GMT+3" if not ZoneInfo else "America/Sao_Paulo",
    "Cameroon": "Africa/Douala",
    "OTC-3": "Etc/GMT+3",
}

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("precision-core")

# Also optionally log to file
file_handler = logging.FileHandler("precision_core.log")
file_handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', '%H:%M:%S'))
logger.addHandler(file_handler)

# =========================
# Personality / Logs Loader
# =========================
def load_personality_logs(path=LOGS_JSON):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Validate presence of categories
            return {
                "idle": data.get("idle_logs", []),
                "pre_trade": data.get("pre_trade_logs", []),
                "firing": data.get("firing_logs", []),
                "martingale": data.get("martingale_logs", []),
                "win": data.get("win_logs", []),
                "loss": data.get("loss_logs", []),
                "praise_desmond": data.get("praise_desmond", []),
                "roast": data.get("roast_others", []),
                "questions": data.get("questions", [])
            }
    except Exception as e:
        logger.warning(f"[⚠️] Could not load logs.json ({e}). Falling back to built-in messages.")
        # fallback minimal messages
        return {
            "idle": ["Precision is idling, waiting for Desmond's next order."],
            "pre_trade": ["Precision locked on target — Desmond got this one."],
            "firing": ["Firing strokes — Precision warming up."],
            "martingale": ["Martingale engaged — trust the process."],
            "win": ["Bullseye! Direct win for Desmond."],
            "loss": ["We missed one; Precision will adapt."],
            "praise_desmond": ["Desmond believed — now it pays."],
            "roast": ["They said bots can't trade. Joke's on them."],
            "questions": ["How do you feel watching Desmond's precision?"]
        }

PERSONALITY = load_personality_logs(LOGS_JSON)

def pick_log(category):
    arr = PERSONALITY.get(category, [])
    if not arr:
        return None
    return random.choice(arr)

# Idle chatter thread
def idle_chatter_loop():
    while True:
        sleep_sec = random.randint(IDLE_LOG_MIN, IDLE_LOG_MAX)
        time.sleep(sleep_sec)
        msg = pick_log("idle")
        if msg:
            logger.info(f"[🤖] {msg}")
        # random praise or question occasionally
        if random.random() < 0.35:
            msg2 = pick_log("praise_desmond")
            if msg2:
                logger.info(f"[🏅] {msg2}")
        if random.random() < 0.2:
            q = pick_log("questions")
            if q:
                logger.info(f"[❓] {q}")

# Start idle chatter thread (daemon)
threading.Thread(target=idle_chatter_loop, daemon=True).start()

# =========================
# Selenium Integration
# =========================
class PocketOptionSelenium:
    CHECK_INTERVAL = 0.5

    def __init__(self, trade_manager=None, headless=False):
        self.trade_manager = trade_manager
        self.driver = None
        try:
            self.driver = self.setup_driver(headless)
            logger.info("[✅] Chrome started and navigated to Pocket Option login.")
        except Exception as e:
            logger.error(f"[❌] Selenium driver setup failed: {e}")
            self.driver = None
        # start monitor for trade results if driver available
        if self.driver:
            self.start_result_monitor()

    def setup_driver(self, headless=False):
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-data-dir=/tmp/chrome-user-data")
        if headless:
            chrome_options.add_argument("--headless=new")
        service = Service("/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get("https://pocketoption.com/en/login/")
        return driver

    def confirm_asset_ready(self, asset_name, timeframe, entry_time_str):
        """
        Returns True if current asset matches asset_name and timeframe is set.
        entry_time_str not heavily used here except for debug display.
        """
        if not self.driver:
            logger.debug("[⚠️] No Selenium driver available, assume asset not ready.")
            return False
        try:
            # find asset name element (selector may need adjustment)
            asset_element = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
            current_asset = asset_element.text.strip()
            logger.debug(f"[🔍] Screen asset: '{current_asset}' vs expected '{asset_name}'")
            if current_asset != asset_name:
                return False
            # check timeframe and set if needed
            try:
                dropdown = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-dropdown")
                current_tf = dropdown.text.strip()
                if current_tf != timeframe:
                    dropdown.click()
                    opt = self.driver.find_element(By.XPATH, f"//li[contains(text(), '{timeframe}')]")
                    opt.click()
                    pyautogui.click(random.randint(100, 300), random.randint(100, 300))
                    logger.info(f"[🕒] Timeframe adjusted to {timeframe}")
            except Exception:
                # ignore if timeframe UI differs
                pass
            return True
        except Exception as e:
            logger.debug(f"[⚠️] confirm_asset_ready exception: {e}")
            return False

    def detect_trade_result(self):
        """
        Implement detection logic specific to your UI. Returns "WIN"/"LOSS"/None
        """
        if not self.driver:
            return None
        try:
            results = self.driver.find_elements(By.CSS_SELECTOR, ".trade-history .trade-result")
            for r in results:
                txt = r.text.strip()
                if txt.startswith("+"):
                    return "WIN"
                if txt == "$0" or "LOSS" in txt.upper():
                    return "LOSS"
            return None
        except Exception:
            return None

    def start_result_monitor(self):
        def monitor():
            while True:
                result = self.detect_trade_result()
                if result == "WIN":
                    if self.trade_manager:
                        self.trade_manager.martingale_stop_flags.clear()
                    logger.info(f"[🏆] {pick_log('win') or 'WIN detected — Precision celebrated.'}")
                elif result == "LOSS":
                    logger.info(f"[💥] {pick_log('loss') or 'LOSS detected — Precision reloading martingale.'}")
                time.sleep(self.CHECK_INTERVAL)
        threading.Thread(target=monitor, daemon=True).start()

# =========================
# Helpers: timezone conversion
# =========================
def get_tz_from_source(source_str):
    if not source_str:
        source_str = "OTC-3"
    key = source_str.strip()
    mapped = SOURCE_TZ_MAP.get(key)
    if mapped:
        # If zoneinfo available and mapping is a real name, try ZoneInfo first
        if ZoneInfo and not mapped.startswith("Etc/"):
            try:
                return ZoneInfo(mapped)
            except Exception:
                pass
        # fallback to pytz timezone
        try:
            return pytz.timezone(mapped)
        except Exception:
            pass
    # last resort: try direct zone name
    try:
        return pytz.timezone(source_str)
    except Exception:
        return pytz.UTC

def parse_entry_time_to_utc(entry_time_str: str, source: str):
    """
    Interpret entry_time_str (HH:MM or HH:MM:SS) as time in 'source' timezone,
    then convert to UTC datetime. If time has already passed in source tz today,
    schedule for tomorrow.
    """
    # determine tz for source
    src_tz = get_tz_from_source(source)
    # parse time
    fmt = "%H:%M:%S" if entry_time_str.count(":") == 2 else "%H:%M"
    try:
        t = datetime.strptime(entry_time_str, fmt).time()
    except Exception as e:
        raise ValueError(f"Invalid time format '{entry_time_str}': {e}")
    # now in source tz
    now_src = datetime.now(pytz.UTC).astimezone(src_tz)
    entry_src = datetime.combine(now_src.date(), t)
    if isinstance(src_tz, datetime.tzinfo):
        # if tz-aware style (ZoneInfo)
        try:
            entry_src = entry_src.replace(tzinfo=src_tz)
        except Exception:
            entry_src = src_tz.localize(entry_src) if hasattr(src_tz, "localize") else entry_src.replace(tzinfo=src_tz)
    else:
        # pytz timezone
        entry_src = src_tz.localize(entry_src)
    # if already passed, assume next day
    if entry_src <= now_src:
        entry_src = entry_src + timedelta(days=1)
    # convert to UTC
    entry_utc = entry_src.astimezone(pytz.UTC)
    # Also produce Jakarta local dt for messaging (not strictly necessary for scheduling)
    jakarta_tz = pytz.timezone(JAKARTA_TZ_NAME)
    entry_jakarta = entry_src.astimezone(jakarta_tz)
    return entry_utc, entry_jakarta

# =========================
# Core Trade Manager
# =========================
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=2):
        self.trading_active = True
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.martingale_stop_flags = {}
        logger.info(f"TradeManager initialized | base_amount: {base_amount}, max_martingale: {max_martingale}")

    def handle_command(self, command: str):
        cmd = command.strip().lower()
        if cmd.startswith("/start"):
            self.trading_active = True
            logger.info("[🚀] Trading started")
        elif cmd.startswith("/stop"):
            self.trading_active = False
            logger.info("[⏹️] Trading stopped")
        else:
            logger.info(f"[ℹ️] Unknown command: {command}")

    def handle_signal(self, signal: dict):
        """
        Signal must include: currency_pair, direction, entry_time, timeframe, martingale_times, source
        """
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Signal ignored.")
            return

        logger.info(f"[📡] Received signal: {signal}")

        source = signal.get("source", "OTC-3")
        try:
            entry_utc, entry_jakarta = parse_entry_time_to_utc(signal["entry_time"], source)
        except Exception as e:
            logger.error(f"[❌] Could not parse entry_time: {e}")
            return

        now_utc = datetime.now(pytz.UTC)
        delta = (entry_utc - now_utc).total_seconds()

        if delta <= 0:
            logger.info(f"[⏹️] Signal entry time {signal['entry_time']} already passed (after timezone conversion). Ignored.")
            return
        if delta > MAX_FUTURE_MINUTES * 60:
            logger.info(f"[🚫] Signal entry {entry_jakarta.strftime('%H:%M')} (Jakarta) is more than {MAX_FUTURE_MINUTES} minutes away. Ignoring.")
            return

        # convert martingale times as well
        mg_utc_list = []
        mg_jakarta_list = []
        for mg in signal.get("martingale_times", []):
            try:
                m_utc, m_jakarta = parse_entry_time_to_utc(mg, source)
                mg_utc_list.append(m_utc)
                mg_jakarta_list.append(m_jakarta)
            except Exception:
                logger.warning(f"[⚠️] Invalid martingale time '{mg}', skipping.")

        # Build normalized schedule dict
        normalized = {
            "currency_pair": signal.get("currency_pair"),
            "direction": signal.get("direction"),
            "timeframe": signal.get("timeframe"),
            "entry_utc": entry_utc,
            "entry_jakarta": entry_jakarta,
            "martingale_utc": mg_utc_list,
            "martingale_jakarta": mg_jakarta_list,
            "raw_signal": signal
        }

        # log pre-trade hype
        logger.info(f"[🎯] Precision locked on target — {normalized['currency_pair']} @ {entry_jakarta.strftime('%H:%M')} Jakarta time.")
        pre = pick_log("pre_trade")
        if pre:
            logger.info(f"[✨] {pre}")

        # schedule main trade
        threading.Thread(target=self._run_scheduled_trade, args=(normalized, 0), daemon=True).start()
        logger.info(f"[⏱️] Main trade scheduled in {delta:.1f}s (Jakarta {entry_jakarta.strftime('%H:%M')})")

        # schedule martingales
        for idx, m_utc in enumerate(mg_utc_list):
            lvl = idx + 1
            if lvl > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {lvl} exceeds max {self.max_martingale}, skip.")
                break
            threading.Thread(target=self._run_scheduled_trade, args=(normalized, lvl), daemon=True).start()
            logger.info(f"[🔁] Martingale level {lvl} scheduled at {mg_jakarta_list[idx].strftime('%H:%M')} (Jakarta)")

    def _run_scheduled_trade(self, normalized: dict, martingale_level: int):
        cp = normalized["currency_pair"]
        direction = normalized.get("direction", "BUY")
        tf = normalized.get("timeframe", "M1")

        # choose datetime for this level
        if martingale_level == 0:
            entry_dt = normalized["entry_utc"]
            entry_jakarta = normalized["entry_jakarta"]
        else:
            idx = martingale_level - 1
            try:
                entry_dt = normalized["martingale_utc"][idx]
                entry_jakarta = normalized["martingale_jakarta"][idx]
            except Exception:
                logger.warning(f"[⚠️] Missing martingale time for level {martingale_level}, skipping.")
                return

        now_utc = datetime.now(pytz.UTC)
        delay = (entry_dt - now_utc).total_seconds()
        logger.info(f"[⏰] Trade level {martingale_level} for {cp} scheduled at {entry_jakarta.strftime('%H:%M')} Jakarta (in {delay:.1f}s)")

        if delay <= 0:
            logger.info(f"[⏹️] Entry time already passed for {cp} (level {martingale_level}). Skipping.")
            return
        if delay > MAX_FUTURE_MINUTES * 60:
            logger.info(f"[🚫] Entry for {cp} (level {martingale_level}) too far in future. Skipping.")
            return

        # wait until shortly before execution, but keep responsive
        # We'll aim to start switching loop a little earlier (e.g., 10s before) if possible
        pre_switch_margin = min(20, delay / 2)  # start switching earlier if close enough
        if delay > pre_switch_margin:
            sleep_time = delay - pre_switch_margin
            logger.info(f"[⏱️] Sleeping {sleep_time:.1f}s before starting asset switching loop for {cp} (level {martingale_level})")
            # small sleep loop to stay responsive
            slept = 0.0
            while slept < sleep_time:
                time.sleep(1.0)
                slept += 1.0

        # Begin firing switching strokes until asset confirmed or entry time arrives
        logger.info(f"[🔄] Beginning asset-switch firing loop for {cp} (level {martingale_level}).")
        firing_start = datetime.now(pytz.UTC)
        confirmed = False

        while True:
            now_utc = datetime.now(pytz.UTC)
            # if time is up, expire
            if now_utc >= entry_dt:
                logger.info(f"[⚠️] Entry time reached ({entry_jakarta.strftime('%H:%M')}) before asset confirmed for {cp}. Trade expired.")
                confirmed = False
                break

            # Fire switch keystroke
            try:
                self._fire_switch_keystroke(cp)
                logger.info(f"[🔥] Firing currency switching stroke for {cp} (level {martingale_level})")
                # occasional witty firing log
                if random.random() < 0.35:
                    msg = pick_log("firing")
                    if msg:
                        logger.info(f"[🔥] {msg}")
            except Exception as e:
                logger.warning(f"[⚠️] _fire_switch_keystroke error: {e}")

            # brief pause for UI to update, then check via Selenium
            time.sleep(1.0)
            try:
                if selenium_integration.confirm_asset_ready(cp, tf, entry_jakarta.strftime("%H:%M")):
                    confirmed = True
                    logger.info(f"[✅] Asset {cp} confirmed (Jakarta {entry_jakarta.strftime('%H:%M')}). Stopped firing switching strokes.")
                    break
            except Exception as e:
                logger.warning(f"[⚠️] Selenium check failed: {e}")

            # next sleep randomized 5-9s but ensure not overshooting entry time
            remaining = (entry_dt - datetime.now(pytz.UTC)).total_seconds()
            if remaining <= 0:
                logger.info(f"[⚠️] Entry time reached while waiting for asset confirmation for {cp}. Trade expired.")
                confirmed = False
                break
            sleep_sec = min(random.randint(SWITCH_FIRE_MIN, SWITCH_FIRE_MAX), max(0.2, remaining))
            time.sleep(sleep_sec)

        if not confirmed:
            logger.info(f"[⛔] Trade for {cp} at level {martingale_level} not executed (asset not confirmed).")
            return

        # wait until exact entry time
        now_utc = datetime.now(pytz.UTC)
        wait_seconds = (entry_dt - now_utc).total_seconds()
        if wait_seconds > 0:
            logger.info(f"[⏱️] Waiting {wait_seconds:.2f}s until entry time for {cp} (Jakarta {entry_jakarta.strftime('%H:%M')}).")
            # sleep in small increments
            slept = 0.0
            while slept < wait_seconds:
                chunk = min(1.0, wait_seconds - slept)
                time.sleep(chunk)
                slept += chunk

        # final timing check
        i
