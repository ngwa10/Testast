"""
Final selenium_integration.py — PocketOptionSelenium (updated with .env login support).

- Uses a unique --user-data-dir per session (UUID) to avoid "already in use" errors.
- Uses signal's original timezone for scheduling and entry checks (no Jakarta time).
- Provides:
    - confirm_asset_ready(currency_pair, entry_time_dt) -> datetime in signal's tz
    - set_timeframe(timeframe)
    - detect_trade_result() -> scans trade history
    - start_result_monitor() -> background thread to detect results and callback to core
    - watch_trade_for_result(currency_pair, placed_at) -> targeted watcher
- Automatically fills login email & password from .env file into Pocket Option login page
"""

import time
import threading
import random
import uuid
from datetime import datetime, timedelta
import pytz
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyautogui
from dotenv import load_dotenv  # ✅ NEW

CHECK_INTERVAL = 0.5  # seconds

# ✅ Load credentials from .env
load_dotenv()
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("[❌] EMAIL or PASSWORD not found in .env file. Please set them before running.")

class PocketOptionSelenium:
    def __init__(self, trade_manager, headless=False):
        self.trade_manager = trade_manager
        self.headless = headless
        self.driver = self.setup_driver(headless)
        self.monitor_thread = None
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

        # Unique user-data-dir to avoid session conflicts
        session_id = str(uuid.uuid4())
        chrome_options.add_argument(f"--user-data-dir=/tmp/chrome-user-data-{session_id}")

        if headless:
            chrome_options.add_argument("--headless=new")

        service = Service("/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get("https://pocketoption.com/en/login/")
        logger = getattr(self.trade_manager, "logger", None)
        if logger:
            logger.info("[✅] Chrome started and navigated to Pocket Option login.")
        else:
            print("[✅] Chrome started and navigated to Pocket Option login.")

        # -----------------------
        # 🔐 Auto-fill login credentials from .env
        # -----------------------
        try:
            wait = WebDriverWait(driver, 30)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))

            # Clear and input credentials
            email_field.clear()
            email_field.send_keys(EMAIL)
            password_field.clear()
            password_field.send_keys(PASSWORD)

            # Optional: Click login button automatically
            try:
                login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_button.click()
                print("[🔐] Credentials entered and login button clicked automatically.")
            except Exception:
                print("[ℹ️] Credentials filled, but login button not found. Please click manually.")
        except Exception as e:
            print(f"[⚠️] Auto-login failed: {e}")

        return driver

    # -----------------
    # Detect current asset visible in UI
    # -----------------
    def detect_asset(self, asset_name):
        try:
            el = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
            current = el.text.strip()
            return current == asset_name
        except Exception:
            return False

    # -----------------
    # Confirm if asset ready and entry time not elapsed
    # -----------------
    def confirm_asset_ready(self, asset_name, entry_time_dt):
        try:
            now = datetime.now(entry_time_dt.tzinfo)
            if now > entry_time_dt:
                return False
        except Exception:
            pass
        return self.detect_asset(asset_name)

    # -----------------
    # Set timeframe by dropdown (M1/M5)
    # -----------------
    def set_timeframe(self, timeframe="M1"):
        try:
            current_element = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-selector .current")
            current_text = current_element.text.strip().upper()
            if current_text == timeframe.upper():
                return
            current_element.click()
            time.sleep(0.3)
            options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector .option")
            for opt in options:
                if opt.text.strip().upper() == timeframe.upper():
                    opt.click()
                    time.sleep(0.2)
                    break
            pyautogui.click(random.randint(100,300), random.randint(100,300))
            print(f"[🎯] Timeframe set to {timeframe}")
        except Exception as e:
            print(f"[❌] set_timeframe failed: {e}")

    # -----------------
    # Parse trade-results in history DOM; returns 'WIN' or 'LOSS' or None
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
        except Exception:
            return None

    # -----------------
    # Generic background monitor: calls trade_manager.on_trade_result
    # -----------------
    def start_result_monitor(self):
        def monitor():
            while True:
                result = self.detect_trade_result()
                if result:
                    with self.trade_manager.pending_lock:
                        pending_currencies = set([t['currency_pair'] for t in self.trade_manager.pending_trades if not t['resolved'] and t.get('placed_at')])
                    for currency in pending_currencies:
                        try:
                            self.trade_manager.on_trade_result(currency, result)
                        except Exception:
                            pass
                time.sleep(CHECK_INTERVAL)
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    # -----------------
    # Optional targeted watch: observe results after a specific placed_at timestamp
    # -----------------
    def watch_trade_for_result(self, currency_pair, placed_at):
        def watch():
            deadline = datetime.now(placed_at.tzinfo) + timedelta(seconds=60)
            while datetime.now(placed_at.tzinfo) < deadline:
                res = self.detect_trade_result()
                if res:
                    try:
                        self.trade_manager.on_trade_result(currency_pair, res)
                    except Exception:
                        pass
                    return
                time.sleep(0.5)
        threading.Thread(target=watch, daemon=True).start()
        
