import requests

def check_headers(url):
    print(f"Checking headers for {url}...")
    try:
        # Note: This requires the server to be running.
        # Since I cannot start a long-running server here, this is for the user or a local test environment.
        response = requests.get(url, allow_redirects=False)
        print(f"Status Code: {response.status_code}")
        print("Headers:")
        for header, value in response.headers.items():
            if header.lower() in ["cache-control", "pragma", "expires"]:
                print(f"  {header}: {value}")
        
        expected = {
            "cache-control": "no-store, no-cache, must-revalidate, max-age=0",
            "pragma": "no-cache",
            "expires": "0"
        }
        
        for k, v in expected.items():
            if response.headers.get(k, "").lower() != v.lower():
                print(f"FAILED: Expected {k} to be {v}, got {response.headers.get(k)}")
            else:
                print(f"SUCCESS: {k} is correct.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Assuming local server on port 5000
    # The check will fail if the server isn't running, but the user can use this script.
    # We test the dashboard routes (which should redirect to login if not authenticated, 
    # but the headers should still be present or the redirect itself should not be cached)
    check_headers("http://127.0.0.1:5000/dashboard_officer")
    check_headers("http://127.0.0.1:5000/dashboard_admin")
