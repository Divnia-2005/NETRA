import time
import unittest
from selenium.webdriver.common.by import By
from selenium_base import BaseSeleniumTest

class TestRegistration(BaseSeleniumTest):
    def test_registration_validation(self):
        """Test 1: Registration Form JS Validation."""
        print("  -> Testing Registration Page")
        self.driver.get(f"{self.base_url}/register")
        time.sleep(1) # Pause for visual confirmation
        
        # Fill in form 
        name_input = self.driver.find_element(By.ID, "name")
        self.slow_typing(name_input, "Automated Tester")
        time.sleep(0.5)
        
        email_input = self.driver.find_element(By.ID, "email")
        self.slow_typing(email_input, "selenium@test.com")
        time.sleep(0.5)
        
        # Test weak password -> shouldn't allow submission
        pw_input = self.driver.find_element(By.ID, "password")
        self.slow_typing(pw_input, "weak")
        time.sleep(0.5)
        
        # The frontend JS checks requirements and disables btn if weak
        submit_btn = self.driver.find_element(By.ID, "register-btn")
        self.assertFalse(submit_btn.is_enabled(), "Submit button should be disabled for weak passwords")
        time.sleep(1) # Pause for visual confirmation

if __name__ == "__main__":
    unittest.main()
