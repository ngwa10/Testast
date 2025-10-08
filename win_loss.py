"""
win_loss.py
Detect trade results using OpenCV template matching with automatic OCR fallback.
- Handles dynamic positioning, size variations, and noise
- Supports multiple templates for improved detection
- Stops detection after 2s if no result
- Automatically falls back to Tesseract OCR if template match fails
"""

import threading
import time
import cv2
import numpy as np
from PIL import ImageGrab
import pytesseract
import shared
import logging
import os
import glob
import re

# Logging setup
logger = logging.getLogger("win_loss")

# ---------------------------
# Configuration
# ---------------------------
DETECTION_TIMEOUT = 2  # seconds

# Template directories (can hold multiple templates)
WIN_TEMPLATE_DIR = "/home/dockuser/templates/win/"
LOSS_TEMPLATE_DIR = "/home/dockuser/templates/loss/"

# Template matching thresholds
PRIMARY_THRESHOLD = 0.7  # confident detection
SECONDARY_THRESHOLD = 0.6  # possible detection (debug/logging)
SHOW_DEBUG_WINDOW = False  # Set True to visualize detection

# OCR keywords
WIN_KEYWORDS = ["WIN", "PROFIT", "SUCCESS"]
LOSS_KEYWORDS = ["LOSS", "LOSE", "FAILED", "FAILURE"]

# ---------------------------
# Utility functions
# ---------------------------
def _load_templates_from_dir(directory: str):
    """Load all PNG templates from a directory."""
    templates = []
    for path in glob.glob(os.path.join(directory, "*.png")):
        template_color = cv2.imread(path)
        template_gray = cv2.imread(path, 0)
        if template_color is not None and template_gray is not None:
            templates.append((template_color, template_gray))
        else:
            logger.warning(f"[⚠️] Could not load template: {path}")
    return templates


def _preprocess_gray(img):
    """Apply noise reduction and contrast normalization to grayscale image."""
    img = cv2.GaussianBlur(img, (3, 3), 0)
    img = cv2.equalizeHist(img)
    return img


def _ocr_fallback(screenshot_gray) -> str:
    """
    Run Tesseract OCR as a fallback detection method.
    Scans entire screenshot for keywords indicating win or loss.
    """
    try:
        text = pytesseract.image_to_string(screenshot_gray)
        text_upper = text.upper()
        logger.info(f"[🔎 OCR] Extracted text: {text_upper.strip()}")

        for kw in WIN_KEYWORDS:
            if re.search(rf"\b{kw}\b", text_upper):
                logger.info("[✅ OCR] WIN detected via OCR fallback")
                return "WIN"

        for kw in LOSS_KEYWORDS:
            if re.search(rf"\b{kw}\b", text_upper):
                logger.info("[❌ OCR] LOSS detected via OCR fallback")
                return "LOSS"

        logger.info("[ℹ️ OCR] No WIN/LOSS keywords found in OCR text")
    except Exception as e:
        logger.error(f"[❌ OCR Fallback Failed] {e}")

    return None


