#!/usr/bin/env python3
"""
Test script for the automated interview scheduling system
This script tests the complete workflow when a vacancy status changes to 'closed'
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from vacancies.models import Vacancy, Shortlist
from candidates.models import Candidate, Application, CV
from core.models import User
from comms.automation_service import AutomatedInterviewScheduler
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_test_data():
    """Create test data for the automation"""
    logger.info("🔧 Creating test data...")
    
    # Create or get manager
    manager, created = User.objects.get_or_create(
        email='noureldin.ashraf@bit68.com',
        defaults={
            'username': 'noureldin.ashraf',
            'first_name': 'Noureldin',
            'last_name': 'Ashraf',
            'is_staff': True
        }
    )
    logger.info(f"✅ Manager: {manager.email}")
    
    # Create or get vacancy
    vacancy, created = Vacancy.objects.get_or_create(
        title='Senior Python Developer',
        defaults={
            'department': 'Engineering',
            'manager': manager,
            'created_by': manager,
            'status': 'collecting_applications',
            'keywords': 'Python, Django, REST API, PostgreSQL',
            'require_dob_in_cv': True,
            'require_egyptian': False,
            'require_relevant_university': True,
            'require_relevant_major': True
        }
    )
    logger.info(f"✅ Vacancy: {vacancy.title} (Status: {vacancy.status})")
    
    # Create test candidates
    candidates_data = [
        {
            'full_name': 'Ahmed Hassan',
            'email': 'ahmed.hassan@example.com',
            'phone': '+201234567890',
            'nationality': 'Egyptian',
            'ai_score_out_of_10': 9.2
        },
        {
            'full_name': 'Sara Mohamed',
            'email': 'sara.mohamed@example.com',
            'phone': '+201234567891',
            'nationality': 'Egyptian',
            'ai_score_out_of_10': 8.8
        },
        {
            'full_name': 'Omar Ali',
            'email': 'omar.ali@example.com',
            'phone': '+201234567892',
            'nationality': 'Egyptian',
            'ai_score_out_of_10': 8.5
        },
        {
            'full_name': 'Fatma Ibrahim',
            'email': 'fatma.ibrahim@example.com',
            'phone': '+201234567893',
            'nationality': 'Egyptian',
            'ai_score_out_of_10': 8.1
        },
        {
            'full_name': 'Mahmoud Youssef',
            'email': 'mahmoud.youssef@example.com',
            'phone': '+201234567894',
            'nationality': 'Egyptian',
            'ai_score_out_of_10': 7.9
        }
    ]
    
    candidates = []
    for candidate_data in candidates_data:
        candidate, created = Candidate.objects.get_or_create(
            email=candidate_data['email'],
            defaults=candidate_data
        )
        candidates.append(candidate)
        logger.info(f"✅ Candidate: {candidate.full_name} (Score: {candidate.ai_score_out_of_10})")
    
    # Create CVs and Applications
    for candidate in candidates:
        cv, created = CV.objects.get_or_create(
            candidate=candidate,
            defaults={
                'extracted_text': f"CV for {candidate.full_name} - Python Developer with 5+ years experience",
                'created_at': timezone.now()
            }
        )
        
        application, created = Application.objects.get_or_create(
            vacancy=vacancy,
            cv=cv,
            defaults={
                'status': 'applied'
            }
        )
        logger.info(f"✅ Application: {candidate.full_name} -> {vacancy.title}")
    
    # Generate shortlist
    shortlist_count = vacancy.generate_shortlist()
    logger.info(f"✅ Shortlist generated with {shortlist_count} candidates")
    
    return vacancy, manager, candidates

def test_automation():
    """Test the automated interview scheduling"""
    logger.info("🚀 Starting automated interview scheduling test...")
    
    # Create test data
    vacancy, manager, candidates = create_test_data()
    
    # Change vacancy status to 'closed' to trigger automation
    logger.info(f"📝 Changing vacancy status from '{vacancy.status}' to 'closed'...")
    vacancy.status = 'closed'
    vacancy.save(update_fields=['status'])
    
    logger.info("✅ Vacancy status changed to 'closed' - automation should have been triggered!")
    
    # Check if interviews were created
    from interviews.models import Interview
    interviews = Interview.objects.filter(vacancy=vacancy)
    logger.info(f"📅 Found {interviews.count()} scheduled interviews:")
    
    for interview in interviews:
        logger.info(f"  - {interview.candidate.full_name}: {interview.scheduled_at.strftime('%Y-%m-%d %H:%M')}")
    
    return interviews.count()

def main():
    """Main test function"""
    try:
        logger.info("🧪 Testing Automated Interview Scheduling System")
        logger.info("=" * 60)
        
        # Run the test
        interview_count = test_automation()
        
        logger.info("=" * 60)
        if interview_count > 0:
            logger.info(f"✅ Test completed successfully! {interview_count} interviews scheduled.")
        else:
            logger.warning("⚠️ Test completed but no interviews were scheduled.")
            
    except Exception as e:
        logger.error(f"❌ Test failed: {str(e)}")
        logger.exception("Full traceback:")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

