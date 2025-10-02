"""
selenium_integration.py — PocketOptionSelenium (production-ready)

- Starts Chrome and auto-logs in (hardcoded credentials)
- Prepares asset/timeframe on request from core
- Starts intensive monitoring for expected result times (30s before result, polling 0.1s)
- Detects WIN/LOSS and notifies core via trade_manager.on_trade_result(currency, result)
- Logs: ready, received orders, reporting results
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

CHECK_INTERVAL = 0.5  # regular scan interval (s) for trade history
INTENSE_POLL_INTERVAL = 0.1  # intensive poll when near result
MONITOR_LEAD_SECONDS = 30  # start intensive monitor this many seconds before expected result

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
        self.monitor_thread = None
        # tracked monitors: keys are tuples (currency, entry_iso) -> dict with threads etc
        self._monitors = {}
        self._monitors_lock = threading.Lock()
        # Start global lightweight monitor to catch any results in history
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
    # Balance fetching
    # -----------------
    def get_balances(self):
        try:
            demo_el = self.driver.find_element(By.CSS_SELECTOR, ".balance-demo")
            real_el = self.driver.find_element(By.CSS_SELECTOR, ".balance-real")
            demo = demo_el.text.strip() if demo_el else "ignored"
            real = real_el.text.strip() if real_el else "ignored"
            return demo, real
        except:
            return "ignored", "ignored"

    # -----------------
    # Select asset & timeframe (UI)
    # -----------------
    def select_asset(self, currency_pair, max_attempts=5):
        for attempt in range(max_attempts):
            try:
                current = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
                if current.text.strip() == currency_pair:
                    return True
                current.click()
                time.sleep(random.uniform(0.6, 1.2))
                # try to find search input under dropdown
                search_input = self.driver.find_element(By.CSS_SELECTOR, ".asset-dropdown input")
                search_input.clear()
                search_input.send_keys(currency_pair)
                time.sleep(0.3)
                options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-dropdown .option")
                for opt in options:
                    txt = opt.text.strip().upper().replace("/", "")
                    if txt == currency_pair.upper() or txt == currency_pair.upper().replace("/", "") or currency_pair.upper() in txt:
                        opt.click()
                        time.sleep(0.4)
                        if self.hotkey_mode:
                            pyautogui.click(random.randint(400, 800), random.randint(200, 400))
                        return True
            except Exception:
                time.sleep(0.5)
        return False

    def set_timeframe(self, timeframe="M1", max_attempts=5):
        for attempt in range(max_attempts):
            try:
                current = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-selector .current")
                if current.text.strip().upper() == timeframe.upper():
                    return True
                current.click()
                time.sleep(random.uniform(0.4, 0.9))
                options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector .option")
                for opt in options:
                    if opt.text.strip().upper() == timeframe.upper():
                        opt.click()
                        time.sleep(0.4)
                        if self.hotkey_mode:
                            pyautogui.click(random.randint(400, 800), random.randint(200, 400))
                        return True
            except Exception:
                time.sleep(0.5)
        return False

    # -----------------
    # Called by Core to prepare trade UI and start monitoring for its result
    # returns True if asset/timeframe selection completed
    # -----------------
    def prepare_for_trade(self, currency_pair, entry_dt, timeframe="M1"):
        """
        Core calls this before scheduling the actual placement.
        Selenium will:
         - Select the asset & timeframe in UI
         - Setup an intensive monitor that will start MONITOR_LEAD_SECONDS before the expected result time
           and poll frequently to detect WIN/LOSS.
         - Return True when selection is done.
        """
        try:
            # select asset/timeframe (blocking, with retries)
            sel_ok = self.select_asset(currency_pair)
            tf_ok = self.set_timeframe(timeframe)
            if not sel_ok or not tf_ok:
                logger.warning(f"[⚠️] Selenium: failed to select {currency_pair}/{timeframe}.")
                return False

            # compute expected result time (entry -> plus timeframe seconds)
            tf_seconds = TIMEFRAME_SECONDS.get(timeframe.upper(), 60)
            expected_result_dt = entry_dt + timedelta(seconds=tf_seconds)

            key = (currency_pair, entry_dt.isoformat())
            with self._monitors_lock:
                if key in self._monitors:
                    # already monitoring this entry
                    logger.debug(f"[ℹ️] Monitor already exists for {key}")
                else:
                    # spawn a dedicated monitor thread for this expected result
                    t = threading.Thread(target=self._monitor_for_result,
                                         args=(currency_pair, entry_dt, expected_result_dt, timeframe),
                                         daemon=True)
                    self._monitors[key] = {"thread": t, "started_at": datetime.utcnow()}
                    t.start()

            logger.info(f"[📥] Selenium received order from Core: {currency_pair} | Timeframe: {timeframe} | Entry at: {entry_dt.strftime('%H:%M:%S')}")
            return True
        except Exception as e:
            logger.error(f"[❌] prepare_for_trade error: {e}")
            return False

    # -----------------
    # Internal monitor per expected result
    # -----------------
    def _monitor_for_result(self, currency_pair, entry_dt, result_dt, timeframe):
        """
        This thread starts light polling, then when within MONITOR_LEAD_SECONDS of result_dt it intensifies polling.
        When detect_trade_result() returns WIN or LOSS, it notifies core and exits.
        """
        iso_key = (currency_pair, entry_dt.isoformat())
        try:
            # Log monitor creation
            logger.debug(f"[🔎] Monitor thread started for {currency_pair} expected result at {result_dt.isoformat()}")

            # Poll lightly until we reach lead time
            while True:
                now = datetime.now(entry_dt.tzinfo)
                seconds_to_result = (result_dt - now).total_seconds()
                if seconds_to_result <= MONITOR_LEAD_SECONDS:
                    break
                # light poll
                time.sleep(max(0.5, min(2.0, seconds_to_result / 5.0)))
            # intensive poll window (until result_dt + small buffer)
            end_time = result_dt + timedelta(seconds=15)  # small post-result buffer
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
            # finished monitoring: cleanup
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
         - text starting with '+' => WIN
         - text equal to '$0' => LOSS
        """
        try:
            elems = self.driver.find_elements(By.CSS_SELECTOR, ".trade-history .trade-result")
            for e in elems:
                txt = e.text.strip()
                if not txt:
                    continue
                # common positive representation
                if txt.startswith("+") or txt.lower().startswith("win"):
                    return "WIN"
                # loss representation
                if txt == "$0" or txt.lower().startswith("0"):
                    return "LOSS"
            return None
        except Exception:
            return None

    # -----------------
    # Global lightweight monitor that keeps scanning trade history and dispatching results (fallback)
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
                        # notify core for any pending currencies
                        try:
                            with self.trade_manager.pending_lock:
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
        self._global_monitor_running = True
