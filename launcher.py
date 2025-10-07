# launcher.py
import os
import time
import pyperclip
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# -----------------------------
# Hardcoded credentials
# -----------------------------
EMAIL = "mylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"

# -----------------------------
# Chrome setup
# -----------------------------
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1280,800")
chrome_options.add_argument("--user-data-dir=/home/dockuser/chrome-profile")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-infobars")
chrome_options.add_argument("--disable-notifications")
chrome_options.add_argument("--remote-debugging-port=9222")
# Headless OFF to see browser in VNC
# chrome_options.add_argument("--headless=new")

# stealth flags
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

# -----------------------------
# ChromeDriver service path (must be defined before creating driver)
# -----------------------------
service = Service("/usr/local/bin/chromedriver")

# -----------------------------
# Launch Chrome and apply stealth script
# -----------------------------
driver = webdriver.Chrome(service=service, options=chrome_options)

# Extra stealth: remove navigator.webdriver for new pages (may raise on old drivers; catch errors)
try:
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """
    })
except Exception as e:
    # Not fatal — log for debugging
    print(f"[⚠️] Warning: couldn't inject webdriver override: {e}")

# -----------------------------
# Wait for DISPLAY to be ready
# -----------------------------
DISPLAY = os.environ.get("DISPLAY", ":1")
timeout = 30
elapsed = 0
interval = 1

print(f"[ℹ️] Waiting for display {DISPLAY} to be ready...")
while elapsed < timeout:
    if os.path.exists(f"/tmp/.X11-unix/X{DISPLAY[-1]}"):
        print(f"[✅] Display {DISPLAY} is ready.")
        break
    time.sleep(interval)
    elapsed += interval
else:
    print(f"[⚠️] Display {DISPLAY} not found. Continuing anyway...")

# -----------------------------
# Navigate to Pocket login
# -----------------------------
driver.get("https://pocketoption.com/login")
print("[ℹ️] Navigated to Pocket login page")
time.sleep(2)

# -----------------------------
# Function to paste text using clipboard
# -----------------------------
def paste_text(element, text):
    pyperclip.copy(text)
    element.click()
    element.send_keys(Keys.CONTROL, "v")  # paste from clipboard

# -----------------------------
# Enter email
# -----------------------------
try:
    email_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.NAME, "email"))
    )
    paste_text(email_input, EMAIL)
    print("[✅] Email entered exactly")
except Exception as e:
    print(f"[❌] Failed to enter email: {e}")

# -----------------------------
# Enter password
# -----------------------------
try:
    password_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.NAME, "password"))
    )
    paste_text(password_input, PASSWORD)
    print("[✅] Password entered exactly")
except Exception as e:
    print(f"[❌] Failed to enter password: {e}")

# -----------------------------
# Click login button
# -----------------------------
try:
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
    )
    login_button.click()
    print("[✅] Login button clicked. Pocket login attempt finished.")
except Exception as e:
    print(f"[❌] Failed to click login: {e}")

# -----------------------------
# Keep browser open indefinitely
# -----------------------------
print("[ℹ️] Browser will remain open. Press Ctrl+C to exit.")
try:
    while True:
        time.sleep(30)
except KeyboardInterrupt:
    driver.quit()
    print("[🛑] Chrome closed by KeyboardInterrupt.")
