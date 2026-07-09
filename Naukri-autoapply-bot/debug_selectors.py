"""
DEBUG SCRIPT - Run this FIRST to find correct selectors on the Recommended Jobs page.
It will open the browser, log in, go to the recommended jobs page, and print all anchor tags found.
"""
import os
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load .env file for local runs; GitHub Actions uses Secrets directly
load_dotenv()

email    = os.environ['NAUKRI_EMAIL']
password = os.environ['NAUKRI_PASSWORD']

driver = webdriver.Firefox()
wait   = WebDriverWait(driver, 15)

# Login
driver.get('https://www.naukri.com/nlogin/login')
time.sleep(3)
wait.until(EC.presence_of_element_located((By.ID, 'usernameField'))).send_keys(email)
driver.find_element(By.ID, 'passwordField').send_keys(password)
driver.find_element(By.ID, 'passwordField').send_keys(Keys.ENTER)
print("Logged in. Waiting...")
time.sleep(6)

# Go to recommended jobs
driver.get('https://www.naukri.com/mnjuser/recommendedjobs')
time.sleep(6)

print("\n========== PAGE TITLE ==========")
print(driver.title)
print("========== CURRENT URL ==========")
print(driver.current_url)

# Print ALL anchor tags and their classes/hrefs
print("\n========== ALL <a> TAGS WITH HREF ==========")
all_links = driver.find_elements(By.TAG_NAME, 'a')
job_links = []
for a in all_links:
    href = a.get_attribute('href') or ''
    cls  = a.get_attribute('class') or ''
    text = a.text.strip()[:60]
    if '/job-listings-' in href or 'naukri.com/' in href and len(href) > 40:
        print(f"  class='{cls}' | text='{text}' | href={href[:80]}")
        job_links.append(href)

print(f"\nTotal potential job links found: {len(job_links)}")

# Also print page source snippet for debugging
print("\n========== PAGE SOURCE SNIPPET (first 3000 chars) ==========")
src = driver.page_source
# Find first job card area
idx = src.find('jobTuple')
if idx == -1:
    idx = src.find('job-card')
if idx == -1:
    idx = src.find('srp-jobtuple')
if idx == -1:
    idx = 0
print(src[max(0,idx-200):idx+3000])

input("\nPress Enter to close browser...")
driver.quit()
