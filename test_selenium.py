"""
Selenium auto-login for Pocket Option
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --------------------------
# Credentials from environment variables or defaults
# --------------------------
EMAIL = os.environ.get("POCKET_EMAIL", "mylivemyfuture@123gmail.com")
PASSWORD = os.environ.get("POCKET_PASSWORD", "AaCcWw3468,")

# --------------------------
# Chrome options
# --------------------------
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--start-maximized")
options.add_argument("--remote-debugging-port=9222")
options.add_argument("--user-data-dir=/tmp/chrome-user-data")
options.add_argument("--headless=new")  # remove if you want GUI

# --------------------------
# Start Chrome WebDriver
# --------------------------
service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

try:
    # Navigate to Pocket Option login page
    driver.get("https://pocketoption.com/en/login/")

    wait = WebDriverWait(driver, 15)

    # Fill email field
    email_input = wait.until(EC.presence_of_element_located((By.NAME, "email")))
    email_input.clear()
    email_input.send_keys(EMAIL)

    # Fill password field
    password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
    password_input.clear()
    password_input.send_keys(PASSWORD)

    # Click login button
    login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
    login_button.click()

    # Wait for dashboard to load (successful login)
    wait.until(EC.url_contains("/en/dashboard"))
    print("[✅] Auto-login successful! Dashboard loaded.")

    # Keep the script running if desired
    while True:
        time.sleep(1)

except Exception as e:
    print(f"[❌] Auto-login failed: {e}")
    exit(1)
