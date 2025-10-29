#!/usr/bin/env python3
"""
Simple test to verify the automation system works
"""

import requests
import json

def test_server():
    """Test if the server is running"""
    try:
        response = requests.get('http://localhost:8040/admin/', timeout=5)
        print(f"✅ Server is running! Status: {response.status_code}")
        return True
    except Exception as e:
        print(f"❌ Server not accessible: {e}")
        return False

def test_vacancy_status_change():
    """Test changing a vacancy status to trigger automation"""
    print("🧪 Testing vacancy status change automation...")
    print("📝 To test manually:")
    print("1. Go to http://localhost:8040/admin/")
    print("2. Login to Django admin")
    print("3. Go to Vacancies → Vacancies")
    print("4. Find a vacancy with status 'collecting_applications'")
    print("5. Change status to 'closed' and save")
    print("6. Check the logs for automation messages")
    print("")
    print("🔍 Look for these log messages:")
    print("🚀 Vacancy X status changed to 'closed', triggering interview scheduling")
    print("✅ Interview scheduling completed for vacancy X")
    print("📧 Interview notifications sent for X interviews")

if __name__ == '__main__':
    print("🧪 Testing Automated Interview Scheduling System")
    print("=" * 60)
    
    if test_server():
        test_vacancy_status_change()
        print("=" * 60)
        print("✅ System is ready for testing!")
        print("🌐 Admin URL: http://localhost:8040/admin/")
    else:
        print("❌ Server is not running. Please start it first.")

