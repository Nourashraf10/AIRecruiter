"""
Django management command for daily interview scheduling
Run this command daily at 11:59 PM to process shortlisted candidates
"""

from django.core.management.base import BaseCommand
from comms.daily_automation_service import DailyAutomationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process daily interview scheduling for shortlisted candidates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without sending emails (for testing)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🕚 Starting daily interview scheduling...')
        )
        
        try:
            # Initialize the daily automation service
            automation_service = DailyAutomationService()
            
            # Process daily interview scheduling
            result = automation_service.process_daily_interview_scheduling()
            
            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ {result['message']}")
                )
                
                # Display summary
                summary = result.get('summary', {})
                self.stdout.write(f"📊 Summary:")
                self.stdout.write(f"   - Vacancies checked: {summary.get('vacancies_checked', 0)}")
                self.stdout.write(f"   - Vacancies processed: {summary.get('vacancies_processed', 0)}")
                self.stdout.write(f"   - Emails sent: {summary.get('total_emails_sent', 0)}")
                self.stdout.write(f"   - Timestamp: {summary.get('timestamp', 'N/A')}")
                
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Daily interview scheduling failed: {result.get('error', 'Unknown error')}")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Error running daily interview scheduling: {str(e)}")
            )
            logger.exception("Full traceback:")

