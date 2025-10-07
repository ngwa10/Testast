"""
win_loss.py
Detect trade results using OpenCV template matching.
- Handles dynamic positioning, size variations, and noise
- Supports multiple templates for improved detection
- Stops detection after 2s if no result
"""

import threading
import time
import cv2
import numpy as np
from PIL import ImageGrab
import shared
import logging
import os
import glob

# Logging setup
logger = logging.getLogger("win_loss")

# ---------------------------
# Configuration
# ---------------------------
DETECTION_TIMEOUT = 2  # seconds

# Template directories (can hold multiple templates)
WIN_TEMPLATE_DIR = "/home/dockuser/templates/win/"
LOSS_TEMPLATE_DIR = "/home/dockuser/templates/loss/"

# Template matching threshold
TEMPLATE_MATCH_THRESHOLD = 0.8

# ---------------------------
# Utility functions
# ---------------------------
def _load_templates_from_dir(directory: str):
    """Load all PNG templates from a directory."""
    templates = []
    for path in glob.glob(os.path.join(directory, "*.png")):
        template = cv2.imread(path, 0)
        if template is not None:
            templates.append(template)
        else:
            logger.warning(f"[⚠️] Could not load template: {path}")
    return templates


def _cv_detect_result() -> str:
    """
    Uses OpenCV template matching to detect WIN/LOSS anywhere on the screen.
    - Multi-scale
    - Multi-template
    - Noise robust
    Returns "WIN", "LOSS", or None.
    """
    try:
        # Grab full screen
        screenshot = np.array(ImageGrab.grab())
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        # Preprocess for robustness
        gray_screenshot = cv2.GaussianBlur(gray_screenshot, (3, 3), 0)  # reduce noise
        gray_screenshot = cv2.equalizeHist(gray_screenshot)             # normalize contrast

        # Load all templates
        win_templates = _load_templates_from_dir(WIN_TEMPLATE_DIR)
        loss_templates = _load_templates_from_dir(LOSS_TEMPLATE_DIR)

        detected_result = None
        best_score = 0.0

        # Helper: match template(s) across scales
        def match_templates(templates, label):
            nonlocal detected_result, best_score
            for template in templates:
                for scale in np.linspace(0.9, 1.1, 5):  # ±10% scale range
                    resized = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                    if resized.shape[0] > gray_screenshot.shape[0] or resized.shape[1] > gray_screenshot.shape[1]:
                        continue
                    res = cv2.matchTemplate(gray_screenshot, resized, cv2.TM_CCOEFF_NORMED)
                    max_val = np.max(res)
                    if max_val > best_score:
                        best_score = max_val
                        detected_result = label

        # Try all WIN and LOSS templates
        match_templates(win_templates, "WIN")
        match_templates(loss_templates, "LOSS")

        # Final decision
        if best_score > TEMPLATE_MATCH_THRESHOLD:
            logger.info(f"[✅] Detected {detected_result} (confidence: {best_score:.3f})")
            return detected_result
        else:
            logger.info(f"[ℹ️] No result detected (best confidence: {best_score:.3f})")

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
                                         
