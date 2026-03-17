import time
import unittest
from selenium.webdriver.common.by import By
from selenium_base import BaseSeleniumTest

class TestLogin(BaseSeleniumTest):
    def test_login_validation(self):
        """Test 2: Login Form Email Validation."""
        print("  -> Testing Login Page")
        self.driver.get(f"{self.base_url}/login")
        time.sleep(1)
        
        # Type an invalid email format
        email_input = self.driver.find_element(By.ID, "email")
        self.slow_typing(email_input, "invalid_email_format")
        time.sleep(0.5)
        
        # The frontend JS shouldn't allow form submission
        submit_btn = self.driver.find_element(By.ID, "login-btn")
        self.assertFalse(submit_btn.is_enabled(), "Submit button should be disabled for invalid emails")
        time.sleep(1)

if __name__ == "__main__":
    unittest.main()
