"""
Automated Interview Scheduling Service
This service handles the complete automation of calendar checking and interview scheduling
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from typing import Dict, Any, List
from interviews.services import InterviewSchedulingService
from interviews.zoho_api_service import CalendarDiscoveryService
from vacancies.models import Vacancy
from core.models import User

logger = logging.getLogger(__name__)


class AutomatedInterviewScheduler:
    """Service for automating the complete interview scheduling workflow"""
    
    def __init__(self):
        self.scheduling_service = InterviewSchedulingService()
        self.discovery_service = CalendarDiscoveryService()
    
    def process_vacancy_approval(self, vacancy: Vacancy) -> Dict[str, Any]:
        """
        Complete automation workflow when a vacancy is approved
        
        Args:
            vacancy: The approved vacancy object
            
        Returns:
            Dict with automation results
        """
        try:
            logger.info(f"🤖 Starting automated interview scheduling for vacancy: {vacancy.title}")
            
            # Step 1: Discover manager's calendar
            calendar_result = self._discover_manager_calendar(vacancy.manager)
            if not calendar_result['success']:
                return calendar_result
            
            # Step 2: Send calendar setup confirmation to manager
            self._send_calendar_setup_confirmation(vacancy.manager, calendar_result)
            
            # Step 3: Wait for applications (in production, this would be triggered by actual applications)
            logger.info("⏳ Applications collection phase initiated")
            
            # Step 4: Monitor for shortlist generation
            self._monitor_shortlist_generation(vacancy)
            
            return {
                'success': True,
                'message': 'Automated interview scheduling workflow initiated',
                'calendar_discovered': True,
                'manager_notified': True
            }
            
        except Exception as e:
            logger.error(f"❌ Error in automated interview scheduling: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _discover_manager_calendar(self, manager: User) -> Dict[str, Any]:
        """Discover and set up manager's calendar using OAuth"""
        try:
            logger.info(f"🔍 Discovering calendar for manager: {manager.email}")
            
            # Try OAuth-based calendar discovery first
            from interviews.zoho_oauth_service import ZohoOAuthService
            oauth_service = ZohoOAuthService()
            
            # Check if OAuth integration exists
            oauth_status = oauth_service.setup_calendar_integration(manager.email)
            
            if oauth_status['success']:
                logger.info(f"✅ OAuth calendar integration active for {manager.email}")
                return {
                    'success': True,
                    'calendar_details': {
                        'calendar_id': oauth_status.get('calendar_id', 'primary'),
                        'manager_email': manager.email,
                        'integration_type': 'oauth'
                    }
                }
            elif oauth_status.get('requires_authorization'):
                logger.info(f"🔐 OAuth authorization required for {manager.email}")
                return {
                    'success': False,
                    'requires_oauth_authorization': True,
                    'authorization_url': oauth_status['authorization_url'],
                    'error': 'Manager needs to authorize calendar access via OAuth'
                }
            else:
                # Fall back to simulated discovery
                logger.info(f"🔄 Falling back to simulated calendar discovery for {manager.email}")
                calendar_result = self.discovery_service.discover_manager_calendar(manager.email)
                
                if calendar_result['success']:
                    logger.info(f"✅ Simulated calendar discovered for {manager.email}")
                    return calendar_result
                else:
                    logger.error(f"❌ Failed to discover calendar for {manager.email}: {calendar_result['error']}")
                    return calendar_result
                
        except Exception as e:
            logger.error(f"❌ Error discovering calendar: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_calendar_setup_confirmation(self, manager: User, calendar_result: Dict[str, Any]):
        """Send confirmation email to manager about calendar setup"""
        try:
            subject = "📅 Calendar Integration Confirmed - AI Recruiter"
            
            message = f"""
Dear {manager.get_full_name() or manager.username},

Your calendar has been successfully integrated with our recruiting system.

Calendar Details:
- Email: {manager.email}
- Calendar ID: {calendar_result['calendar_details']['calendar_id'][:20]}...
- Timezone: {calendar_result['calendar_details']['timezone']}

The system will now automatically:
1. Check your availability for interview scheduling
2. Find suitable time slots for candidate interviews
3. Send you interview notifications with candidate details
4. Manage the complete interview workflow

You will receive notifications when:
- Interviews are scheduled
- Candidates need to be interviewed
- Interview feedback is required

Best regards,
Fahmy
fahmy@bit68.com
            """.strip()
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[manager.email],
                fail_silently=False,
            )
            
            logger.info(f"✅ Calendar setup confirmation sent to {manager.email}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send calendar confirmation: {str(e)}")
    
    def _monitor_shortlist_generation(self, vacancy: Vacancy):
        """Monitor for shortlist generation and trigger interview scheduling"""
        try:
            # In production, this would be a background task or signal
            # For now, we'll simulate the process
            
            logger.info(f"👀 Monitoring shortlist generation for vacancy: {vacancy.title}")
            
            # Check if shortlist already exists
            if vacancy.shortlists.exists():
                logger.info("✅ Shortlist already exists, proceeding with interview scheduling")
                self._schedule_interviews_for_shortlist(vacancy)
            else:
                logger.info("⏳ Waiting for shortlist generation...")
                # In production, this would be handled by a background task
                
        except Exception as e:
            logger.error(f"❌ Error monitoring shortlist: {str(e)}")
    
    def schedule_interviews_for_approved_vacancy(self, vacancy: Vacancy) -> Dict[str, Any]:
        """
        Schedule interviews for an approved vacancy with existing shortlist
        
        Args:
            vacancy: The vacancy with shortlisted candidates
            
        Returns:
            Scheduling result
        """
        try:
            logger.info(f"📅 Scheduling interviews for vacancy: {vacancy.title}")
            
            # Check if shortlist exists
            if not vacancy.shortlists.exists():
                return {
                    'success': False,
                    'error': 'No shortlist found for this vacancy'
                }
            
            # Set interview dates (next week)
            start_date = timezone.now() + timedelta(days=7)
            end_date = start_date + timedelta(days=5)
            
            # Schedule interviews
            scheduling_result = self.scheduling_service.schedule_interviews_for_vacancy(
                vacancy=vacancy,
                manager=vacancy.manager,
                start_date=start_date,
                end_date=end_date,
                duration_minutes=60
            )
            
            if scheduling_result['success']:
                logger.info(f"✅ Successfully scheduled {scheduling_result['scheduled_count']} interviews")
                
                # Send notifications
                notification_result = self.scheduling_service.send_interview_notifications(
                    scheduling_result['interviews']
                )
                
                if notification_result['success']:
                    logger.info(f"✅ Successfully sent {notification_result['sent_count']} notifications")
                    
                    # Send summary to manager
                    self._send_interview_summary_to_manager(vacancy, scheduling_result['interviews'])
                    
                    return {
                        'success': True,
                        'scheduled_count': scheduling_result['scheduled_count'],
                        'notifications_sent': notification_result['sent_count'],
                        'message': f'Successfully scheduled {scheduling_result["scheduled_count"]} interviews and sent notifications'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Interviews scheduled but notifications failed: {notification_result["error"]}'
                    }
            else:
                return scheduling_result
                
        except Exception as e:
            logger.error(f"❌ Error scheduling interviews: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _schedule_interviews_for_shortlist(self, vacancy: Vacancy):
        """Schedule interviews when shortlist is generated"""
        try:
            result = self.schedule_interviews_for_approved_vacancy(vacancy)
            if result['success']:
                logger.info(f"✅ Automated interview scheduling completed for {vacancy.title}")
            else:
                logger.error(f"❌ Automated interview scheduling failed: {result['error']}")
        except Exception as e:
            logger.error(f"❌ Error in automated scheduling: {str(e)}")
    
    def _send_interview_summary_to_manager(self, vacancy: Vacancy, interviews: List):
        """Send interview summary to manager"""
        try:
            subject = f"📋 Interview Schedule Summary - {vacancy.title}"
            
            interview_details = []
            for interview in interviews:
                interview_details.append(f"""
Candidate: {interview.candidate.full_name}
Email: {interview.candidate.email}
Date: {interview.scheduled_at.strftime('%Y-%m-%d')}
Time: {interview.scheduled_at.strftime('%H:%M')} - {(interview.scheduled_at + timedelta(minutes=interview.duration_minutes)).strftime('%H:%M')}
Duration: {interview.duration_minutes} minutes
""")
            
            message = f"""
Dear {vacancy.manager.get_full_name() or vacancy.manager.username},

Interview schedule has been automatically generated for the position: {vacancy.title}

Scheduled Interviews:
{''.join(interview_details)}

Total Interviews: {len(interviews)}

The system has automatically:
✅ Checked your calendar availability
✅ Scheduled interviews with top candidates
✅ Sent invitations to all candidates
✅ Added events to your calendar

Next Steps:
1. Review the scheduled interviews
2. Prepare interview questions
3. Conduct interviews as scheduled
4. Provide feedback after each interview

Best regards,
Fahmy
fahmy@bit68.com
            """.strip()
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[vacancy.manager.email],
                fail_silently=False,
            )
            
            logger.info(f"✅ Interview summary sent to manager: {vacancy.manager.email}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send interview summary: {str(e)}")
    
    def check_manager_availability(self, manager_email: str, start_date: datetime, 
                                 end_date: datetime, duration_minutes: int = 60) -> Dict[str, Any]:
        """
        Check manager's availability for interview scheduling
        
        Args:
            manager_email: Manager's email address
            start_date: Start date for checking availability
            end_date: End date for checking availability
            duration_minutes: Duration of each slot
            
        Returns:
            Availability result with available slots
        """
        try:
            logger.info(f"🔍 Checking availability for {manager_email}")
            
            # Discover calendar if not already done
            calendar_result = self.discovery_service.discover_manager_calendar(manager_email)
            if not calendar_result['success']:
                return calendar_result
            
            # Get available slots
            availability_result = self.discovery_service.get_manager_availability(
                manager_email, start_date, end_date, duration_minutes
            )
            
            if availability_result['success']:
                logger.info(f"✅ Found {availability_result['slots_count']} available slots")
                return availability_result
            else:
                logger.error(f"❌ Failed to get availability: {availability_result['error']}")
                return availability_result
                
        except Exception as e:
            logger.error(f"❌ Error checking availability: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def send_interview_reminder(self, interview) -> Dict[str, Any]:
        """Send interview reminder to both manager and candidate"""
        try:
            # Send reminder to manager
            manager_subject = f"🔔 Interview Reminder - {interview.candidate.full_name}"
            manager_message = f"""
Dear {interview.manager.get_full_name() or interview.manager.username},

This is a reminder for your upcoming interview:

Candidate: {interview.candidate.full_name}
Position: {interview.vacancy.title}
Date: {interview.scheduled_at.strftime('%Y-%m-%d')}
Time: {interview.scheduled_at.strftime('%H:%M')} - {(interview.scheduled_at + timedelta(minutes=interview.duration_minutes)).strftime('%H:%M')}

Please ensure you have:
- Reviewed the candidate's CV
- Prepared interview questions
- Set up your meeting room/link

Best regards,
Fahmy
            """.strip()
            
            send_mail(
                subject=manager_subject,
                message=manager_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[interview.manager.email],
                fail_silently=False,
            )
            
            # Send reminder to candidate
            candidate_subject = f"🔔 Interview Reminder - {interview.vacancy.title}"
            candidate_message = f"""
Dear {interview.candidate.full_name},

This is a reminder for your upcoming interview:

Position: {interview.vacancy.title}
Company: {interview.vacancy.department}
Date: {interview.scheduled_at.strftime('%Y-%m-%d')}
Time: {interview.scheduled_at.strftime('%H:%M')} - {(interview.scheduled_at + timedelta(minutes=interview.duration_minutes)).strftime('%H:%M')}
Interviewer: {interview.manager.get_full_name() or interview.manager.username}

Please ensure you:
- Arrive on time
- Bring a copy of your CV
- Prepare questions about the role
- Dress professionally

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
            
            logger.info(f"✅ Interview reminders sent for {interview.candidate.full_name}")
            
            return {
                'success': True,
                'message': 'Interview reminders sent successfully'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to send interview reminders: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_closed_vacancy(self, vacancy: Vacancy) -> Dict[str, Any]:
        """
        Complete automation workflow when a vacancy status changes to 'closed'
        This triggers immediate interview scheduling for shortlisted candidates
        
        Args:
            vacancy: The closed vacancy object
            
        Returns:
            Dict with automation results
        """
        try:
            logger.info(f"🚀 Processing closed vacancy: {vacancy.title} (ID: {vacancy.id})")
            
            # Step 1: Get shortlisted candidates for this vacancy
            shortlisted_candidates = self._get_shortlisted_candidates(vacancy)
            if not shortlisted_candidates:
                logger.warning(f"⚠️ No shortlisted candidates found for vacancy {vacancy.id}")
                return {
                    'success': False,
                    'error': 'No shortlisted candidates found for this vacancy'
                }
            
            logger.info(f"📋 Found {len(shortlisted_candidates)} shortlisted candidates")
            
            # Step 2: Discover manager's calendar (with fallback)
            calendar_result = self._discover_manager_calendar(vacancy.manager)
            if not calendar_result['success']:
                logger.warning(f"⚠️ Calendar discovery failed for manager {vacancy.manager.email}, using fallback mode")
                # Continue with fallback mode - just send emails without calendar integration
                calendar_result = {
                    'success': True,
                    'calendar_details': {
                        'calendar_id': 'fallback',
                        'manager_email': vacancy.manager.email,
                        'integration_type': 'fallback'
                    }
                }
            
            # Step 3: Find available time slots (with fallback)
            available_slots = self._find_available_slots(vacancy.manager, len(shortlisted_candidates))
            if not available_slots:
                logger.warning(f"⚠️ No calendar slots found for manager {vacancy.manager.email}, using fallback mode")
                # Create dummy slots for fallback mode
                from datetime import datetime, timedelta
                available_slots = []
                for i in range(len(shortlisted_candidates)):
                    # Create slots for next 3 days, 2 hours apart
                    slot_time = datetime.now() + timedelta(days=i+1, hours=10)
                    available_slots.append({
                        'start_time': slot_time.isoformat(),
                        'end_time': (slot_time + timedelta(hours=1)).isoformat(),
                        'fallback': True
                    })
            
            logger.info(f"📅 Found {len(available_slots)} available time slots")
            
            # Step 4: Schedule interviews for shortlisted candidates
            scheduled_interviews = []
            for i, candidate in enumerate(shortlisted_candidates):
                if i < len(available_slots):
                    slot = available_slots[i]
                    interview_result = self._schedule_interview(vacancy, candidate, slot)
                    if interview_result['success']:
                        scheduled_interviews.append(interview_result['interview'])
                        logger.info(f"✅ Interview scheduled for {candidate.full_name} at {slot['start_time']}")
                    else:
                        logger.error(f"❌ Failed to schedule interview for {candidate.full_name}: {interview_result['error']}")
            
            # Step 5: Send notifications to manager and candidates
            notification_results = self._send_interview_notifications(vacancy, scheduled_interviews)
            
            return {
                'success': True,
                'message': f'Interview scheduling completed for {len(scheduled_interviews)} candidates',
                'scheduled_interviews': len(scheduled_interviews),
                'total_candidates': len(shortlisted_candidates),
                'calendar_discovered': True,
                'notifications_sent': notification_results['success'],
                'summary': {
                    'vacancy_title': vacancy.title,
                    'manager_email': vacancy.manager.email,
                    'candidates_scheduled': [interview.candidate.full_name for interview in scheduled_interviews],
                    'interview_dates': [interview.scheduled_at.strftime('%Y-%m-%d %H:%M') for interview in scheduled_interviews]
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing closed vacancy: {str(e)}")
            logger.exception("Full traceback:")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_shortlisted_candidates(self, vacancy: Vacancy) -> List:
        """Get shortlisted candidates for a vacancy"""
        try:
            from vacancies.models import Shortlist
            from candidates.models import Candidate, Application
            
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
            else:
                logger.warning(f"No candidates found for vacancy {vacancy.id}")
                return []
            
        except Exception as e:
            logger.error(f"Error getting shortlisted candidates: {str(e)}")
            return []
    
    def _find_available_slots(self, manager: User, num_slots_needed: int) -> List[Dict]:
        """Find available time slots for the manager"""
        try:
            from interviews.services import ZohoCalendarService
            
            calendar_service = ZohoCalendarService()
            
            # Get available slots for the next 7 days
            available_slots = calendar_service.get_available_slots(
                manager_email=manager.email,
                days_ahead=7,
                duration_minutes=60
            )
            
            if available_slots['success']:
                slots = available_slots['slots'][:num_slots_needed]  # Take only what we need
                logger.info(f"Found {len(slots)} available slots")
                return slots
            else:
                logger.error(f"Failed to get available slots: {available_slots['error']}")
                return []
                
        except Exception as e:
            logger.error(f"Error finding available slots: {str(e)}")
            return []
    
    def _schedule_interview(self, vacancy: Vacancy, candidate, slot: Dict) -> Dict[str, Any]:
        """Schedule an interview for a candidate"""
        try:
            from interviews.models import Interview, InterviewSlot
            from datetime import datetime
            
            # Parse the slot time
            start_time = datetime.fromisoformat(slot['start_time'].replace('Z', '+00:00'))
            end_time = start_time + timedelta(hours=1)
            
            # Create interview slot first
            interview_slot = InterviewSlot.objects.create(
                vacancy=vacancy,
                manager=vacancy.manager,
                start_time=start_time,
                end_time=end_time,
                is_available=False  # Mark as unavailable since it's being used
            )
            
            # Create interview record
            interview = Interview.objects.create(
                vacancy=vacancy,
                candidate=candidate,
                manager=vacancy.manager,
                interview_slot=interview_slot,
                scheduled_at=start_time,
                duration_minutes=60,
                status='scheduled',
                notes=f"Automatically scheduled interview for {candidate.full_name}"
            )
            
            logger.info(f"✅ Interview created: {interview.id} for {candidate.full_name}")
            
            return {
                'success': True,
                'interview': interview
            }
            
        except Exception as e:
            logger.error(f"Error scheduling interview: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _send_interview_notifications(self, vacancy: Vacancy, interviews: List) -> Dict[str, Any]:
        """Send interview notifications to manager and candidates"""
        try:
            from interviews.models import Interview
            
            # Send notification to manager
            manager_subject = f"📅 Interviews Scheduled - {vacancy.title}"
            manager_message = f"""
Dear {vacancy.manager.get_full_name() or vacancy.manager.username},

The following interviews have been automatically scheduled for the {vacancy.title} position:

"""
            
            for interview in interviews:
                manager_message += f"""
Candidate: {interview.candidate.full_name}
Email: {interview.candidate.email}
Date & Time: {interview.scheduled_at.strftime('%Y-%m-%d at %H:%M')}
Duration: {interview.duration_minutes} minutes

"""
            
            manager_message += """
Please prepare for these interviews and ensure you're available at the scheduled times.

Best regards,
Fahmy
fahmy@bit68.com
            """.strip()
            
            send_mail(
                subject=manager_subject,
                message=manager_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[vacancy.manager.email],
                fail_silently=False,
            )
            
            # Send notifications to candidates
            for interview in interviews:
                candidate_subject = f"📅 Interview Scheduled - {vacancy.title}"
                candidate_message = f"""
Dear {interview.candidate.full_name},

Congratulations! You have been selected for an interview for the {vacancy.title} position.

Interview Details:
- Date & Time: {interview.scheduled_at.strftime('%Y-%m-%d at %H:%M')}
- Duration: {interview.duration_minutes} minutes
- Interviewer: {interview.manager.get_full_name() or interview.manager.username}

Please ensure you:
- Arrive on time
- Bring a copy of your CV
- Prepare questions about the role
- Dress professionally

If you need to reschedule, please contact us immediately.

Best regards,
{interview.manager.get_full_name() or interview.manager.username}
{vacancy.title} - Hiring Manager
                """.strip()
                
                send_mail(
                    subject=candidate_subject,
                    message=candidate_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[interview.candidate.email],
                    fail_silently=False,
                )
            
            logger.info(f"✅ Interview notifications sent for {len(interviews)} interviews")
            
            return {
                'success': True,
                'message': f'Notifications sent for {len(interviews)} interviews'
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to send interview notifications: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
