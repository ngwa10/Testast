"""
Core logic for Pocket Option Telegram Trading Bot.
- Receives parsed signals from Telegram listener.
- Executes trades via pyautogui hotkeys.
- Switches assets automatically.
- Handles martingale logic.
- Integrates with Selenium for asset confirmation, timeframe adjustment, and WIN detection.
"""

import time
import threading
from datetime import datetime, timedelta, timezone
import logging
import random
import pyautogui
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

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

    # --------------------------
    # Command Handler
    # --------------------------
    def handle_command(self, command):
        cmd = command.strip().lower()
        if cmd.startswith("/start"):
            self.trading_active = True
            logger.info("[🚀] Trading started")
        elif cmd.startswith("/stop"):
            self.trading_active = False
            logger.info("[⏹️] Trading stopped")
        elif cmd.startswith("/status"):
            status = "ACTIVE" if self.trading_active else "PAUSED"
            logger.info(f"[ℹ️] Trading status: {status}")
        else:
            logger.info(f"[ℹ️] Unknown command: {command}")

    # --------------------------
    # Signal Handler
    # --------------------------
    def handle_signal(self, signal):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Signal ignored.")
            return
        logger.info(f"[📡] Processing signal: {signal}")

        # Schedule direct trade
        entry_time = signal.get("entry_time")
        if entry_time:
            threading.Thread(target=self._run_scheduled_trade, args=(entry_time, signal, 0), daemon=True).start()

        # Schedule martingale trades
        for i, mg_time in enumerate(signal.get("martingale_times", [])):
            if i + 1 > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {i+1} exceeds max {self.max_martingale}; skipping.")
                break
            threading.Thread(target=self._run_scheduled_trade, args=(mg_time, signal, i+1), daemon=True).start()

    # --------------------------
    # Scheduled trade execution
    # --------------------------
    def _run_scheduled_trade(self, entry_time_str, signal, martingale_level):
        cp = signal["currency_pair"]
        tf = signal["timeframe"]
        direction = signal["direction"]

        # Determine timezone offset based on signal source
        raw_text = signal.get("source_text", "")
        tz_offset = None
        if "💥 GET THIS SIGNAL HERE!" in raw_text or "💰 HOW TO START" in raw_text:
            tz_offset = -4  # UTC-4
        elif "💥 TRADE WITH DESMOND!" in raw_text:
            tz_offset = -3  # Cameroon
        else:
            tz_offset = -3  # default

        entry_dt_local = datetime.strptime(entry_time_str, "%H:%M")
        now_utc = datetime.now(timezone.utc)
        entry_dt = datetime(
            now_utc.year, now_utc.month, now_utc.day,
            entry_dt_local.hour, entry_dt_local.minute,
            tzinfo=timezone(timedelta(hours=tz_offset))
        )
        entry_dt = entry_dt.astimezone(timezone.utc)

        # Don't schedule trades too far in the future
        if (entry_dt - now_utc).total_seconds() > 600:
            logger.info(f"[⏱️] Signal {cp} entry time too far in future ({entry_dt.isoformat()}). Skipping trade.")
            return

        # Wait until entry time if close
        delay = (entry_dt - now_utc).total_seconds()
        if delay > 0:
            logger.info(f"[⏰] Waiting {delay:.2f}s until trade entry for {cp} (level {martingale_level})")
            time.sleep(min(delay, 10))  # max 10s sleep here, rest handled by firing loop

        # --------------------------
        # Start firing switching strokes
        # --------------------------
        logger.info(f"[🔄] Beginning asset-switch firing loop for {cp} (level {martingale_level}). Firing every 5–9s randomly.")
        confirmed = False
        while True:
            now_utc = datetime.now(timezone.utc)
            if now_utc >= entry_dt:
                logger.info(f"[⚠️] Entry time {entry_dt.isoformat()} reached before asset confirmed for {cp} (level {martingale_level}). Trade expired.")
                confirmed = False
                break

            # Fire switching stroke
            try:
                self._fire_switch_keystroke(cp)
                logger.info(f"[🔥] Firing currency switching strokes for {cp} (level {martingale_level})")
            except Exception as e:
                logger.warning(f"[⚠️] Error firing switch keystroke: {e}")

            # Allow Selenium a short time to confirm
            time.sleep(1)
            try:
                if selenium_integration.confirm_asset_ready(cp, tf, entry_dt.astimezone(timezone.utc).strftime("%H:%M")):
                    confirmed = True
                    logger.info(f"[✅] Asset {cp} confirmed by Selenium. Stopped firing switching strokes.")
                    break
            except Exception as e:
                logger.warning(f"[⚠️] Selenium check failed: {e}")

            # Random sleep 5–9s but don't overshoot entry time
            remaining = (entry_dt - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                logger.info(f"[⚠️] Entry time reached while waiting for asset confirmation for {cp}. Trade expired.")
                confirmed = False
                break
            sleep_sec = min(random.randint(5, 9), max(0.2, remaining))
            time.sleep(sleep_sec)

        # --------------------------
        # Place trade if asset confirmed
        # --------------------------
        if confirmed:
            self.place_trade(direction, martingale_level)
        else:
            logger.info(f"[⚠️] Trade for {cp} at level {martingale_level} expired (not executed)")

    # --------------------------
    # Place trade via pyautogui
    # --------------------------
    def place_trade(self, direction="BUY", martingale_level=0):
        amount = self.base_amount * (2 ** martingale_level)
        logger.info(f"[🎯] Placing trade: {direction} | amount: {amount} | level {martingale_level}")
        try:
            if direction.upper() == "BUY":
                pyautogui.keyDown('shift'); pyautogui.press('w'); pyautogui.keyUp('shift')
            elif direction.upper() == "SELL":
                pyautogui.keyDown('shift'); pyautogui.press('s'); pyautogui.keyUp('shift')
            logger.info(f"[🔥] Just fired a {direction} stroke for trade (level {martingale_level})")
        except Exception as e:
            logger.error(f"[❌] Error sending trade hotkeys: {e}")

# =========================
# Selenium Integration
# =========================
class PocketOptionSelenium:
    CHECK_INTERVAL = 0.5

    def __init__(self, trade_manager, headless=False):
        self.trade_manager = trade_manager
        self.driver = self.setup_driver(headless)
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
        logger.info("[✅] Chrome started and navigated to Pocket Option login.")
        return driver

    def confirm_asset_ready(self, asset_name, timeframe, entry_time_str):
        fmt = "%H:%M"
        try:
            entry_dt = datetime.strptime(entry_time_str, fmt)
            now = datetime.now()
            if now > entry_dt:
                return False
            asset_element = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
            current_asset = asset_element.text.strip()
            if current_asset != asset_name:
                return False
            self.set_timeframe(timeframe)
            return True
        except Exception:
            return False

    def set_timeframe(self, timeframe):
        try:
            dropdown = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-dropdown")
            current = dropdown.text.strip()
            if current != timeframe:
                dropdown.click()
                option = self.driver.find_element(By.XPATH, f"//li[contains(text(), '{timeframe}')]")
                option.click()
                pyautogui.click(random.randint(100, 300), random.randint(100, 300))
        except Exception:
            pass

    def detect_trade_result(self):
        try:
            results = self.driver.find_elements(By.CSS_SELECTOR, ".trade-history .trade-result")
            for r in results:
                text = r.text.strip()
                if text.startswith("+"):
                    return "WIN"
                elif text == "$0":
                    return "LOSS"
            return None
        except Exception:
            return None

    def start_result_monitor(self):
        def monitor():
            while True:
                result = self.detect_trade_result()
                if result == "WIN":
                    self.trade_manager.martingale_stop_flags = {}
                    logger.info("[✅] WIN detected. Martingale levels stopped.")
                time.sleep(self.CHECK_INTERVAL)
        threading.Thread(target=monitor, daemon=True).start()

# =========================
# Instantiate Core and Selenium
# =========================
trade_manager = TradeManager()
selenium_integration = PocketOptionSelenium(trade_manager)
                             
