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
AUDIO_DETECTION_ENABLED = True
AUDIO_SAMPLE_DURATION = 1.0  # seconds to listen per check
AUDIO_DEVICE = "VNCOutput.monitor"  # PulseAudio monitor from start.sh
WIN_THRESHOLD = 0.02
LOSS_THRESHOLD = 0.01

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
    Audio detection: checks if RMS exceeds thresholds.
    Returns "WIN", "LOSS", or None.
    Logs RMS values for debugging.
    """
    if not AUDIO_DETECTION_ENABLED:
        return None
    try:
        # Record from PulseAudio monitor
        data = sd.rec(
            int(AUDIO_SAMPLE_DURATION * 44100),
            samplerate=44100,
            channels=1,
            blocking=True,
            device=AUDIO_DEVICE
        )
        rms = (np.mean(np.square(data))) ** 0.5

        # Log RMS for debugging
        logger.info(f"[🔊] Audio RMS: {rms:.5f}")

        if rms > WIN_THRESHOLD:
            logger.info(f"[📣] Audio RMS above WIN threshold, reporting WIN")
            return "WIN"
        elif rms > LOSS_THRESHOLD:
            logger.info(f"[📣] Audio RMS above LOSS threshold, reporting LOSS")
            return "LOSS"
        else:
            logger.info(f"[ℹ️] Audio below detection thresholds")
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


# ---------------------------
# Audio debug utility
# ---------------------------
def test_audio_monitor(duration: float = 2.0):
    """
    Records from the PulseAudio monitor for `duration` seconds
    and prints RMS value to verify audio capture.
    """
    print(f"[ℹ️] Testing audio monitor '{AUDIO_DEVICE}' for {duration} seconds...")
    try:
        data = sd.rec(
            int(duration * 44100),
            samplerate=44100,
            channels=1,
            blocking=True,
            device=AUDIO_DEVICE
        )
        rms = (np.mean(np.square(data))) ** 0.5
        print(f"[✅] RMS detected: {rms:.5f}")
        if rms > WIN_THRESHOLD:
            print("[✅] Audio above WIN threshold detected!")
        elif rms > LOSS_THRESHOLD:
            print("[✅] Audio above LOSS threshold detected!")
        else:
            print("[ℹ️] Audio below thresholds.")
    except Exception as e:
        print(f"[❌] Audio test failed: {e}")


# ---------------------------
# Screenshot OCR debug utility
# ---------------------------
def test_screenshot_ocr():
    """
    Captures the configured screen region and prints detected text.
    """
    print(f"[ℹ️] Testing OCR for region {SCREENSHOT_REGION}...")
    try:
        im = pyautogui.screenshot(region=SCREENSHOT_REGION)
        im.show()  # optional: display the screenshot in VNC
        text = pytesseract.image_to_string(im).strip()
        print(f"[✅] Detected text: '{text}'")
    except Exception as e:
        print(f"[❌] OCR test failed: {e}")
        
