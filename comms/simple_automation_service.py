"""
Simplified Automation Service for Interview Scheduling
This version focuses on email notifications without complex calendar integration
"""

import logging
from typing import Dict, Any, List
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import User
from vacancies.models import Vacancy, Shortlist
from candidates.models import Candidate, Application
from comms.models import OutgoingEmail

logger = logging.getLogger(__name__)


class SimpleAutomationService:
    """Simplified automation service for interview scheduling"""
    
    def process_closed_vacancy(self, vacancy: Vacancy) -> Dict[str, Any]:
        """
        Process a closed vacancy and send interview notifications
        
        Args:
            vacancy: The vacancy that was closed
            
        Returns:
            Dict with success status and details
        """
        try:
            logger.info(f"🚀 Processing closed vacancy: {vacancy.title} (ID: {vacancy.id})")
            
            # Step 1: Get shortlisted candidates
            shortlisted_candidates = self._get_shortlisted_candidates(vacancy)
            if not shortlisted_candidates:
                logger.warning(f"⚠️ No shortlisted candidates found for vacancy {vacancy.id}")
                return {
                    'success': False,
                    'error': 'No shortlisted candidates found for this vacancy'
                }
            
            logger.info(f"📋 Found {len(shortlisted_candidates)} shortlisted candidates")
            
            # Step 2: Send email notifications
            notification_results = self._send_interview_notifications(vacancy, shortlisted_candidates)
            
            return {
                'success': True,
                'message': f'Interview notifications sent for {len(shortlisted_candidates)} candidates',
                'scheduled_interviews': len(shortlisted_candidates),
                'total_candidates': len(shortlisted_candidates),
                'notifications_sent': notification_results['success'],
                'summary': {
                    'vacancy_title': vacancy.title,
                    'manager_email': vacancy.manager.email,
                    'candidates_notified': len(shortlisted_candidates),
                    'emails_sent': notification_results.get('emails_sent', 0)
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing closed vacancy: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_shortlisted_candidates(self, vacancy: Vacancy) -> List:
        """Get shortlisted candidates for a vacancy"""
        try:
            # Try to get shortlist entries first
            try:
                shortlist_entries = Shortlist.objects.filter(vacancy=vacancy).order_by('rank')
                if shortlist_entries.exists():
                    candidates = [entry.candidate for entry in shortlist_entries]
                    logger.info(f"Found {len(candidates)} candidates in shortlist")
                    return candidates
            except Exception as e:
                logger.warning(f"Shortlist table not available: {str(e)}")
            
            # Fallback: Get candidates from applications (top 5 by AI score)
            applications = Application.objects.filter(vacancy=vacancy).select_related('cv__candidate')
            candidates = []
            
            for app in applications:
                if app.cv and app.cv.candidate:
                    candidates.append(app.cv.candidate)
            
            # Sort by AI score and take top 5
            candidates = sorted(candidates, key=lambda c: c.ai_score_out_of_10 or 0, reverse=True)[:5]
            
            if candidates:
                logger.info(f"Found {len(candidates)} candidates from applications (fallback)")
                return candidates
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting shortlisted candidates: {str(e)}")
            return []
    
    def _send_interview_notifications(self, vacancy: Vacancy, candidates: List) -> Dict[str, Any]:
        """Send interview notifications to manager and candidates"""
        try:
            emails_sent = 0
            
            # Send email to manager
            manager_result = self._send_manager_notification(vacancy, candidates)
            if manager_result['success']:
                emails_sent += 1
            
            # Send emails to candidates
            for candidate in candidates:
                candidate_result = self._send_candidate_notification(vacancy, candidate)
                if candidate_result['success']:
                    emails_sent += 1
            
            logger.info(f"✅ Interview notifications sent for {emails_sent} recipients")
            
            return {
                'success': True,
                'emails_sent': emails_sent,
                'total_recipients': len(candidates) + 1  # +1 for manager
            }
            
        except Exception as e:
            logger.error(f"Error sending interview notifications: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_manager_notification(self, vacancy: Vacancy, candidates: List) -> Dict[str, Any]:
        """Send notification email to manager"""
        try:
            subject = f"Interview Scheduling Required - {vacancy.title}"
            
            message = f"""
Dear {vacancy.manager.get_full_name() or vacancy.manager.username},

The vacancy "{vacancy.title}" has been closed and interviews need to be scheduled.

Shortlisted Candidates:
"""
            
            for i, candidate in enumerate(candidates, 1):
                message += f"""
{i}. {candidate.full_name}
   Email: {candidate.email}
   AI Score: {candidate.ai_score_out_of_10}/10
"""
            
            message += f"""

Please coordinate with the candidates to schedule interviews.

Best regards,
AI Recruiting System
"""
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[vacancy.manager.email],
                fail_silently=False,
            )
            
            # Log the email
            OutgoingEmail.objects.create(
                to_address=vacancy.manager.email,
                subject=subject,
                body=message,
                sent_at=timezone.now()
            )
            
            logger.info(f"✅ Manager notification sent to: {vacancy.manager.email}")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"❌ Failed to send manager notification: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _send_candidate_notification(self, vacancy: Vacancy, candidate: Candidate) -> Dict[str, Any]:
        """Send notification email to candidate"""
        try:
            subject = f"Interview Invitation - {vacancy.title}"
            
            message = f"""
Dear {candidate.full_name},

Congratulations! You have been shortlisted for the position "{vacancy.title}".

Your AI Score: {candidate.ai_score_out_of_10}/10

The hiring manager will contact you shortly to schedule an interview.

Best regards,
AI Recruiting System
"""
            
            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[candidate.email],
                fail_silently=False,
            )
            
            # Log the email
            OutgoingEmail.objects.create(
                to_address=candidate.email,
                subject=subject,
                body=message,
                sent_at=timezone.now()
            )
            
            logger.info(f"✅ Candidate notification sent to: {candidate.email}")
            
            return {'success': True}
            
        except Exception as e:
            logger.error(f"❌ Failed to send candidate notification to {candidate.email}: {str(e)}")
            return {'success': False, 'error': str(e)}
