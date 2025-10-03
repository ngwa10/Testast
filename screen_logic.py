import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image
import pytesseract

# -------------------------
# Gmail credentials (use App Password if 2FA)
# -------------------------
EMAIL = "ylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"

# -------------------------
# Chrome setup
# -------------------------
chrome_options = Options()
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-setuid-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--user-data-dir=/home/dockuser/chrome-profile")

service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=chrome_options)

# -------------------------
# Wait for UI to load
# -------------------------
print("[⏱️] Waiting 10 seconds for UI readiness...")
time.sleep(10)

# -------------------------
# Gmail login (with explicit waits)
# -------------------------
try:
    driver.get("https://mail.google.com/")
    wait = WebDriverWait(driver, 20)

    email_input = wait.until(EC.presence_of_element_located((By.ID, "identifierId")))
    email_input.send_keys(EMAIL)
    email_input.send_keys(Keys.RETURN)

    password_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))
    password_input.send_keys(PASSWORD)
    password_input.send_keys(Keys.RETURN)

    print("[✅] Gmail login attempted successfully")

except Exception as e:
    print("[⚠️] Gmail login failed:", e)

# -------------------------
# Screenshot function
# -------------------------
def take_screenshot(name):
    img_path = f"/home/dockuser/{name}.png"
    driver.save_screenshot(img_path)
    print(f"[✅] Screenshot saved: {img_path}")
    return img_path

# Screenshots to capture
screenshots = ["gmail_login", "balance_screen", "currency_dropdown", "timeframe_dropdown"]

for s in screenshots:
    take_screenshot(s)

# -------------------------
# OCR check
# -------------------------
def check_text_in_screenshot(filename, keyword):
    img = Image.open(filename)
    text = pytesseract.image_to_string(img)
    return keyword.lower() in text.lower()

results = {
    "gmail": check_text_in_screenshot("/home/dockuser/gmail_login.png", "gmail"),
    "balance": check_text_in_screenshot("/home/dockuser/balance_screen.png", "$"),
    "currency": check_text_in_screenshot("/home/dockuser/currency_dropdown.png", "USD"),
    "timeframe": check_text_in_screenshot("/home/dockuser/timeframe_dropdown.png", "1M")
}

print("[ℹ️] Screenshot results:", results)

# Retry once if some elements missing
if not all(results.values()):
    print("[⚠️] Some UI elements not detected, retrying once...")
    driver.refresh()
    time.sleep(5)
    for s in screenshots:
        take_screenshot(s)

print("[✅] Screen logic completed.")
    
