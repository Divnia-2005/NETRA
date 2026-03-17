import time
import unittest
from selenium.webdriver.common.by import By
from selenium_base import BaseSeleniumTest

class TestPublicEntry(BaseSeleniumTest):
    def test_public_entry_form(self):
        """Test 4: Public Entry Page Interactivity."""
        print("  -> Testing Public Entry Page")
        self.driver.get(f"{self.base_url}/public-entry")
        time.sleep(1)
        
        # Click the 'volunteer' role button instead of default attendee
        volunteer_btn = self.driver.find_element(By.ID, "btn-volunteer")
        volunteer_btn.click()
        time.sleep(0.5)
        
        # Assert class got appended signifying role was selected successfully
        self.assertIn("tab-active", volunteer_btn.get_attribute("class"))
        
        # Enter Name and Phone Number
        name_input = self.driver.find_element(By.ID, "user-name")
        self.slow_typing(name_input, "John Doe")
        time.sleep(0.5)
        
        phone_input = self.driver.find_element(By.ID, "user-phone")
        self.slow_typing(phone_input, "9876543210")
        time.sleep(0.5)
        
        otp_btn = self.driver.find_element(By.ID, "send-otp-btn")
        self.assertTrue(otp_btn.is_enabled())
        time.sleep(1)

if __name__ == "__main__":
    unittest.main()
