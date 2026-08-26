# Naukri-automatic-job-apply-bot
Automation that applies to jobs on Naukri.com easily for fatster job hunting and it uses Selenium package for browser automation.

## Steps to run the Mozilla file

- Open/Download Mozilla browser
- Open a new tab and type about:profiles
- Create a new profile and launch the new profile
- Login into Naukri.com into the new profile.
- goto about:profiles and Copy the path of the Root Directory
- Open Naukri-auto-apply-bot python file and paste the path in profiles variable
- Add your Firstname, Lastname, keywords(Job roles) and location(optional)
- Run the Naukri-autoapply bot by python Naukri-Mozilla.py
- Please note this script was built in selenium version 3

## Steps to run the Edge file
- Download Edge driver and include its filepath in the naukri-Edge file
- Add your Firstname, Lastname, keywords(Job roles) and location(optional)
- Run the Naukri-autoapply bot by python Naukri-Edge.py
- Please note this script was built in selenium version 4

## Run Show Interest every day on GitHub Actions

- Add repository secrets named `NAUKRI_EMAIL` and `NAUKRI_PASSWORD`.
- For GitHub-hosted runners, also create `NAUKRI_COOKIES` using `python export_cookies.py` locally. This avoids login OTP challenges.
- The workflow runs `Naukri-Show-Interest.py` once daily at 10:00 AM India Standard Time.
- You can also run it manually from GitHub Actions using **Run workflow**.

