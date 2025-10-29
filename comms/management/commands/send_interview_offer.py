from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from interviews.services import ZohoCalendarService, InterviewSchedulingService


class Command(BaseCommand):
    help = "Compute free slots via CalDAV and email a proposed interview slot to manager and candidate"

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Manager email (also used for CalDAV auth)')
        parser.add_argument('--password', required=True, help='CalDAV password')
        parser.add_argument('--caldav', required=True, help='CalDAV events collection URL')
        parser.add_argument('--candidate', required=True, help='Candidate email to receive the proposal')
        parser.add_argument('--vacancy', required=True, help='Vacancy title for email context')
        parser.add_argument('--days', type=int, default=7, help='Search range in days from tomorrow')
        parser.add_argument('--duration', type=int, default=60, help='Slot duration in minutes')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        caldav = options['caldav']
        candidate_email = options['candidate']
        vacancy_title = options['vacancy']
        days = options['days']
        duration = options['duration']

        start_date = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=days)

        cal = ZohoCalendarService(manager_email=username)
        cal.configure_basic_auth_caldav(caldav, username, password)

        slots = cal.get_available_slots(start_date, end_date, duration, manager_email=username)
        if not slots:
            self.stdout.write(self.style.WARNING("No free slots found"))
            return

        slot = slots[0]

        notify = InterviewSchedulingService()
        result = notify.send_free_slot_offer(
            manager_email=username,
            candidate_email=candidate_email,
            vacancy_title=vacancy_title,
            slot_start=slot['start_time'],
            duration_minutes=duration,
        )

        if result.get('success'):
            self.stdout.write(self.style.SUCCESS("Free slot proposal emailed successfully"))
        else:
            self.stdout.write(self.style.ERROR(f"Failed to send emails: {result.get('error')}"))


