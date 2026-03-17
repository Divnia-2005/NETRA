import unittest
import HtmlTestRunner
import os

if __name__ == "__main__":
    # Ensure reports directory exists
    os.makedirs("test_reports", exist_ok=True)
    
    # Discover all tests starting with 'test_' in the current directory
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir='.', pattern='test_0*.py')
    
    # Run the tests with HTML Test Runner
    runner = HtmlTestRunner.HTMLTestRunner(
        output="test_reports", 
        report_title="NETRA Automated Testing Report", 
        failfast=False,
        combine_reports=True # Puts all separated test files into one clean HTML file
    )
    runner.run(suite)
