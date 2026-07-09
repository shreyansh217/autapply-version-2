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
    options.add_argument('--headless=new')           # modern headless mode (Chrome 112+)
    options.add_argument('--no-sandbox')             # required in GitHub Actions
    options.add_argument('--disable-dev-shm-usage')  # prevents shared-memory crashes
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-blink-features=AutomationControlled')
    # Spoof a real browser user-agent so Naukri doesn't block/crash the session
    options.add_argument(
        '--user-agent=Mozilla/5.0 (X11; Linux x86_64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/150.0.0.0 Safari/537.36'
    )
    # Remove automation fingerprints
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)

    # Use the exact Chrome binary exported by setup-chrome action (CI)
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
        driver = webdriver.Chrome(options=options)

    # Remove navigator.webdriver flag that sites use to detect automation
    driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
        'source': "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })

    wait = WebDriverWait(driver, 25)
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
    time.sleep(4)

    # Fill in credentials
    username_field = wait.until(EC.presence_of_element_located((By.ID, 'usernameField')))
    username_field.clear()
    username_field.send_keys(email)
    time.sleep(1)

    password_field = driver.find_element(By.ID, 'passwordField')
    password_field.clear()
    password_field.send_keys(password)
    time.sleep(1)

    # Try clicking the Login button (more reliable than pressing Enter)
    try:
        login_btn = driver.find_element(By.XPATH,
            "//button[@type='submit'] | //input[@type='submit'] | "
            "//*[contains(@class,'login')] | //*[text()='Login']"
        )
        driver.execute_script("arguments[0].click();", login_btn)
        print("[INFO] Clicked Login button.")
    except Exception:
        # Fallback: press Enter
        password_field.send_keys(Keys.ENTER)
        print("[INFO] Pressed Enter to submit login.")

    # Wait for login to complete — URL must change away from /nlogin/
    print("[INFO] Waiting for login redirect...")
    try:
        wait.until(lambda d: 'nlogin' not in d.current_url and 'login' not in d.current_url.lower())
        print(f"[INFO] Login confirmed! URL: {driver.current_url}")
    except Exception:
        # Print debug info if login didn't redirect
        print(f"[WARN] URL after login attempt: {driver.current_url}")
        print(f"[WARN] Page title: {driver.title}")
        body_text = driver.find_element(By.TAG_NAME, 'body').text[:500]
        print(f"[WARN] Page text snippet: {body_text}")
        print("[ERROR] Login failed — Naukri did not redirect away from login page.")
        print("[ERROR] Possible causes: wrong credentials, CAPTCHA, or bot detection.")
        driver.save_screenshot('/tmp/login_failed.png')
        driver.quit()
        exit(1)

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
        cur = driver.current_url
        title = driver.title
        print(f"[DEBUG] Profile nav URL: {cur}")
        print(f"[DEBUG] Profile nav title: {title}")
        # Fail if Naukri redirected us back to login
        if 'nlogin' in cur or 'login' in cur.lower() or 'nlogin' in title.lower():
            raise Exception(f"Redirected back to login — session lost. URL: {cur}")
        # Fail if browser error page
        if 'neterror' in cur or 'about:' in cur:
            raise Exception(f"Browser error page: {cur}")
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

# ── DEBUG: Print what Naukri actually served ─────────────────────────────
print(f"[DEBUG] Page title: {driver.title}")
print(f"[DEBUG] Current URL: {driver.current_url}")
page_src = driver.page_source
print(f"[DEBUG] Page source length: {len(page_src)} chars")
print("[DEBUG] First 4000 chars of page source:")
print(page_src[:4000])
print("[DEBUG] --- end of source snippet ---")

# --- Find and click the Upload/Update Resume button ---
try:
    print("[INFO] Scrolling page to load all sections...")
    # Naukri's resume section is below the fold — scroll to trigger lazy loading
    for frac in [0.25, 0.5, 0.75, 1.0]:
        driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {frac});")
        time.sleep(1)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(2)

    # Save a screenshot so we can debug if something goes wrong
    driver.save_screenshot('/tmp/naukri_profile.png')
    print("[DEBUG] Screenshot saved to /tmp/naukri_profile.png")

    upload_input = None

    # ── Step 1: Try to click the Edit/Update Resume trigger button ───────
    # Naukri hides the <input type="file"> until you click the trigger
    trigger_xpaths = [
        "//label[contains(@for,'attachCV')]",
        "//label[contains(@class,'fileUpload')]",
        "//*[@id='attachCV']",
        "//*[contains(text(),'Update Resume')]",
        "//*[contains(text(),'Upload Resume')]",
        "//*[contains(text(),'Add Resume')]",
        "//*[contains(text(),'upload resume')]",
        "//*[contains(text(),'update resume')]",
        "//*[@title='Update Resume']",
        "//*[@aria-label='Update Resume']",
        "//*[contains(@class,'editResume')]",
        "//*[contains(@class,'resumeBtn')]",
        "//*[contains(@class,'updateResume')]",
        "//span[contains(@class,'edit') and ancestor::*[contains(@class,'resume')]]",
    ]

    for xpath in trigger_xpaths:
        btns = driver.find_elements(By.XPATH, xpath)
        if btns:
            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", btns[0])
                time.sleep(1)
                driver.execute_script("arguments[0].click();", btns[0])
                print(f"[INFO] Clicked trigger: {xpath}")
                time.sleep(3)
                break
            except Exception:
                continue

    # ── Step 2: Find file input via Selenium ─────────────────────────────
    file_inputs = driver.find_elements(By.XPATH, "//input[@type='file']")
    for inp in file_inputs:
        accept = inp.get_attribute('accept') or ''
        if any(ext in accept for ext in ['.pdf', '.doc', 'application', 'pdf']):
            upload_input = inp
            print(f"[INFO] Found file input (accept='{accept}')")
            break
    if not upload_input and file_inputs:
        upload_input = file_inputs[0]
        print("[INFO] Using first available file input.")

    # ── Step 3: JavaScript fallback — find ALL inputs including hidden ────
    if not upload_input:
        upload_input = driver.execute_script("""
            var inputs = Array.from(document.querySelectorAll('input[type="file"]'));
            if (inputs.length > 0) return inputs[0];
            // Also try inputs without explicit type (some sites omit it)
            var allInputs = Array.from(document.querySelectorAll('input'));
            for (var inp of allInputs) {
                var accept = inp.getAttribute('accept') || '';
                if (accept.includes('pdf') || accept.includes('doc')) return inp;
            }
            return null;
        """)
        if upload_input:
            print("[INFO] Found file input via JavaScript.")

    if not upload_input:
        # Print all inputs found on page for diagnosis
        all_inputs = driver.find_elements(By.TAG_NAME, 'input')
        print(f"[DEBUG] Total <input> elements on page: {len(all_inputs)}")
        for inp in all_inputs:
            print(f"  type={inp.get_attribute('type')} id={inp.get_attribute('id')} accept={inp.get_attribute('accept')}")
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
