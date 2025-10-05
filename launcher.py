# launcher.py
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# -----------------------------
# Hardcoded credentials
# -----------------------------
EMAIL = "AaCcWw3468"
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
# NOTE: headless mode is OFF so we can see the browser in VNC
# chrome_options.add_argument("--headless=new")  # DO NOT use headless

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
# Enter email
# -----------------------------
try:
    email_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.NAME, "email"))
    )
    email_input.clear()
    email_input.send_keys(EMAIL)
    print("[✅] Email entered")
except Exception as e:
    print(f"[❌] Failed to enter email: {e}")

# -----------------------------
# Enter password
# -----------------------------
try:
    password_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.NAME, "password"))
    )
    password_input.clear()
    password_input.send_keys(PASSWORD)
    print("[✅] Password entered")
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
