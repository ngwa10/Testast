# launcher.py
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
chrome_options.add_argument("--headless=new")  # comment this out if you want to see GUI in VNC

service = Service("/usr/local/bin/chromedriver")

# -----------------------------
# Launch Chrome
# -----------------------------
driver = webdriver.Chrome(service=service, options=chrome_options)
driver.get("https://accounts.google.com/signin")

time.sleep(3)  # wait for page to load

# -----------------------------
# Fill email
# -----------------------------
email_input = driver.find_element(By.XPATH, "//input[@type='email']")
email_input.send_keys(EMAIL)
driver.find_element(By.XPATH, "//div[@id='identifierNext']").click()

time.sleep(3)

# -----------------------------
# Fill password
# -----------------------------
password_input = driver.find_element(By.XPATH, "//input[@type='password']")
password_input.send_keys(PASSWORD)
driver.find_element(By.XPATH, "//div[@id='passwordNext']").click()

time.sleep(5)  # wait for login to complete

print("[✅] Gmail login attempt finished.")

# -----------------------------
# Keep browser open (optional)
# -----------------------------
try:
    while True:
        time.sleep(30)
except KeyboardInterrupt:
    driver.quit()
    print("[🛑] Chrome closed by KeyboardInterrupt.")
