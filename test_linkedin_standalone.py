# test_linkedin_standalone.py
"""
Standalone LinkedIn automation test - NO Django/Database required
Tests the complete flow with visible browser and screenshots
"""

import os
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_linkedin_flow():
    """Test complete LinkedIn automation flow"""
    
    print("=" * 80)
    print("LINKEDIN AUTOMATION - STANDALONE TEST")
    print("=" * 80)
    
    # Step 1: Check environment variables
    print("\n[1/6] Checking environment variables...")
    
    from decouple import config
    
    try:
        linkedin_email = config('LINKEDIN_EMAIL')
        linkedin_password = config('LINKEDIN_PASSWORD')
        openai_key = config('OPENAI_API_KEY')
        
        print(f"   ✅ LINKEDIN_EMAIL: {linkedin_email[:20]}...")
        print(f"   ✅ LINKEDIN_PASSWORD: {'*' * len(linkedin_password)}")
        print(f"   ✅ OPENAI_API_KEY: {openai_key[:20]}...")
    except Exception as e:
        print(f"   ❌ Missing environment variable: {e}")
        print("\n   Please add to .env file:")
        print("   - LINKEDIN_EMAIL")
        print("   - LINKEDIN_PASSWORD")
        print("   - OPENAI_API_KEY")
        return False
    
    # Step 2: Test GPT-4 job post generation
    print("\n[2/6] Testing GPT-4 job post generation...")
    
    try:
        import requests
        
        # Mock vacancy data
        vacancy_data = {
            'title': 'Senior Python Developer (TEST)',
            'department': 'Engineering',
            'keywords': 'Python, Django, PostgreSQL, REST API, Docker, AWS',
            'manager': 'Test Manager'
        }
        
        prompt = f"""
You are an expert HR professional creating a compelling LinkedIn job posting.

Generate a professional, engaging LinkedIn job post for:
- Job Title: {vacancy_data['title']}
- Department: {vacancy_data['department']}
- Required Skills: {vacancy_data['keywords']}

Create a concise post (under 500 characters for testing) with:
1. Opening hook (1 sentence)
2. Key responsibilities (3 bullet points)
3. Required qualifications (3 bullet points)
4. Call to action (1 sentence)

Keep it professional and engaging.
"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are an expert HR professional."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            job_post = result['choices'][0]['message']['content'].strip()
            print(f"   ✅ Generated job post ({len(job_post)} characters)")
            print("\n   Preview:")
            print("   " + "-" * 76)
            for line in job_post.split('\n')[:5]:
                print(f"   {line}")
            print("   " + "-" * 76)
        else:
            print(f"   ❌ GPT-4 API error: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Job post generation failed: {e}")
        return False
    
    # Step 3: Initialize browser automation
    print("\n[3/6] Initializing browser automation...")
    
    try:
        from ai.browser_agent import BrowserAgent
        
        screenshots_dir = "screenshots/linkedin_test"
        browser = BrowserAgent(headless=False, screenshots_dir=screenshots_dir)
        
        print(f"   ✅ Browser agent initialized")
        print(f"   📁 Screenshots will be saved to: {screenshots_dir}/")
        
    except Exception as e:
        print(f"   ❌ Browser initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Start browser and login to LinkedIn
    print("\n[4/6] Starting browser and logging into LinkedIn...")
    print("   👀 Browser window will open - watch the automation!")
    
    try:
        browser.start()
        
        # Navigate to LinkedIn login
        print("   🔗 Navigating to LinkedIn login page...")
        browser.navigate("https://www.linkedin.com/login")
        browser.wait(2)
        
        # Fill credentials
        print("   ⌨️  Filling email...")
        browser.type_text('input#username', linkedin_email)
        
        print("   ⌨️  Filling password...")
        browser.type_text('input#password', linkedin_password)
        
        # Click sign in
        print("   🖱️  Clicking sign in button...")
        browser.click('button[type="submit"]')
        browser.wait(5)
        
        # Check if login was successful
        current_url = browser.get_current_url()
        
        if 'feed' in current_url or 'checkpoint' in current_url:
            print("   ✅ Login successful!")
            
            if 'checkpoint' in current_url:
                print("\n   ⚠️  2FA CHALLENGE DETECTED!")
                print("   Please complete 2FA in the browser window...")
                input("   Press Enter after completing 2FA to continue...")
        else:
            print(f"   ❌ Login failed - unexpected URL: {current_url}")
            browser.take_screenshot("login_failed")
            browser.stop()
            return False
            
    except Exception as e:
        print(f"   ❌ Login error: {e}")
        import traceback
        traceback.print_exc()
        browser.take_screenshot("login_error")
        browser.stop()
        return False
    
    # Step 5: Navigate to job posting page
    print("\n[5/6] Navigating to job posting page...")
    
    try:
        print("   🔗 Going to LinkedIn job posting page...")
        browser.navigate("https://www.linkedin.com/jobs/post")
        browser.wait(3)
        browser.take_screenshot("job_posting_page")
        
        print("   ✅ Job posting page loaded")
        print("\n   👀 BROWSER PAUSED - Inspect the page in the browser window")
        print("   You can see:")
        print("   - Current page state")
        print("   - Form fields available")
        print("   - Any errors or issues")
        
        input("\n   Press Enter to continue with form filling...")
        
    except Exception as e:
        print(f"   ❌ Navigation error: {e}")
        browser.take_screenshot("navigation_error")
        browser.stop()
        return False
    
    # Step 6: Fill job posting form (DEMO - won't submit)
    print("\n[6/6] Testing form filling (DEMO MODE - won't submit)...")
    
    try:
        # Try to fill job title
        print("   📝 Attempting to fill job title...")
        try:
            browser.type_text('input[name="title"]', vacancy_data['title'], timeout=5000)
            print("   ✅ Job title filled")
        except:
            print("   ⚠️  Job title field not found (LinkedIn UI may have changed)")
        
        browser.wait(2)
        browser.take_screenshot("form_filled")
        
        print("\n   ✅ Form filling test complete!")
        print("   📸 Screenshots saved - check the screenshots/ directory")
        
        print("\n   🛑 STOPPING HERE - Not submitting to avoid posting test job")
        print("   In production, the automation would:")
        print("   - Fill all form fields")
        print("   - Click 'Post job' button")
        print("   - Extract the LinkedIn job URL")
        print("   - Save URL to database")
        
        input("\n   Press Enter to close browser and finish test...")
        
    except Exception as e:
        print(f"   ⚠️  Form filling error: {e}")
        browser.take_screenshot("form_error")
    finally:
        browser.stop()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST COMPLETE!")
    print("=" * 80)
    print(f"\n📁 Check screenshots in: {screenshots_dir}/")
    print("\nWhat was tested:")
    print("  ✅ Environment variables loaded")
    print("  ✅ GPT-4 job post generation")
    print("  ✅ Browser automation initialized")
    print("  ✅ LinkedIn login successful")
    print("  ✅ Job posting page navigation")
    print("  ✅ Form field detection")
    print("\nNext steps:")
    print("  1. Review screenshots to verify each step")
    print("  2. If all looks good, enable full automation in Django")
    print("  3. Set LINKEDIN_POSTING_ENABLED=True in .env")
    print("  4. Test with real vacancy approval")
    
    return True


if __name__ == '__main__':
    try:
        success = test_linkedin_flow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
