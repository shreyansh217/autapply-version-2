# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

"""
Naukri Filter Auto-Apply Bot
=============================
Applies to all jobs from a filtered Naukri search URL.
Filter: Software Engineer | 1yr exp | CTC 10-50 LPA

Run: python Naukri-Filter-Apply.py
"""

import pandas as pd
import time
import re
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Load .env file for local runs; GitHub Actions uses Secrets directly
load_dotenv()

# ======================================================
#  CONFIGURATION
# ======================================================
EMAIL     = os.environ['NAUKRI_EMAIL']
PASSWORD  = os.environ['NAUKRI_PASSWORD']
FIRSTNAME = ''
LASTNAME  = ''
MAX_APPLY = 100
MAX_PAGES = 15

FILTER_URL = (
    'https://www.naukri.com/software-engineer-jobs'
    '?k=software%20engineer'
    '&nignbevent_src=jobsearchDeskGNB'
    '&experience=1'
    '&ctcFilter=10to15'
    '&ctcFilter=15to25'
    '&ctcFilter=25to50'
)
# ======================================================

joblinks   = []
applied    = 0
failed     = 0
result_log = {'passed': [], 'failed': []}


def page_url(base, n):
    path, _, query = base.partition('?')
    path = re.sub(r'-\d+$', '', path)
    suffix = f'-{n}' if n > 1 else ''
    return f"{path}{suffix}?{query}" if query else f"{path}{suffix}"


def scrape_page(drv):
    """
    Naukri's new search page (React) uses:
      - div[class*='srp-jobtuple-wrapper'] or
      - div[class*='jobTuple'] or
      - a[class*='title'] inside job cards
    We collect job URLs directly from anchor tags.
    """
    # Scroll the page to trigger lazy-loading
    for y in range(0, 8000, 500):
        drv.execute_script(f"window.scrollTo(0, {y});")
        time.sleep(0.3)
    time.sleep(1)

    found = []

    # Strategy 1: article[data-job-id] (old recommended-jobs style)
    for card in drv.find_elements(By.CSS_SELECTOR, 'article[data-job-id]'):
        job_id = card.get_attribute('data-job-id')
        href = None
        for a in card.find_elements(By.TAG_NAME, 'a'):
            h = a.get_attribute('href') or ''
            if 'naukri.com/job-listings' in h:
                href = h
                break
        if not href and job_id:
            href = f'https://www.naukri.com/job-listings-{job_id}'
        if href and href not in joblinks:
            found.append(href)

    # Strategy 2: New React search page - anchor tags with job-listings href
    for a in drv.find_elements(By.TAG_NAME, 'a'):
        h = a.get_attribute('href') or ''
        if 'naukri.com/job-listings' in h and h not in joblinks and h not in found:
            found.append(h)

    # Strategy 3: data-job-id on any element
    if not found:
        for el in drv.find_elements(By.CSS_SELECTOR, '[data-job-id]'):
            job_id = el.get_attribute('data-job-id')
            href = f'https://www.naukri.com/job-listings-{job_id}'
            if href not in joblinks and href not in found:
                found.append(href)

    return found


def is_logged_in(drv):
    """Check if we're logged in by looking for login button absence."""
    try:
        login_btns = drv.find_elements(By.XPATH, "//a[text()='Login']")
        return len(login_btns) == 0
    except:
        return False


def click_apply(drv):
    selectors = [
        (By.XPATH, "//button[normalize-space()='Apply']"),
        (By.XPATH, "//button[normalize-space()='Easy Apply']"),
        (By.XPATH, "//a[normalize-space()='Apply']"),
        (By.XPATH, "//a[normalize-space()='Easy Apply']"),
        (By.CSS_SELECTOR, "button.apply-button"),
        (By.CSS_SELECTOR, "button[class*='apply']"),
        (By.CSS_SELECTOR, "a[class*='apply']"),
        (By.XPATH, "//*[contains(@class,'applyBtn')]"),
        (By.XPATH, "//*[contains(@class,'apply-btn')]"),
    ]
    for by, sel in selectors:
        els = drv.find_elements(by, sel)
        if els:
            drv.execute_script("arguments[0].scrollIntoView({block:'center'});", els[0])
            time.sleep(0.5)
            drv.execute_script("arguments[0].click();", els[0])
            return True
    return False


def handle_form(drv):
    try:
        if drv.find_elements(By.XPATH, "//*[contains(text(),'daily quota')]"):
            return 'quota'
        fn = drv.find_elements(By.ID, 'CUSTOM-FIRSTNAME')
        if fn:
            fn[0].clear(); fn[0].send_keys(FIRSTNAME)
        ln = drv.find_elements(By.ID, 'CUSTOM-LASTNAME')
        if ln:
            ln[0].clear(); ln[0].send_keys(LASTNAME)
        sub = drv.find_elements(By.XPATH, "//*[normalize-space(text())='Submit and Apply']")
        if sub:
            drv.execute_script("arguments[0].click();", sub[0])
            time.sleep(2)
    except:
        pass
    return 'ok'


