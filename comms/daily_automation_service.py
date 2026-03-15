"""
Daily Automation Service for Interview Scheduling
Runs daily (or manually) to add shortlisted candidates to Pending Interview Approvals.
Does not assign slots or send emails; the recruiter selects candidates and clicks
"Send interview emails for selected" on the dashboard to schedule and send.
"""

import logging
from typing import Dict, Any, List, Optional
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import User
from vacancies.models import Vacancy, Shortlist
from candidates.models import Candidate, Application, CandidateVacancyProfile
from comms.models import OutgoingEmail
from core.email_utils import email_subject  # questionnaire only (IT policy)
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
            vac_count = collecting_vacancies.count()
            logger.info(f"📋 Found {vac_count} vacancy(ies) in 'collecting_applications' status")
            
            if vac_count == 0:
                logger.info("ℹ️ No vacancies in 'collecting_applications' status — nothing to process. Move vacancies to this status and ensure shortlists exist.")
                return {
                    'success': True,
                    'message': 'No vacancies in collecting_applications status to process',
                    'processed_vacancies': 0,
                    'total_emails_sent': 0,
                    'summary': {
                        'vacancies_checked': 0,
                        'vacancies_processed': 0,
                        'total_emails_sent': 0,
                        'reason': 'no_vacancies_collecting_applications',
                        'timestamp': timezone.now().isoformat()
                    }
                }
            
            total_emails_sent = 0
            processed_vacancies = 0
            
            # Process each vacancy
            for vacancy in collecting_vacancies:
                logger.info(f"📝 Processing vacancy: {vacancy.title} (ID: {vacancy.id})")
                if not getattr(vacancy, 'manager_id', None) or not vacancy.manager:
                    logger.warning(f"⚠️ Vacancy {vacancy.title} has no manager assigned — skipping. Assign a manager in Admin > Vacancies.")
                    continue

                # Ensure shortlist is up to date (top 5 by AI score) before picking candidates
                try:
                    from candidates.signals import update_shortlist_for_vacancy
                    update_shortlist_for_vacancy(vacancy)
                except Exception as e:
                    logger.warning(f"⚠️ Could not update shortlist for {vacancy.title}: {e}")

                # Log who is in the shortlist (so we can see if a specific candidate was included)
                shortlist_entries = Shortlist.objects.filter(vacancy=vacancy).order_by('rank').select_related('candidate')
                shortlist_names = [e.candidate.full_name for e in shortlist_entries]
                logger.info(f"📋 Shortlist for {vacancy.title}: {shortlist_names or '(empty)'}")

                # Get all eligible candidates for this vacancy (shortlisted and not already scheduled)
                eligible_candidates = self._get_eligible_candidates(vacancy)
                if not eligible_candidates:
                    logger.warning(f"⚠️ No eligible shortlisted candidates for {vacancy.title} — ensure the vacancy has applications with AI scores and candidates are not already scheduled.")
                    continue

                logger.info(f"📋 Eligible (not yet scheduled): {[c.full_name for c in eligible_candidates]}")

                # Only add shortlisted candidates to Pending Interview Approvals (no slot, no emails).
                # Recruiter selects candidates and clicks "Send interview emails for selected" to schedule and send.
                added_count = 0
                for candidate in eligible_candidates:
                    interview, created = Interview.objects.get_or_create(
                        vacancy=vacancy,
                        candidate=candidate,
                        defaults={
                            'manager': vacancy.manager,
                            'status': 'pending_approval',
                            'interview_slot': None,
                            'scheduled_at': None,
                            'duration_minutes': 60,
                        },
                    )
                    if created:
                        added_count += 1
                        logger.info(f"✅ Added to Pending Interview Approvals: {vacancy.title} — {candidate.full_name}")
                    else:
                        logger.debug(f"Already in Pending/scheduled: {candidate.full_name} for {vacancy.title}")

                if added_count > 0:
                    processed_vacancies += 1
            
            logger.info("ℹ️ Daily task only adds candidates to Pending Interview Approvals. Use the dashboard to select and send interview emails (which schedules the slot and sends emails).")
            logger.info(f"🎉 Daily interview scheduling completed: {processed_vacancies} vacancy(ies) with new pending approvals")
            
            return {
                'success': True,
                'message': f'Daily scheduling completed: {processed_vacancies} vacancy(ies) updated. New entries appear in Pending Interview Approvals.',
                'processed_vacancies': processed_vacancies,
                'total_emails_sent': 0,
                'summary': {
                    'vacancies_checked': collecting_vacancies.count(),
                    'vacancies_processed': processed_vacancies,
                    'total_emails_sent': 0,
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
        logger.info(f"Calendar returned {len(slots) if slots else 0} slot(s) for manager {vacancy.manager.email} ({start_date.date()} to {end_date.date()})")
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
            
            # Create interview (notifications will be sent only after manager approval from dashboard)
            interview = Interview.objects.create(
                vacancy=vacancy,
                candidate=candidate,
                manager=vacancy.manager,
                interview_slot=interview_slot,
                scheduled_at=slot['start_time'],
                duration_minutes=slot.get('duration_minutes', 60),
                status='scheduled',
            )
            
            return {
                'success': True,
                'emails_sent': 0,
                'interview_id': interview.id,
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def schedule_pending_interview(self, interview: Interview, used_slots_by_manager: Optional[Dict[Any, set]] = None) -> bool:
        """
        Assign a calendar slot to a pending_approval interview and mark as scheduled.
        Used when the recruiter clicks "Send interview emails for selected" on the dashboard.
        used_slots_by_manager: dict keyed by manager id, value = set of slot keys (to avoid double-booking same manager).
        Returns True if slot was assigned, False if no slot available or already scheduled.
        """
        if interview.status != 'pending_approval':
            return True
        if used_slots_by_manager is None:
            used_slots_by_manager = {}
        used = used_slots_by_manager.setdefault(interview.manager_id, set())
        slot = self._find_manager_free_slot(interview.vacancy, used)
        if not slot:
            return False
        try:
            interview_slot = InterviewSlot.objects.create(
                vacancy=interview.vacancy,
                manager=interview.manager,
                start_time=slot['start_time'],
                end_time=slot['end_time'],
                is_available=False,
            )
            interview.interview_slot = interview_slot
            interview.scheduled_at = slot['start_time']
            interview.duration_minutes = slot.get('duration_minutes', 60)
            interview.status = 'scheduled'
            interview.save(update_fields=['interview_slot', 'scheduled_at', 'duration_minutes', 'status'])
            used.add(f"{slot['start_time']}_{slot['end_time']}")
            return True
        except Exception as e:
            logger.warning(f"Could not schedule pending interview {interview.id}: {e}")
            return False

    def _send_questionnaire_email(self, vacancy: Vacancy, candidate: Candidate) -> None:
        """Send the pre-interview questionnaire via email to the chosen shortlisted candidate. Skips if already sent for this vacancy."""
        from django.db import transaction
        try:
            with transaction.atomic():
                profile = CandidateVacancyProfile.objects.select_for_update().filter(
                    candidate=candidate, vacancy=vacancy
                ).first()
                if not profile:
                    profile, _ = CandidateVacancyProfile.objects.get_or_create(
                        candidate=candidate,
                        vacancy=vacancy,
                        defaults={'application_status': 'shortlisted'},
                    )
                if profile.questionnaire_email_sent_at:
                    logger.info(f"Skipping questionnaire send to {candidate.email} for '{vacancy.title}' — already sent")
                    return
                profile.questionnaire_email_sent_at = timezone.now()
                profile.save(update_fields=['questionnaire_email_sent_at'])
        except Exception as e:
            logger.warning(f"Could not lock/set questionnaire flag: {e}")
            return
        target_email = candidate.email
        questionnaire = vacancy.questionnaire_template or (
            "1) Why this role?\n2) When can you start?\n3) What is your expected salary?"
        )
        safe_title = "".join(c if ord(c) < 128 else " " for c in (vacancy.title or "")).strip() or "Position"
        subject = email_subject(f"Pre-Interview Questions - {safe_title}")
        message = (
            f"Dear {candidate.full_name},\n\n"
            f"You have been shortlisted for the position '{vacancy.title}'.\n"
            f"Please complete this quick questionnaire by replying to this email:\n\n"
            f"{questionnaire}\n\n"
            f"Best regards,\nFahmy"
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
Fahmy
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
            subject = email_subject(f"Interview Invitation - {vacancy.title}")
            
            message = f"""
Dear {candidate.full_name},

Congratulations! You have been shortlisted for the position "{vacancy.title}".

Your AI Score: {candidate.ai_score_out_of_10}/10

The hiring manager will contact you shortly to schedule an interview.

Best regards,
Fahmy
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
