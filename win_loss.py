"""
win_loss.py
Detect trade results using screenshot + optional audio.
Detection starts in the last 10 seconds of a trade, stops after 2 seconds if no result.
Reports directly to core.py via shared.trade_manager.trade_result_received(...)
"""

import threading
import time
from datetime import datetime
import pyautogui
from PIL import Image
import pytesseract
import numpy as np
import sounddevice as sd
import shared
import logging

# Logging setup
logger = logging.getLogger("win_loss")

# ---------------------------
# Configuration
# ---------------------------
SCREENSHOT_REGION = (1000, 300, 200, 80)  # (left, top, width, height) adjust to your trade result area
DETECTION_TIMEOUT = 2  # seconds
AUDIO_DETECTION_ENABLED = True  # if you want to detect the audio layer
AUDIO_SAMPLE_DURATION = 1.0  # seconds to listen per check
AUDIO_THRESHOLD = 0.02  # simple RMS threshold for detecting click/sound


# ---------------------------
# Utility functions
# ---------------------------
def _ocr_detect_result() -> str:
    """
    Capture the screen area and try to read the trade result.
    Returns "WIN", "LOSS", or None
    """
    try:
        im = pyautogui.screenshot(region=SCREENSHOT_REGION)
        text = pytesseract.image_to_string(im).strip()
        text_upper = text.upper()
        if text_upper.startswith("+"):  # green win
            return "WIN"
        elif text_upper == "$0" or "LOSS" in text_upper:  # red loss
            return "LOSS"
    except Exception as e:
        logger.error(f"[❌] OCR detection failed: {e}")
    return None


def _audio_detect_result() -> str:
    """
    Simple audio detection: checks if RMS exceeds threshold
    Returns "WIN", "LOSS", or None
    """
    if not AUDIO_DETECTION_ENABLED:
        return None
    try:
        data = sd.rec(int(AUDIO_SAMPLE_DURATION * 44100), samplerate=44100, channels=1, blocking=True)
        rms = (np.mean(np.square(data))) ** 0.5
        if rms > AUDIO_THRESHOLD:
            # You can customize: maybe the broker uses distinct sounds for win/loss
            return "WIN"  # placeholder
    except Exception as e:
        logger.error(f"[❌] Audio detection failed: {e}")
    return None


# ---------------------------
# Core monitoring function
# ---------------------------
def _monitor_trade(trade_id: str):
    start_time = time.time()
    logger.info(f"[🔎] Win/Loss detection started for trade {trade_id}")

    while time.time() - start_time < DETECTION_TIMEOUT:
        # Screenshot OCR detection
        result = _ocr_detect_result()
        if result:
            logger.info(f"[📣] Trade {trade_id} result detected via OCR: {result}")
            shared.trade_manager.trade_result_received(trade_id, result)
            return

        # Audio detection layer
        result = _audio_detect_result()
        if result:
            logger.info(f"[📣] Trade {trade_id} result detected via audio: {result}")
            shared.trade_manager.trade_result_received(trade_id, result)
            return

        time.sleep(0.1)  # small delay to avoid hogging CPU

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

