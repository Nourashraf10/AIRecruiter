# test_linkedin_simple.py
"""
Simple standalone test for LinkedIn automation without database dependency.
Tests GPT-4 content generation and Playwright installation.
"""

import os
import sys

def test_openai_api():
    """Test OpenAI API connection"""
    print("=" * 80)
    print("TEST 1: OpenAI API Connection")
    print("=" * 80)
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("❌ OPENAI_API_KEY not set in environment")
        return False
    
    print(f"✅ OPENAI_API_KEY found: {api_key[:20]}...")
    
    try:
        import requests
        
        # Test API with a simple request
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": "Say 'LinkedIn automation test successful' in exactly those words."
                }
            ],
            "max_tokens": 20
        }
        
        print("🔄 Testing OpenAI API...")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            message = result['choices'][0]['message']['content']
            print(f"✅ OpenAI API working!")
            print(f"   Response: {message}")
            return True
        else:
            print(f"❌ OpenAI API error: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ OpenAI API test failed: {str(e)}")
        return False


def test_playwright_installation():
    """Test Playwright installation"""
    print("\n" + "=" * 80)
    print("TEST 2: Playwright Installation")
    print("=" * 80)
    
    try:
        from playwright.sync_api import sync_playwright
        print("✅ Playwright module imported successfully")
        
        # Try to launch browser
        print("🔄 Testing browser launch...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://example.com")
            title = page.title()
            browser.close()
            
        print(f"✅ Browser launched successfully!")
        print(f"   Test page title: {title}")
        return True
        
    except Exception as e:
        print(f"❌ Playwright test failed: {str(e)}")
        print("\n💡 Tip: Run 'playwright install chromium' to install browsers")
        return False


def test_pillow():
    """Test Pillow (PIL) installation"""
    print("\n" + "=" * 80)
    print("TEST 3: Pillow (Image Processing)")
    print("=" * 80)
    
    try:
        from PIL import Image
        import io
        
        # Create a test image
        img = Image.new('RGB', (100, 100), color='red')
        
        # Save to bytes
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        
        print(f"✅ Pillow working!")
        print(f"   Created test image: 100x100 pixels")
        return True
        
    except Exception as e:
        print(f"❌ Pillow test failed: {str(e)}")
        return False


def test_job_post_generation():
    """Test job post content generation"""
    print("\n" + "=" * 80)
    print("TEST 4: LinkedIn Job Post Generation")
    print("=" * 80)
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("⚠️  Skipping (no API key)")
        return None
    
    try:
        import requests
        
        # Simulate vacancy data
        vacancy_data = {
            'title': 'Senior Python Developer',
            'department': 'Engineering',
            'keywords': 'Python, Django, PostgreSQL, REST API, Docker, AWS',
            'manager': 'John Smith'
        }
        
        prompt = f"""
You are an expert HR professional creating a compelling LinkedIn job posting.

Generate a professional, engaging LinkedIn job post for:
- Job Title: {vacancy_data['title']}
- Department: {vacancy_data['department']}
- Required Skills: {vacancy_data['keywords']}

Create a post with:
1. Opening hook (1-2 sentences)
2. About the role (2-3 sentences)
3. Key responsibilities (4-6 bullet points)
4. Required qualifications (4-6 bullet points)
5. Call to action (1-2 sentences)

Keep under 3000 characters. Use professional but engaging tone.
"""
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert HR professional who creates compelling LinkedIn job postings."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.7
        }
        
        print(f"🔄 Generating job post for: {vacancy_data['title']}")
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            job_post = result['choices'][0]['message']['content'].strip()
            
            print(f"✅ Job post generated successfully!")
            print(f"   Character count: {len(job_post)}")
            print(f"   Within LinkedIn limit (3000): {'✅ Yes' if len(job_post) <= 3000 else '❌ No'}")
            print("\n" + "-" * 80)
            print("GENERATED JOB POST:")
            print("-" * 80)
            print(job_post)
            print("-" * 80)
            return True
        else:
            print(f"❌ Job post generation failed: {response.status_code}")
            print(f"   {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Job post generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 80)
    print("LINKEDIN AUTOMATION - STANDALONE TEST SUITE")
    print("=" * 80)
    print()
    
    results = {}
    
    # Run tests
    results['openai'] = test_openai_api()
    results['playwright'] = test_playwright_installation()
    results['pillow'] = test_pillow()
    results['job_post'] = test_job_post_generation()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    for test_name, result in results.items():
        if result is None:
            status = "⚠️  SKIPPED"
        elif result:
            status = "✅ PASSED"
        else:
            status = "❌ FAILED"
        print(f"{test_name.upper()}: {status}")
    
    print("=" * 80)
    
    # Filter out None values
    actual_results = {k: v for k, v in results.items() if v is not None}
    
    if actual_results and all(actual_results.values()):
        print("\n🎉 All tests passed! LinkedIn automation is ready.")
        print("\nNext steps:")
        print("1. Configure LinkedIn credentials in .env file")
        print("2. Set LINKEDIN_POSTING_ENABLED=True when ready")
        print("3. Test with real vacancy approval")
        return 0
    elif not actual_results:
        print("\n⚠️  No tests could run. Check your configuration.")
        return 1
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
