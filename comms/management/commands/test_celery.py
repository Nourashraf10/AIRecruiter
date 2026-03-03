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
        parser.add_argument(
            '--direct',
            action='store_true',
            help='With --run-daily-task: run in this process (no Celery). Use if worker never returns result.',
        )
        parser.add_argument(
            '--no-wait',
            action='store_true',
            help='With --run-daily-task: send task to worker and exit immediately (check worker logs for result)',
        )

    def handle(self, *args, **options):
        if options['test_connection']:
            self.test_connection()
        elif options['run_daily_task']:
            self.run_daily_task(no_wait=options.get('no_wait', False), direct=options.get('direct', False))
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

    def run_daily_task(self, no_wait=False, direct=False):
        """Run the daily interview scheduling task manually (via Celery or directly in-process)."""
        if direct:
            self._run_daily_task_direct()
            return
        self.stdout.write(
            self.style.SUCCESS('🕚 Running daily interview scheduling task (via Celery worker)...')
        )
        try:
            result = daily_interview_scheduling_task.delay()
            self.stdout.write(f"   Task id: {result.id}")
            if no_wait:
                self.stdout.write(
                    self.style.SUCCESS('✅ Task sent. Check worker logs: docker compose logs -f celeryworker')
                )
                return
            self.stdout.write('⏳ Waiting for task to complete (up to 5 min)...')
            try:
                task_result = result.get(timeout=300)
                if task_result.get('success'):
                    self.stdout.write(
                        self.style.SUCCESS(f"✅ {task_result.get('message')}")
                    )
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
                self.stdout.write(
                    self.style.WARNING(
                        '   Worker may not be running or not returning results. '
                        'Run in this process instead: python manage.py test_celery --run-daily-task --direct'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Failed to send task: {str(e)}")
            )

    def _run_daily_task_direct(self):
        """Run daily interview scheduling in this process (no Celery). Same logic as Celery task."""
        self.stdout.write(
            self.style.SUCCESS('🕚 Running daily interview scheduling in this process (no worker)...')
        )
        try:
            from comms.daily_automation_service import DailyAutomationService
            automation_service = DailyAutomationService()
            result = automation_service.process_daily_interview_scheduling()
            if result.get('success'):
                self.stdout.write(self.style.SUCCESS(f"✅ {result.get('message')}"))
                summary = result.get('summary', {})
                if summary:
                    self.stdout.write(f"📊 Summary:")
                    self.stdout.write(f"   - Vacancies checked: {summary.get('vacancies_checked', 0)}")
                    self.stdout.write(f"   - Vacancies processed: {summary.get('vacancies_processed', 0)}")
                    self.stdout.write(f"   - Emails sent: {summary.get('total_emails_sent', 0)}")
            else:
                self.stdout.write(
                    self.style.ERROR(f"❌ Failed: {result.get('error', 'Unknown error')}")
                )
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {str(e)}"))
