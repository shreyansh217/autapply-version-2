"""
export_cookies.py — Run this ONCE locally to generate NAUKRI_COOKIES secret.

Steps:
  1. Run:  python export_cookies.py
  2. A browser window opens — log in to Naukri (complete OTP if asked)
  3. Press Enter in terminal after you are fully logged in
  4. Copy the printed base64 string
  5. Go to GitHub → Settings → Secrets → Actions → New secret
     Name:  NAUKRI_COOKIES
     Value: (paste the base64 string)
"""

import json
import base64
import time
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()
email    = os.environ.get('NAUKRI_EMAIL', '')
password = os.environ.get('NAUKRI_PASSWORD', '')

if not email or not password:
    print("[ERROR] Set NAUKRI_EMAIL and NAUKRI_PASSWORD in your .env file first.")
    exit(1)

# Open a VISIBLE browser (not headless) so you can complete OTP if needed
options = Options()
options.add_argument('--window-size=1200,800')
driver = webdriver.Chrome(options=options)
wait   = WebDriverWait(driver, 30)

print("[INFO] Opening Naukri login page...")
driver.get('https://www.naukri.com/nlogin/login')
time.sleep(3)

# Auto-fill credentials
try:
    wait.until(EC.presence_of_element_located((By.ID, 'usernameField'))).send_keys(email)
    driver.find_element(By.ID, 'passwordField').send_keys(password)
    driver.find_element(By.ID, 'passwordField').send_keys(Keys.ENTER)
    print("[INFO] Credentials submitted.")
except Exception as e:
    print(f"[WARN] Auto-fill failed: {e}")
    print("[INFO] Please log in manually in the browser window.")

print()
print("=" * 60)
print("  If Naukri asks for OTP, complete it in the browser window.")
print("  Once you are fully logged in (see your profile/homepage),")
print("  come back here and press Enter.")
print("=" * 60)
input("\n  >> Press Enter when you are logged in: ")

# Export all cookies
cookies = driver.get_cookies()
driver.quit()

if not cookies:
    print("[ERROR] No cookies found. Are you sure you logged in?")
    exit(1)

# Remove 'expiry' to avoid domain issues when loading later
for c in cookies:
    c.pop('expiry', None)

cookies_json = json.dumps(cookies)
cookies_b64  = base64.b64encode(cookies_json.encode()).decode()

print()
print("=" * 60)
print("  SUCCESS! Add this as GitHub Secret 'NAUKRI_COOKIES':")
print("=" * 60)
print()
print(cookies_b64)
print()
print("=" * 60)
print("  GitHub → repo Settings → Secrets & variables → Actions")
print("  → New repository secret")
print("  Name:  NAUKRI_COOKIES")
print("  Value: (paste the string above)")
print("=" * 60)
