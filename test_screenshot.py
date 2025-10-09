import os
from PIL import Image
import mss
import mss.tools
import datetime

DEBUG_SHOT_DIR = "/home/dockuser/screenshots/debug/"
os.makedirs(DEBUG_SHOT_DIR, exist_ok=True)

try:
    with mss.mss() as sct:
        monitor = sct.monitors[0]  # Full screen
        sct_img = sct.grab(monitor)
        screenshot = sct_img.rgb  # Raw RGB bytes

        # Convert to PIL Image
        img = Image.frombytes("RGB", sct_img.size, screenshot)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(DEBUG_SHOT_DIR, f"test_{timestamp}.png")
        img.save(screenshot_path)
        print(f"✅ Screenshot saved successfully at {screenshot_path}!")
except Exception as e:
    print("❌ Screenshot failed:", e)
