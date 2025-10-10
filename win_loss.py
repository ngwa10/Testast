import threading
import time
import cv2
import numpy as np
from PIL import Image
import shared
import logging
import os
import glob
import pytesseract
import hashlib
import datetime
import mss
import re  # 🆕 for balance extraction

logger = logging.getLogger("win_loss")

# ---------------------------
# Configuration
# ---------------------------
DEBUG_MODE = True  # 🔧 Toggle False in production

WIN_TEMPLATE_DIR = "/home/dockuser/templates/win/"
LOSS_TEMPLATE_DIR = "/home/dockuser/templates/loss/"
DEBUG_SHOT_DIR = "/home/dockuser/screenshots/debug/"
MAX_TEMPLATES = 30
TEMPLATE_MATCH_THRESHOLD = 0.8
ROI_PAD = 20
FAST_SCAN_INTERVAL = 0.1
FAST_SCAN_DURATION = 6  # 🆕 6 seconds total (3s before + 3s after expiry)

# Ensure directories exist
os.makedirs(WIN_TEMPLATE_DIR, exist_ok=True)
os.makedirs(LOSS_TEMPLATE_DIR, exist_ok=True)
os.makedirs(DEBUG_SHOT_DIR, exist_ok=True)

# ---------------------------
# Utilities
# ---------------------------
def _image_hash(img):
    return hashlib.md5(cv2.imencode('.png', img)[1]).hexdigest()

def _load_templates_from_dir(directory: str):
    templates = []
    for path in glob.glob(os.path.join(directory, "*.png")):
        template = cv2.imread(path, 0)
        if template is not None:
            templates.append(template)
    if DEBUG_MODE:
        logger.debug(f"[📂] Loaded {len(templates)} templates from {directory}")
    return templates

def _cleanup_templates(template_dir):
    files = sorted(glob.glob(os.path.join(template_dir, "*.png")), key=os.path.getmtime)
    while len(files) > MAX_TEMPLATES:
        os.remove(files[0])
        logger.info(f"[🗑️] Removed old template: {os.path.basename(files[0])}")
        files.pop(0)

def _save_template_if_needed(img, template_dir, prefix):
    try:
        h = _image_hash(img)
        for f in os.listdir(template_dir):
            existing_img = cv2.imread(os.path.join(template_dir, f))
            if _image_hash(existing_img) == h:
                if DEBUG_MODE:
                    logger.debug(f"[🔁] Duplicate {prefix} template detected — skip saving.")
                return False
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.png"
        save_path = os.path.join(template_dir, filename)
        cv2.imwrite(save_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        logger.info(f"[💾] Saved {prefix} template: {save_path}")
        _cleanup_templates(template_dir)
        return True
    except Exception as e:
        logger.warning(f"[⚠️] Template save failed: {e}")
    return False

# ---------------------------
# ROI prediction
# ---------------------------
def _predict_result_roi(screenshot):
    if DEBUG_MODE:
        logger.debug("[🎯] Predicting ROI for result detection")
    hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 50, 150])
    upper = np.array([180, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        if DEBUG_MODE:
            logger.debug("[🔍] No contours detected — returning full screen ROI")
        return screenshot

    rightmost = max(contours, key=lambda c: cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2])
    x, y, w, h = cv2.boundingRect(rightmost)
    roi_x1 = max(x + w - ROI_PAD, 0)
    roi_y1 = max(y - ROI_PAD, 0)
    roi_x2 = min(x + w + ROI_PAD, screenshot.shape[1])
    roi_y2 = min(y + h + ROI_PAD, screenshot.shape[0])
    roi = screenshot[roi_y1:roi_y2, roi_x1:roi_x2]

    if DEBUG_MODE:
        logger.debug(f"[📐] ROI coordinates: ({roi_x1},{roi_y1})–({roi_x2},{roi_y2}) size={roi.shape}")
    return roi

# ---------------------------
# OCR helpers
# ---------------------------
def _extract_balance_from_text(text: str) -> str:
    """🆕 Try to extract balance-like values from OCR text."""
    if not text:
        return None

    # Common money/number patterns: $12.34, 1,234.56, 1000.00
    matches = re.findall(r"(\$?\d{1,3}(?:[,\d]{0,6})?(?:\.\d{1,2})?)", text)
    if not matches:
        return None

    # Prioritize values with '$', then largest numeric
    dollar_values = [m for m in matches if "$" in m]
    if dollar_values:
        return dollar_values[-1]  # latest balance reading

    try:
        numeric_values = [float(m.replace(",", "").replace("$", "")) for m in matches]
        max_val = max(numeric_values)
        return f"{max_val:,.2f}"
    except Exception:
        return None

# ---------------------------
# Template & OCR detection
# ---------------------------
def _capture_template_from_roi(roi, result_type):
    if DEBUG_MODE:
        logger.debug(f"[📸] Capturing new {result_type} template candidate")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data['text']):
        t = text.strip()
        if result_type == "WIN" and t.startswith("+"):
            _save_template_if_needed(roi, WIN_TEMPLATE_DIR, "win")
            break
        elif result_type == "LOSS" and t == "$0":
            _save_template_if_needed(roi, LOSS_TEMPLATE_DIR, "loss")
            break

