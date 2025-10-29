from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json

class Command(BaseCommand):
    help = "Set up the periodic task for checking feedback requests"

    def handle(self, *args, **options):
        # Create or get the crontab schedule for every minute
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute='*',
            hour='*',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        if created:
            self.stdout.write("Created crontab schedule for every minute")
        else:
            self.stdout.write("Found existing crontab schedule for every minute")

        # Create or update the periodic task
        task, created = PeriodicTask.objects.get_or_create(
            name='Check and Send Feedback Requests',
            defaults={
                'task': 'interviews.tasks.check_and_send_feedback_requests',
                'crontab': schedule,
                'enabled': True,
                'args': json.dumps([]),
                'kwargs': json.dumps({}),
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS("✅ Created periodic task: Check and Send Feedback Requests")
            )
        else:
            # Update existing task to make sure it's enabled
            task.enabled = True
            task.crontab = schedule
            task.save()
            self.stdout.write(
                self.style.SUCCESS("✅ Updated periodic task: Check and Send Feedback Requests")
            )
        
        self.stdout.write(f"Task: {task.task}")
        self.stdout.write(f"Schedule: Every minute")
        self.stdout.write(f"Enabled: {task.enabled}")
