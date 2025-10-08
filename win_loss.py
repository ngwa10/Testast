import threading
import time
import cv2
import numpy as np
from PIL import ImageGrab
import shared
import logging
import os
import glob
import pytesseract
import hashlib
import datetime

logger = logging.getLogger("win_loss")

# Configuration
DETECTION_MAX_TIME = 2  # seconds after expiry
WIN_TEMPLATE_DIR = "/home/dockuser/templates/win/"
LOSS_TEMPLATE_DIR = "/home/dockuser/templates/loss/"
MAX_TEMPLATES = 30
TEMPLATE_MATCH_THRESHOLD = 0.8
ROI_PAD = 20  # pixels around predicted result

# Ensure template directories exist
os.makedirs(WIN_TEMPLATE_DIR, exist_ok=True)
os.makedirs(LOSS_TEMPLATE_DIR, exist_ok=True)


# ---------------------------
# Utility functions
# ---------------------------
def _load_templates_from_dir(directory: str):
    logger.debug(f"[📂] Loading templates from {directory}")
    templates = []
    for path in glob.glob(os.path.join(directory, "*.png")):
        template = cv2.imread(path, 0)
        if template is not None:
            templates.append(template)
            logger.debug(f"[🧩] Loaded template: {os.path.basename(path)}")
    logger.debug(f"[📊] Total templates loaded from {directory}: {len(templates)}")
    return templates


def _image_hash(img):
    return hashlib.md5(cv2.imencode('.png', img)[1]).hexdigest()


def _cleanup_templates(template_dir):
    files = sorted(
        glob.glob(os.path.join(template_dir, "*.png")),
        key=os.path.getmtime
    )
    while len(files) > MAX_TEMPLATES:
        os.remove(files[0])
        logger.info(f"[🗑️] Removed old template: {os.path.basename(files[0])}")
        files.pop(0)


def _save_template_if_needed(img, template_dir, prefix):
    existing_files = os.listdir(template_dir)
    h = _image_hash(img)
    for f in existing_files:
        existing_img = cv2.imread(os.path.join(template_dir, f))
        if _image_hash(existing_img) == h:
            logger.debug(f"[⚖️] Template already exists, skipping save.")
            return False
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    cv2.imwrite(os.path.join(template_dir, filename), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    logger.info(f"[💾] Saved {prefix} template: {filename}")
    _cleanup_templates(template_dir)
    return True


# ---------------------------
# ROI detection
# ---------------------------
def _predict_result_roi(screenshot):
    """
    Detect trend/candle lines dynamically and return ROI where win/loss is likely.
    Works for any bright line or candle color.
    """
    logger.debug(f"[🔍] Predicting ROI from screenshot size {screenshot.shape}")
    hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)

    lower = np.array([0, 50, 150])
    upper = np.array([180, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        logger.debug("[⚪] No contours found — using full screenshot as ROI.")
        return screenshot

    rightmost = max(contours, key=lambda c: cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2])
    x, y, w, h = cv2.boundingRect(rightmost)

    roi_x1 = max(x + w - ROI_PAD, 0)
    roi_y1 = max(y - ROI_PAD, 0)
    roi_x2 = min(x + w + ROI_PAD, screenshot.shape[1])
    roi_y2 = min(y + h + ROI_PAD, screenshot.shape[0])

    roi = screenshot[roi_y1:roi_y2, roi_x1:roi_x2]
    logger.debug(f"[📏] ROI coordinates: ({roi_x1},{roi_y1}) - ({roi_x2},{roi_y2}) size={roi.shape}")
    return roi


def _capture_template_from_roi(roi, result_type):
    logger.debug(f"[🖼️] Capturing template for type {result_type}")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data['text']):
        t = text.strip()
        if result_type == "WIN" and t.startswith("+"):
            logger.debug(f"[🏆] OCR matched WIN text: {t}")
            _save_template_if_needed(roi, WIN_TEMPLATE_DIR, "win")
            break
        elif result_type == "LOSS" and t == "$0":
            logger.debug(f"[💀] OCR matched LOSS text: {t}")
            _save_template_if_needed(roi, LOSS_TEMPLATE_DIR, "loss")
            break