def _match_templates(roi, templates, type_name):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    for i, template in enumerate(templates):
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        max_val = np.max(res)
        if DEBUG_MODE:
            logger.debug(f"[🧩] {type_name} template[{i}] match score: {max_val:.3f}")
        if max_val >= TEMPLATE_MATCH_THRESHOLD:
            logger.info(f"[✅] {type_name} template matched (score={max_val:.3f})")
            return True
    return False

# ---------------------------
# Core detection with mss
# ---------------------------
def _cv_detect_result(trade_id=None) -> str:
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Full screen
            sct_img = sct.grab(monitor)
            screenshot = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)  # 🆕 fixed color format

        timestamp = datetime.datetime.now().strftime("%H%M%S_%f")

        # 🆕 OCR all visible text on screen
        full_gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        full_text = pytesseract.image_to_string(full_gray)
        balance = _extract_balance_from_text(full_text)
        if full_text.strip():
            logger.info(f"[💬] Full-screen OCR text:\n{full_text.strip()}")
        if balance:
            logger.info(f"[💰] Detected balance (approx): {balance}")

        # Save full screenshot
        if DEBUG_MODE:
            debug_path = os.path.join(DEBUG_SHOT_DIR, f"{trade_id or 'unknown'}_{timestamp}.png")
            cv2.imwrite(debug_path, screenshot)
            logger.debug(f"[💾] Saved full screenshot: {debug_path}")

        roi = _predict_result_roi(screenshot)

        # Save ROI
        if DEBUG_MODE:
            roi_path = os.path.join(DEBUG_SHOT_DIR, f"{trade_id or 'unknown'}_{timestamp}_ROI.png")
            cv2.imwrite(roi_path, roi)
            logger.debug(f"[💾] Saved ROI image: {roi_path}")

        # Template matching
        win_templates = _load_templates_from_dir(WIN_TEMPLATE_DIR)
        loss_templates = _load_templates_from_dir(LOSS_TEMPLATE_DIR)
        win_detected = _match_templates(roi, win_templates, "WIN")
        loss_detected = _match_templates(roi, loss_templates, "LOSS")

        # OCR inside ROI
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        ocr_text = pytesseract.image_to_string(gray_roi)
        if DEBUG_MODE:
            logger.debug(f"[🔡] ROI OCR text: {ocr_text.strip()!r}")

        ocr_win = any(s.startswith("+") for s in ocr_text.split())
        ocr_loss = "$0" in ocr_text

        if win_detected or ocr_win:
            logger.info(f"[🏆] WIN detected ({'OCR' if ocr_win else 'template'})")
            _capture_template_from_roi(roi, "WIN")
            return "WIN"
        if loss_detected or ocr_loss:
            logger.info(f"[💀] LOSS detected ({'OCR' if ocr_loss else 'template'})")
            _capture_template_from_roi(roi, "LOSS")
            return "LOSS"

        if DEBUG_MODE:
            logger.debug("[ℹ️] No result detected this round")

    except Exception as e:
        logger.exception(f"[❌] Detection failed: {e}")
    return None

# ---------------------------
# Monitoring thread
# ---------------------------
def _monitor_trade(trade_id: str, expiry_timestamp: float = None):
    logger.info(f"[🔎] Starting monitor for {trade_id}")

    if expiry_timestamp:
        now = time.time()
        wait = expiry_timestamp - now - 3  # 🆕 start scanning 3s before expiry
        if wait > 0:
            logger.info(f"[⏳] Waiting {wait:.2f}s before detection phase")
            time.sleep(wait)

    logger.info(f"[⚡] Trade {trade_id}: detection window active (3s pre + 3s post expiry)")
    end_time = (expiry_timestamp or time.time()) + 3  # 🆕 continue 3s after expiry
    scan_count = 0

    while time.time() < end_time:
        result = _cv_detect_result(trade_id)
        scan_count += 1
        if DEBUG_MODE:
            logger.debug(f"[🔁] Scan #{scan_count} result={result}")

        if result:
            logger.info(f"[📣] Trade {trade_id}: detected {result} after {scan_count} scans")
            shared.trade_manager.trade_result_received(trade_id, result)
            return
        time.sleep(FAST_SCAN_INTERVAL)

    logger.warning(f"[⚠️] Trade {trade_id}: no result detected after {FAST_SCAN_DURATION}s")
    shared.trade_manager.trade_result_received(trade_id, "NO_RESULT")

# ---------------------------
# Public API
# ---------------------------
def start_trade_result_monitor(trade_id: str, expiry_timestamp: float = None):
    logger.info(f"[🧠] Starting monitor thread for {trade_id}, expiry={expiry_timestamp}")
    t = threading.Thread(target=_monitor_trade, args=(trade_id, expiry_timestamp), daemon=True)
    t.start()
    logger.info(f"[🚀] Detection thread launched for {trade_id}")
        
