#!/usr/bin/env python3
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, TimeoutException

# Get credentials from environment variables
EMAIL = os.getenv("PO_EMAIL")
PASSWORD = os.getenv("PO_PASSWORD")

if not EMAIL or not PASSWORD:
    raise ValueError("❌ PO_EMAIL or PO_PASSWORD environment variables are not set!")

# Attach to the already running Chrome session
options = Options()
options.debugger_address = "127.0.0.1:9222"  # Must match the port from start.sh

print("📡 Connecting to existing Chrome instance...")
driver = webdriver.Chrome(options=options)

# Give the page time to load (adjust if needed)
time.sleep(5)

# Try filling the login form
print("🔐 Attempting to fill login fields...")
success = False

for attempt in range(10):  # retry up to 10 times if fields aren't visible yet
    try:
        email_field = driver.find_element(By.NAME, "email")
        password_field = driver.find_element(By.NAME, "password")

        email_field.clear()
        email_field.send_keys(EMAIL)

        password_field.clear()
        password_field.send_keys(PASSWORD)
        password_field.send_keys(Keys.RETURN)

        print("✅ Login form filled and submitted successfully!")
        success = True
        break
    except NoSuchElementException:
        print(f"⏳ Login fields not found yet (attempt {attempt+1}/10)...")
        time.sleep(2)

if not success:
    print("❌ Failed to find login fields after multiple attempts. Check selector names.")

# Keep the session alive (optional)
while True:
    time.sleep(60)
      