def _cv_detect_result() -> str:
    """
    Uses OpenCV template matching to detect WIN/LOSS anywhere on the screen.
    - Multi-scale
    - Multi-template
    - Noise robust
    - Dual mode: color and grayscale matching
    - Automatic OCR fallback if detection fails
    Returns "WIN", "LOSS", or None.
    """
    try:
        # Grab full screen
        screenshot_color = np.array(ImageGrab.grab())
        screenshot_gray = cv2.cvtColor(screenshot_color, cv2.COLOR_BGR2GRAY)

        # Preprocess for robustness
        screenshot_gray = _preprocess_gray(screenshot_gray)

        # Load all templates
        win_templates = _load_templates_from_dir(WIN_TEMPLATE_DIR)
        loss_templates = _load_templates_from_dir(LOSS_TEMPLATE_DIR)

        detected_result = None
        best_score = 0.0
        best_rect = None

        # Helper: match template(s) across scales
        def match_templates(templates, label):
            nonlocal detected_result, best_score, best_rect
            for template_color, template_gray in templates:
                # Preprocess grayscale template (same as screenshot)
                template_gray = _preprocess_gray(template_gray)

                for scale in np.linspace(0.8, 1.2, 9):  # ±20% scale range
                    resized_color = cv2.resize(template_color, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                    resized_gray = cv2.resize(template_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

                    if (
                        resized_gray.shape[0] > screenshot_gray.shape[0]
                        or resized_gray.shape[1] > screenshot_gray.shape[1]
                    ):
                        continue

                    # Grayscale matching
                    res_gray = cv2.matchTemplate(screenshot_gray, resized_gray, cv2.TM_CCOEFF_NORMED)
                    max_val_gray = np.max(res_gray)

                    # Color matching
                    res_color = cv2.matchTemplate(screenshot_color, resized_color, cv2.TM_CCOEFF_NORMED)
                    max_val_color = np.max(res_color)

                    # Use best of both
                    max_val = max(max_val_gray, max_val_color)

                    if max_val > best_score:
                        best_score = max_val
                        detected_result = label
                        max_loc = np.unravel_index(res_gray.argmax(), res_gray.shape)[::-1]
                        h, w = resized_gray.shape
                        best_rect = (max_loc, (max_loc[0] + w, max_loc[1] + h))

        # Try all WIN and LOSS templates
        match_templates(win_templates, "WIN")
        match_templates(loss_templates, "LOSS")

        # Final decision from template matching
        if best_score >= PRIMARY_THRESHOLD:
            logger.info(f"[✅ TM] Detected {detected_result} (confidence: {best_score:.3f})")

            if SHOW_DEBUG_WINDOW and best_rect:
                vis = screenshot_color.copy()
                cv2.rectangle(vis, best_rect[0], best_rect[1], (0, 255, 0), 2)
                cv2.imshow("Detection", vis)
                cv2.waitKey(0)
                cv2.destroyAllWindows()

            return detected_result

        elif best_score >= SECONDARY_THRESHOLD:
            logger.info(
                f"[⚠️ TM] Low-confidence detection: {detected_result} (confidence: {best_score:.3f})"
            )
            return detected_result
        else:
            logger.info(f"[ℹ️ TM] No result detected via template matching (best: {best_score:.3f})")

        # ---------------------------
        # OCR Fallback (Automatic)
        # ---------------------------
        logger.info("[🔁] Falling back to OCR...")
        ocr_result = _ocr_fallback(screenshot_gray)
        if ocr_result:
            return ocr_result

    except Exception as e:
        logger.error(f"[❌] OpenCV detection failed: {e}")

    return None


# ---------------------------
# Core monitoring function
# ---------------------------
def _monitor_trade(trade_id: str):
    start_time = time.time()
    logger.info(f"[🔎] Win/Loss detection started for trade {trade_id}")

    while time.time() - start_time < DETECTION_TIMEOUT:
        result = _cv_detect_result()
        if result:
            logger.info(f"[📣] Trade {trade_id} result detected: {result}")
            shared.trade_manager.trade_result_received(trade_id, result)
            return
        time.sleep(0.1)

    # Timeout without result
    logger.warning(f"[⚠️] Trade {trade_id}: no result detected after {DETECTION_TIMEOUT}s")
    shared.trade_manager.trade_result_received(trade_id, "NO_RESULT")


# ---------------------------
# Public API
# ---------------------------
def start_trade_result_monitor(trade_id: str):
    """
    Starts a daemon thread to detect trade result for a given trade_id.
    """
    t = threading.Thread(target=_monitor_trade, args=(trade_id,), daemon=True)
    t.start()


# ---------------------------
# Screenshot debug utility
# ---------------------------
def test_screenshot_cv():
    """
    Captures full screen and tests OpenCV template matching.
    Shows best match confidence score for debugging.
    """
    print("[ℹ️] Testing OpenCV template detection...")
    result = _cv_detect_result()
    print(f"[✅] Detected result: {result}")
