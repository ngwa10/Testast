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
EMAIL = "AaCcWw3468@123gmail.com"
PASSWORD = "mylivemyfuture@123gmail.com"

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

service = Service("/usr/local/bin/chromedriver")

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
# Launch Chrome and navigate to Pocket login
# -----------------------------
driver = webdriver.Chrome(service=service, options=chrome_options)
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
