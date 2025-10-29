import requests
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from django.conf import settings
from django.utils import timezone
from typing import List, Dict, Any
import logging
from .zoho_api_service import CalendarDiscoveryService, SimpleCalDavClient
from django.core.mail import send_mail


logger = logging.getLogger(__name__)


class ZohoCalendarService:
    """Service for integrating with Zoho Calendar"""
    
    def __init__(self, manager_email: str = None):
        self.manager_email = manager_email
        self.discovery_service = CalendarDiscoveryService()
        
        # Legacy support for hardcoded calendar (for backward compatibility)
        self.base_url = "https://calendar.zoho.com"
        self.calendar_id = "zz0801123036b8058043c80769e4cff0ea6c26f366f0cca02bc2ea27b0f6630ea6e0f02052b6a11c367d8b57b55d32f4a3b96a58d4"
        self.calendar_uid = "0882e3bb90a64bb0b8a9e441d0435566"
        self.caldav_url = "https://calendar.zoho.com/caldav/0882e3bb90a64bb0b8a9e441d0435566/events/"
        self._caldav_client: SimpleCalDavClient | None = None
        self._basic_username: str | None = None
        self._basic_password: str | None = None
        
    def get_available_slots(self, start_date: datetime, end_date: datetime, duration_minutes: int = 60, manager_email: str = None) -> List[Dict[str, Any]]:
        """
        Get available time slots from Zoho Calendar
        
        Args:
            start_date: Start date for checking availability
            end_date: End date for checking availability
            duration_minutes: Duration of each slot in minutes
            manager_email: Manager's email address (optional, uses self.manager_email if not provided)
            
        Returns:
            List of available time slots
        """
        try:
            # Use provided manager_email or fall back to instance variable
            email = manager_email or self.manager_email
            
            # Try to load per-manager integration with basic auth
            if email and not self._caldav_client:
                try:
                    from .models import CalendarIntegration
                    from core.models import User
                    manager = User.objects.filter(email=email).first()
                    if manager:
                        integ = getattr(manager, 'calendar_integration', None)
                        if integ and integ.caldav_url and integ.caldav_username and integ.caldav_password and integ.is_active:
                            self.configure_basic_auth_caldav(integ.caldav_url, integ.caldav_username, integ.caldav_password)
                except Exception:
                    pass

            if email and self._caldav_client:
                # Use CalDAV credentials if configured on this service instance
                start_iso = start_date.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                end_iso = end_date.astimezone(dt_timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                raw = self._caldav_client.fetch_events_raw(start_iso, end_iso)
                busy = self._caldav_client.parse_ics_events(raw)
                return self._compute_free_slots_from_busy(busy, start_date, end_date, duration_minutes)
            elif email:
                # Without direct credentials, fall back to simulation for now
                return self._simulate_available_slots(start_date, end_date, duration_minutes)
            else:
                # Legacy behavior - simulate available slots
                available_slots = self._simulate_available_slots(start_date, end_date, duration_minutes)
                logger.info(f"Found {len(available_slots)} available slots between {start_date} and {end_date}")
                return available_slots
            
        except Exception as e:
            logger.error(f"Error getting available slots: {str(e)}")
            return []

    def configure_basic_auth_caldav(self, caldav_url: str, username: str, password: str) -> None:
        """Configure the service to use direct CalDAV basic auth for availability."""
        self.caldav_url = caldav_url
        self._basic_username = username
        self._basic_password = password
        self._caldav_client = SimpleCalDavClient(caldav_url, username, password)
    
    def _simulate_available_slots(self, start_date: datetime, end_date: datetime, duration_minutes: int) -> List[Dict[str, Any]]:
        """
        Simulate available slots for testing purposes
        In production, this would be replaced with actual Zoho Calendar API calls
        """
        available_slots = []
        current_date = start_date.replace(hour=9, minute=0, second=0, microsecond=0)  # Start at 9 AM
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                # Create slots from 9 AM to 5 PM with 1-hour intervals
                for hour in range(9, 17):  # 9 AM to 5 PM
                    slot_start = current_date.replace(hour=hour, minute=0)
                    slot_end = slot_start + timedelta(minutes=duration_minutes)
                    
                    # Skip if slot is in the past
                    if slot_start > timezone.now():
                        available_slots.append({
                            'start_time': slot_start,
                            'end_time': slot_end,
                            'duration_minutes': duration_minutes,
                            'is_available': True
                        })
            
            current_date += timedelta(days=1)
        
        return available_slots

    def _compute_free_slots_from_busy(self, busy_events: List[Dict[str, Any]], start_date: datetime, end_date: datetime, duration_minutes: int) -> List[Dict[str, Any]]:
        """Given busy intervals, compute working-hours free slots of given duration."""
        # Normalize busy intervals to UTC-aware datetimes
        to_aware = lambda dt: dt if timezone.is_aware(dt) else timezone.make_aware(dt, dt_timezone.utc)
        busy = [
            {
                'start': to_aware(ev['start']).astimezone(dt_timezone.utc),
                'end': to_aware(ev['end']).astimezone(dt_timezone.utc),
            }
            for ev in busy_events if ev.get('start') and ev.get('end')
        ]
        busy.sort(key=lambda x: x['start'])

        slots: List[Dict[str, Any]] = []
        current = start_date.astimezone(dt_timezone.utc)
        end_bound = end_date.astimezone(dt_timezone.utc)
        work_start_hour = 9
        work_end_hour = 17

        while current < end_bound:
            # skip weekends
            if current.weekday() >= 5:
                current = (current + timedelta(days=1)).replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
                continue
            day_start = current.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
            day_end = current.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)
            if day_end > end_bound:
                day_end = end_bound
            pointer = max(current, day_start)
            # walk through busy intervals intersecting this day
            for ev in busy:
                if ev['end'] <= day_start or ev['start'] >= day_end:
                    continue
                # free window before this busy block
                if pointer < ev['start']:
                    window_start = pointer
                    window_end = min(ev['start'], day_end)
                    slots.extend(self._slice_window(window_start, window_end, duration_minutes))
                pointer = max(pointer, ev['end'])
                if pointer >= day_end:
                    break
            # tail window after last busy
            if pointer < day_end:
                slots.extend(self._slice_window(pointer, day_end, duration_minutes))

            # advance to next day
            current = (day_start + timedelta(days=1))
        # future-only
        now_utc = timezone.now().astimezone(dt_timezone.utc)
        slots = [s for s in slots if s['start_time'] > now_utc]
        return slots

    def _slice_window(self, window_start: datetime, window_end: datetime, duration_minutes: int) -> List[Dict[str, Any]]:
        slots: List[Dict[str, Any]] = []
        step = timedelta(minutes=duration_minutes)
        start_ptr = window_start
        while start_ptr + step <= window_end:
            slots.append({
                'start_time': start_ptr,
                'end_time': start_ptr + step,
                'duration_minutes': duration_minutes,
                'is_available': True,
            })
            start_ptr += step
        return slots
    
    def create_event(self, title: str, start_time: datetime, end_time: datetime, 
                    description: str = "", attendees: List[str] = None) -> Dict[str, Any]:
        """
        Create an event in Zoho Calendar
        
        Args:
            title: Event title
            start_time: Event start time
            end_time: Event end time
            description: Event description
            attendees: List of attendee email addresses
            
        Returns:
            Event creation result
        """
        try:
            # For now, we'll simulate event creation
            # In production, you would use the Zoho Calendar API
            
            event_data = {
                'title': title,
                'start_time': start_time,
                'end_time': end_time,
                'description': description,
                'attendees': attendees or [],
                'created': True,
                'event_id': f"event_{int(timezone.now().timestamp())}"
            }
            
            logger.info(f"Created event: {title} at {start_time}")
            return event_data
            
        except Exception as e:
            logger.error(f"Error creating event: {str(e)}")
            return {'created': False, 'error': str(e)}
    
    def check_availability(self, start_time: datetime, end_time: datetime) -> bool:
        """
        Check if a specific time slot is available
        
        Args:
            start_time: Start time to check
            end_time: End time to check
            
        Returns:
            True if available, False otherwise
        """
        try:
            # For now, we'll simulate availability check
            # In production, you would check against actual calendar events
            
            # Simulate some busy times (e.g., lunch break 12-1 PM)
            if start_time.hour == 12:
                return False
            
            # Simulate some random busy slots
            if start_time.minute == 30:  # Every 30-minute mark is busy
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking availability: {str(e)}")
            return False


