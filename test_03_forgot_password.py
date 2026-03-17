import time
import unittest
from selenium.webdriver.common.by import By
from selenium_base import BaseSeleniumTest

class TestForgotPassword(BaseSeleniumTest):
    def test_forgot_password_page(self):
        """Test 3: Forgot Password UI Elements."""
        print("  -> Testing Forgot Password Page")
        self.driver.get(f"{self.base_url}/forgot-password")
        time.sleep(1)
        
        # Find email input and enter data
        email_input = self.driver.find_element(By.NAME, "email")
        self.slow_typing(email_input, "admin@netra.com")
        time.sleep(0.5)
        
        submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.assertTrue(submit_btn.is_enabled(), "Forgot password submit button should be available")
        self.assertEqual(submit_btn.text.strip(), "Send OTP")
        time.sleep(1)

if __name__ == "__main__":
    unittest.main()
