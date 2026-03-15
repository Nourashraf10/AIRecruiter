"""
Check daily interview scheduling setup and explain why the task might not run.

The task is SENT by Celery Beat at the scheduled time and RUN by the Celery worker.
If you see nothing in the worker logs at the scheduled time, Beat likely didn't send the task.
"""

from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = "Check daily interview scheduling periodic task and show how to debug"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("📋 Daily interview scheduling check\n"))
        try:
            from django_celery_beat.models import PeriodicTask, CrontabSchedule

            task = (
                PeriodicTask.objects.filter(task="comms.tasks.daily_interview_scheduling_task")
                .select_related("crontab")
                .first()
            )
            if not task:
                self.stdout.write(
                    self.style.ERROR("❌ No periodic task found for 'comms.tasks.daily_interview_scheduling_task'.")
                )
                self.stdout.write(
                    "   Create it from the dashboard (set the time once) or run migrations and ensure comms.apps ready() ran."
                )
                return

            enabled = "✅ Enabled" if task.enabled else "❌ DISABLED (task will not run)"
            self.stdout.write(f"   Task: {task.name}")
            self.stdout.write(f"   Status: {enabled}")
            if not task.enabled:
                self.stdout.write(self.style.WARNING("   → Enable it in Django Admin > Periodic Tasks, or set the time again from the dashboard."))

            crontab = task.crontab
            if crontab:
                tz = getattr(crontab, "timezone", None) or "UTC"
                self.stdout.write(f"   Schedule: every day at {crontab.hour}:{crontab.minute} ({tz})")
                self.stdout.write("")
            else:
                self.stdout.write(self.style.WARNING("   No crontab set — task will never run. Set the time from the dashboard."))
                self.stdout.write("")

            self.stdout.write(self.style.SUCCESS("🔍 Where to look when nothing runs at the scheduled time\n"))
            self.stdout.write("1) CELERY BEAT sends the task at the scheduled time. Check Beat logs:")
            self.stdout.write("   docker compose logs celerybeat")
            self.stdout.write("   (or: docker-compose logs celerybeat)")
            self.stdout.write("")
            self.stdout.write("2) CELERY WORKER runs the task and logs '🕚 Starting daily interview scheduling task'. Check worker logs:")
            self.stdout.write("   docker compose logs celeryworker")
            self.stdout.write("")
            self.stdout.write("3) If Beat logs show nothing at your set time: ensure Beat is running and the task is Enabled.")
            self.stdout.write("   If Beat logs show the task being sent but worker shows nothing: ensure the worker is running and connected to the same broker (Redis).")
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("▶ Run the task now (to test and see worker logs):\n"))
            self.stdout.write("   docker compose exec web python manage.py test_celery --run-daily-task")
            self.stdout.write("   (or run inside the worker container: python manage.py daily_interview_scheduling)")
            self.stdout.write("")

        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"❌ django_celery_beat not available: {e}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
