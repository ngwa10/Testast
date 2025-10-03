# screen_logic.py
import logging
import time
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

CHROME_PROFILE_DIR = "/home/dockuser/chrome-profile"
SCREENSHOT_DIR = "/home/dockuser/screen_logic_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

def setup_chrome():
    """Launch Chrome in VNC session with your profile."""
    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    chrome_options.add_argument("--start-maximized")

    service = Service("/usr/local/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.get("https://pocketoption.com/en/login/")
    logging.info("[ℹ️] Chrome launched and navigated to PocketOption login.")
    return driver

def wait_for_captcha_solve():
    """Wait for manual captcha solving with a 3-minute delay."""
    logging.info("[⏳] Waiting 3 minutes for manual login / captcha solving...")
    time.sleep(180)
    logging.info("[✅] 3 minutes elapsed. Proceeding to capture balance and dropdowns.")

def capture_screenshots(driver):
    """Capture balance, currency dropdown, and timeframe dropdown screenshots."""
    elements_to_capture = {
        "balance": ["css:.balance", "xpath://div[contains(@class,'balance')]"],
        "currency_dropdown": ["css:.asset-selector", "xpath://button[contains(@class,'asset')]"],
        "timeframe_dropdown": ["css:.timeframe-selector", "xpath://div[contains(@class,'timeframe')]"]
    }

    results = {}

    for name, selectors in elements_to_capture.items():
        found = False
        for sel in selectors:
            try:
                if sel.startswith("css:"):
                    elem = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel[4:]))
                    )
                else:
                    elem = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, sel[6:]))
                    )
                screenshot_file = os.path.join(
                    SCREENSHOT_DIR, f"{name}_{datetime.now().strftime('%H%M%S')}.png"
                )
                elem.screenshot(screenshot_file)
                logging.info(f"[📷] Captured screenshot of {name}: {screenshot_file}")
                found = True
                break
            except Exception:
                continue
        results[name] = found

    # Log summary
    captured = [k for k, v in results.items() if v]
    if len(captured) == 3:
        logging.info("[✅] Successfully captured all elements (balance, currency dropdown, timeframe).")
    elif captured:
        logging.warning(f"[⚠️] Only captured some elements: {captured}")
    else:
        logging.error("[❌] Could not capture any of the elements. Retrying once...")
        # Retry once
        time.sleep(2)
        capture_screenshots(driver)

def main():
    driver = setup_chrome()
    wait_for_captcha_solve()
    capture_screenshots(driver)
    logging.info("[ℹ️] screen_logic initial setup done. Waiting for Core signals...")

if __name__ == "__main__":
    main()
    
