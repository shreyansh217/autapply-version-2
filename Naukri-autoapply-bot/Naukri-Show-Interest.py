import csv
import base64
import json
import os
import time

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

load_dotenv()

EMAIL = os.environ.get('NAUKRI_EMAIL', '')
PASSWORD = os.environ.get('NAUKRI_PASSWORD', '')
COOKIES = os.environ.get('NAUKRI_COOKIES', '')
MAX_INTEREST = int(os.environ.get('NAUKRI_MAX_INTEREST', '50'))
MAX_SCROLLS = int(os.environ.get('NAUKRI_MAX_SCROLLS', '15'))
HEADLESS = os.environ.get('NAUKRI_HEADLESS', '').lower() in ('1', 'true', 'yes')

RECOMMENDED_JOBS_URL = 'https://www.naukri.com/mnjuser/recommended-earjobs'
RESULTS_FILE = 'interest_applied.csv'


def collect_job_links(driver):
    links = []
    for anchor in driver.find_elements(By.TAG_NAME, 'a'):
        try:
            href = anchor.get_attribute('href') or ''
            if 'naukri.com/job-listings' in href and href not in links:
                links.append(href)
        except StaleElementReferenceException:
            continue
    return links


def click_interest_buttons(driver, limit):
    selectors = [
        (By.XPATH, "//*[self::button or self::a or @role='button'][normalize-space()='Share interest']"),
        (By.XPATH, "//*[self::button or self::a or @role='button'][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'share interest')]"),
        (By.XPATH, "//*[self::button or self::a][normalize-space()=\"I'm Interested\"]"),
        (By.XPATH, "//*[self::button or self::a][normalize-space()=\"I'm interested\"]"),
        (By.XPATH, "//*[self::button or self::a][contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show interest')]") ,
        (By.CSS_SELECTOR, "button[aria-label*='Interested']"),
        (By.CSS_SELECTOR, "button[class*='interested']"),
    ]
    clicked = 0
    attempts = 0
    while clicked < limit and attempts < limit * 3:
        attempts += 1
        found_button = False
        for by, selector in selectors:
            for element in driver.find_elements(by, selector):
                try:
                    if element.get_attribute('data-interest-automation-clicked') == 'true':
                        continue
                    if not element.is_displayed() or not element.is_enabled():
                        continue
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", element
                    )
                    time.sleep(0.5)
                    clicked_now = driver.execute_script(
                        """
                        if (arguments[0].getAttribute('data-interest-automation-clicked') === 'true') {
                            return false;
                        }
                        arguments[0].setAttribute('data-interest-automation-clicked', 'true');
                        arguments[0].click();
                        return true;
                        """,
                        element,
                    )
                    if clicked_now:
                        clicked += 1
                        found_button = True
                    time.sleep(1)
                    break
                except StaleElementReferenceException:
                    continue
            if found_button:
                break
        if not found_button:
            break
    return clicked


def login(driver, wait):
    driver.get('https://www.naukri.com/nlogin/login')
    username = wait.until(
        EC.presence_of_element_located((By.ID, 'usernameField'))
    )
    username.send_keys(EMAIL)
    driver.find_element(By.ID, 'passwordField').send_keys(PASSWORD)
    driver.find_element(By.ID, 'passwordField').send_keys(Keys.ENTER)
    wait.until(lambda current: 'login' not in current.current_url.lower())


def authenticate(driver, wait):
    if not COOKIES:
        login(driver, wait)
        return

    driver.get('https://www.naukri.com')
    time.sleep(2)
    cookies = json.loads(base64.b64decode(COOKIES))
    for cookie in cookies:
        cookie.pop('expiry', None)
        try:
            driver.add_cookie(cookie)
        except Exception:
            continue
    driver.get(RECOMMENDED_JOBS_URL)
    time.sleep(4)
    if 'login' in driver.current_url.lower():
        raise RuntimeError('NAUKRI_COOKIES is expired or invalid')


if not COOKIES and (not EMAIL or not PASSWORD):
    raise SystemExit('Set Naukri credentials or NAUKRI_COOKIES before running.')

options = webdriver.ChromeOptions()
if HEADLESS:
    options.add_argument('--headless=new')
options.add_argument('--window-size=1440,1000')
driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 25)
job_links = []
passed = []
failed = []

try:
    print('[INFO] Authenticating with Naukri...')
    authenticate(driver, wait)

    driver.get(RECOMMENDED_JOBS_URL)
    time.sleep(5)
    previous_count = 0
    for scroll_number in range(MAX_SCROLLS):
        for link in collect_job_links(driver):
            if link not in job_links:
                job_links.append(link)
        print(f'[INFO] Scroll {scroll_number + 1}: {len(job_links)} jobs collected')
        if len(job_links) == previous_count:
            break
        previous_count = len(job_links)
        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(3)

    print(f'[INFO] Showing interest in up to {MAX_INTEREST} Recommended Jobs cards')
    clicked = click_interest_buttons(driver, MAX_INTEREST)
    for index in range(clicked):
        passed.append(f'{RECOMMENDED_JOBS_URL}#interest-{index + 1}')
    if clicked >= MAX_INTEREST:
        print(f'[INFO] MAX_INTEREST reached: {MAX_INTEREST}')
    print(f'[OK] Show Interest controls clicked: {clicked}')
    if clicked == 0:
        print('[WARN] No Show Interest controls found on the Recommended Jobs page')

finally:
    driver.quit()

with open(RESULTS_FILE, 'w', newline='', encoding='utf-8') as csv_file:
    writer = csv.writer(csv_file)
    writer.writerow(['interested', 'skipped'])
    for index in range(max(len(passed), len(failed))):
        writer.writerow([
            passed[index] if index < len(passed) else '',
            failed[index] if index < len(failed) else '',
        ])

print(f'[DONE] Interested: {len(passed)} | Skipped: {len(failed)}')
print(f'[INFO] Results saved to {RESULTS_FILE}')