from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Interview
from .services import InterviewSchedulingService
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, name="interviews.tasks.send_feedback_request_task")
def send_feedback_request_task(self, interview_id):
    """
    Celery task to send feedback request email to manager after interview ends.
    
    Args:
        interview_id (int): The ID of the interview to send feedback request for
    """
    logger.info(f"Starting feedback request task for interview {interview_id}")
    
    try:
        interview = Interview.objects.get(id=interview_id)
        
        if interview.feedback_request_sent:
            logger.info(f"Feedback already sent for interview {interview_id}")
            return {'success': True, 'message': 'Feedback already sent'}
        
        scheduling_service = InterviewSchedulingService()
        result = scheduling_service.send_feedback_request(interview)
        
        if result.get('success'):
            logger.info(f"Feedback request sent successfully for interview {interview_id}")
        else:
            logger.error(f"Failed to send feedback request for interview {interview_id}: {result.get('error')}")
        
        return result
        
    except Interview.DoesNotExist:
        error_msg = f"Interview with ID {interview_id} not found"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
        
    except Exception as e:
        error_msg = f"Unexpected error in feedback request task: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

@shared_task(bind=True, name="interviews.tasks.check_and_send_feedback_requests")
def check_and_send_feedback_requests(self):
    """
    Periodic task that checks for interviews that need feedback requests sent.
    This runs every minute and finds interviews that have ended but haven't had feedback requested.
    """
    logger.info("Checking for interviews that need feedback requests")
    
    try:
        now = timezone.now()
        
        # Find interviews that:
        # 1. Are scheduled (not cancelled)
        # 2. Have ended (scheduled_at + duration <= now)
        # 3. Haven't had feedback requested yet
        # 4. Are within the last 24 hours (to avoid processing very old interviews)
        
        cutoff_time = now - timedelta(hours=24)
        
        interviews_needing_feedback = Interview.objects.filter(
            status='scheduled',
            scheduled_at__gte=cutoff_time,
            feedback_request_sent=False
        )
        
        sent_count = 0
        for interview in interviews_needing_feedback:
            # Calculate when the interview ended
            interview_end_time = interview.scheduled_at + timedelta(minutes=interview.duration_minutes)
            
            # If the interview has ended, send feedback request
            if interview_end_time <= now:
                logger.info(f"Interview {interview.id} ended at {interview_end_time}, sending feedback request")
                
                scheduling_service = InterviewSchedulingService()
                result = scheduling_service.send_feedback_request(interview)
                
                if result.get('success'):
                    sent_count += 1
                    logger.info(f"Feedback request sent for interview {interview.id}")
                else:
                    logger.error(f"Failed to send feedback request for interview {interview.id}: {result.get('error')}")
        
        logger.info(f"Feedback request check completed. Sent {sent_count} feedback requests.")
        return {'success': True, 'sent_count': sent_count}
        
    except Exception as e:
        error_msg = f"Error in feedback request check: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

@shared_task(bind=True, name="interviews.tasks.process_manager_feedback_emails")
def process_manager_feedback_emails(self):
    """
    Periodic task to process manager feedback emails
    """
    logger.info("Processing manager feedback emails")
    
    try:
        from zoho_mail_monitor import ZohoMailMonitor
        
        monitor = ZohoMailMonitor()
        count = monitor.process_manager_feedback_emails_once()
        
        logger.info(f"Manager feedback emails processed: {count}")
        return {'success': True, 'count': count}
        
    except Exception as e:
        error_msg = f"Error processing manager feedback emails: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}

@shared_task(bind=True, name="interviews.tasks.process_questionnaire_reply_emails")
def process_questionnaire_reply_emails(self):
    """
    Periodic task to process candidate questionnaire reply emails
    """
    logger.info("Processing candidate questionnaire reply emails")
    
    try:
        from zoho_mail_monitor import ZohoMailMonitor
        
        monitor = ZohoMailMonitor()
        count = monitor.process_questionnaire_reply_emails_once()
        
        logger.info(f"Questionnaire reply emails processed: {count}")
        return {'success': True, 'count': count}
        
    except Exception as e:
        error_msg = f"Error processing questionnaire reply emails: {str(e)}"
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
