from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# --- CONFIGURATION ---
BASE_URL = "http://localhost:5000"
EMAIL = "aleenashibu2028@mca.ajce.in"
PASSWORD = "Aleena@2005"

def run_test():
    # Initialize WebDriver (Chrome)
    # Ensure you have 'chromedriver' in your PATH or use webdriver-manager
    driver = webdriver.Chrome()
    driver.maximize_window()
    
    try:
        # 1. Go to Home Page
        print(f"Navigating to Home: {BASE_URL}")
        driver.get(BASE_URL)
        
        # Wait for preloader to finish (based on landing.html timeout)
        time.sleep(2) 
        
        # 2. Go to Login Page
        # We find the 'Login' link in the navbar or hero section
        print("Clicking Login link...")
        wait = WebDriverWait(driver, 10)
        login_link = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Login")))
        login_link.click()
        
        # 3. Enter Credentials
        print("Entering credentials...")
        email_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
        password_field = driver.find_element(By.ID, "password")
        login_btn = driver.find_element(By.ID, "login-btn")
        
        email_field.send_keys(EMAIL)
        password_field.send_keys(PASSWORD)
        
        # 4. Click Login Button
        print("Submitting login form...")
        login_btn.click()
        
        # 5. Verify Redirection
        # Wait for the URL to change to a dashboard page
        wait.until(EC.url_contains("dashboard"))
        
        current_url = driver.current_url
        print(f"Success! Redirected to: {current_url}")
        
        if "dashboard_admin" in current_url:
            print("Validated: Logged in as ADMIN.")
        elif "dashboard_officer" in current_url:
            print("Validated: Logged in as OFFICER.")
        else:
            print("Validated: Dashboard reached, but unknown role.")

    except Exception as e:
        print(f"Test Failed: {e}")
        # Take a screenshot on failure
        driver.save_screenshot("login_failure.png")
        print("Screenshot saved as 'login_failure.png'")
        
    finally:
        print("Closing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    run_test()
