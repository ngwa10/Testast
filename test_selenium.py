from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time

# --------------------------
# Chrome options
# --------------------------
options = Options()
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--disable-gpu")
options.add_argument("--start-maximized")
options.add_argument("--user-data-dir=/tmp/chrome-user-data")
# options.add_argument("--headless=new")  # optional

# --------------------------
# Start Chrome
# --------------------------
service = Service("/usr/local/bin/chromedriver")
driver = webdriver.Chrome(service=service, options=options)

# --------------------------
# Navigate to login page
# --------------------------
driver.get("https://pocketoption.com/en/login/")

# Now you can add your auto-fill logic here
