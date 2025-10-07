"""
win_loss.py
Detect trade results using OpenCV template matching + optional audio.
Detection starts in the last 10 seconds of a trade, stops after 2 seconds if no result.
Reports directly to core.py via shared.trade_manager.trade_result_received(...)
"""

import threading
import time
import cv2
import numpy as np
from PIL import ImageGrab
import sounddevice as sd
import shared
import logging

# Logging setup
logger = logging.getLogger("win_loss")

# ---------------------------
# Configuration
# ---------------------------
DETECTION_TIMEOUT = 2  # seconds
AUDIO_DETECTION_ENABLED = True
AUDIO_SAMPLE_DURATION = 1.0  # seconds to listen per check
AUDIO_DEVICE = "VNCOutput.monitor"  # PulseAudio monitor from start.sh
WIN_THRESHOLD = 0.02
LOSS_THRESHOLD = 0.01

# Paths to templates
WIN_TEMPLATE_PATH = "/home/dockuser/templates/win_template.png"
LOSS_TEMPLATE_PATH = "/home/dockuser/templates/loss_template.png"

# Template matching threshold
TEMPLATE_MATCH_THRESHOLD = 0.8

# ---------------------------
# Utility functions
# ---------------------------
def _cv_detect_result() -> str:
    """
    Uses OpenCV template matching to detect WIN/LOSS anywhere on the screen.
    Returns "WIN", "LOSS", or None
    """
    try:
        # Grab full screen
        screenshot = np.array(ImageGrab.grab())
        gray_screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        # Check WIN template
        win_template = cv2.imread(WIN_TEMPLATE_PATH, 0)
        if win_template is not None:
            res_win = cv2.matchTemplate(gray_screenshot, win_template, cv2.TM_CCOEFF_NORMED)
            if np.max(res_win) > TEMPLATE_MATCH_THRESHOLD:
                return "WIN"

        # Check LOSS template
        loss_template = cv2.imread(LOSS_TEMPLATE_PATH, 0)
        if loss_template is not None:
            res_loss = cv2.matchTemplate(gray_screenshot, loss_template, cv2.TM_CCOEFF_NORMED)
            if np.max(res_loss) > TEMPLATE_MATCH_THRESHOLD:
                return "LOSS"

    except Exception as e:
        logger.error(f"[❌] OpenCV detection failed: {e}")
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
        # OpenCV template detection
        result = _cv_detect_result()
        if result:
            logger.info(f"[📣] Trade {trade_id} result detected via OpenCV: {result}")
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
# Screenshot debug utility
# ---------------------------
def test_screenshot_cv():
    """
    Captures full screen and tests OpenCV template matching.
    """
    print(f"[ℹ️] Testing OpenCV template detection...")
    result = _cv_detect_result()
    print(f"[✅] Detected result: {result}")
        
