from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --------------------------
# Credentials
# --------------------------
EMAIL = "mylivemyfuture@123gmail.com"
PASSWORD = "AaCcWw3468,"

# --------------------------
# Chrome options
# --------------------------
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--start-maximized")
options.add_argument("--user-data-dir=/tmp/chrome-user-data")
options.add_argument("--disable-blink-features=AutomationControlled")
# options.add_argument("--headless=new")  # comment out for VNC

# --------------------------
# Start Chrome
# --------------------------
service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 20)

# --------------------------
# Human-like typing function
# --------------------------
def human_typing(element, text, delay=0.1):
    """Type like a human, character by character, using JS to set value."""
    for char in text:
        # Append char via JS (prevents site JS from clearing)
        driver.execute_script("arguments[0].value += arguments[1];", element, char)
        element.send_keys(char)  # triggers normal input events
        time.sleep(delay)

try:
    # --------------------------
    # Navigate to Pocket Option login
    # --------------------------
    driver.get("https://pocketoption.com/en/login/")

    # --------------------------
    # Email input
    # --------------------------
    email_input = wait.until(EC.element_to_be_clickable((By.NAME, "email")))
    email_input.click()
    human_typing(email_input, EMAIL, delay=0.05)
    email_input.send_keys(Keys.TAB)  # triggers site events

    # --------------------------
    # Password input
    # --------------------------
    password_input = wait.until(EC.element_to_be_clickable((By.NAME, "password")))
    password_input.click()

    # Force visibility for VNC
    driver.execute_script("arguments[0].type='text';", password_input)

    human_typing(password_input, PASSWORD, delay=0.05)

    # --------------------------
    # Login button
    # --------------------------
    login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
    login_button.click()

    print("[✅] Auto-login completed successfully!")

    # Keep browser open for verification
    time.sleep(10)

except Exception as e:
    print(f"[❌] Auto-login failed: {e}")
    raise

finally:
    driver.quit()
