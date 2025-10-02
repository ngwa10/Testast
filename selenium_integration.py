"""
selenium_integration.py — PocketOptionSelenium

Notes:
- Hardcoded EMAIL/PASSWORD here (deployment). Change if needed.
- chromedriver path: /usr/local/bin/chromedriver (change if different).
- Uses pyautogui for some clicks (hotkey_mode). Requires DISPLAY (Xvfb / VNC).
- Behaviors implemented:
  * select_asset: opens dropdown, waits 2-10s, focuses search, types CADUSD (no slash),
    waits 2-10s, clicks first result preferring "OTC", random delay 2-10s between actions.
  * set_timeframe: clicks timeframe dropdown, waits, selects 1M/5M, random delays.
  * prepare_for_trade: selects asset/timeframe and spawns a monitor for expected result time.
  * intensive monitoring: starts MONITOR_LEAD_SECONDS before result_dt and polls every INTENSE_POLL_INTERVAL.
  * logs readiness, receipt of orders, results sent to core.
"""

import time
import threading
import random
import uuid
import logging
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pyautogui

logger = logging.getLogger(__name__)

# Hardcoded credentials (deployment)
EMAIL = "mylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"

CHECK_INTERVAL = 0.5  # regular scan interval (s)
INTENSE_POLL_INTERVAL = 0.1  # intensive poll interval (s)
MONITOR_LEAD_SECONDS = 30  # seconds before expected result to start intensive monitoring

pyautogui.FAILSAFE = False

# timeframe seconds mapping
TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 300
}

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL or PASSWORD not set.")

