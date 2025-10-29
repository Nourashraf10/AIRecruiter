"""
Daily Automation Service for Interview Scheduling
Runs daily at 11:59 PM to check shortlisted candidates and send interview emails
"""

import logging
from typing import Dict, Any, List, Optional
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import User
from vacancies.models import Vacancy, Shortlist
from candidates.models import Candidate, Application
from comms.models import OutgoingEmail
from interviews.models import Interview, InterviewSlot
from interviews.services import ZohoCalendarService, InterviewSchedulingService

logger = logging.getLogger(__name__)


class DailyAutomationService:
    """Daily automation service for interview scheduling"""
    
    def process_daily_interview_scheduling(self) -> Dict[str, Any]:
        """
        Process daily interview scheduling for vacancies in 'collecting_applications' status
        
        Returns:
            Dict with success status and details
        """
        try:
            logger.info(f"🕚 Daily interview scheduling started at {timezone.now()}")
            
            # Get all vacancies in 'collecting_applications' status
            collecting_vacancies = Vacancy.objects.filter(status='collecting_applications')
            logger.info(f"📋 Found {collecting_vacancies.count()} vacancies in 'collecting_applications' status")
            
            if collecting_vacancies.count() == 0:
                logger.info("ℹ️ No vacancies in 'collecting_applications' status to process")
                return {
                    'success': True,
                    'message': 'No vacancies in collecting_applications status to process',
                    'processed_vacancies': 0,
                    'total_emails_sent': 0
                }
            
            total_emails_sent = 0
            processed_vacancies = 0
            
            # Process each vacancy
            for vacancy in collecting_vacancies:
                logger.info(f"📝 Processing vacancy: {vacancy.title} (ID: {vacancy.id})")
                
                # Get all eligible candidates for this vacancy
                eligible_candidates = self._get_eligible_candidates(vacancy)
                if not eligible_candidates:
                    logger.info(f"ℹ️ No eligible shortlisted candidates found for vacancy {vacancy.title}")
                    continue

                logger.info(f"📋 Found {len(eligible_candidates)} eligible candidates for {vacancy.title}")
                
                # Track used slots for this manager to avoid conflicts
                used_slots = set()
                vacancy_processed = False
                
                # Process each eligible candidate
                for candidate in eligible_candidates:
                    # Find a free slot on manager calendar (next 7 days, 60 minutes)
                    slot = self._find_manager_free_slot(vacancy, used_slots)
                    if not slot:
                        logger.warning(f"⚠️ No available calendar slot found for manager {vacancy.manager.email} (vacancy {vacancy.title})")
                        break

                    # Create InterviewSlot and Interview, then notify
                    scheduling_result = self._create_and_notify(vacancy, candidate, slot)
                    if scheduling_result.get('success'):
                        # Mark this slot as used
                        slot_key = f"{slot['start_time']}_{slot['end_time']}"
                        used_slots.add(slot_key)
                        vacancy_processed = True
                        total_emails_sent += scheduling_result.get('emails_sent', 0)
                        logger.info(f"✅ Scheduled interview and sent notifications for {vacancy.title} - {candidate.full_name}")
                    else:
                        logger.error(f"❌ Failed scheduling/notifications: {scheduling_result.get('error')}")
                
                if vacancy_processed:
                    processed_vacancies += 1
            
            logger.info(f"🎉 Daily interview scheduling completed: {processed_vacancies} vacancies processed, {total_emails_sent} emails sent")
            
            return {
                'success': True,
                'message': f'Daily interview scheduling completed: {processed_vacancies} vacancies processed, {total_emails_sent} emails sent',
                'processed_vacancies': processed_vacancies,
                'total_emails_sent': total_emails_sent,
                'summary': {
                    'vacancies_checked': collecting_vacancies.count(),
                    'vacancies_processed': processed_vacancies,
                    'total_emails_sent': total_emails_sent,
                    'timestamp': timezone.now().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error in daily interview scheduling: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_shortlisted_candidates(self, vacancy: Vacancy) -> List[Candidate]:
        """Get shortlisted candidates for a vacancy (ordered by rank then AI score fallback)."""
        try:
            # Try to get shortlist entries first
            try:
                shortlist_entries = Shortlist.objects.filter(vacancy=vacancy).order_by('rank')
                if shortlist_entries.exists():
                    candidates = [entry.candidate for entry in shortlist_entries]
                    logger.info(f"Found {len(candidates)} candidates in shortlist for {vacancy.title}")
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
                logger.info(f"Found {len(candidates)} candidates from applications (fallback) for {vacancy.title}")
                return candidates
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting shortlisted candidates for {vacancy.title}: {str(e)}")
            return []
    
    def _get_eligible_candidates(self, vacancy: Vacancy) -> List[Candidate]:
        """Return all shortlisted candidates who weren't already scheduled for this vacancy."""
        candidates = self._get_shortlisted_candidates(vacancy)
        eligible_candidates = []
        
        for candidate in candidates:
            already_scheduled = Interview.objects.filter(vacancy=vacancy, candidate=candidate).exists()
            if not already_scheduled:
                eligible_candidates.append(candidate)
        
        return eligible_candidates

    def _pick_next_shortlisted_candidate(self, vacancy: Vacancy) -> Optional[Candidate]:
        """Return the highest-ranked shortlisted candidate who wasn't already scheduled for this vacancy."""
        eligible_candidates = self._get_eligible_candidates(vacancy)
        return eligible_candidates[0] if eligible_candidates else None

    def _find_manager_free_slot(self, vacancy: Vacancy, used_slots: set = None) -> Optional[Dict[str, Any]]:
        """Find a free slot for the manager using ZohoCalendarService, avoiding used slots."""
        if used_slots is None:
            used_slots = set()
            
        start_date = timezone.now() + timedelta(days=1)
        end_date = start_date + timedelta(days=7)
        calendar = ZohoCalendarService(manager_email=vacancy.manager.email)
        slots = calendar.get_available_slots(start_date, end_date, duration_minutes=60, manager_email=vacancy.manager.email)
        
        if slots:
            # Find the first slot that hasn't been used yet
            for s in slots:
                slot_key = f"{s.get('start_time', s.get('start'))}_{s.get('end_time', s.get('end'))}"
                if slot_key not in used_slots:
                    return {
                        'start_time': s.get('start_time', s.get('start')),  # support both shapes
                        'end_time': s.get('end_time', s.get('end')),
                        'duration_minutes': s.get('duration_minutes', 60),
                    }
        
        return None

    def _create_and_notify(self, vacancy: Vacancy, candidate: Candidate, slot: Dict[str, Any]) -> Dict[str, Any]:
        """Create InterviewSlot + Interview and send emails to manager and candidate."""
        try:
            # Create interview slot
            interview_slot = InterviewSlot.objects.create(
                vacancy=vacancy,
                manager=vacancy.manager,
                start_time=slot['start_time'],
                end_time=slot['end_time'],
                is_available=False,
            )

            # Create interview
            interview = Interview.objects.create(
                vacancy=vacancy,
                candidate=candidate,
                manager=vacancy.manager,
                interview_slot=interview_slot,
                scheduled_at=slot['start_time'],
                duration_minutes=slot.get('duration_minutes', 60),
                status='scheduled',
            )

            # Send notifications
            svc = InterviewSchedulingService()
            notify_result = svc.send_interview_notifications([interview])
            if notify_result.get('success'):
                # Send questionnaire via email to the specified candidate mailbox
                try:
                    self._send_questionnaire_email(vacancy, candidate)
                except Exception as e:
                    logger.warning(f"Questionnaire email send failed for {candidate.email}: {str(e)}")
                return {'success': True, 'emails_sent': notify_result.get('sent_count', 0)}
            return {'success': False, 'error': notify_result.get('error', 'Failed to send notifications')}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _send_questionnaire_email(self, vacancy: Vacancy, candidate: Candidate) -> None:
        """Send the pre-interview questionnaire via email to the chosen shortlisted candidate."""
        target_email = candidate.email
        questionnaire = vacancy.questionnaire_template or (
            "1) Why this role?\n2) When can you start?\n3) What is your expected salary?"
        )
        subject = f"Pre-Interview Questionnaire - {vacancy.title}"
        message = (
            f"Dear {candidate.full_name},\n\n"
            f"You have been shortlisted for the position '{vacancy.title}'.\n"
            f"Please complete this quick questionnaire by replying to this email:\n\n"
            f"{questionnaire}\n\n"
            f"Best regards,\nAI Recruiting System"
        )
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[target_email],
            fail_silently=False,
        )
        OutgoingEmail.objects.create(
            to_address=target_email,
            subject=subject,
            body=message,
            sent_at=timezone.now()
        )
    
    def _send_manager_notification(self, vacancy: Vacancy, candidates: List) -> Dict[str, Any]:
        """Send notification email to manager"""
        try:
            subject = f"Daily Interview Scheduling - {vacancy.title}"
            
            message = f"""
Dear {vacancy.manager.get_full_name() or vacancy.manager.username},

This is your daily interview scheduling update for the vacancy "{vacancy.title}".

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
