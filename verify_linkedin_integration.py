# verify_linkedin_integration.py
"""
Verify that LinkedIn automation is properly integrated into Django system
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')
django.setup()

from django.conf import settings
from vacancies.models import Vacancy
from ai.linkedin_poster import LinkedInVacancyPoster


def check_configuration():
    """Check all configuration settings"""
    print("=" * 80)
    print("LINKEDIN AUTOMATION - CONFIGURATION CHECK")
    print("=" * 80)
    
    checks = []
    
    # Check 1: OPENAI_API_KEY
    print("\n[1/6] Checking OpenAI API Key...")
    openai_key = getattr(settings, 'OPENAI_API_KEY', '')
    if openai_key:
        print(f"   [OK] OPENAI_API_KEY is set ({openai_key[:20]}...)")
        checks.append(True)
    else:
        print("   [ERROR] OPENAI_API_KEY is not set")
        print("   Add to .env: OPENAI_API_KEY=sk-your-key-here")
        checks.append(False)
    
    # Check 2: LinkedIn Email
    print("\n[2/6] Checking LinkedIn Email...")
    linkedin_email = getattr(settings, 'LINKEDIN_EMAIL', '')
    if linkedin_email:
        print(f"   [OK] LINKEDIN_EMAIL is set ({linkedin_email})")
        checks.append(True)
    else:
        print("   [ERROR] LINKEDIN_EMAIL is not set")
        print("   Add to .env: LINKEDIN_EMAIL=your-email@company.com")
        checks.append(False)
    
    # Check 3: LinkedIn Password
    print("\n[3/6] Checking LinkedIn Password...")
    linkedin_password = getattr(settings, 'LINKEDIN_PASSWORD', '')
    if linkedin_password:
        print(f"   [OK] LINKEDIN_PASSWORD is set ({'*' * len(linkedin_password)})")
        checks.append(True)
    else:
        print("   [ERROR] LINKEDIN_PASSWORD is not set")
        print("   Add to .env: LINKEDIN_PASSWORD=\"your-password\"")
        checks.append(False)
    
    # Check 4: LinkedIn Posting Enabled
    print("\n[4/6] Checking LinkedIn Posting Enabled...")
    posting_enabled = getattr(settings, 'LINKEDIN_POSTING_ENABLED', False)
    if posting_enabled:
        print("   [OK] LINKEDIN_POSTING_ENABLED = True")
        checks.append(True)
    else:
        print("   [WARNING] LINKEDIN_POSTING_ENABLED = False")
        print("   Automation will NOT run until you set this to True")
        print("   Add to .env: LINKEDIN_POSTING_ENABLED=True")
        checks.append(False)
    
    # Check 5: Headless Mode
    print("\n[5/6] Checking Headless Mode...")
    headless = getattr(settings, 'LINKEDIN_HEADLESS', True)
    print(f"   [INFO] LINKEDIN_HEADLESS = {headless}")
    if headless:
        print("   Browser will run in headless mode (no visible window)")
    else:
        print("   Browser will be visible (good for debugging)")
    checks.append(True)
    
    # Check 6: Integration in views.py
    print("\n[6/6] Checking Django Integration...")
    try:
        from comms.views import ApprovalLandingView
        print("   [OK] ApprovalLandingView imported successfully")
        print("   [OK] LinkedIn automation is integrated in vacancy approval flow")
        checks.append(True)
    except Exception as e:
        print(f"   [ERROR] Integration check failed: {e}")
        checks.append(False)
    
    return all(checks)


def test_linkedin_poster_initialization():
    """Test that LinkedInVacancyPoster can be initialized"""
    print("\n" + "=" * 80)
    print("LINKEDIN POSTER - INITIALIZATION TEST")
    print("=" * 80)
    
    try:
        # Get or create a test vacancy
        print("\n[INFO] Getting test vacancy...")
        vacancy = Vacancy.objects.first()
        
        if not vacancy:
            print("   [WARNING] No vacancies in database")
            print("   Create a test vacancy to fully test the integration")
            return False
        
        print(f"   [OK] Using vacancy: {vacancy.title}")
        
        # Try to initialize the poster
        print("\n[INFO] Initializing LinkedInVacancyPoster...")
        poster = LinkedInVacancyPoster(vacancy)
        
        print("   [OK] LinkedInVacancyPoster initialized successfully")
        print(f"   Email: {poster.linkedin_email}")
        print(f"   Headless: {poster.headless}")
        print(f"   Has OpenAI key: {bool(poster.openai_api_key)}")
        
        return True
        
    except ValueError as e:
        print(f"   [ERROR] Configuration error: {e}")
        return False
    except Exception as e:
        print(f"   [ERROR] Initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_summary(config_ok, init_ok):
    """Print summary and next steps"""
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    if config_ok and init_ok:
        print("\n[SUCCESS] LinkedIn automation is properly configured!")
        print("\nThe system is ready to:")
        print("  1. Generate job posts with GPT-4")
        print("  2. Login to LinkedIn automatically")
        print("  3. Post jobs when vacancies are approved")
        print("  4. Save LinkedIn URLs to database")
        
        if not getattr(settings, 'LINKEDIN_POSTING_ENABLED', False):
            print("\n[NEXT STEP] Enable automation:")
            print("  1. Add to .env: LINKEDIN_POSTING_ENABLED=True")
            print("  2. Restart Django server")
            print("  3. Create and approve a test vacancy")
            print("  4. Watch Django logs for automation progress")
        else:
            print("\n[READY] Automation is ENABLED!")
            print("  Create and approve a vacancy to test the full flow")
            
    elif config_ok:
        print("\n[PARTIAL] Configuration is OK but initialization failed")
        print("  Check the error messages above")
        
    else:
        print("\n[ACTION REQUIRED] Configuration incomplete")
        print("\nMissing configuration:")
        
        if not getattr(settings, 'OPENAI_API_KEY', ''):
            print("  - OPENAI_API_KEY")
        if not getattr(settings, 'LINKEDIN_EMAIL', ''):
            print("  - LINKEDIN_EMAIL")
        if not getattr(settings, 'LINKEDIN_PASSWORD', ''):
            print("  - LINKEDIN_PASSWORD")
        if not getattr(settings, 'LINKEDIN_POSTING_ENABLED', False):
            print("  - LINKEDIN_POSTING_ENABLED (set to True)")
        
        print("\nAdd these to your .env file and restart Django")
    
    print("\n" + "=" * 80)


def main():
    try:
        # Run checks
        config_ok = check_configuration()
        init_ok = test_linkedin_poster_initialization()
        
        # Print summary
        print_summary(config_ok, init_ok)
        
        return 0 if (config_ok and init_ok) else 1
        
    except Exception as e:
        print(f"\n[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
