# screen_logic.py
"""
screen_logic.py — Hybrid automation for PocketOption (Selenium + screen detection + OCR)

What this file does (high level):
1. Launch Chrome (Selenium) in non-headless mode with a unique profile.
2. Autofill email/password via Selenium.
3. Wait up to 3 minutes for manual captcha solving.
4. Immediately take a screenshot of the Gmail/account area and attempt to read the email using:
   - OpenCV template matching (to find the region) AND/OR
   - pytesseract OCR (to extract text)
5. Capture screenshots for balance, currency dropdown and timeframe dropdown and attempt to detect them.
6. Retry detection once if initial attempt fails.
7. Log results (which elements were found and the detected Gmail/email if any).

Tool mapping (inline in code):
- Selenium: chrome launch, navigation, autofill and submit
- pyautogui: full-screen screenshot capture
- OpenCV (cv2): template matching to locate UI elements visually
- pytesseract: OCR to read text (email, balance text)
- PIL (Pillow): image loading/saving utilities
"""

import os
import time
import uuid
import logging
from datetime import datetime
from typing import Optional, Tuple

# Selenium (Tool: Selenium)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Screen detection / OCR tools (Tool: pyautogui + OpenCV + pytesseract)
import pyautogui
from PIL import Image
import numpy as np
import cv2
import pytesseract

# -------------------------
# Config & logging
# -------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("screen_logic")

# environment / constants
EMAIL = "mylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"
CHROMEDRIVER_PATH = "/usr/local/bin/chromedriver"
SCREENSHOT_DIR = "/home/dockuser/screen_logic_screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Template paths (place your reference images here)
TEMPLATES_DIR = "/home/dockuser/screen_logic_templates"
GMAIL_TEMPLATE = os.path.join(TEMPLATES_DIR, "gmail_label.png")         # small image showing Gmail label / avatar etc.
BALANCE_TEMPLATE = os.path.join(TEMPLATES_DIR, "balance_icon.png")      # reference image for balance region
CURRENCY_TEMPLATE = os.path.join(TEMPLATES_DIR, "currency_dropdown.png")
TIMEFRAME_TEMPLATE = os.path.join(TEMPLATES_DIR, "timeframe_dropdown.png")

# Detection settings
TEMPLATE_MATCH_CONFIDENCE = 0.70  # template matching threshold
OCR_LANG = "eng"  # pytesseract language


