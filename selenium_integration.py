"""
selenium_integration.py — PocketOptionSelenium (FULL INTEGRATED)

Features:
- Auto-fills login (manual click required)
- Monitors login screen: detects email & login button, screenshots captcha periodically
- Dashboard detection with balance, currency, timeframe, buy/sell buttons
- Selects asset and timeframe per trade order
- Monitors trade results via text & audio
- Sends results back to Core (win/loss)
- Handles retries with logs if unable to complete tasks
- Audio detection for win/loss sounds inside Docker container
"""

import time
import threading
import random
import uuid
import logging
from datetime import datetime, timedelta
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import pyautogui
from PIL import ImageGrab  # Screenshots
import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

# ------------------------
# Credentials
# ------------------------
EMAIL = "mylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"

# ------------------------
# Constants
# ------------------------
CHECK_INTERVAL = 0.5
INTENSE_POLL_INTERVAL = 0.1
MONITOR_LEAD_SECONDS = 30
TIMEFRAME_SECONDS = {"M1": 60, "M5": 300}
AUDIO_SAMPLE_RATE = 44100
AUDIO_BLOCK_DURATION = 0.1
WIN_PEAK_THRESHOLD = 0.6
LOSS_PEAK_THRESHOLD = 0.6
SCREENSHOT_INTERVAL = 2  # seconds on login screen

pyautogui.FAILSAFE = False

