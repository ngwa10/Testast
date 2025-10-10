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
import mss.tools

logger = logging.getLogger("win_loss")

# ---------------------------
# Configuration
# ---------------------------
DEBUG_MODE = True  # 🔧 Toggle this to False for production

WIN_TEMPLATE_DIR = "/home/dockuser/templates/win/"
LOSS_TEMPLATE_DIR = "/home/dockuser/templates/loss/"
DEBUG_SHOT_DIR = "/home/dockuser/screenshots/debug/"
MAX_TEMPLATES = 30
TEMPLATE_MATCH_THRESHOLD = 0.8
ROI_PAD = 20
FAST_SCAN_INTERVAL = 0.1
SCAN_DURATION_PRE = 3
SCAN_DURATION_POST = 3

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
# ROI & Template Capture
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

# ---------------------------
# Win/Loss Detection (Full-Screen)
# ---------------------------
def _cv_detect_result(trade_id=None) -> str:
    try:
        with mss.mss() as sct:
            monitor = sct.monitors[0]  # Full screen
            sct_img = sct.grab(monitor)
            screenshot = np.array(sct_img)[:, :, :3]  # RGB

        timestamp = datetime.datetime.now().strftime("%H%M%S_%f")

        # Save full screenshot for debugging
        if DEBUG_MODE:
            debug_path = os.path.join(DEBUG_SHOT_DIR, f"{trade_id or 'unknown'}_{timestamp}.png")
            Image.fromarray(screenshot).save(debug_path)
            logger.debug(f"[💾] Saved full screenshot: {debug_path}")

        win_templates = _load_templates_from_dir(WIN_TEMPLATE_DIR)
        loss_templates = _load_templates_from_dir(LOSS_TEMPLATE_DIR)

        # ---------------- Dynamic sliding window detection ----------------
        WINDOW_SIZE = (150, 50)  # width, height of sliding window
        STEP_SIZE = 20           # pixels to move window each step

        def scan_templates(screen, templates, type_name):
            gray_screen = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
            h_screen, w_screen = gray_screen.shape
            for y in range(0, h_screen - WINDOW_SIZE[1], STEP_SIZE):
                for x in range(0, w_screen - WINDOW_SIZE[0], STEP_SIZE):
                    window = gray_screen[y:y+WINDOW_SIZE[1], x:x+WINDOW_SIZE[0]]
                    for i, template in enumerate(templates):
                        res = cv2.matchTemplate(window, template, cv2.TM_CCOEFF_NORMED)
                        max_val = np.max(res)
                        if DEBUG_MODE:
                            logger.debug(f"[🧩] {type_name} template[{i}] window match score: {max_val:.3f} at ({x},{y})")
                        if max_val >= TEMPLATE_MATCH_THRESHOLD:
                            return True, (x, y, template.shape[1], template.shape[0])
            return False, None

        win_detected, win_pos = scan_templates(screenshot, win_templates, "WIN")
        loss_detected, loss_pos = scan_templates(screenshot, loss_templates, "LOSS")

        # ---------------- OCR verification ----------------
        gray_full = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
        ocr_text_full = pytesseract.image_to_string(gray_full)
        if DEBUG_MODE:
            logger.debug(f"[🔡] Full-screen OCR text: {ocr_text_full.strip()!r}")

        # ---------------- Balance/Timeframe capture ----------------
        # Pocket Option does not show "$" reliably, so we just log detected numeric values or timeframe
        balance_candidates = [s for s in ocr_text_full.split() if any(c.isdigit() for c in s)]
        balance_detected = balance_candidates[0] if balance_candidates else None
        if balance_detected:
            logger.info(f"[💰] Detected balance/timeframe (approx): {balance_detected}")

        # ---------------- Capture dynamic ROI for template learning ----------------
        def capture_template_from_pos(pos, result_type):
            if pos:
                x, y, w, h = pos
                roi = screenshot[y:y+h, x:x+w]
                _capture_template_from_roi(roi, result_type)

        # ---------------- Determine result ----------------
        ocr_win = any(s.startswith("+") for s in ocr_text_full.split())
        ocr_loss = "$0" in ocr_text_full

        if win_detected or ocr_win:
            logger.info(f"[🏆] WIN detected ({'OCR' if ocr_win else 'template'})")
            capture_template_from_pos(win_pos, "WIN")
            return "WIN"
        if loss_detected or ocr_loss:
            logger.info(f"[💀] LOSS detected ({'OCR' if ocr_loss else 'template'})")
            capture_template_from_pos(loss_pos, "LOSS")
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
        wait = expiry_timestamp - now - 1
        if wait > 0:
            logger.info(f"[⏳] Waiting {wait:.2f}s before detection phase")
            time.sleep(wait)

    logger.info(f"[⚡] Trade {trade_id}: detection window active (3s pre + 3s post expiry)")
    end_time = (expiry_timestamp or time.time()) + SCAN_DURATION_POST
    scan_count = 0
    start_time = time.time()

    while time.time() < end_time:
        result = _cv_detect_result(trade_id)
        scan_count += 1
        if DEBUG_MODE:
            logger.debug(f"[🔁] Scan #{scan_count} result={result}")

        if result:
            logger.info(f"[📣] Trade {trade_id}: detected {result} after {time.time()-start_time:.2f}s")
            shared.trade_manager.trade_result_received(trade_id, result)
            return
        time.sleep(FAST_SCAN_INTERVAL)

    logger.warning(f"[⚠️] Trade {trade_id}: no result detected after {SCAN_DURATION_PRE + SCAN_DURATION_POST}s")
    shared.trade_manager.trade_result_received(trade_id, "NO_RESULT")

# ---------------------------
# Public API
# ---------------------------
def start_trade_result_monitor(trade_id: str, expiry_timestamp: float = None):
    logger.info(f"[🧠] Starting monitor thread for {trade_id}, expiry={expiry_timestamp}")
    t = threading.Thread(target=_monitor_trade, args=(trade_id, expiry_timestamp), daemon=True)
    t.start()
    logger.info(f"[🚀] Detection thread launched for {trade_id}")
    
