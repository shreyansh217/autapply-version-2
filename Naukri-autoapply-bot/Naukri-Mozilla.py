import csv
import time
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load .env file for local runs; GitHub Actions uses Secrets directly
load_dotenv()

# ===================== CONFIGURATION =====================
firstname = ''          # Your First Name
lastname  = ''          # Your Last Name
email     = os.environ['NAUKRI_EMAIL']
password  = os.environ['NAUKRI_PASSWORD']
maxcount  = 100         # Max jobs to apply to per run
# =========================================================

# --- Job Sources ---
# 1. Recommended Jobs page (always included)
# 2. Any filtered search URLs you want to also apply to
SEARCH_URLS = [
    'https://www.naukri.com/software-engineer-jobs?k=software+engineer&nignbevent_src=jobsearchDeskGNB&experience=1&ctcFilter=10to15&ctcFilter=15to25&ctcFilter=25to50',
    # Add more search URLs here if needed:
    # 'https://www.naukri.com/python-developer-jobs?...',
]
MAX_PAGES_PER_URL = 5   # How many pages of results to scrape per search URL

# -----------------------------------------------------------

joblink      = []
applied      = 0
failed       = 0
applied_list = {'passed': [], 'failed': []}

def collect_jobs_from_page(driver):
    """Scrape all article[data-job-id] cards visible on current page."""
    found = []
    cards = driver.find_elements(By.CSS_SELECTOR, 'article[data-job-id]')
    for card in cards:
        job_id = card.get_attribute('data-job-id')
        if job_id:
            # Try to find an actual job-listing href inside the card
            anchors = card.find_elements(By.TAG_NAME, 'a')
            href = None
            for a in anchors:
                h = a.get_attribute('href') or ''
                if 'naukri.com' in h and 'job-listings' in h:
                    href = h
                    break
            if not href:
                # Build URL from job ID as fallback
                href = f'https://www.naukri.com/job-listings-{job_id}'
            if href not in joblink:
                found.append(href)
    return found

# --- Launch Firefox (Headless - no browser window) ---
try:
    options = Options()
    options.add_argument('--headless')   # runs Firefox invisibly
    driver = webdriver.Firefox(options=options)
    wait = WebDriverWait(driver, 10)
    print("Browser launched in headless mode (no window).")
except Exception as e:
    print(f"Webdriver exception: {e}")
    print("\nTROUBLESHOOT:")
    print("  1. Make sure Firefox is installed.")
    print("  2. Download geckodriver: https://github.com/mozilla/geckodriver/releases")
    print("  3. Place geckodriver.exe in C:\\Windows\\System32\\")
    exit(1)

# --- Login to Naukri ---
try:
    driver.get('https://www.naukri.com/nlogin/login')
    time.sleep(3)
    wait.until(EC.presence_of_element_located((By.ID, 'usernameField'))).send_keys(email)
    driver.find_element(By.ID, 'passwordField').send_keys(password)
    driver.find_element(By.ID, 'passwordField').send_keys(Keys.ENTER)
    print("Logged in! Waiting for page to load...")
    time.sleep(5)
except Exception as e:
    print(f"Login failed: {e}")
    driver.quit()
    exit(1)

# ================================================================
# SOURCE 1: Recommended Jobs page (scroll to load all)
# ================================================================
print("\n[Source 1] Recommended Jobs page...")
driver.get('https://www.naukri.com/mnjuser/recommendedjobs')
time.sleep(5)

last_count = 0
scroll_attempts = 0
while scroll_attempts < 15:
    new_links = collect_jobs_from_page(driver)
    for link in new_links:
        if link not in joblink:
            joblink.append(link)
    print(f"  Scroll {scroll_attempts+1}: {len(joblink)} jobs collected")
    if len(joblink) == last_count:
        break
    last_count = len(joblink)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)
    scroll_attempts += 1

print(f"  -> Recommended Jobs total: {len(joblink)}")

