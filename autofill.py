#!/usr/bin/env python3
"""
autofill.py
-----------------------------------
Attach to the Chrome instance started with --remote-debugging-port=9222
and automatically fill PocketOption login (email + password).
"""

import os
import sys
import time
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException, JavascriptException

# =========================
# Credentials (prefer environment variables)
# =========================
EMAIL = os.getenv("POCKET_EMAIL") or "mylivemyfuture@123gmail.com"
PASSWORD = os.getenv("POCKET_PASS") or "AaCcWw3468"

def mask_email(email):
    if "@" not in email:
        return email
    name, domain = email.split("@", 1)
    return name[0] + "*" * (len(name) - 2) + name[-1] + "@" + domain

print(f"🟢 Starting autofill.py with email: {mask_email(EMAIL)}")

# =========================
# Connect to running Chrome
# =========================
options = Options()
options.debugger_address = "127.0.0.1:9222"

driver = None
for attempt in range(1, 21):
    try:
        driver = webdriver.Chrome(options=options)
        print("📡 Connected to existing Chrome session.")
        break
    except WebDriverException:
        print(f"⏳ Waiting for Chrome (attempt {attempt}/20)...")
        time.sleep(2)

if not driver:
    print("❌ Could not connect to Chrome. Exiting.")
    sys.exit(1)

# =========================
# Find or open PocketOption login page
# =========================
def open_login_tab():
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        if "pocketoption.com" in driver.current_url and "login" in driver.current_url:
            print("🔎 Found existing PocketOption login tab.")
            return
    print("🌐 Opening login page...")
    driver.execute_script("window.open('https://pocketoption.com/login', '_blank');")
    time.sleep(2)
    driver.switch_to.window(driver.window_handles[-1])

open_login_tab()

# =========================
# Wait for login elements
# =========================
def wait_for_element(selectors, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        for by, sel in selectors:
            try:
                el = driver.find_element(by, sel)
                if el:
                    return el
            except Exception:
                pass
        time.sleep(0.5)
    return None

email_selectors = [
    (By.NAME, "email"),
    (By.CSS_SELECTOR, "input[type='email']"),
    (By.CSS_SELECTOR, "input[placeholder*='Email']"),
]
password_selectors = [
    (By.NAME, "password"),
    (By.CSS_SELECTOR, "input[type='password']"),
    (By.CSS_SELECTOR, "input[placeholder*='Password']"),
]

email_el = wait_for_element(email_selectors)
password_el = wait_for_element(password_selectors)

if not email_el or not password_el:
    print("❌ Could not find email or password fields. Exiting.")
    sys.exit(1)

# =========================
# Fill the form
# =========================
def set_value_js(el, value):
    try:
        driver.execute_script("""
            arguments[0].focus();
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, el, value)
    except JavascriptException:
        el.clear()
        el.send_keys(value)

print("✏️ Filling in email and password...")
set_value_js(email_el, EMAIL)
time.sleep(0.5)
set_value_js(password_el, PASSWORD)
time.sleep(0.5)

# =========================
# Submit the form
# =========================
submitted = False

# Try clicking submit button
try:
    submit_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
    submit_btn.click()
    submitted = True
    print("📤 Submitted login form by clicking button.")
except Exception:
    pass

# Try pressing ENTER
if not submitted:
    try:
        password_el.send_keys(Keys.RETURN)
        submitted = True
        print("📤 Submitted by pressing ENTER.")
    except Exception:
        pass

# Try submitting form via JS
if not submitted:
    try:
        driver.execute_script("arguments[0].form.submit();", password_el)
        submitted = True
        print("📤 Submitted via JS form.submit().")
    except Exception:
        pass

# =========================
# Check result
# =========================
time.sleep(5)
current_url = driver.current_url
if "login" not in current_url.lower():
    print("✅ Login appears successful!")
else:
    print("⚠️ Login may have failed (still on login page). Check for CAPTCHA or 2FA.")

# =========================
# Done
# =========================
driver.quit()
print("✅ Autofill complete. Exiting.")
sys.exit(0)