def _match_templates(roi, templates):
    logger.debug(f"[🔎] Matching ROI against {len(templates)} templates...")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    for idx, template in enumerate(templates):
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        max_val = np.max(res)
        logger.debug(f"[📈] Template {idx} match confidence: {max_val:.3f}")
        if max_val >= TEMPLATE_MATCH_THRESHOLD:
            logger.debug(f"[✅] Template {idx} matched (score {max_val:.3f})")
            return True
    return False


# ---------------------------
# Core detection
# ---------------------------
def _cv_detect_result() -> str:
    try:
        logger.debug("[📸] Taking screenshot for detection...")
        screenshot = np.array(ImageGrab.grab())
        logger.debug(f"[🖼️] Screenshot captured: shape={screenshot.shape}")

        roi = _predict_result_roi(screenshot)

        win_templates = _load_templates_from_dir(WIN_TEMPLATE_DIR)
        loss_templates = _load_templates_from_dir(LOSS_TEMPLATE_DIR)

        win_detected = _match_templates(roi, win_templates)
        loss_detected = _match_templates(roi, loss_templates)

        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        ocr_text = pytesseract.image_to_string(gray_roi)
        logger.debug(f"[🔠] OCR text detected: {ocr_text.strip()}")

        ocr_win = any(s.startswith("+") for s in ocr_text.split())
        ocr_loss = "$0" in ocr_text

        if win_detected or ocr_win:
            logger.info("[🏆] WIN detected (template/OCR match)")
            _capture_template_from_roi(roi, "WIN")
            return "WIN"

        if loss_detected or ocr_loss:
            logger.info("[💀] LOSS detected (template/OCR match)")
            _capture_template_from_roi(roi, "LOSS")
            return "LOSS"

        logger.debug("[ℹ️] No result detected in this frame.")
    except Exception as e:
        logger.error(f"[❌] Detection failed: {e}", exc_info=True)
    return None


# ---------------------------
# Monitoring
# ---------------------------
def _monitor_trade(trade_id: str, expiration_time: float):
    """
    trade_id: Unique identifier of trade
    expiration_time: Unix timestamp (time.time() + trade_duration_seconds)
    """
    logger.info(f"[🔎] Monitoring started for trade {trade_id}")

    # Wait until 1 second before expiration
    seconds_until_expiry = expiration_time - time.time()
    if seconds_until_expiry > 1:
        logger.info(f"[⏳] Trade {trade_id} expires in {seconds_until_expiry:.2f}s — waiting...")
        time.sleep(max(0, seconds_until_expiry - 1))

    logger.info(f"[🚀] Trade {trade_id} expired — starting result detection window (2s post-expiry max).")

    start_time = time.time()
    while time.time() - start_time < DETECTION_MAX_TIME:
        result = _cv_detect_result()
        if result:
            logger.info(f"[📣] Trade {trade_id} result detected: {result}")
            shared.trade_manager.trade_result_received(trade_id, result)
            return
        time.sleep(0.1)  # fast polling, short detection window

    logger.warning(f"[⚠️] Trade {trade_id}: NO_RESULT detected after {DETECTION_MAX_TIME}s post-expiry.")
    shared.trade_manager.trade_result_received(trade_id, "NO_RESULT")


# ---------------------------
# Public API
# ---------------------------
def start_trade_result_monitor(trade_id: str, expiration_time: float):
    logger.info(f"[🕒] Starting trade monitor for {trade_id} (expires at {datetime.datetime.fromtimestamp(expiration_time)})")
    t = threading.Thread(target=_monitor_trade, args=(trade_id, expiration_time), daemon=True)
    t.start()