# ================================================================
# SOURCE 2+: Filtered Search URLs (paginated)
# ================================================================
for src_idx, base_url in enumerate(SEARCH_URLS):
    print(f"\n[Source {src_idx+2}] {base_url[:80]}...")
    before = len(joblink)

    for page_num in range(1, MAX_PAGES_PER_URL + 1):
        # Naukri appends page number as "-{n}" before the query string
        # e.g. /software-engineer-jobs-{n}?...
        # Split URL at '?' to insert page number
        if '?' in base_url:
            path, query = base_url.split('?', 1)
        else:
            path, query = base_url, ''

        # Remove trailing page number if already present (e.g. -1, -2)
        import re
        path = re.sub(r'-\d+$', '', path)

        page_url = f"{path}-{page_num}?{query}" if query else f"{path}-{page_num}"
        driver.get(page_url)
        print(f"  Page {page_num}: {page_url[:90]}")
        time.sleep(4)

        # Scroll page to load lazy-loaded cards
        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        new_links = collect_jobs_from_page(driver)
        added = 0
        for link in new_links:
            if link not in joblink:
                joblink.append(link)
                added += 1

        print(f"    Added {added} new jobs (total: {len(joblink)})")
        if added == 0:
            print("    No new jobs on this page, stopping pagination.")
            break

    print(f"  -> This source added {len(joblink) - before} jobs")

print(f"\n{'='*50}")
print(f"TOTAL JOBS TO APPLY: {len(joblink)}")
print(f"{'='*50}\n")

# ================================================================
# APPLY TO ALL COLLECTED JOBS
# ================================================================
for job_url in joblink:
    if applied >= maxcount:
        print(f"Reached max apply limit ({maxcount}). Stopping.")
        break

    driver.get(job_url)
    time.sleep(4)

    try:
        # Try all known Apply button variants
        apply_btn = None
        for xpath in [
            "//*[text()='Apply']",
            "//*[text()='Easy Apply']",
            "//button[contains(translate(@class,'APPLY','apply'),'apply')]",
            "//a[contains(translate(@class,'APPLY','apply'),'apply')]",
        ]:
            btns = driver.find_elements(By.XPATH, xpath)
            if btns:
                apply_btn = btns[0]
                break

        if apply_btn is None:
            raise Exception("No Apply button found on page")

        driver.execute_script("arguments[0].scrollIntoView(true);", apply_btn)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", apply_btn)
        time.sleep(3)
        applied += 1
        applied_list['passed'].append(job_url)
        print(f"[OK] Applied ({applied}/{maxcount}): {job_url}")

    except Exception as e:
        failed += 1
        applied_list['failed'].append(job_url)
        print(f"[FAIL] Failed ({failed}): {str(e)[:60]}")
        continue

    # Handle optional application form fields
    try:
        if driver.find_elements(By.XPATH, "//*[text()='Your daily quota has been expired.']"):
            print('[WARN] Daily quota reached. Stopping.')
            break
        fname_field = driver.find_elements(By.XPATH, "//input[@id='CUSTOM-FIRSTNAME']")
        if fname_field:
            fname_field[0].send_keys(firstname)
        lname_field = driver.find_elements(By.XPATH, "//input[@id='CUSTOM-LASTNAME']")
        if lname_field:
            lname_field[0].send_keys(lastname)
        submit_btn = driver.find_elements(By.XPATH, "//*[text()='Submit and Apply']")
        if submit_btn:
            submit_btn[0].click()
            time.sleep(2)
    except:
        pass

# --- Done ---
print(f'\n{"="*50}')
print(f'COMPLETED | Applied: {applied} | Failed: {failed}')
print(f'{"="*50}')
print('Saving results to CSV...')

try:
    driver.quit()
except:
    pass

csv_file = "naukriapplied.csv"
passed = applied_list['passed']
failed_list = applied_list['failed']
max_rows = max(len(passed), len(failed_list))
with open(csv_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['passed', 'failed'])
    for i in range(max_rows):
        p = passed[i] if i < len(passed) else ''
        fl = failed_list[i] if i < len(failed_list) else ''
        writer.writerow([p, fl])
print(f"Saved to {csv_file}")