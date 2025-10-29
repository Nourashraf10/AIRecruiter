"""
Celery tasks for the AI Recruiter application
"""

import logging
from celery import shared_task
from django.utils import timezone
from .daily_automation_service import DailyAutomationService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def daily_interview_scheduling_task(self):
    """
    Celery task to run daily interview scheduling at 11:59 PM
    
    This task:
    1. Finds vacancies in 'collecting_applications' status
    2. Picks the next shortlisted candidate who hasn't been scheduled
    3. Finds a free slot in the manager's calendar
    4. Creates InterviewSlot and Interview records
    5. Sends interview emails to manager and candidate
    6. Sends questionnaire email to the candidate
    """
    try:
        logger.info(f"🕚 Starting daily interview scheduling task at {timezone.now()}")
        
        # Initialize the daily automation service
        automation_service = DailyAutomationService()
        
        # Process daily interview scheduling
        result = automation_service.process_daily_interview_scheduling()
        
        if result['success']:
            logger.info(f"✅ Daily interview scheduling completed: {result['message']}")
            
            # Log summary
            summary = result.get('summary', {})
            logger.info(f"📊 Summary: {summary.get('vacancies_processed', 0)} vacancies processed, "
                       f"{summary.get('total_emails_sent', 0)} emails sent")
            
            return {
                'success': True,
                'message': result['message'],
                'summary': summary
            }
        else:
            logger.error(f"❌ Daily interview scheduling failed: {result.get('error', 'Unknown error')}")
            return {
                'success': False,
                'error': result.get('error', 'Unknown error')
            }
            
    except Exception as exc:
        logger.error(f"❌ Daily interview scheduling task failed: {str(exc)}")
        
        # Retry the task with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_feedback_requests_task(self):
    """
    Celery task to send feedback request emails for completed interviews
    
    This task:
    1. Finds interviews that have ended but haven't had feedback requested
    2. Sends feedback request emails to managers
    3. Updates the interview records
    """
    try:
        logger.info(f"📧 Starting feedback requests task at {timezone.now()}")
        
        from interviews.models import Interview, InterviewFeedback
        from interviews.services import InterviewSchedulingService
        from datetime import timedelta
        
        now = timezone.now()
        window_start = now - timedelta(hours=24)
        
        # Find interviews that need feedback requests
        due_interviews = []
        qs = Interview.objects.select_related('candidate', 'manager', 'vacancy') \
                              .filter(status='scheduled', scheduled_at__gte=window_start)
        
        for interview in qs:
            end_time = interview.scheduled_at + timedelta(minutes=interview.duration_minutes)
            if end_time <= now and not interview.feedback_request_sent:
                # Check if feedback already provided
                has_feedback = InterviewFeedback.objects.filter(interview=interview).exists()
                if not has_feedback:
                    due_interviews.append(interview)
        
        if not due_interviews:
            logger.info("ℹ️ No due feedback requests found")
            return {'success': True, 'message': 'No due feedback requests found', 'sent_count': 0}
        
        # Send feedback requests
        service = InterviewSchedulingService()
        sent_count = 0
        
        for interview in due_interviews:
            result = service.send_feedback_request(interview)
            if result.get('success'):
                sent_count += 1
                logger.info(f"✅ Feedback request sent for interview {interview.id}")
            else:
                logger.error(f"❌ Failed to send feedback request for interview {interview.id}: {result.get('error')}")
        
        logger.info(f"📧 Feedback requests task completed: {sent_count} requests sent")
        
        return {
            'success': True,
            'message': f'Feedback requests sent: {sent_count}',
            'sent_count': sent_count
        }
        
    except Exception as exc:
        logger.error(f"❌ Feedback requests task failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def test_celery_connection_task(self):
    """
    Simple test task to verify Celery is working
    """
    try:
        logger.info("🧪 Testing Celery connection...")
        return {
            'success': True,
            'message': 'Celery is working!',
            'timestamp': timezone.now().isoformat()
        }
    except Exception as exc:
        logger.error(f"❌ Celery test failed: {str(exc)}")
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, name="comms.tasks.check_linkedin_inbox")
def check_linkedin_inbox(self):
    try:
        from zoho_mail_monitor import ZohoMailMonitor
        monitor = ZohoMailMonitor()
        count = monitor.process_linkedin_applications_once()
        logger.info(f"LinkedIn applications processed: {count}")
        return {'success': True, 'count': count}
    except Exception as e:
        logger.exception("LinkedIn inbox check failed")
        return {'success': False, 'error': str(e)}
