"""
Management command to test Celery setup and tasks
"""

from django.core.management.base import BaseCommand
from comms.tasks import test_celery_connection_task, daily_interview_scheduling_task
import time


class Command(BaseCommand):
    help = 'Test Celery setup and run tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-connection',
            action='store_true',
            help='Test basic Celery connection',
        )
        parser.add_argument(
            '--run-daily-task',
            action='store_true',
            help='Run the daily interview scheduling task manually',
        )

    def handle(self, *args, **options):
        if options['test_connection']:
            self.test_connection()
        elif options['run_daily_task']:
            self.run_daily_task()
        else:
            self.stdout.write(
                self.style.WARNING('Please specify --test-connection or --run-daily-task')
            )

    def test_connection(self):
        """Test basic Celery connection"""
        self.stdout.write(
            self.style.SUCCESS('🧪 Testing Celery connection...')
        )
        
        try:
            # Send the test task
            result = test_celery_connection_task.delay()
            
            self.stdout.write('⏳ Waiting for task to complete...')
            
            # Wait for result (with timeout)
            try:
                task_result = result.get(timeout=30)
                if task_result.get('success'):
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ {task_result.get('message')}")
                    )
                    self.stdout.write(f"📅 Timestamp: {task_result.get('timestamp')}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Task failed: {task_result.get('error', 'Unknown error')}")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Task timeout or error: {str(e)}")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to send task: {str(e)}")
            )

    def run_daily_task(self):
        """Run the daily interview scheduling task manually"""
        self.stdout.write(
            self.style.SUCCESS('🕚 Running daily interview scheduling task...')
        )
        
        try:
            # Send the daily task
            result = daily_interview_scheduling_task.delay()
            
            self.stdout.write('⏳ Waiting for task to complete...')
            
            # Wait for result (with timeout)
            try:
                task_result = result.get(timeout=120)  # 2 minutes timeout
                if task_result.get('success'):
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ {task_result.get('message')}")
                    )
                    
                    # Display summary
                    summary = task_result.get('summary', {})
                    if summary:
                        self.stdout.write(f"📊 Summary:")
                        self.stdout.write(f"   - Vacancies checked: {summary.get('vacancies_checked', 0)}")
                        self.stdout.write(f"   - Vacancies processed: {summary.get('vacancies_processed', 0)}")
                        self.stdout.write(f"   - Emails sent: {summary.get('total_emails_sent', 0)}")
                        self.stdout.write(f"   - Timestamp: {summary.get('timestamp', 'N/A')}")
                else:
                    self.stdout.write(
                        self.style.ERROR(f"❌ Task failed: {task_result.get('error', 'Unknown error')}")
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"❌ Task timeout or error: {str(e)}")
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to send task: {str(e)}")
            )