class PocketOptionSelenium:
    def __init__(self, trade_manager, headless=True, hotkey_mode=True):
        self.trade_manager = trade_manager
        self.headless = headless
        self.hotkey_mode = hotkey_mode
        self.driver = self.setup_driver(headless)
        self._monitors = {}           # key: (currency, entry_iso) -> monitor info
        self._monitors_lock = threading.Lock()
        self._global_monitor_running = False
        self.start_result_monitor()
        logger.info("[🟢] Selenium initialized and ready — waiting for orders from Core.")

    # -----------------
    # Setup Chrome
    # -----------------
    def setup_driver(self, headless=True):
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--start-maximized")

        session_id = str(uuid.uuid4())
        chrome_options.add_argument(f"--user-data-dir=/tmp/chrome-user-data-{session_id}")

        if headless:
            chrome_options.add_argument("--headless=new")

        service = Service("/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get("https://pocketoption.com/en/login/")
        logger.info("[✅] Chrome started and navigated to login.")

        # Auto-login
        try:
            wait = WebDriverWait(driver, 30)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            email_field.clear()
            email_field.send_keys(EMAIL)
            password_field.clear()
            password_field.send_keys(PASSWORD)
            login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            logger.info("[🔐] Login submitted.")
            time.sleep(3)
        except Exception as e:
            logger.warning(f"[⚠️] Auto-login failed: {e}")
        return driver

    # -----------------
    # Utility: small randomized pause (2-10s)
    # -----------------
    def _rand_pause(self, a=2.0, b=10.0):
        s = random.uniform(a, b)
        logger.debug(f"[⌛] Waiting {s:.1f}s (randomized pause).")
        time.sleep(s)

    # -----------------
    # Select asset: opens dropdown, types pair (no slash), clicks first result (prefer OTC)
    # -----------------
    def select_asset(self, currency_pair, max_attempts=5):
        """
        currency_pair is normalized e.g. "CADUSD" (no slash).
        Steps:
          1) Click asset-name-selector to open dropdown
          2) pause 2-10s
          3) focus search input inside dropdown
          4) type currency_pair (no slash)
          5) pause 2-10s
          6) click first result preferring OTC
          7) pause 2-10s and return True
        """
        try:
            for attempt in range(max_attempts):
                try:
                    # 1) click asset dropdown opener
                    opener = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
                    opener.click()
                    logger.debug("[🖱️] Clicked asset dropdown opener.")
                    self._rand_pause()

                    # 2) find search input
                    # try multiple selectors (site may vary)
                    search_input = None
                    try:
                        search_input = self.driver.find_element(By.CSS_SELECTOR, ".asset-dropdown input")
                    except Exception:
                        try:
                            search_input = self.driver.find_element(By.CSS_SELECTOR, "input[data-test='asset-search']")
                        except Exception:
                            pass

                    if not search_input:
                        logger.debug("[⚠️] Search input not found; retrying...")
                        time.sleep(0.5)
                        continue

                    # 3) type the currency pair without slash
                    search_term = currency_pair.replace("/", "").replace(" ", "").upper()
                    search_input.clear()
                    # send chars with small delay
                    for ch in search_term:
                        search_input.send_keys(ch)
                        time.sleep(0.05)
                    logger.debug(f"[🔍] Typed search term '{search_term}' into asset search.")
                    self._rand_pause()

                    # 4) find results list and click the first entry (prefer OTC)
                    options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-dropdown .option")
                    if not options:
                        # try alternate selector
                        options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-list .asset-item")
                    if not options:
                        logger.debug("[⚠️] No asset options found after search; retrying...")
                        time.sleep(0.5)
                        continue

                    # choose first that contains OTC or first overall
                    chosen = None
                    for opt in options:
                        txt = opt.text.strip().upper()
                        if "OTC" in txt and (search_term in txt or search_term.replace("/", "") in txt):
                            chosen = opt
                            logger.debug(f"[📈] Found OTC entry in options: '{txt[:80]}'")
                            break
                    if not chosen:
                        chosen = options[0]
                        logger.debug(f"[📈] Choosing first option: '{chosen.text.strip()[:80]}'")

                    # click chosen element
                    try:
                        chosen.click()
                    except Exception:
                        # fallback: use JS click
                        self.driver.execute_script("arguments[0].click();", chosen)
                    logger.debug("[🖱️] Clicked chosen asset option.")
                    self._rand_pause()

                    # center click to ensure dropdown closed (if hotkey_mode)
                    if self.hotkey_mode:
                        # click near center of window/chart area
                        try:
                            width = self.driver.execute_script("return window.innerWidth")
                            height = self.driver.execute_script("return window.innerHeight")
                            x = int(width * 0.5) + random.randint(-30, 30)
                            y = int(height * 0.4) + random.randint(-20, 20)
                            pyautogui.click(x, y)
                            logger.debug(f"[🖱️] Clicked center area to close asset dropdown at ({x},{y}).")
                        except Exception:
                            pass
                        self._rand_pause(0.6, 1.5)

                    return True

                except Exception as e:
                    logger.debug(f"[⚠️] select_asset attempt failed: {e}")
                    time.sleep(0.6)
            return False
        except Exception as e:
            logger.error(f"[❌] select_asset fatal error: {e}")
            return False

    # -----------------
    # Set timeframe: open dropdown, wait, pick timeframe (1M/5M)
    # -----------------
    def set_timeframe(self, timeframe="M1", max_attempts=5):
        try:
            for attempt in range(max_attempts):
                try:
                    # open timeframe dropdown
                    tf_opener = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-selector .current")
                    tf_opener.click()
                    logger.debug("[🖱️] Clicked timeframe dropdown opener.")
                    self._rand_pause()

                    # find timeframe options
                    options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector .option")
                    if not options:
                        # fallback selectors
                        options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-list .option")
                    if not options:
                        logger.debug("[⚠️] No timeframe options found; retrying...")
                        time.sleep(0.4)
                        continue

                    selected = None
                    tf_upper = timeframe.upper()
                    for opt in options:
                        txt = opt.text.strip().upper()
                        # Accept "1M", "1 MIN", "1 MINUTE" etc.
                        if tf_upper in txt or (tf_upper == "M1" and ("1M" in txt or "1 MIN" in txt)) or (tf_upper == "M5" and ("5M" in txt or "5 MIN" in txt)):
                            selected = opt
                            break

                    if not selected:
                        # choose first as fallback
                        selected = options[0]

                    try:
                        selected.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", selected)

                    logger.debug(f"[🖱️] Selected timeframe option: {selected.text.strip()[:40]}")
                    self._rand_pause()

                    # random click center to close timeframe
                    if self.hotkey_mode:
                        try:
                            width = self.driver.execute_script("return window.innerWidth")
                            height = self.driver.execute_script("return window.innerHeight")
                            x = int(width * 0.52) + random.randint(-40, 40)
                            y = int(height * 0.45) + random.randint(-30, 30)
                            pyautogui.click(x, y)
                            logger.debug(f"[🖱️] Clicked center area to close timeframe at ({x},{y}).")
                        except Exception:
                            pass
                        self._rand_pause()

                    return True

                except Exception as e:
                    logger.debug(f"[⚠️] set_timeframe attempt failed: {e}")
                    time.sleep(0.5)
            return False
        except Exception as e:
            logger.error(f"[❌] set_timeframe fatal error: {e}")
            return False

    # -----------------
    # Called by Core to prepare trade UI and start monitoring for its result
    # returns True when selection finished (asset+tf) and monitor thread launched
    # -----------------
    def prepare_for_trade(self, currency_pair, entry_dt, timeframe="M1"):
        """
        Core calls this before scheduling the actual placement.
        currency_pair: e.g. "CADUSD" (no slash)
        entry_dt: tz-aware datetime (entry time)
        timeframe: "M1" or "M5"
        """
        try:
            logger.info(f"[📥] Selenium received order from Core: {currency_pair} | Timeframe: {timeframe} | Entry at: {entry_dt.strftime('%H:%M:%S')}")
            # Perform the UI actions in sequence with randomized pauses
            sel_ok = self.select_asset(currency_pair)
            if not sel_ok:
                logger.warning(f"[⚠️] select_asset failed for {currency_pair}")
            tf_ok = self.set_timeframe(timeframe)
            if not tf_ok:
                logger.warning(f"[⚠️] set_timeframe failed for {timeframe}")

            # compute expected result time (entry -> plus timeframe seconds)
            tf_seconds = TIMEFRAME_SECONDS.get(timeframe.upper(), 60)
            expected_result_dt = entry_dt + timedelta(seconds=tf_seconds)

            key = (currency_pair, entry_dt.isoformat())
            with self._monitors_lock:
                if key in self._monitors:
                    logger.debug(f"[ℹ️] Monitor already exists for {key}")
                else:
                    t = threading.Thread(target=self._monitor_for_result,
                                         args=(currency_pair, entry_dt, expected_result_dt, timeframe),
                                         daemon=True)
                    self._monitors[key] = {"thread": t, "started_at": datetime.utcnow()}
                    t.start()

            logger.info(f"[✅] Asset {currency_pair} and timeframe {timeframe} selected successfully. Monitor set for result at {expected_result_dt.strftime('%H:%M:%S')}")
            return True
        except Exception as e:
            logger.error(f"[❌] prepare_for_trade error: {e}")
            return False

    # -----------------
    # Internal monitor per expected result
    # -----------------
    def _monitor_for_result(self, currency_pair, entry_dt, result_dt, timeframe):
        iso_key = (currency_pair, entry_dt.isoformat())
        try:
            logger.debug(f"[🔎] Monitor thread started for {currency_pair} expected result at {result_dt.isoformat()}")
            # Poll lightly until MONITOR_LEAD_SECONDS before result_dt
            while True:
                now = datetime.now(entry_dt.tzinfo)
                seconds_to_result = (result_dt - now).total_seconds()
                if seconds_to_result <= MONITOR_LEAD_SECONDS:
                    break
                # sleep a fraction
                time.sleep(max(0.5, min(2.0, seconds_to_result / 5.0)))
            # intensive poll window (until result_dt + small buffer)
            end_time = result_dt + timedelta(seconds=15)
            logger.info(f"[🔔] Selenium intensive monitoring started for {currency_pair} — checking every {INTENSE_POLL_INTERVAL}s until {end_time.strftime('%H:%M:%S')}")
            while datetime.now(entry_dt.tzinfo) <= end_time:
                res = self.detect_trade_result()
                if res:
                    logger.info(f"[📤] Selenium detected trade result for {currency_pair}: {res}. Sending result to Core.")
                    try:
                        self.trade_manager.on_trade_result(currency_pair, res)
                    except Exception as e:
                        logger.error(f"[❌] Error notifying core for {currency_pair}: {e}")
                    break
                time.sleep(INTENSE_POLL_INTERVAL)
        except Exception as e:
            logger.error(f"[❌] Monitor thread error for {currency_pair}: {e}")
        finally:
            with self._monitors_lock:
                if iso_key in self._monitors:
                    del self._monitors[iso_key]
            logger.debug(f"[🔚] Monitor thread ended for {currency_pair} entry {entry_dt.isoformat()}")

    # -----------------
    # Parse trade-results in history DOM; returns 'WIN' or 'LOSS' or None
    # -----------------
    def detect_trade_result(self):
        """
        Scans the trade history for the latest entry result.
        Heuristics:
         - text starting with '+' or 'win' => WIN
         - text equal to '$0' or starting with '0' => LOSS
        """
        try:
            elems = self.driver.find_elements(By.CSS_SELECTOR, ".trade-history .trade-result")
            for e in elems:
                txt = e.text.strip()
                if not txt:
                    continue
                if txt.startswith("+") or txt.lower().startswith("win"):
                    return "WIN"
                if txt == "$0" or txt.lower().startswith("0"):
                    return "LOSS"
            return None
        except Exception:
            return None

    # -----------------
    # Global lightweight monitor (fallback)
    # -----------------
    def start_result_monitor(self):
        if self._global_monitor_running:
            return
        self._global_monitor_running = True

        def monitor():
            while True:
                try:
                    res = self.detect_trade_result()
                    if res:
                        try:
                            with self.trade_manager._pending_lock:
                                pending_currencies = {t['currency_pair'] for t in self.trade_manager.pending_trades if not t['resolved'] and t.get('placed_at')}
                        except Exception:
                            pending_currencies = set()
                        for currency in pending_currencies:
                            try:
                                logger.info(f"[📤] Global monitor sending result {res} for {currency} to Core.")
                                self.trade_manager.on_trade_result(currency, res)
                            except Exception as e:
                                logger.error(f"[❌] Error in global monitor callback: {e}")
                except Exception:
                    pass
                time.sleep(CHECK_INTERVAL)

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