# ════════════════════════════════════════════════════
#  LAUNCH BROWSER
# ════════════════════════════════════════════════════
print("Starting Naukri Filter Apply Bot...")
try:
    driver = webdriver.Firefox()
    wait   = WebDriverWait(driver, 20)
    driver.maximize_window()
    print("[OK] Browser launched")
except Exception as e:
    print(f"[ERR] Browser failed: {e}")
    exit(1)

# ════════════════════════════════════════════════════
#  LOGIN
# ════════════════════════════════════════════════════
try:
    driver.get('https://www.naukri.com/nlogin/login')
    time.sleep(4)
    wait.until(EC.presence_of_element_located((By.ID, 'usernameField'))).send_keys(EMAIL)
    driver.find_element(By.ID, 'passwordField').send_keys(PASSWORD)
    driver.find_element(By.ID, 'passwordField').send_keys(Keys.ENTER)
    print("[OK] Login submitted - waiting for session...")
    time.sleep(8)  # Wait longer for session to establish

    # Verify login succeeded
    if 'login' in driver.current_url.lower():
        print("[WARN] Still on login page - check credentials")
    else:
        print(f"[OK] Logged in! Current page: {driver.current_url[:60]}")
except Exception as e:
    print(f"[ERR] Login error: {e}")
    driver.quit()
    exit(1)

# ════════════════════════════════════════════════════
#  SCRAPE ALL PAGES
# ════════════════════════════════════════════════════
print("\n" + "-"*60)
print(" Scraping jobs from filter...")
print("-"*60)

for pg in range(1, MAX_PAGES + 1):
    url = page_url(FILTER_URL, pg)
    print(f"\n  [Page {pg:02d}] Loading...")
    driver.get(url)
    time.sleep(5)  # Give the React page time to render

    # Verify still logged in
    if not is_logged_in(driver):
        print("  [WARN] Session lost - re-logging in...")
        driver.get('https://www.naukri.com/nlogin/login')
        time.sleep(3)
        try:
            driver.find_element(By.ID, 'usernameField').send_keys(EMAIL)
            driver.find_element(By.ID, 'passwordField').send_keys(PASSWORD)
            driver.find_element(By.ID, 'passwordField').send_keys(Keys.ENTER)
            time.sleep(6)
            driver.get(url)
            time.sleep(5)
        except:
            pass

    print(f"  URL: {url[:75]}")
    new = scrape_page(driver)

    if not new:
        print(f"  -> No jobs found on page {pg}. Stopping.")
        # Print page source hint for debugging
        src = driver.page_source[:500]
        print(f"  Page snippet: {src[:200]}")
        break

    for j in new:
        if j not in joblinks:
            joblinks.append(j)

    print(f"  -> +{len(new)} jobs found  |  Total: {len(joblinks)}")

    if len(joblinks) >= MAX_APPLY * 2:
        print(f"  -> Collected enough ({len(joblinks)}). Stopping scrape.")
        break

print("\n" + "-"*60)
print(f"  COLLECTED {len(joblinks)} JOBS - Starting applications...")
print("-"*60 + "\n")

# ════════════════════════════════════════════════════
#  APPLY TO EACH JOB
# ════════════════════════════════════════════════════
for idx, job_url in enumerate(joblinks, start=1):
    if applied >= MAX_APPLY:
        print(f"\n[STOP] Max limit reached ({MAX_APPLY} applications).")
        break

    print(f"[{idx:03d}/{len(joblinks)}] ", end='', flush=True)
    driver.get(job_url)
    time.sleep(4)

    try:
        clicked = click_apply(driver)
        if not clicked:
            raise Exception("No Apply button found")

        time.sleep(3)
        status = handle_form(driver)

        if status == 'quota':
            print("[STOP] Daily quota reached!")
            result_log['passed'].append(job_url)
            break

        applied += 1
        result_log['passed'].append(job_url)
        print(f"[OK] Applied ({applied}/{MAX_APPLY})  ...{job_url[-50:]}")

    except Exception as e:
        failed += 1
        result_log['failed'].append(job_url)
        print(f"[SKIP] {str(e)[:70]}")

# ════════════════════════════════════════════════════
#  DONE
# ════════════════════════════════════════════════════
print("\n" + "-"*60)
print(f"  FINISHED | Applied: {applied}  Skipped: {failed}")
print("-"*60)

try:
    driver.quit()
except:
    pass

csv_file = 'filter_applied.csv'
df = pd.DataFrame({k: pd.Series(v) for k, v in result_log.items()})
df.to_csv(csv_file, index=False)
print(f"\nResults saved -> {csv_file}")
