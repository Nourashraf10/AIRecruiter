#!/usr/bin/env python
"""Wait for web service to be ready"""
import requests
import time
import sys

def wait_for_web(url="http://web:8000/admin/", max_attempts=30, delay=2):
    """Wait for web service to be accessible"""
    print(f"Waiting for web service at {url}...")
    
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, timeout=2)
            if response.status_code in [200, 302, 404]:
                print("✅ Web service is ready!")
                return True
        except requests.exceptions.ConnectionError:
            pass
        except Exception as e:
            print(f"⚠️ Error: {e}")
        
        if attempt < max_attempts - 1:
            print(f"⏳ Attempt {attempt + 1}/{max_attempts} - waiting {delay}s...")
            time.sleep(delay)
    
    print("⚠️ Web service not ready after all attempts, continuing anyway...")
    return False

if __name__ == "__main__":
    wait_for_web()
    sys.exit(0)



