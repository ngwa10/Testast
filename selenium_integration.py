"""
selenium_integration.py — PocketOptionSelenium (updated)

Features:
- Persistent Chrome session with unique --user-data-dir
- Auto-login (email & password)
- Asset selection via dropdown (CADUSD format, handles OTC)
- Timeframe selection
- Randomized humanized delays & random clicks to clear dropdowns
- Trade result monitoring (WIN / LOSS)
- Optional targeted watcher
- Balance fetching (real & demo)
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
from dotenv import load_dotenv

# ---------------------------
# HARDCODED CREDENTIALS (for testing only)
# ---------------------------
EMAIL = "mylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"

CHECK_INTERVAL = 0.5  # seconds

if not EMAIL or not PASSWORD:
    raise ValueError("[❌] EMAIL or PASSWORD not set. Please set them before running.")


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

        session_id = str(uuid.uuid4())
        chrome_options.add_argument(f"--user-data-dir=/tmp/chrome-user-data-{session_id}")
        chrome_options.add_experimental_option("detach", True)
        if headless:
            chrome_options.add_argument("--headless=new")

        service = Service("/usr/local/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.get("https://pocketoption.com/en/login/")

        print("[✅] Chrome started and navigated to Pocket Option login.")

        # Auto-login
        try:
            wait = WebDriverWait(driver, 30)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))

            try: email_field.clear()
            except: pass
            try: email_field.send_keys(EMAIL)
            except:
                driver.execute_script("arguments[0].value = arguments[1];", email_field, EMAIL)

            try: password_field.clear()
            except: pass
            try: password_field.send_keys(PASSWORD)
            except:
                try:
                    password_field.click()
                    time.sleep(0.1)
                    pyautogui.typewrite(PASSWORD, interval=0.05)
                except:
                    driver.execute_script("arguments[0].value = arguments[1];", password_field, PASSWORD)

            # Click login button
            login_button = None
            try:
                login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except:
                for b in driver.find_elements(By.TAG_NAME, "button"):
                    try:
                        txt = b.text.strip().lower()
                        if txt and ("log" in txt or "sign" in txt):
                            login_button = b
                            break
                    except: continue

            if login_button:
                try:
                    login_button.click()
                    print("[🔐] Credentials entered and login button clicked.")
                except:
                    try:
                        driver.execute_script("arguments[0].click();", login_button)
                        print("[🔐] Login clicked via JS.")
                    except:
                        print("[⚠️] Login click failed. Please click manually.")
            else:
                print("[ℹ️] Login button not found. Please click manually.")

        except Exception as e:
            print(f"[⚠️] Auto-login failed: {e}")

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
            print(f"[💰] Demo: {demo}, Real: {real}")
            return demo, real
        except:
            print("[💰] Balances ignored")
            return "ignored", "ignored"

    # -----------------
    # Asset selection
    # -----------------
    def select_asset(self, currency_pair):
        try:
            wait = WebDriverWait(self.driver, 10)
            current_asset_el = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
            if current_asset_el.text.strip() == currency_pair:
                print(f"[🎯] Asset already selected: {currency_pair}")
                return True

            # Open dropdown
            current_asset_el.click()
            time.sleep(random.uniform(1, 3))

            # Type in search bar
            search_input = self.driver.find_element(By.CSS_SELECTOR, ".asset-dropdown input")
            search_input.clear()
            search_input.send_keys(currency_pair)
            time.sleep(random.uniform(1, 2))

            # Click top result with correct OTC
            options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-dropdown .option")
            selected = False
            for opt in options:
                txt = opt.text.strip()
                if txt.upper().replace("/", "") == currency_pair.upper() or txt.upper().replace("/", "") == f"{currency_pair} OTC":
                    opt.click()
                    selected = True
                    break

            # Random click outside dropdown to close
            pyautogui.click(random.randint(400, 800), random.randint(200, 400))
            time.sleep(random.uniform(0.5, 1.5))

            if selected:
                print(f"[🎯] Asset selected: {currency_pair}")
                return True
            else:
                print(f"[❌] Asset {currency_pair} not found.")
                return False

        except Exception as e:
            print(f"[❌] select_asset failed: {e}")
            return False

    # -----------------
    # Timeframe selection
    # -----------------
    def set_timeframe(self, timeframe="M1"):
        try:
            current_element = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-selector .current")
            if current_element.text.strip().upper() == timeframe.upper():
                print(f"[🎯] Timeframe already set: {timeframe}")
                return True

            current_element.click()
            time.sleep(random.uniform(1, 3))

            options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector .option")
            selected = False
            for opt in options:
                if opt.text.strip().upper() == timeframe.upper():
                    opt.click()
                    selected = True
                    break

            # Random click outside dropdown
            pyautogui.click(random.randint(400, 800), random.randint(200, 400))
            time.sleep(random.uniform(0.5, 1.5))

            if selected:
                print(f"[🎯] Timeframe set: {timeframe}")
                return True
            else:
                print(f"[❌] Timeframe {timeframe} not found.")
                return False

        except Exception as e:
            print(f"[❌] set_timeframe failed: {e}")
            return False

    # -----------------
    # Detect trade results
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
    # Background monitor
    # -----------------
    def start_result_monitor(self):
        def monitor():
            while True:
                result = self.detect_trade_result()
                if result:
                    try:
                        with self.trade_manager.pending_lock:
                            pending_currencies = set(
                                [t['currency_pair'] for t in self.trade_manager.pending_trades
                                 if not t['resolved'] and t.get('placed_at')]
                            )
                    except:
                        pending_currencies = set()
                    for currency in pending_currencies:
                        try:
                            self.trade_manager.on_trade_result(currency, result)
                        except:
                            pass
                time.sleep(CHECK_INTERVAL)
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    # -----------------
    # Targeted watcher
    # -----------------
    def watch_trade_for_result(self, currency_pair, placed_at):
        def watch():
            deadline = datetime.now(placed_at.tzinfo) + timedelta(seconds=60)
            while datetime.now(placed_at.tzinfo) < deadline:
                res = self.detect_trade_result()
                if res:
                    try:
                        self.trade_manager.on_trade_result(currency_pair, res)
                    except:
                        pass
                    return
                time.sleep(0.5)
        threading.Thread(target=watch, daemon=True).start()

    # -----------------
    # Confirm asset ready (entry time)
    # -----------------
    def confirm_asset_ready(self, asset_name, entry_time_dt):
        try:
            now = datetime.now(entry_time_dt.tzinfo)
            if now > entry_time_dt:
                print(f"[❌] Entry time passed for {asset_name}")
                return False
        except:
            pass
        return self.select_asset(asset_name)
        
