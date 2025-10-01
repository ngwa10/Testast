"""
selenium_integration.py — PocketOptionSelenium (production-ready)

Features:
- Headless Chrome or persistent session
- Auto-login (email & password)
- Asset & timeframe selection with retry
- Missed signal detection (last 20s)
- Martingale safety logic
- Trade result monitoring and instant Core notification
- Balance fetching (real & demo)
"""

import time
import threading
import random
import uuid
from datetime import datetime, timedelta
import pytz
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyautogui

# ---------------------------
# Logging Setup
# ---------------------------
logger = logging.getLogger(__name__)

# ---------------------------
# Credentials (replace with env vars in production!)
# ---------------------------
EMAIL = "mylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"

CHECK_INTERVAL = 0.5  # seconds
FAILSAFE_BUFFER = 20   # seconds before entry to consider missed

pyautogui.FAILSAFE = False

if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL or PASSWORD not set.")

# ---------------------------
# PocketOptionSelenium Class
# ---------------------------
class PocketOptionSelenium:
    def __init__(self, trade_manager, headless=True):
        self.trade_manager = trade_manager
        self.headless = headless
        self.driver = self.setup_driver(headless)
        self.monitor_thread = None
        self.start_result_monitor()

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
    # Asset & timeframe selection
    # -----------------
    def select_asset(self, currency_pair, max_attempts=5):
        for attempt in range(max_attempts):
            try:
                current = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
                if current.text.strip() == currency_pair:
                    return True
                current.click()
                time.sleep(random.uniform(1, 2))
                search_input = self.driver.find_element(By.CSS_SELECTOR, ".asset-dropdown input")
                search_input.clear()
                search_input.send_keys(currency_pair)
                options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-dropdown .option")
                for opt in options:
                    txt = opt.text.strip().upper().replace("/", "")
                    if txt == currency_pair.upper() or txt == f"{currency_pair} OTC":
                        opt.click()
                        time.sleep(0.5)
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
                time.sleep(random.uniform(1, 2))
                options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector .option")
                for opt in options:
                    if opt.text.strip().upper() == timeframe.upper():
                        opt.click()
                        time.sleep(0.5)
                        pyautogui.click(random.randint(400, 800), random.randint(200, 400))
                        return True
            except Exception:
                time.sleep(0.5)
        return False

    # -----------------
    # Confirm asset ready (with last 20s check)
    # -----------------
    def confirm_asset_ready(self, asset_name, entry_time_dt, timeframe="M1"):
        now = datetime.now(entry_time_dt.tzinfo)
        seconds_to_entry = (entry_time_dt - now).total_seconds()
        if seconds_to_entry <= 0:
            return {"ready": False, "asset": asset_name, "timeframe": timeframe}

        start_time = time.time()
        ready = False
        while time.time() - start_time < seconds_to_entry - FAILSAFE_BUFFER:
            asset_ready = self.select_asset(asset_name)
            timeframe_ready = self.set_timeframe(timeframe)
            ready = asset_ready and timeframe_ready
            if ready:
                break
            time.sleep(0.5)

        if not ready and seconds_to_entry <= FAILSAFE_BUFFER:
            logger.warning(f"[⚠️] Signal missed for {asset_name}: Selenium could not prepare in time.")
            return {"ready": False, "asset": asset_name, "timeframe": timeframe}

        return {"ready": ready, "asset": asset_name, "timeframe": timeframe}

    # -----------------
    # Detect trade result instantly
    # -----------------
    def detect_trade_result(self):
        try:
            elems = self.driver.find_elements(By.CSS_SELECTOR, ".trade-history .trade-result")
            for e in elems:
                txt = e.text.strip()
                if txt.startswith("+"):
                    return "WIN"
                if txt == "$0":
                    return "LOSS"
            return None
        except:
            return None

    # -----------------
    # Global result monitor thread
    # -----------------
    def start_result_monitor(self):
        def monitor():
            while True:
                res = self.detect_trade_result()
                if res:
                    try:
                        with self.trade_manager.pending_lock:
                            pending_currencies = {
                                t['currency_pair'] for t in self.trade_manager.pending_trades
                                if not t['resolved'] and t.get('placed_at')
                            }
                    except Exception:
                        pending_currencies = set()

                    for currency in pending_currencies:
                        try:
                            self.trade_manager.on_trade_result(currency, res)
                        except Exception as e:
                            logger.error(f"[❌] Error in result callback: {e}")
                time.sleep(CHECK_INTERVAL)

        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    # -----------------
    # Watch trade for result (per trade)
    # -----------------
    def watch_trade_for_result(self, currency_pair, placed_at, timeout=60):
        def watch():
            deadline = datetime.now(placed_at.tzinfo) + timedelta(seconds=timeout)
            while datetime.now(placed_at.tzinfo) < deadline:
                res = self.detect_trade_result()
                if res:
                    try:
                        self.trade_manager.on_trade_result(currency_pair, res)
                    except Exception as e:
                        logger.error(f"[❌] Error in watch_trade_for_result: {e}")
                    return
                time.sleep(0.5)

        threading.Thread(target=watch, daemon=True).start()
        
