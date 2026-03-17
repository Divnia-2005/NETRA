import time
import subprocess
import unittest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class BaseSeleniumTest(unittest.TestCase):
    flask_process = None

    @classmethod
    def setUpClass(cls):
        print("\n[INFO] Starting local Flask server for testing...")
        cls.flask_process = subprocess.Popen(
            ["python", "app.py"], 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        time.sleep(3)  # Give Flask a few seconds to fully boot up

        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--log-level=3")
        
        service = Service(ChromeDriverManager().install())
        cls.driver = webdriver.Chrome(service=service, options=chrome_options)
        cls.base_url = "http://localhost:5000"

    @classmethod
    def tearDownClass(cls):
        print("\n[INFO] Closing browser and shutting down test server...")
        cls.driver.quit()
        if cls.flask_process:
            cls.flask_process.terminate()
            cls.flask_process.wait()
            print("[INFO] Flask server shut down successfully.")

    def slow_typing(self, element, text):
        """Helper to type slowly so you can watch what it is doing"""
        for char in text:
            element.send_keys(char)
            time.sleep(0.05)
