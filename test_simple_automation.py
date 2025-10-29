#!/usr/bin/env python3
"""
Simple automation test that bypasses calendar integration
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'recruiter.settings')
django.setup()

from vacancies.models import Vacancy
from candidates.models import Candidate, Application
from django.core.mail import send_mail
from django.conf import settings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def simple_automation():
    """Simple automation that just sends emails"""
    print("🔧 Simple Automation Test (Email Only)")
    print("=" * 40)
    
    # Get vacancy
    vacancy = Vacancy.objects.get(id=1)
    print(f"Vacancy: {vacancy.title}")
    print(f"Status: {vacancy.status}")
    print(f"Manager: {vacancy.manager.email}")
    
    # Get candidates
    applications = Application.objects.filter(vacancy=vacancy)
    candidates = []
    for app in applications:
        if app.cv and app.cv.candidate:
            candidates.append(app.cv.candidate)
    
    print(f"Candidates: {len(candidates)}")
    for candidate in candidates:
        print(f"  - {candidate.full_name} (Score: {candidate.ai_score_out_of_10})")
    
    if not candidates:
        print("❌ No candidates found!")
        return
    
    # Send emails
    print(f"\n📧 Sending emails...")
    
    # Email to manager
    manager_subject = f"Interview Scheduling - {vacancy.title}"
    manager_message = f"""
Dear {vacancy.manager.get_full_name() or vacancy.manager.username},

The vacancy "{vacancy.title}" has been closed and interviews need to be scheduled.

Shortlisted Candidates:
"""
    
    for i, candidate in enumerate(candidates[:5], 1):
        manager_message += f"""
{i}. {candidate.full_name}
   Email: {candidate.email}
   AI Score: {candidate.ai_score_out_of_10}/10
"""
    
    manager_message += f"""

Please coordinate with the candidates to schedule interviews.

Best regards,
AI Recruiting System
"""
    
    try:
        send_mail(
            subject=manager_subject,
            message=manager_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vacancy.manager.email],
            fail_silently=False,
        )
        print(f"✅ Manager email sent to: {vacancy.manager.email}")
    except Exception as e:
        print(f"❌ Failed to send manager email: {str(e)}")
    
    # Email to candidates
    for candidate in candidates[:5]:
        candidate_subject = f"Interview Invitation - {vacancy.title}"
        candidate_message = f"""
Dear {candidate.full_name},

Congratulations! You have been shortlisted for the position "{vacancy.title}".

Your AI Score: {candidate.ai_score_out_of_10}/10

The hiring manager will contact you shortly to schedule an interview.

Best regards,
AI Recruiting System
"""
        
        try:
            send_mail(
                subject=candidate_subject,
                message=candidate_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidate.email],
                fail_silently=False,
            )
            print(f"✅ Candidate email sent to: {candidate.email}")
        except Exception as e:
            print(f"❌ Failed to send candidate email to {candidate.email}: {str(e)}")
    
    print(f"\n✅ Simple automation completed!")

if __name__ == '__main__':
    simple_automation()