# -------------------------
# Utilities - Tool map
#   - pyautogui: grab screenshots
#   - OpenCV: template matching
#   - pytesseract: OCR
# -------------------------
def grab_full_screenshot() -> str:
    """Tool: pyautogui (screenshot)
    Returns path to saved screenshot PNG.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    fn = os.path.join(SCREENSHOT_DIR, f"full_{ts}.png")
    img = pyautogui.screenshot()
    img.save(fn)
    logger.debug(f"[📷] Saved full screenshot: {fn}")
    return fn


def load_image_cv(path: str) -> Optional[np.ndarray]:
    """Tool: OpenCV (cv2)
    Load image as BGR numpy array or return None."""
    try:
        img = cv2.imread(path)
        if img is None:
            logger.warning(f"[⚠️] OpenCV failed to load image: {path}")
        return img
    except Exception as e:
        logger.exception(f"[❌] load_image_cv error for {path}: {e}")
        return None


def template_match_on_screen(template_path: str, confidence: float = TEMPLATE_MATCH_CONFIDENCE) -> Optional[Tuple[int, int, int, int]]:
    """Tool: OpenCV + pyautogui
    Performs template matching using a saved template to locate the region on the current screen.
    Returns bounding box (x, y, w, h) in screen coordinates or None.
    """
    try:
        screen_path = grab_full_screenshot()
        screen = load_image_cv(screen_path)
        if screen is None:
            return None
        template = load_image_cv(template_path)
        if template is None:
            return None

        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        logger.debug(f"[🎯] Template match max_val={max_val:.3f} for {template_path}")
        if max_val >= confidence:
            top_left = max_loc
            h, w = template.shape[:2]
            x, y = int(top_left[0]), int(top_left[1])
            return (x, y, w, h)
        else:
            return None
    except Exception as e:
        logger.exception(f"[❌] template_match_on_screen error for {template_path}: {e}")
        return None


def ocr_crop_image(path: str, bbox: Tuple[int, int, int, int]) -> str:
    """Tool: PIL + pytesseract
    Crop bbox from image at path and return OCR text.
    bbox is (x, y, w, h) in pixels."""
    try:
        img = Image.open(path)
        x, y, w, h = bbox
        crop = img.crop((x, y, x + w, y + h))
        # save crop for debug
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        crop_file = os.path.join(SCREENSHOT_DIR, f"crop_{ts}.png")
        crop.save(crop_file)
        logger.debug(f"[📷] Saved crop for OCR: {crop_file}")
        # run OCR
        text = pytesseract.image_to_string(crop, lang=OCR_LANG)
        return text.strip()
    except Exception as e:
        logger.exception(f"[❌] ocr_crop_image error: {e}")
        return ""


# -------------------------
# Selenium: launch Chrome, autofill login (Tool: Selenium)
# -------------------------
def launch_chrome_and_login(chromedriver_path: str = CHROMEDRIVER_PATH, wait_for_manual_seconds: int = 180):
    """
    Tool: Selenium
    Launch Chrome (non-headless), navigate to PocketOption, autofill login. Wait for manual captcha solving.
    Returns Selenium WebDriver instance (or None on failure).
    """
    logger.info("[ℹ️] Launching Chrome (Selenium) with a unique profile...")
    try:
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--start-maximized")

        # use a unique user-data-dir to avoid 'already in use' errors
        profile_dir = f"/tmp/chrome-profile-{uuid.uuid4()}"
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")

        # ensure non-headless so VNC shows the browser
        chrome_options.headless = False

        driver = webdriver.Chrome(service=Service(chromedriver_path), options=chrome_options)
        driver.get("https://pocketoption.com/en/login/")
        logger.info("[✅] Chrome launched and navigated to https://pocketoption.com/en/login/")

        # Attempt to fill email/password if present
        try:
            wait = WebDriverWait(driver, 30)
            email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
            email_field.clear()
            email_field.send_keys(EMAIL)
            password_field.clear()
            password_field.send_keys(PASSWORD)
            logger.info("[🔐] Autofilled email and password fields (Selenium).")
            # attempt to click submit
            try:
                login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                login_btn.click()
                logger.info("[🔐] Clicked login button.")
            except Exception:
                logger.debug("[ℹ️] Login button click failed; maybe manual submit required.")
        except Exception as e:
            logger.warning(f"[⚠️] Could not find login form fields via Selenium: {e}")

        # Give manual time for captcha solving (VNC)
        if wait_for_manual_seconds > 0:
            logger.info(f"[⌛] Waiting up to {wait_for_manual_seconds}s for manual captcha/login completion...")
            time.sleep(wait_for_manual_seconds)
            logger.info("[✅] Manual wait complete; proceeding to screen detection.")

        return driver

    except Exception as e:
        logger.exception(f"[❌] launch_chrome_and_login failed: {e}")
        return None


# -------------------------
# Detect Gmail/account info right after login
#   Steps:
#   1) Try template matching for a Gmail label/icon area (Tool: OpenCV)
#   2) If matched, OCR that crop to read email (Tool: pytesseract)
#   3) If template not provided or match fails, OCR a heuristic region (Tool: pytesseract)
# -------------------------
def detect_and_log_gmail():
    """Attempt to find Gmail/account text & log it. Retries once on failure."""
    attempt = 0
    while attempt < 2:
        attempt += 1
        logger.info(f"[🔎] Detecting Gmail/account info (attempt {attempt})...")
        screen_path = grab_full_screenshot()

        # Prefer template matching to find the Gmail label / avatar area
        gmail_bbox = None
        if os.path.exists(GMAIL_TEMPLATE):
            gmail_bbox = template_match_on_screen(GMAIL_TEMPLATE)
            if gmail_bbox:
                logger.info("[🎯] Gmail template matched on screen.")
                text = ocr_crop_image(screen_path, gmail_bbox)
                if text:
                    logger.info(f"[📧] Gmail/account text (template->OCR): {text}")
                    return text
                else:
                    logger.warning("[⚠️] OCR returned empty text for Gmail crop (template).")
            else:
                logger.debug("[ℹ️] Gmail template not matched on screen.")
        else:
            logger.debug("[ℹ️] Gmail template file not present; falling back to heuristic OCR.")

        # Fallback heuristic: OCR top-right area of the screen (commonly where login/account shows)
        try:
            logger.debug("[🧭] Falling back to heuristic region OCR (top-right).")
            img = Image.open(screen_path)
            w, h = img.size
            # heuristic region: top-right corner (adjust as needed)
            region = (int(w * 0.6), 0, w, int(h * 0.18))
            crop = img.crop(region)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            fallback_fn = os.path.join(SCREENSHOT_DIR, f"gmail_fallback_crop_{ts}.png")
            crop.save(fallback_fn)
            logger.debug(f"[📷] Saved fallback crop: {fallback_fn}")
            # OCR the fallback
            text = pytesseract.image_to_string(crop, lang=OCR_LANG).strip()
            if text:
                logger.info(f"[📧] Gmail/account text (heuristic OCR): {text}")
                return text
            else:
                logger.warning("[⚠️] Heuristic OCR returned empty text for Gmail region.")
        except Exception as e:
            logger.exception(f"[❌] Heuristic fallback OCR error: {e}")

        if attempt < 2:
            logger.info("[🔁] Retry detection in 2 seconds...")
            time.sleep(2)
    logger.error("[❌] Could not detect Gmail/account information after 2 attempts.")
    return ""


# -------------------------
# Detect balance, currency dropdown, timeframe dropdown
#   Use template matching first; fallback to OCR heuristics.
# -------------------------
def detect_balance_currency_timeframe_once() -> dict:
    """
    Returns a dict: {'balance': bool, 'currency_dropdown': bool, 'timeframe_dropdown': bool}
    Each value True/False whether the element was detected.
    """
    results = {"balance": False, "currency_dropdown": False, "timeframe_dropdown": False}
    screen_path = grab_full_screenshot()

    # Balance detection (Tool: OpenCV + OCR fallback)
    if os.path.exists(BALANCE_TEMPLATE):
        bbox = template_match_on_screen(BALANCE_TEMPLATE)
        if bbox:
            logger.info("[🎯] Balance template matched.")
            results["balance"] = True
        else:
            logger.debug("[ℹ️] Balance template not matched.")
    else:
        logger.debug("[ℹ️] No balance template provided.")

    # Currency dropdown detection
    if os.path.exists(CURRENCY_TEMPLATE):
        bbox = template_match_on_screen(CURRENCY_TEMPLATE)
        if bbox:
            logger.info("[🎯] Currency dropdown template matched.")
            results["currency_dropdown"] = True
        else:
            logger.debug("[ℹ️] Currency dropdown template not matched.")
    else:
        logger.debug("[ℹ️] No currency dropdown template provided.")

    # Timeframe detection
    if os.path.exists(TIMEFRAME_TEMPLATE):
        bbox = template_match_on_screen(TIMEFRAME_TEMPLATE)
        if bbox:
            logger.info("[🎯] Timeframe dropdown template matched.")
            results["timeframe_dropdown"] = True
        else:
            logger.debug("[ℹ️] Timeframe template not matched.")
    else:
        logger.debug("[ℹ️] No timeframe template provided.")

    # Fallback: try OCR detection for balance if template not found
    if not results["balance"]:
        try:
            img = Image.open(screen_path)
            w, h = img.size
            # heuristic region for balance (top-left / top-center) — adjust as needed
            region = img.crop((int(w * 0.02), int(h * 0.02), int(w * 0.4), int(h * 0.12)))
            txt = pytesseract.image_to_string(region, lang=OCR_LANG)
            if txt and any(s.lower() in txt.lower() for s in ["$", "balance", "€", "£"]):
                logger.info(f"[📊] OCR heuristic found balance-like text: {txt.strip()[:80]}")
                results["balance"] = True
            else:
                logger.debug("[ℹ️] OCR heuristic did not find balance-like text.")
        except Exception as e:
            logger.exception(f"[❌] OCR heuristic for balance failed: {e}")

    return results


def detect_balance_currency_timeframe_with_retry() -> dict:
    """Try detection, retry once if not all found."""
    attempt = 0
    while attempt < 2:
        attempt += 1
        logger.info(f"[🔎] Detecting balance/currency/timeframe (attempt {attempt})...")
        res = detect_balance_currency_timeframe_once()
        found_count = sum(1 for v in res.values() if v)
        if found_count == 3:
            logger.info("[✅] Detected all three elements (balance, currency, timeframe).")
            return res
        elif found_count > 0:
            logger.warning(f"[⚠️] Detected some elements: {res}. Will retry once.")
        else:
            logger.warning("[⚠️] No elements detected on this attempt.")
        if attempt < 2:
            time.sleep(2)
    logger.error("[❌] Failed to detect all required UI elements after 2 attempts.")
    return res


# -------------------------
# High level orchestration
# -------------------------
def run_initial_screen_checks(chrome_wait_seconds: int = 180):
    """
    1) Launch Chrome & attempt autofill login (Selenium).
    2) Wait for manual captcha for up to chrome_wait_seconds.
    3) Immediately detect and log Gmail/account info (screen detection + OCR).
    4) Detect balance, currency dropdown, timeframe and log which ones were found.
    Returns a dict with all results.
    """
    driver = launch_chrome_and_login(wait_for_manual_seconds=chrome_wait_seconds)
    if driver is None:
        logger.error("[❌] Chrome failed to launch. Aborting initial checks.")
        return {"chrome_launched": False}

    # 1) detect gmail/account info
    gmail_text = detect_and_log_gmail()

    # 2) detect balance/currency/timeframe (with retry)
    ui_results = detect_balance_currency_timeframe_with_retry()

    summary = {
        "chrome_launched": True,
        "gmail_text": gmail_text,
        "balance_detected": ui_results.get("balance", False),
        "currency_dropdown_detected": ui_results.get("currency_dropdown", False),
        "timeframe_dropdown_detected": ui_results.get("timeframe_dropdown", False),
    }

    logger.info(f"[📋] Initial screen checks summary: {summary}")
    return summary


# -------------------------
# If run as script, execute initial checks
# -------------------------
if __name__ == "__main__":
    # default: wait 3 minutes for manual captcha solving after autofill
    results = run_initial_screen_checks(chrome_wait_seconds=180)
    logger.info(f"[ℹ️] run_initial_screen_checks returned: {results}")
