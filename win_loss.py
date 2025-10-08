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
logger.setLevel(logging.DEBUG)  # Enable detailed debugging logs

# Configuration
DETECTION_TIMEOUT = 2  # seconds
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
            logger.debug(f"[✅] Loaded template: {os.path.basename(path)} (shape={template.shape})")
        else:
            logger.warning(f"[⚠️] Failed to load template: {path}")
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
        logger.info(f"[🗑️] Removing old template: {os.path.basename(files[0])}")
        os.remove(files[0])
        files.pop(0)


def _save_template_if_needed(img, template_dir, prefix):
    logger.debug(f"[💾] Checking if new {prefix} template should be saved...")
    existing_files = os.listdir(template_dir)
    h = _image_hash(img)
    for f in existing_files:
        existing_img = cv2.imread(os.path.join(template_dir, f))
        if _image_hash(existing_img) == h:
            logger.debug(f"[🧩] Duplicate template detected — not saving.")
            return False
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{prefix}_{timestamp}.png"
    save_path = os.path.join(template_dir, filename)
    cv2.imwrite(save_path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    logger.info(f"[💾] Saved {prefix} template: {filename}")
    _cleanup_templates(template_dir)
    return True

# ---------------------------
# Trend/Candle ROI detection
# ---------------------------
def _predict_result_roi(screenshot):
    logger.debug(f"[🖼️] Predicting ROI on screenshot with shape {screenshot.shape}")
    hsv = cv2.cvtColor(screenshot, cv2.COLOR_BGR2HSV)
    lower = np.array([0, 50, 150])
    upper = np.array([180, 255, 255])
    mask = cv2.inRange(hsv, lower, upper)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    logger.debug(f"[🧩] Found {len(contours)} contours")

    if not contours:
        logger.warning("[⚠️] No contours found — falling back to full screen ROI")
        return screenshot

    rightmost = max(contours, key=lambda c: cv2.boundingRect(c)[0] + cv2.boundingRect(c)[2])
    x, y, w, h = cv2.boundingRect(rightmost)
    roi_x1 = max(x + w - ROI_PAD, 0)
    roi_y1 = max(y - ROI_PAD, 0)
    roi_x2 = min(x + w + ROI_PAD, screenshot.shape[1])
    roi_y2 = min(y + h + ROI_PAD, screenshot.shape[0])
    logger.debug(f"[📐] ROI coordinates: ({roi_x1}, {roi_y1}), ({roi_x2}, {roi_y2})")
    roi = screenshot[roi_y1:roi_y2, roi_x1:roi_x2]
    logger.debug(f"[🔍] ROI shape: {roi.shape}")
    return roi

def _capture_template_from_roi(roi, result_type):
    logger.debug(f"[🧠] Capturing {result_type} template from ROI")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    for i, text in enumerate(data['text']):
        t = text.strip()
        if not t:
            continue
        logger.debug(f"[OCR] Detected text fragment: '{t}'")
        if result_type == "WIN" and t.startswith("+"):
            logger.info(f"[🏆] WIN text detected in ROI: '{t}'")
            _save_template_if_needed(roi, WIN_TEMPLATE_DIR, "win")
            break
        elif result_type == "LOSS" and t == "$0":
            logger.info(f"[💣] LOSS text detected in ROI: '{t}'")
            _save_template_if_needed(roi, LOSS_TEMPLATE_DIR, "loss")
            break

def _match_templates(roi, templates):
    logger.debug(f"[🧮] Matching ROI against {len(templates)} templates...")
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    for i, template in enumerate(templates):
        res = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
        max_val = np.max(res)
        logger.debug(f"[🔢] Template {i+1}/{len(templates)} match score: {max_val:.3f}")
        if max_val >= TEMPLATE_MATCH_THRESHOLD:
            logger.info(f"[✅] Template match success! Score={max_val:.3f}")
            return True
    logger.debug("[❌] No template matched above threshold.")
    return False

# ---------------------------
# Core detection
# ---------------------------
def _cv_detect_result() -> str:
    try:
        logger.debug("[📸] Capturing screenshot...")
        screenshot = np.array(ImageGrab.grab())
        logger.debug(f"[📸] Screenshot captured successfully (shape={screenshot.shape})")

        roi = _predict_result_roi(screenshot)

        logger.debug("[📂] Loading templates for detection...")
        win_templates = _load_templates_from_dir(WIN_TEMPLATE_DIR)
        loss_templates = _load_templates_from_dir(LOSS_TEMPLATE_DIR)

        logger.debug("[🧩] Running template matching...")
        win_detected = _match_templates(roi, win_templates)
        loss_detected = _match_templates(roi, loss_templates)

        logger.debug("[🔤] Running OCR detection...")
        gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        ocr_text = pytesseract.image_to_string(gray_roi)
        logger.debug(f"[📄] OCR text output:\n{ocr_text}")

        ocr_win = any(s.startswith("+") for s in ocr_text.split())
        ocr_loss = "$0" in ocr_text
        logger.debug(f"[⚙️] OCR result flags: WIN={ocr_win}, LOSS={ocr_loss}")

        if win_detected or ocr_win:
            logger.info("[🏁] WIN detected via template or OCR")
            _capture_template_from_roi(roi, "WIN")
            return "WIN"
        if loss_detected or ocr_loss:
            logger.info("[💀] LOSS detected via template or OCR")
            _capture_template_from_roi(roi, "LOSS")
            return "LOSS"

        logger.info("[ℹ️] No result detected in current frame.")
    except Exception as e:
        logger.error(f"[❌] Detection failed: {e}", exc_info=True)
    return None

# ---------------------------
# Monitoring
# ---------------------------
def _monitor_trade(trade_id: str):
    start_time = time.time()
    logger.info(f"[🔎] Win/Loss detection started for trade {trade_id}")
    iteration = 0
    while time.time() - start_time < DETECTION_TIMEOUT:
        iteration += 1
        logger.debug(f"[🔁] Detection iteration {iteration}")
        result = _cv_detect_result()
        if result:
            logger.info(f"[📣] Trade {trade_id} result detected: {result}")
            shared.trade_manager.trade_result_received(trade_id, result)
            return
        time.sleep(0.1)
    logger.warning(f"[⚠️] Trade {trade_id}: NO_RESULT after {DETECTION_TIMEOUT}s")
    shared.trade_manager.trade_result_received(trade_id, "NO_RESULT")

# ---------------------------
# Public API
# ---------------------------
def start_trade_result_monitor(trade_id: str):
    logger.info(f"[🚀] Starting trade monitor thread for {trade_id}")
    t = threading.Thread(target=_monitor_trade, args=(trade_id,), daemon=True)
    t.start()
    