class PocketOptionSelenium:
    def __init__(self, trade_manager, headless=True, hotkey_mode=True):
        self.trade_manager = trade_manager
        self.headless = headless
        self.hotkey_mode = hotkey_mode
        self.driver = self.setup_driver(headless)
        self._monitors = {}
        self._monitors_lock = threading.Lock()
        self._global_monitor_running = False
        self.dashboard_detected = False
        self.dashboard_refresh_done = False
        self._login_monitor_running = False

        # Start audio monitor
        self.start_audio_monitor()

        # Monitor login screen (manual captcha verification)
        threading.Thread(target=self.monitor_login_screen, daemon=True).start()

        # Wait until dashboard is detected
        if not self.check_dashboard():
            logger.error("[❌] Dashboard not detected. Exiting initialization.")
            raise RuntimeError("Dashboard not detected")

        self.start_result_monitor()
        logger.info("[🟢] Selenium initialized and ready — waiting for trade orders from Core.")

    # -----------------
    # Setup Chrome & autofill
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

        try:
            wait = WebDriverWait(driver, 30)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            email_field.clear()
            email_field.send_keys(EMAIL)
            password_field.clear()
            password_field.send_keys(PASSWORD)
            logger.info("[🔐] Auto-filled email and password (manual click required for captcha).")
        except Exception as e:
            logger.warning(f"[⚠️] Auto-fill failed: {e}")

        return driver

    # -----------------
    # Monitor login screen & screenshots
    # -----------------
    def monitor_login_screen(self):
        if self._login_monitor_running:
            return
        self._login_monitor_running = True
        start_time = datetime.now()
        while True:
            elapsed = (datetime.now() - start_time).total_seconds()
            try:
                email_field = self.driver.find_elements(By.NAME, "email")
                login_button = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
                if email_field or login_button:
                    logger.info("[📝] Detected email field and login button on login screen.")
                    # Take screenshot
                    screenshot_path = f"/tmp/login_screenshot_{int(time.time())}.png"
                    img = ImageGrab.grab()
                    img.save(screenshot_path)
                    logger.info(f"[📸] Screenshot saved: {screenshot_path}")
                    logger.info("Boss, I salute you are preparing us to start firing 🔥")
                else:
                    logger.info("[ℹ️] No login elements detected on screen currently.")
            except Exception as e:
                logger.warning(f"[⚠️] Login monitor error: {e}")
            if elapsed > 300:
                logger.warning("Didn't detect anything on login screen after 5 minutes.")
                break
            time.sleep(SCREENSHOT_INTERVAL)

    # -----------------
    # Dashboard check
    # -----------------
    def check_dashboard(self, max_retries=3, wait_time=180, refresh_interval=30):
        attempt = 0
        while attempt < max_retries:
            start_time_inner = time.time()
            while time.time() - start_time_inner < wait_time:
                try:
                    found_elements = {}
                    if "cabinet" in self.driver.current_url:
                        found_elements['cabinet_url'] = True
                    balance_elem = self.driver.find_elements(By.CSS_SELECTOR, ".balance")
                    if balance_elem:
                        found_elements['balance'] = balance_elem[0].text
                        logger.info(f"[💰] Balance detected: {balance_elem[0].text}")
                    currency_elem = self.driver.find_elements(By.CSS_SELECTOR, ".asset-name-selector")
                    if currency_elem:
                        found_elements['currency_selector'] = True
                    tf_elem = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector")
                    if tf_elem:
                        found_elements['timeframe_selector'] = True
                    trade_buttons = self.driver.find_elements(By.CSS_SELECTOR, ".trade-buttons button")
                    if trade_buttons:
                        found_elements['buy_sell_buttons'] = len(trade_buttons)
                    if found_elements:
                        self.dashboard_detected = True
                        logger.info(f"[✅] Dashboard detected! Elements found: {found_elements}")
                        return True
                except Exception as e:
                    logger.warning(f"[⚠️] Exception during dashboard check: {e}")
                time.sleep(refresh_interval)
            attempt += 1
        logger.error("[❌] Max retry limit reached — dashboard not detected.")
        return False

    # -----------------
    # Small randomized pause
    # -----------------
    def _rand_pause(self, a=2.0, b=10.0):
        s = random.uniform(a, b)
        logger.debug(f"[⌛] Waiting {s:.1f}s (randomized pause).")
        time.sleep(s)

    # -----------------
    # Select asset
    # -----------------
    def select_asset(self, currency_pair, max_attempts=5):
        try:
            for attempt in range(max_attempts):
                try:
                    opener = self.driver.find_element(By.CSS_SELECTOR, ".asset-name-selector")
                    opener.click()
                    self._rand_pause()
                    search_input = None
                    try:
                        search_input = self.driver.find_element(By.CSS_SELECTOR, ".asset-dropdown input")
                    except:
                        try:
                            search_input = self.driver.find_element(By.CSS_SELECTOR, "input[data-test='asset-search']")
                        except:
                            pass
                    if not search_input:
                        time.sleep(0.5)
                        continue
                    search_term = currency_pair.replace("/", "").replace(" ", "").upper()
                    search_input.clear()
                    for ch in search_term:
                        search_input.send_keys(ch)
                        time.sleep(0.05)
                    self._rand_pause()
                    options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-dropdown .option")
                    if not options:
                        options = self.driver.find_elements(By.CSS_SELECTOR, ".asset-list .asset-item")
                    if not options:
                        time.sleep(0.5)
                        continue
                    chosen = None
                    for opt in options:
                        txt = opt.text.strip().upper()
                        if "OTC" in txt and (search_term in txt or search_term.replace("/", "") in txt):
                            chosen = opt
                            break
                    if not chosen:
                        chosen = options[0]
                    try:
                        chosen.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", chosen)
                    self._rand_pause()
                    logger.info(f"[✅] Asset selected: {currency_pair}")
                    return True
                except Exception:
                    time.sleep(0.5)
            return False
        except Exception as e:
            logger.error(f"[❌] select_asset fatal error: {e}")
            return False

    # -----------------
    # Set timeframe
    # -----------------
    def set_timeframe(self, timeframe="M1", max_attempts=5):
        try:
            for attempt in range(max_attempts):
                try:
                    tf_opener = self.driver.find_element(By.CSS_SELECTOR, ".timeframe-selector .current")
                    tf_opener.click()
                    self._rand_pause()
                    options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-selector .option")
                    if not options:
                        options = self.driver.find_elements(By.CSS_SELECTOR, ".timeframe-list .option")
                    selected = options[0]
                    tf_upper = timeframe.upper()
                    for opt in options:
                        txt = opt.text.strip().upper()
                        if tf_upper in txt or (tf_upper == "M1" and "1M" in txt) or (tf_upper == "M5" and "5M" in txt):
                            selected = opt
                            break
                    try:
                        selected.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", selected)
                    self._rand_pause()
                    logger.info(f"[✅] Timeframe set: {timeframe}")
                    return True
                except Exception:
                    time.sleep(0.5)
            return False
        except Exception as e:
            logger.error(f"[❌] set_timeframe fatal error: {e}")
            return False

    # -----------------
    # Prepare for trade
    # -----------------
    def prepare_for_trade(self, currency_pair, entry_dt, timeframe="M1"):
        try:
            if random.random() < 0.5:
                try:
                    self.driver.refresh()
                    logger.info(f"[🔄] Optional refresh triggered before preparing trade for {currency_pair}")
                except:
                    pass
            sel_ok = self.select_asset(currency_pair)
            tf_ok = self.set_timeframe(timeframe)
            if not sel_ok or not tf_ok:
                logger.warning(f"[⚠️] Asset/timeframe setup failed for {currency_pair}/{timeframe}")
                # Retry logic
                retries = 0
                while retries < 2:
                    time.sleep(2)
                    sel_ok = self.select_asset(currency_pair)
                    tf_ok = self.set_timeframe(timeframe)
                    if sel_ok and tf_ok:
                        break
                    retries += 1
                if not sel_ok or not tf_ok:
                    if retries == 1:
                        logger.error("Boss I am not able to complete my task I am sorry.")
                    else:
                        logger.error("Boss Desmond I am sorry this was my last time to try I could not get this one.")
                    return False

            tf_seconds = TIMEFRAME_SECONDS.get(timeframe.upper(), 60)
            expected_result_dt = entry_dt + timedelta(seconds=tf_seconds)
            key = (currency_pair, entry_dt.isoformat())
            with self._monitors_lock:
                if key not in self._monitors:
                    t = threading.Thread(target=self._monitor_for_result,
                                         args=(currency_pair, entry_dt, expected_result_dt, timeframe),
                                         daemon=True)
                    self._monitors[key] = {"thread": t, "started_at": datetime.utcnow()}
                    t.start()

            logger.info(f"[✅] Asset {currency_pair} and timeframe {timeframe} selected successfully. Monitor set for {expected_result_dt.strftime('%H:%M:%S')}")
            return True
        except Exception as e:
            logger.error(f"[❌] prepare_for_trade error: {e}")
            return False

    # -----------------
    # Monitor trade result
    # -----------------
    def _monitor_for_result(self, currency_pair, entry_dt, result_dt, timeframe):
        iso_key = (currency_pair, entry_dt.isoformat())
        try:
            while True:
                now = datetime.now(entry_dt.tzinfo)
                seconds_to_result = (result_dt - now).total_seconds()
                if seconds_to_result <= MONITOR_LEAD_SECONDS:
                    break
                time.sleep(max(0.5, min(2.0, seconds_to_result / 5.0)))

            end_time = result_dt + timedelta(seconds=15)
            while datetime.now(entry_dt.tzinfo) <= end_time:
                res = self.detect_trade_result()
                if res:
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

    # -----------------
    # Detect trade result via text
    # -----------------
    def detect_trade_result(self):
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
        except:
            return None

    # -----------------
    # Global monitor
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
                        except:
                            pending_currencies = set()
                        for currency in pending_currencies:
                            try:
                                self.trade_manager.on_trade_result(currency, res)
                            except Exception as e:
                                logger.error(f"[❌] Error in global monitor callback: {e}")
                except:
                    pass
                time.sleep(CHECK_INTERVAL)

        t = threading.Thread(target=monitor, daemon=True)
        t.start()

    # -----------------
    # Audio monitor
    # -----------------
    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            return
        audio_data = np.abs(indata[:, 0])
        peak = np.max(audio_data)
        if peak > WIN_PEAK_THRESHOLD:
            logger.info("[🔔] Audio detected: WIN sound")
            try:
                self.trade_manager.on_trade_result("AUDIO_DETECTED", "WIN")
            except:
                pass
        elif peak > LOSS_PEAK_THRESHOLD:
            logger.info("[🔔] Audio detected: LOSS sound")
            try:
                self.trade_manager.on_trade_result("AUDIO_DETECTED", "LOSS")
            except:
                pass

    def start_audio_monitor(self):
        try:
            stream = sd.InputStream(
                samplerate=AUDIO_SAMPLE_RATE,
                channels=1,
                callback=self._audio_callback,
                blocksize=int(AUDIO_SAMPLE_RATE * AUDIO_BLOCK_DURATION),
                dtype='float32'
            )
            stream.start()
            logger.info("[🎧] Audio monitor started")
        except Exception as e:
            logger.warning(f"[⚠️] Audio monitor failed to start: {e}")
