#!/usr/bin/env python3
"""
Test the fixed automation system
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')
django.setup()

from vacancies.models import Vacancy, Shortlist
from candidates.models import Candidate, Application
from comms.automation_service import AutomatedInterviewScheduler
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_fixed_automation():
    """Test the fixed automation system"""
    print("🔧 Testing Fixed Automation System")
    print("=" * 40)
    
    # Get vacancy
    vacancy = Vacancy.objects.get(id=1)
    print(f"Vacancy: {vacancy.title} (Status: {vacancy.status})")
    
    # Check if shortlist exists
    shortlist_count = vacancy.shortlists.count()
    print(f"Shortlist entries: {shortlist_count}")
    
    if shortlist_count == 0:
        print("Creating shortlist...")
        # Get candidate and application
        candidate = Candidate.objects.get(full_name='Hanya Ashraf')
        application = Application.objects.filter(vacancy=vacancy, cv__candidate=candidate).first()
        
        if application:
            shortlist_entry = Shortlist.objects.create(
                vacancy=vacancy,
                candidate=candidate,
                application=application,
                rank=1,
                ai_score=candidate.ai_score_out_of_10,
                notes='Top candidate for interview'
            )
            print(f"✅ Created shortlist: {shortlist_entry}")
        else:
            print("❌ No application found")
            return
    else:
        for entry in vacancy.shortlists.all():
            print(f"  - {entry.candidate.full_name} (Rank: {entry.rank}, Score: {entry.ai_score})")
    
    # Test automation
    print(f"\n🚀 Testing automation...")
    try:
        scheduler = AutomatedInterviewScheduler()
        result = scheduler.process_closed_vacancy(vacancy)
        
        print(f"✅ Automation completed!")
        print(f"Success: {result.get('success', False)}")
        print(f"Message: {result.get('message', 'No message')}")
        
        if not result.get('success', False):
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Automation failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_fixed_automation()

