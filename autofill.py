from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import os
import time

EMAIL = os.getenv("PO_EMAIL")
PASSWORD = os.getenv("PO_PASSWORD")

options = Options()
options.debugger_address = "127.0.0.1:9222"  # attach to running Chrome

driver = webdriver.Chrome(options=options)

# Wait until login page loads
time.sleep(5)

# Find fields — you might need to tweak these selectors if they change
email_field = driver.find_element(By.NAME, "email")
password_field = driver.find_element(By.NAME, "password")

# Fill them
email_field.clear()
email_field.send_keys(EMAIL)
password_field.clear()
password_field.send_keys(PASSWORD)

# Submit
password_field.send_keys(Keys
                         
