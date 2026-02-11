from django.apps import AppConfig


class CommsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'comms'

    def ready(self):
        """
        Ensure the daily interview scheduling periodic task exists when Django starts.

        This is mainly to support django_celery_beat's DatabaseScheduler: if the
        PeriodicTask row for `comms.tasks.daily_interview_scheduling_task` does not
        exist yet, we create it with a default crontab schedule (matching settings).

        - If the task already exists (e.g. you edited it in admin or via dashboard),
          we leave it untouched.
        - If django_celery_beat is not installed or the DB isn't ready yet
          (e.g. during initial migration), we silently skip.
        """
        try:
            from django.conf import settings
            from django.apps import apps

            # Only run if django_celery_beat is installed
            if not apps.is_installed("django_celery_beat"):
                return

            from django_celery_beat.models import PeriodicTask, CrontabSchedule

            # Default time taken from CELERY_BEAT_SCHEDULE in settings.py
            default_hour = 0
            default_minute = 56

            # Create or reuse a crontab schedule (timezone uses model default)
            schedule, _ = CrontabSchedule.objects.get_or_create(
                minute=str(default_minute),
                hour=str(default_hour),
                day_of_week="*",
                day_of_month="*",
                month_of_year="*",
            )

            # Ensure the periodic task row exists; do not overwrite existing config
            PeriodicTask.objects.get_or_create(
                task="comms.tasks.daily_interview_scheduling_task",
                defaults={
                    "name": "Daily Interview Scheduling",
                    "crontab": schedule,
                    "enabled": True,
                },
            )

        except Exception:
            # Swallow all errors here to avoid breaking Django startup
            return

