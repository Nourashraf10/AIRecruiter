# check_vacancy_status.py
"""
Quick script to check the status of the most recent vacancy
and see if LinkedIn posting was attempted.
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')

try:
    django.setup()
    
    from vacancies.models import Vacancy
    from django.conf import settings
    
    print("=" * 80)
    print("VACANCY STATUS CHECK")
    print("=" * 80)
    
    # Check LinkedIn automation settings
    print("\n📋 LinkedIn Automation Configuration:")
    print(f"   LINKEDIN_POSTING_ENABLED: {getattr(settings, 'LINKEDIN_POSTING_ENABLED', False)}")
    print(f"   LINKEDIN_EMAIL: {getattr(settings, 'LINKEDIN_EMAIL', 'Not set')[:20]}...")
    print(f"   LINKEDIN_HEADLESS: {getattr(settings, 'LINKEDIN_HEADLESS', True)}")
    print(f"   OPENAI_API_KEY: {'Set' if getattr(settings, 'OPENAI_API_KEY', None) else 'Not set'}")
    
    # Get recent vacancies
    print("\n📊 Recent Vacancies:")
    print("-" * 80)
    
    vacancies = Vacancy.objects.all().order_by('-created_at')[:5]
    
    if not vacancies:
        print("❌ No vacancies found in database")
    else:
        for i, v in enumerate(vacancies, 1):
            print(f"\n{i}. {v.title}")
            print(f"   Status: {v.status}")
            print(f"   Created: {v.created_at}")
            print(f"   LinkedIn URL: {v.linkedin_url or 'Not posted'}")
            print(f"   LinkedIn Posted At: {v.linkedin_posted_at or 'N/A'}")
            
            if v.status == 'approved' and not v.linkedin_url:
                print("   ⚠️  Status is 'approved' but no LinkedIn URL - posting may have failed")
            elif v.status == 'collecting_applications' and v.linkedin_url:
                print(f"   ✅ Successfully posted to LinkedIn!")
    
    print("\n" + "=" * 80)
    print("DIAGNOSIS:")
    print("=" * 80)
    
    latest = vacancies.first() if vacancies else None
    
    if not latest:
        print("❌ No vacancies to check")
    elif not getattr(settings, 'LINKEDIN_POSTING_ENABLED', False):
        print("ℹ️  LinkedIn posting is DISABLED in settings")
        print("   Set LINKEDIN_POSTING_ENABLED=True in .env to enable")
    elif not getattr(settings, 'LINKEDIN_EMAIL', ''):
        print("❌ LinkedIn credentials not configured")
        print("   Add LINKEDIN_EMAIL and LINKEDIN_PASSWORD to .env")
    elif not getattr(settings, 'OPENAI_API_KEY', None):
        print("❌ OpenAI API key not configured")
        print("   Add OPENAI_API_KEY to .env")
    elif latest.status == 'approved' and not latest.linkedin_url:
        print("⚠️  Vacancy approved but LinkedIn posting failed or didn't run")
        print("\nPossible reasons:")
        print("   1. LinkedIn posting is disabled (LINKEDIN_POSTING_ENABLED=False)")
        print("   2. Missing credentials (check .env file)")
        print("   3. Error during automation (check Django logs)")
        print("   4. Browser automation failed (check screenshots/ directory)")
    elif latest.linkedin_url:
        print(f"✅ LinkedIn posting successful!")
        print(f"   URL: {latest.linkedin_url}")
    else:
        print(f"ℹ️  Vacancy status: {latest.status}")
        print("   Waiting for approval to trigger LinkedIn posting")
    
    print("=" * 80)
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()
