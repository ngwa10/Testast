#!/usr/bin/env python3
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException, WebDriverException

EMAIL = os.getenv("PO_EMAIL")
PASSWORD = os.getenv("PO_PASSWORD")
if not EMAIL or not PASSWORD:
    raise ValueError("❌ PO_EMAIL or PO_PASSWORD environment variables are not set!")

options = Options()
options.debugger_address = "127.0.0.1:9222"

print("📡 Connecting to existing Chrome instance...")
driver = webdriver.Chrome(options=options)
time.sleep(3)

# =========================
# 1️⃣ Ensure correct tab
# =========================
print("🔎 Checking open tabs...")
for handle in driver.window_handles:
    driver.switch_to.window(handle)
    if "pocketoption.com/login" in driver.current_url.lower():
        print(f"✅ Switched to PocketOption tab: {driver.current_url}")
        break
else:
    print("⚠️ PocketOption login tab not found.")

time.sleep(3)

# =========================
# 2️⃣ Try normal Selenium typing
# =========================
def try_selenium_typing():
    print("🧪 Attempting standard Selenium fill...")
    for attempt in range(10):
        try:
            email_field = driver.find_element(By.CSS_SELECTOR, "input[name='email'], input[type='email']")
            password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[type='password']")

            driver.execute_script("arguments[0].scrollIntoView(true);", email_field)
            driver.execute_script("arguments[0].scrollIntoView(true);", password_field)

            email_field.clear()
            email_field.send_keys(EMAIL)
            password_field.clear()
            password_field.send_keys(PASSWORD)
            password_field.send_keys(Keys.RETURN)
            print("✅ Selenium typing success!")
            return True
        except NoSuchElementException:
            print(f"⏳ Fields not found yet (attempt {attempt+1}/10)...")
            time.sleep(2)
    return False

# =========================
# 3️⃣ JS DOM manipulation fallback
# =========================
def try_js_fill():
    print("🪄 Attempting JS DOM fill...")
    try:
        driver.execute_script("""
            const email = document.querySelector("input[name='email'], input[type='email']");
            const pass = document.querySelector("input[name='password'], input[type='password']");
            if (email) { email.value = arguments[0]; email.dispatchEvent(new Event('input', { bubbles: true })); }
            if (pass) { pass.value = arguments[1]; pass.dispatchEvent(new Event('input', { bubbles: true })); }
        """, EMAIL, PASSWORD)
        # Try submitting the form
        driver.execute_script("""
            const form = document.querySelector('form');
            if (form) form.submit();
        """)
        print("✅ JS field injection done.")
        return True
    except WebDriverException as e:
        print("❌ JS injection failed:", e)
        return False

# =========================
# 4️⃣ Focus + Paste fallback
# =========================
def try_focus_paste():
    print("📋 Attempting focus + paste fallback...")
    try:
        email_field = driver.find_element(By.CSS_SELECTOR, "input[name='email'], input[type='email']")
        password_field = driver.find_element(By.CSS_SELECTOR, "input[name='password'], input[type='password']")
        
        email_field.click()
        driver.execute_script(f"document.execCommand('insertText', false, '{EMAIL}');")
        time.sleep(1)
        password_field.click()
        driver.execute_script(f"document.execCommand('insertText', false, '{PASSWORD}');")
        time.sleep(1)
        password_field.send_keys(Keys.RETURN)
        print("✅ Focus + paste fallback worked.")
        return True
    except Exception as e:
        print("❌ Focus + paste fallback failed:", e)
        return False

# =========================
# 🧪 Try all approaches
# =========================
if try_selenium_typing():
    pass
elif try_js_fill():
    pass
elif try_focus_paste():
    pass
else:
    print("🚨 All autofill strategies failed. Manual login may be required.")

# Keep session alive
while True:
    time.sleep(60)
