# test_selenium.py
from selenium import webdriver
from selenium.webdriver.common.by import By

driver = webdriver.Chrome()
driver.get("https://www.google.com")
print("✅ Page title:", driver.title)
driver.quit()
