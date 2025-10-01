"""
Final selenium_integration.py — PocketOptionSelenium.

- Uses a unique --user-data-dir per session (UUID) to avoid "already in use" errors.
- Provides:
    - confirm_asset_ready(currency_pair, entry_time_str)
    - set_timeframe(timeframe)  -> selects M1 or M5 via dropdown
    - detect_trade_result() -> scans trade history
    - start_result_monitor() -> background thread to detect results and callback to core
    - watch_trade_for_result(currency_pair, placed_at) -> optional targeted watcher
- When a result is detected, calls: trade_manager.on_trade_result(currency_pair, result)
  (In our core the method is named trade_manager.on_trade_result -> core implements on_trade_result as on_trade_result wrapper above.)
"""

import time
import threading
import random
import uuid
from datetime import datetime
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import pyautogui

CHECK_INTERVAL = 0.5  # seconds

class PocketOptionSelenium:
    def __init__(self, trade_manager, headless=False):
        self.trade_manager = trade_manager
        self.headless = headless
        self.driver = self.setup_driver(headless)
        self.monitor_thread = None
        # start generic results monitor
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
        logger = getattr(trade_manager, "logger", None)
        print("[✅] Chrome started and navigated to Pocket Option login.")
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
    def confirm_asset_ready(self, asset_name, entry_time_str, source_tz="UTC"):
        # Check entry time not elapsed (naive check assuming entry_time_str is Jakarta-converted or HH:MM)
        fmt = "%H:%M"
        try:
            entry_dt = datetime.strptime(entry_time_str, fmt)
            now = datetime.now()
            if now > entry_dt:
                return False
        except Exception:
            pass

        return self.detect_asset(asset_name)

    # -----------------
    # Set timeframe by dropdown (M1/M5)
    # -----------------
    def set_timeframe(self, timeframe="M1"):
        try:
            # current element
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
            # click safe area to close dropdown
            pyautogui.click(random.randint(100,300), random.randint(100,300))
            print(f"[🎯] Timeframe set to {timeframe}")
        except Exception as e:
            print(f"[❌] set_timeframe failed: {e}")

    # -----------------
    # Parse trade-results in history DOM; returns 'WIN' or 'LOSS' or None
    # Implementation depends on page structure; adapt selectors to real site.
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
    # Generic background monitor: calls trade_manager.on_trade_result(currency, result)
    # We're using a heuristic: when a result appears in history, we call back for all pending trades
    # of the same currency (TradeManager will match the earliest pending). This keeps coupling loose.
    # -----------------
    def start_result_monitor(self):
        def monitor():
            while True:
                result = self.detect_trade_result()
                if result:
                    # We don't know which currency from DOM easily; trade_manager will map by earliest pending trade
                    # So we call trade_manager.on_trade_result for each unique pending currency we have
                    with self.trade_manager.pending_lock:
                        pending_currencies = set([t['currency_pair'] for t in self.trade_manager.pending_trades if not t['resolved'] and t.get('placed_at')])
                    # If there are pending currencies, report to trade_manager for each (tm will match earliest)
                    for currency in pending_currencies:
                        try:
                            self.trade_manager.on_trade_result(currency, result)
                        except Exception:
                            pass
                time.sleep(CHECK_INTERVAL)
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    # -----------------
    # Optional targeted watch: attempt to observe results after a specific placed_at timestamp.
    # This is a best-effort helper; actual mapping is primarily handled by the above monitor.
    # -----------------
    def watch_trade_for_result(self, currency_pair, placed_at):
        def watch():
            # Wait up to some reasonable window for a result (e.g., 60 seconds)
            deadline = datetime.now() + timedelta(seconds=60)
            while datetime.now() < deadline:
                res = self.detect_trade_result()
                if res:
                    try:
                        self.trade_manager.on_trade_result(currency_pair, res)
                    except Exception:
                        pass
                    return
                time.sleep(0.5)
        threading.Thread(target=watch, daemon=True).start()
        
