import time
import os
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Load .env file for local runs; GitHub Actions uses Secrets directly
load_dotenv()

# ============================================================
# Credentials — set in .env locally or GitHub Secrets on CI
# ============================================================
email    = os.environ['NAUKRI_EMAIL']
password = os.environ['NAUKRI_PASSWORD']

# Resume path: looks for resume.pdf next to this script (repo root)
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
RESUME_PATH = os.path.join(SCRIPT_DIR, 'resume.pdf')

# Fallback to RESUME_PATH env var if the file isn't committed yet
if not os.path.isfile(RESUME_PATH):
    RESUME_PATH = os.environ.get('RESUME_PATH', '')

# Validate resume file exists before starting browser
if not os.path.isfile(RESUME_PATH):
    print(f"[ERROR] Resume file not found: {RESUME_PATH}")
    print("Please update RESUME_PATH in the script and try again.")
    exit(1)

print(f"[INFO] Resume file found: {RESUME_PATH}")

# --- Launch Chrome (Headless - no browser window) ---
try:
    options = Options()
    options.add_argument('--headless')               # runs Chrome invisibly
    options.add_argument('--no-sandbox')             # required in GitHub Actions
    options.add_argument('--disable-dev-shm-usage')  # prevents shared-memory crashes
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-blink-features=AutomationControlled')
    # NOTE: --single-process and --no-zygote removed — they crash Chrome 112+

    # Use the exact Chrome binary exported by setup-chrome action (CI)
    # Falls back to system Chrome for local runs
    chrome_bin = os.environ.get('CHROME_BIN', '')
    if chrome_bin:
        options.binary_location = chrome_bin
        print(f"[INFO] Using Chrome binary: {chrome_bin}")

    # Use the exact ChromeDriver exported by setup-chrome action (CI)
    chromedriver_bin = os.environ.get('CHROMEDRIVER_BIN', '')
    if chromedriver_bin:
        print(f"[INFO] Using ChromeDriver: {chromedriver_bin}")
        driver = webdriver.Chrome(service=Service(chromedriver_bin), options=options)
    else:
        # Local fallback: Selenium Manager auto-detects chromedriver
        driver = webdriver.Chrome(options=options)

    wait = WebDriverWait(driver, 20)
    print("[INFO] Chrome launched in headless mode (no window).")
except Exception as e:
    print(f"[ERROR] Webdriver exception: {e}")
    print("\nTROUBLESHOOT:")
    print("  1. Make sure Google Chrome is installed.")
    print("  2. On CI: CHROME_BIN / CHROMEDRIVER_BIN env vars set by setup-chrome action.")
    exit(1)

# --- Login to Naukri ---
try:
    print("[INFO] Navigating to Naukri login page...")
    driver.get('https://www.naukri.com/nlogin/login')
    time.sleep(3)

    wait.until(EC.presence_of_element_located((By.ID, 'usernameField'))).send_keys(email)
    driver.find_element(By.ID, 'passwordField').send_keys(password)
    driver.find_element(By.ID, 'passwordField').send_keys(Keys.ENTER)
    print("[INFO] Logged in! Waiting for page to load...")
    time.sleep(5)
except Exception as e:
    print(f"[ERROR] Login failed: {e}")
    driver.quit()
    exit(1)

# --- Navigate to Profile / Resume Upload page (with retry) ---
profile_loaded = False
for attempt in range(1, 4):  # retry up to 3 times
    try:
        print(f"[INFO] Navigating to profile page (attempt {attempt}/3)...")
        driver.get('https://www.naukri.com/mnjuser/profile?id=&altresid')
        time.sleep(6)
        # Check we actually landed on the profile page, not an error page
        if 'neterror' in driver.current_url or 'about:' in driver.current_url:
            raise Exception(f"Landed on error page: {driver.current_url}")
        print("[INFO] Profile page loaded successfully.")
        profile_loaded = True
        break
    except Exception as e:
        print(f"[WARN] Attempt {attempt} failed: {e}")
        time.sleep(5)

if not profile_loaded:
    print("[ERROR] Could not load profile page after 3 attempts.")
    driver.quit()
    exit(1)

# --- Find and click the Upload/Update Resume button ---
try:
    print("[INFO] Looking for resume upload button...")

    upload_input = None

    # Strategy 1: Direct file <input> element (hidden, triggered by JS)
    file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
    for inp in file_inputs:
        accept = inp.get_attribute('accept') or ''
        # Look for inputs that accept doc/pdf types
        if any(ext in accept for ext in ['.pdf', '.doc', 'application']):
            upload_input = inp
            print(f"[INFO] Found file input (accept='{accept}')")
            break

    if not upload_input:
        # Strategy 2: Any file input on the page
        if file_inputs:
            upload_input = file_inputs[0]
            print("[INFO] Found generic file input.")

    if not upload_input:
        # Strategy 3: Click the visible "Update Resume" / "Upload Resume" button first
        for xpath in [
            "//*[contains(text(),'Update Resume')]",
            "//*[contains(text(),'Upload Resume')]",
            "//*[contains(text(),'upload resume')]",
            "//*[contains(text(),'update resume')]",
            "//label[contains(@class,'fileUpload')]",
            "//label[contains(@for,'attachCV')]",
        ]:
            btns = driver.find_elements(By.XPATH, xpath)
            if btns:
                print(f"[INFO] Clicking upload trigger: {xpath}")
                driver.execute_script("arguments[0].click();", btns[0])
                time.sleep(2)
                # Now try to find the file input again
                file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
                if file_inputs:
                    upload_input = file_inputs[0]
                break

    if not upload_input:
        raise Exception("Could not find any file upload input on the profile page.")

    # Make the input visible in case it's hidden (Naukri hides them via CSS)
    driver.execute_script("arguments[0].style.display = 'block'; arguments[0].style.visibility = 'visible';", upload_input)
    time.sleep(1)

    # Send the file path directly to the input
    upload_input.send_keys(RESUME_PATH)
    print("[INFO] Resume file path sent to input. Waiting for upload...")
    time.sleep(5)

except Exception as e:
    print(f"[ERROR] Upload step failed: {e}")
    driver.quit()
    exit(1)

# --- Wait for upload confirmation ---
try:
    # Look for success indicators on the page
    success_indicators = [
        "//*[contains(text(),'Resume uploaded')]",
        "//*[contains(text(),'successfully')]",
        "//*[contains(text(),'Upload successful')]",
        "//*[contains(text(),'updated successfully')]",
    ]

    confirmed = False
    for xpath in success_indicators:
        elements = driver.find_elements(By.XPATH, xpath)
        if elements:
            print(f"[OK] Upload confirmed: '{elements[0].text.strip()}'")
            confirmed = True
            break

    if not confirmed:
        # Also check if resume filename now appears on the page
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        resume_name = os.path.basename(RESUME_PATH).replace('%20', ' ')
        if resume_name.lower() in page_text.lower() or 'Shreyansh' in page_text:
            print("[OK] Resume appears to have been uploaded (filename detected on page).")
            confirmed = True

    if not confirmed:
        print("[WARN] Could not confirm upload via text. Check the browser window manually.")
        print("[INFO] Keeping browser open for 15 seconds so you can verify...")
        time.sleep(15)
    else:
        time.sleep(3)

except Exception as e:
    print(f"[WARN] Could not verify upload confirmation: {e}")
    time.sleep(10)

# --- Done ---
print("\n" + "="*50)
print("Resume upload script COMPLETED.")
print("="*50)

try:
    driver.quit()
except:
    pass
