# ai/test_linkedin_poster.py
"""
Test script for LinkedIn job posting automation.
Run this to test the LinkedIn poster without approving a real vacancy.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')
django.setup()

from vacancies.models import Vacancy
from ai.linkedin_poster import LinkedInVacancyPoster
from django.contrib.auth import get_user_model
import argparse


def test_content_generation():
    """Test GPT content generation only"""
    print("=" * 80)
    print("TEST 1: GPT Content Generation")
    print("=" * 80)
    
    # Get or create a test vacancy
    User = get_user_model()
    manager = User.objects.first()
    
    if not manager:
        print("❌ No users found in database. Please create a user first.")
        return False
    
    # Create test vacancy
    vacancy, created = Vacancy.objects.get_or_create(
        title='Senior Python Developer (TEST)',
        defaults={
            'department': 'Engineering',
            'manager': manager,
            'created_by': manager,
            'keywords': 'Python, Django, PostgreSQL, REST API, Docker, AWS',
            'status': 'approved'
        }
    )
    
    if created:
        print(f"✅ Created test vacancy: {vacancy.title}")
    else:
        print(f"ℹ️  Using existing test vacancy: {vacancy.title}")
    
    try:
        poster = LinkedInVacancyPoster(vacancy, headless=True)
        content = poster.generate_job_post_content()
        
        print("\n" + "=" * 80)
        print("GENERATED JOB POST CONTENT:")
        print("=" * 80)
        print(content)
        print("=" * 80)
        print(f"\nCharacter count: {len(content)}")
        print(f"Within LinkedIn limit (3000): {'✅ Yes' if len(content) <= 3000 else '❌ No'}")
        
        # Clean up test vacancy
        if created:
            vacancy.delete()
            print(f"\n🗑️  Deleted test vacancy")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Content generation test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if created:
            vacancy.delete()
        
        return False


def test_browser_automation(headless=False, stop_before_submit=False):
    """Test browser automation with LinkedIn"""
    print("\n" + "=" * 80)
    print("TEST 2: Browser Automation")
    print(f"Headless: {headless}, Stop before submit: {stop_before_submit}")
    print("=" * 80)
    
    # Get or create a test vacancy
    User = get_user_model()
    manager = User.objects.first()
    
    if not manager:
        print("❌ No users found in database. Please create a user first.")
        return False
    
    vacancy, created = Vacancy.objects.get_or_create(
        title='Full Stack Developer (TEST)',
        defaults={
            'department': 'Engineering',
            'created_by': manager,
            'manager': manager,
            'keywords': 'React, Node.js, TypeScript, MongoDB, GraphQL',
            'status': 'approved'
        }
    )
    
    if created:
        print(f"✅ Created test vacancy: {vacancy.title}")
    else:
        print(f"ℹ️  Using existing test vacancy: {vacancy.title}")
    
    try:
        poster = LinkedInVacancyPoster(vacancy, headless=headless)
        
        if stop_before_submit:
            print("\n⚠️  MANUAL MODE: Browser will stop before submitting")
            print("You can manually inspect the form and submit if desired")
            input("\nPress Enter to start browser automation...")
        
        result = poster.execute()
        
        print("\n" + "=" * 80)
        print("AUTOMATION RESULT:")
        print("=" * 80)
        print(f"Success: {result['success']}")
        print(f"LinkedIn URL: {result.get('url', 'N/A')}")
        print(f"Error: {result.get('error', 'None')}")
        print("=" * 80)
        
        # Clean up test vacancy
        if created and not result['success']:
            vacancy.delete()
            print(f"\n🗑️  Deleted test vacancy (posting failed)")
        elif created:
            print(f"\nℹ️  Test vacancy kept in database with LinkedIn URL")
        
        return result['success']
        
    except Exception as e:
        print(f"\n❌ Browser automation test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if created:
            vacancy.delete()
        
        return False


def test_login_only():
    """Test LinkedIn login only"""
    print("\n" + "=" * 80)
    print("TEST 3: LinkedIn Login Only")
    print("=" * 80)
    
    from ai.browser_agent import BrowserAgent
    from django.conf import settings
    
    linkedin_email = getattr(settings, 'LINKEDIN_EMAIL', '')
    linkedin_password = getattr(settings, 'LINKEDIN_PASSWORD', '')
    
    if not linkedin_email or not linkedin_password:
        print("❌ LinkedIn credentials not configured")
        print("Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in your .env file")
        return False
    
    print(f"Testing login with: {linkedin_email}")
    
    try:
        with BrowserAgent(headless=False, screenshots_dir="screenshots/login_test") as browser:
            # Navigate to LinkedIn
            browser.navigate("https://www.linkedin.com/login")
            browser.wait(2)
            
            # Fill credentials
            browser.type_text('input#username', linkedin_email)
            browser.type_text('input#password', linkedin_password)
            
            # Click sign in
            browser.click('button[type="submit"]')
            browser.wait(5)
            
            # Check result
            current_url = browser.get_current_url()
            
            if 'feed' in current_url or 'checkpoint' in current_url:
                print("✅ Login successful!")
                
                if 'checkpoint' in current_url:
                    print("⚠️  2FA challenge detected")
                    print("Please complete 2FA manually in the browser")
                    input("Press Enter after completing 2FA...")
                
                browser.take_screenshot("login_success")
                return True
            else:
                print(f"❌ Login failed - unexpected URL: {current_url}")
                browser.take_screenshot("login_failed")
                return False
                
    except Exception as e:
        print(f"❌ Login test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(description='Test LinkedIn job posting automation')
    parser.add_argument('--test', choices=['content', 'browser', 'login', 'all'], 
                       default='all', help='Which test to run')
    parser.add_argument('--headless', action='store_true', 
                       help='Run browser in headless mode')
    parser.add_argument('--stop-before-submit', action='store_true',
                       help='Stop before submitting the job post')
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("LINKEDIN JOB POSTING AUTOMATION - TEST SUITE")
    print("=" * 80)
    
    results = {}
    
    if args.test in ['content', 'all']:
        results['content'] = test_content_generation()
    
    if args.test in ['login', 'all']:
        results['login'] = test_login_only()
    
    if args.test in ['browser', 'all']:
        results['browser'] = test_browser_automation(
            headless=args.headless,
            stop_before_submit=args.stop_before_submit
        )
    
    # Print summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    for test_name, success in results.items():
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name.upper()}: {status}")
    print("=" * 80)
    
    all_passed = all(results.values())
    if all_passed:
        print("\n🎉 All tests passed!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
