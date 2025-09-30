"""
Selenium integration for Pocket Option:
- Confirms asset for core.py
- Confirms and toggles timeframe (M1/M5)
- Detects trade results (WIN/LOSS) to stop martingale
- Does not switch assets
"""

import time
import threading
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import random
import pyautogui

CHECK_INTERVAL = 0.5  # seconds

class PocketOptionSelenium:
    def __init__(self, core_trade_manager, headless=False):
        self.trade_manager = core_trade_manager
        self.driver = self.setup_driver(headless)
        self.current_asset = None
        self.monitor_thread = None

    # --------------------------
    # Setup WebDriver
    # --------------------------
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
        print("[✅] Chrome started and navigated to Pocket Option login.")
        return driver

    # --------------------------
    # Detect current asset
    # --------------------------
    def detect_asset(self, asset_name):
        """
        Checks Pocket Option UI for the currently selected asset.
        Returns True if asset is selected.
        """
        try:
            asset_element = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
            current = asset_element.text.strip()
            if current == asset_name:
                self.current_asset = current
                return True
            return False
        except Exception:
            return False

    # --------------------------
    # Confirm asset ready
    # --------------------------
    def confirm_asset_ready(self, asset_name, entry_time_str):
        """
        Confirm if asset is ready and entry time not elapsed.
        Returns True if asset is visible and entry time not elapsed.
        """
        fmt = "%H:%M"
        entry_dt = datetime.strptime(entry_time_str, fmt)
        now = datetime.now()
        if now > entry_dt:
            return False  # Entry time elapsed

        return self.detect_asset(asset_name)

    # --------------------------
    # Detect trade result
    # --------------------------
    def detect_trade_result(self):
        """
        Returns "WIN", "LOSS", or None
        """
        try:
            result_elements = self.driver.find_elements(By.CSS_SELECTOR, ".trade-history .trade-result")
            for elem in result_elements:
                text = elem.text.strip()
                if text.startswith("+"):
                    return "WIN"
                elif text == "$0":
                    return "LOSS"
            return None
        except Exception:
            return None

    # --------------------------
    # Monitor results in background
    # --------------------------
    def start_result_monitor(self):
        def monitor():
            while True:
                result = self.detect_trade_result()
                if result == "WIN":
                    # Stop martingale for current trade
                    self.trade_manager.martingale_stop_flags = {}
                    print("[✅] WIN detected. Martingale levels stopped.")
                time.sleep(CHECK_INTERVAL)
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()

    # --------------------------
    # Set timeframe
    # --------------------------
    def set_timeframe(self, timeframe="M1"):
        """
        Adjust Pocket Option chart to M1 or M5
        """
        try:
            # Detect current timeframe
            current_element = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-selector .current")
            current_timeframe = current_element.text.strip()
            if current_timeframe.upper() == timeframe.upper():
                return  # Already correct

            # Open dropdown and select desired timeframe
            current_element.click()
            time.sleep(0.5)
            option_elements = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector .option")
            for opt in option_elements:
                if opt.text.strip().upper() == timeframe.upper():
                    opt.click()
                    time.sleep(0.3)
                    break

            # Click randomly on safe area to close dropdown
            safe_x = random.randint(100, 300)
            safe_y = random.randint(100, 300)
            pyautogui.click(safe_x, safe_y)
            print(f"[🎯] Timeframe set to {timeframe}, dropdown safely closed.")

        except Exception as e:
            print(f"[❌] Could not set timeframe: {e}")
