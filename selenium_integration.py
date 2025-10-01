import time
import threading
import random
import uuid
from datetime import datetime, timedelta
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyautogui

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

    # -----------------
    # Setup Chrome
    # -----------------
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
            current_asset_el = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
            if current_asset_el.text.strip() == currency_pair:
                return True

            current_asset_el.click()
            time.sleep(random.uniform(1, 3))

            search_input = self.driver.find_element(By.CSS_SELECTOR, ".asset-dropdown input")
            search_input.clear()
            search_input.send_keys(currency_pair)
            time.sleep(random.uniform(1, 2))

            options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-dropdown .option")
            selected = False
            for opt in options:
                txt = opt.text.strip()
                if txt.upper().replace("/", "") == currency_pair.upper() or txt.upper().replace("/", "") == f"{currency_pair} OTC":
                    opt.click()
                    selected = True
                    break

            pyautogui.click(random.randint(400, 800), random.randint(200, 400))
            time.sleep(random.uniform(0.5, 1.5))
            return selected

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

            pyautogui.click(random.randint(400, 800), random.randint(200, 400))
            time.sleep(random.uniform(0.5, 1.5))
            return selected

        except Exception as e:
            print(f"[❌] set_timeframe failed: {e}")
            return False

    # -----------------
    # Detect trade results (instant push)
    # -----------------
    def detect_trade_result(self):
        try:
            elems = self.driver.find_elements(By.CSS_SELECTOR, ".trade-history .trade-result")
            for e in elems:
                txt = e.text.strip()
                if txt.startswith("+"):
                    self.push_result("WIN")
                    return "WIN"
                if txt == "$0":
                    self.push_result("LOSS")
                    return "LOSS"
            return None
        except:
            return None

    # -----------------
    # Push result instantly
    # -----------------
    def push_result(self, result):
        try:
            with self.trade_manager.pending_lock:
                pending_currencies = set(
                    [t['currency_pair'] for t in self.trade_manager.pending_trades
                     if not t['resolved'] and t.get('placed_at')]
                )
            for currency in pending_currencies:
                try:
                    self.trade_manager.on_trade_result(currency, result)
                except:
                    pass
        except:
            pass

    # -----------------
    # Background monitor
    # -----------------
    def start_result_monitor(self):
        def monitor():
            while True:
                self.detect_trade_result()
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
                    return
                time.sleep(0.5)
        threading.Thread(target=watch, daemon=True).start()

    # -----------------
    # Confirm asset ready with retry (until 20s before entry)
    # -----------------
    def confirm_asset_ready(self, asset_name, entry_time_dt, timeframe="M1"):
        """
        Ensure asset and timeframe are selected and ready.
        Returns a dict: {"ready": True/False, "asset": asset_name, "timeframe": timeframe}
        """
        while datetime.now(entry_time_dt.tzinfo) < entry_time_dt - timedelta(seconds=20):
            try:
                asset_ready = self.select_asset(asset_name)
                timeframe_ready = self.set_timeframe(timeframe)
                if asset_ready and timeframe_ready:
                    return {"ready": True, "asset": asset_name, "timeframe": timeframe}
            except Exception as e:
                print(f"[⚠️] confirm_asset_ready retry failed: {e}")
            time.sleep(0.5)
        print(f"[❌] Asset {asset_name} not ready before entry {entry_time_dt.strftime('%H:%M:%S')}")
        return {"ready": False, "asset": asset_name, "timeframe": timeframe}
        