class InterviewSchedulingService:
    """Service for scheduling interviews with shortlisted candidates"""
    
    def __init__(self):
        self.calendar_service = ZohoCalendarService()
    
    def schedule_interviews_for_vacancy(self, vacancy, manager, start_date: datetime = None, 
                                      end_date: datetime = None, duration_minutes: int = 60) -> Dict[str, Any]:
        """
        Schedule interviews for all shortlisted candidates of a vacancy
        
        Args:
            vacancy: Vacancy object
            manager: Manager user object
            start_date: Start date for scheduling (default: tomorrow)
            end_date: End date for scheduling (default: 7 days from start)
            duration_minutes: Duration of each interview
            
        Returns:
            Scheduling result with success status and details
        """
        try:
            # Get shortlisted candidates
            shortlisted_candidates = vacancy.get_shortlisted_candidates()
            
            if not shortlisted_candidates.exists():
                return {
                    'success': False,
                    'error': 'No shortlisted candidates found for this vacancy'
                }
            
            # Set default dates if not provided
            if not start_date:
                start_date = timezone.now() + timedelta(days=1)
            if not end_date:
                end_date = start_date + timedelta(days=7)
            
            # Get available slots using manager's email for dynamic calendar discovery
            available_slots = self.calendar_service.get_available_slots(
                start_date, end_date, duration_minutes, manager.email
            )
            
            if len(available_slots) < shortlisted_candidates.count():
                return {
                    'success': False,
                    'error': f'Not enough available slots. Found {len(available_slots)} slots for {shortlisted_candidates.count()} candidates'
                }
            
            # Schedule interviews
            scheduled_interviews = []
            from .models import InterviewSlot, Interview
            
            for i, candidate_shortlist in enumerate(shortlisted_candidates):
                if i >= len(available_slots):
                    break
                
                slot = available_slots[i]
                candidate = candidate_shortlist.candidate
                
                # Create interview slot
                interview_slot = InterviewSlot.objects.create(
                    vacancy=vacancy,
                    manager=manager,
                    start_time=slot['start_time'],
                    end_time=slot['end_time'],
                    is_available=False
                )
                
                # Create interview
                interview = Interview.objects.create(
                    vacancy=vacancy,
                    candidate=candidate,
                    manager=manager,
                    interview_slot=interview_slot,
                    scheduled_at=slot['start_time'],
                    duration_minutes=duration_minutes
                )
                
                # Feedback requests will be handled automatically by the periodic task
                logger.info(f"Interview {interview.id} created - feedback request will be sent automatically when interview ends")
                
                scheduled_interviews.append(interview)
            
            return {
                'success': True,
                'scheduled_count': len(scheduled_interviews),
                'interviews': scheduled_interviews,
                'message': f'Successfully scheduled {len(scheduled_interviews)} interviews'
            }
            
        except Exception as e:
            logger.error(f"Error scheduling interviews: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_interview_notifications(self, interviews: List) -> Dict[str, Any]:
        """
        Send email notifications for scheduled interviews
        
        Args:
            interviews: List of Interview objects
            
        Returns:
            Notification result
        """
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            
            sent_count = 0
            
            for interview in interviews:
                # Send notification to manager
                manager_subject = f"Interview Scheduled: {interview.candidate.full_name} - {interview.vacancy.title}"
                manager_message = f"""
Dear {interview.manager.get_full_name() or interview.manager.username},

An interview has been scheduled for the position: {interview.vacancy.title}

Candidate: {interview.candidate.full_name}
Email: {interview.candidate.email}
Phone: {interview.candidate.phone}

Interview Details:
Date: {interview.scheduled_at.strftime('%Y-%m-%d')}
Time: {interview.scheduled_at.strftime('%H:%M')} - {(interview.scheduled_at + timedelta(minutes=interview.duration_minutes)).strftime('%H:%M')}
Duration: {interview.duration_minutes} minutes

Best regards,
AI Recruiting System
                """.strip()
                
                send_mail(
                    subject=manager_subject,
                    message=manager_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[interview.manager.email],
                    fail_silently=False,
                )
                
                # Send notification to candidate
                candidate_subject = f"Interview Invitation: {interview.vacancy.title}"
                candidate_message = f"""
Dear {interview.candidate.full_name},

Congratulations! You have been shortlisted for an interview for the position: {interview.vacancy.title}

Interview Details:
Date: {interview.scheduled_at.strftime('%Y-%m-%d')}
Time: {interview.scheduled_at.strftime('%H:%M')} - {(interview.scheduled_at + timedelta(minutes=interview.duration_minutes)).strftime('%H:%M')}
Duration: {interview.duration_minutes} minutes

Interviewer: {interview.manager.get_full_name() or interview.manager.username}

Please prepare for the interview and arrive on time.

Best regards,
{interview.manager.get_full_name() or interview.manager.username}
{interview.vacancy.title} - Hiring Manager
                """.strip()
                
                send_mail(
                    subject=candidate_subject,
                    message=candidate_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[interview.candidate.email],
                    fail_silently=False,
                )
                
                # Update notification status
                interview.manager_notified = True
                interview.candidate_notified = True
                interview.manager_notification_sent_at = timezone.now()
                interview.candidate_notification_sent_at = timezone.now()
                interview.save()
                
                sent_count += 1
            
            return {
                'success': True,
                'sent_count': sent_count,
                'message': f'Successfully sent {sent_count} interview notifications'
            }
            
        except Exception as e:
            logger.error(f"Error sending interview notifications: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def send_free_slot_offer(self, manager_email: str, candidate_email: str, vacancy_title: str, slot_start: datetime, duration_minutes: int = 60) -> Dict[str, Any]:
        """Send a free slot proposal to manager and candidate via email."""
        try:
            from django.core.mail import send_mail
            local_tz = timezone.get_current_timezone()
            start_local = slot_start.astimezone(local_tz)
            end_local = (slot_start + timedelta(minutes=duration_minutes)).astimezone(local_tz)

            subject_mgr = f"Free Interview Slot Available - {vacancy_title}"
            msg_mgr = f"A free slot is available at {start_local.strftime('%Y-%m-%d %H:%M')} - {end_local.strftime('%H:%M')} ({duration_minutes}m) with the following shortlisted candidate:\n{candidate_email}\n Please confirm to proceed."

            subject_cand = f"Interview Slot Proposal - {vacancy_title}"
            msg_cand = f"We propose an interview at {start_local.strftime('%Y-%m-%d %H:%M')} - {end_local.strftime('%H:%M')} ({duration_minutes}m).\nReply to confirm or request another time."

            send_mail(subject_mgr, msg_mgr, settings.DEFAULT_FROM_EMAIL, [manager_email], fail_silently=False)
            send_mail(subject_cand, msg_cand, settings.DEFAULT_FROM_EMAIL, [candidate_email], fail_silently=False)
            return {'success': True}
        except Exception as e:
            logger.error(f"Error sending free slot offer: {str(e)}")
            return {'success': False, 'error': str(e)}


    def send_feedback_request(self, interview) -> Dict[str, Any]:
        try:
            manager_email = interview.manager.email
            candidate_name = interview.candidate.full_name
            local_tz = timezone.get_current_timezone()
            start_local = interview.scheduled_at.astimezone(local_tz)
            end_local = (interview.scheduled_at + timedelta(minutes=interview.duration_minutes)).astimezone(local_tz)
            
            subject = f"Feedback Request: {interview.vacancy.title} - {candidate_name}"
            message = (
                f"Dear {interview.manager.get_full_name() or interview.manager.username},\n\n"
                f"Please provide feedback for your interview with {candidate_name}.\n\n"
                f"Interview Details:\n"
                f"- Date: {start_local.strftime('%Y-%m-%d')}\n"
                f"- Time: {start_local.strftime('%H:%M')} - {end_local.strftime('%H:%M')}\n"
                f"- Duration: {interview.duration_minutes} minutes\n\n"
                f"Please reply to this email to provide feedback.\n\n"
                f"Thank you!"

            )

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[manager_email],
                fail_silently=False,
            )

            interview.feedback_request_sent = True
            interview.feedback_request_sent_at = timezone.now()
            interview.save(update_fields=['feedback_request_sent', 'feedback_request_sent_at'])

            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

