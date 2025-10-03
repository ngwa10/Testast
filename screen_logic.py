# screen_logic.py
import logging
import time
import uuid
from pathlib import Path
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
import pyautogui  # For screen detection and screenshots

# -------------------------
# Logging setup
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

# -------------------------
# Paths for screenshots
# -------------------------
SCREENSHOT_DIR = Path("/home/dockuser/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------------
# Selenium Chrome setup
# -------------------------
def launch_chrome():
    """
    Launch Chrome in Docker with a unique user-data-dir to avoid conflicts.
    Tool: Selenium
    """
    logging.info("[ℹ️] Launching Chrome with Selenium...")
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    # Unique profile to avoid session conflicts
    options.add_argument(f"--user-data-dir=/home/dockuser/chrome-profile/{uuid.uuid4()}")

    try:
        driver = webdriver.Chrome(options=options)
        logging.info("[✅] Chrome launched successfully.")
        return driver
    except WebDriverException as e:
        logging.error(f"[❌] Failed to launch Chrome: {e}")
        return None

# -------------------------
# Gmail autofill
# -------------------------
def autofill_gmail(driver):
    """
    Tool: Selenium
    Assumes user profile has saved Gmail credentials.
    """
    logging.info("[ℹ️] Attempting Gmail autofill...")
    try:
        driver.get("https://mail.google.com/")
        # Wait until inbox loads (or login autofill completes)
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='main']"))
        )
        logging.info("[✅] Gmail loaded and autofill attempted.")
    except TimeoutException:
        logging.warning("[⚠️] Gmail page did not load in time.")
    except Exception as e:
        logging.error(f"[❌] Gmail autofill error: {e}")

# -------------------------
# Screenshot helper
# -------------------------
def take_screenshot(name):
    """
    Tool: pyautogui
    Takes a screenshot of the full screen.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{name}_{timestamp}.png"
    pyautogui.screenshot(path)
    logging.info(f"[📸] Screenshot saved: {path}")
    return path

# -------------------------
# Screen detection placeholders
# -------------------------
def detect_balance():
    """
    Tool: pyautogui (screen detection)
    Stub: replace with actual image detection if needed.
    """
    logging.info("[ℹ️] Attempting to detect balance on screen...")
    # TODO: implement actual screen detection logic
    return True

def detect_currency_dropdown():
    logging.info("[ℹ️] Attempting to detect currency dropdown...")
    # TODO: implement actual detection logic
    return True

def detect_timeframe_dropdown():
    logging.info("[ℹ️] Attempting to detect timeframe dropdown...")
    # TODO: implement actual detection logic
    return True

# -------------------------
# Main workflow
# -------------------------
def main():
    driver = launch_chrome()
    if not driver:
        logging.error("[❌] Chrome launch failed. Exiting screen logic.")
        return

    # Wait 3 minutes for any UI or login processes
    logging.info("[⏱️] Waiting 3 minutes for UI readiness...")
    time.sleep(180)

    # Attempt Gmail autofill
    autofill_gmail(driver)
    take_screenshot("gmail")

    # Screen detection + screenshots for trading UI
    success_balance = detect_balance()
    success_currency = detect_currency_dropdown()
    success_timeframe = detect_timeframe_dropdown()

    # Retry once if nothing or incomplete
    if not (success_balance and success_currency and success_timeframe):
        logging.info("[🔁] Retry screen detection in 5 seconds...")
        time.sleep(5)
        take_screenshot("retry_balance")
        take_screenshot("retry_currency")
        take_screenshot("retry_timeframe")

    # Log results
    logging.info(f"[📊] Detection summary -> Balance: {success_balance}, Currency: {success_currency}, Timeframe: {success_timeframe}")

    # Keep Chrome open for core bot hotkeys
    logging.info("[ℹ️] Screen logic finished initial setup. Chrome remains open for trading automation.")

if __name__ == "__main__":
    main()
