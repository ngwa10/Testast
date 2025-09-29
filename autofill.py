#!/usr/bin/env python3
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, SessionNotCreatedException, WebDriverException

EMAIL = os.getenv("PO_EMAIL")
PASSWORD = os.getenv("PO_PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("❌ PO_EMAIL or PO_PASSWORD environment variables are not set!")

options = Options()
options.debugger_address = "127.0.0.1:9222"

# =========================
# Retry loop to attach Selenium to Chrome
# =========================
max_attempts = 15
for attempt in range(max_attempts):
    try:
        driver = webdriver.Chrome(options=options)
        print("📡 Connected to Chrome debugger!")
        break
    except SessionNotCreatedException:
        print(f"⏳ Chrome not ready yet, retrying ({attempt+1}/{max_attempts})...")
        time.sleep(2)
else:
    raise RuntimeError("❌ Could not connect to Chrome debugger after multiple attempts")

time.sleep(2)

# =========================
# Switch to PocketOption tab
# =========================
for handle in driver.window_handles:
    driver.switch_to.window(handle)
    if "pocketoption.com/login" in driver.current_url.lower():
        print(f"✅ Switched to PocketOption tab: {driver.current_url}")
        break
else:
    print("⚠️ PocketOption login tab not found")

time.sleep(2)

# =========================
# Fill email and password
# =========================
def autofill():
    try:
        email_field = driver.find_element(By.CSS_SELECTOR, "input[name='email'], input[type='email']")
        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[type='password']")

        email_field.clear()
        email_field.send_keys(EMAIL)
        password_field.clear()
        password_field.send_keys(PASSWORD)
        password_field.send_keys(Keys.RETURN)
        print("✅ Autofill done!")
    except NoSuchElementException:
        print("❌ Email/password fields not found")
    except WebDriverException as e:
        print("❌ WebDriver exception:", e)

autofill()

# =========================
# Keep session alive
# =========================
while True:
    time.sleep(60)
