# launcher.py
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# -----------------------------
# Hardcoded credentials
# -----------------------------
EMAIL = "AaCcWw3468"
PASSWORD = "mylivemyfuture@123gmail.com"

# -----------------------------
# Wait for DISPLAY to be ready
# -----------------------------
DISPLAY = os.environ.get("DISPLAY", ":1")
timeout = 30  # seconds
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
chrome_options.add_argument("--headless=new")  # comment out if you want to see GUI in VNC

service = Service("/usr/local/bin/chromedriver")

# -----------------------------
# Launch Chrome
# -----------------------------
driver = webdriver.Chrome(service=service, options=chrome_options)
driver.get("https://accounts.google.com/signin")
time.sleep(3)

# -----------------------------
# Autofill email (without clicking Next)
# -----------------------------
try:
    email_input = driver.find_element(By.XPATH, "//input[@type='email']")
    email_input.send_keys(EMAIL)
    print("[✅] Email autofilled.")
except Exception as e:
    print(f"[❌] Failed to autofill email: {e}")

time.sleep(3)

# -----------------------------
# Autofill password (without clicking Next)
# -----------------------------
try:
    password_input = driver.find_element(By.XPATH, "//input[@type='password']")
    password_input.send_keys(PASSWORD)
    print("[✅] Password autofilled.")
except Exception as e:
    print(f"[❌] Failed to autofill password: {e}")

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
