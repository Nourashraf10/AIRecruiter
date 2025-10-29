from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from interviews.services import ZohoCalendarService, InterviewSchedulingService


class Command(BaseCommand):
    help = "Compute free slots via CalDAV, create InterviewSlot and Interview, and email notifications"

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Manager email (also used for CalDAV auth)')
        parser.add_argument('--password', required=True, help='CalDAV password')
        parser.add_argument('--caldav', required=True, help='CalDAV events collection URL')
        parser.add_argument('--candidate', required=True, help='Candidate email')
        parser.add_argument('--vacancy_id', type=int, required=True, help='Vacancy ID to attach interview to')
        parser.add_argument('--days', type=int, default=7, help='Search range in days from tomorrow')
        parser.add_argument('--duration', type=int, default=60, help='Slot duration in minutes')

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model
        from candidates.models import Candidate
        from vacancies.models import Vacancy
        from interviews.models import InterviewSlot, Interview

        username = options['username']
        password = options['password']
        caldav = options['caldav']
        candidate_email = options['candidate']
        vacancy_id = options['vacancy_id']
        days = options['days']
        duration = options['duration']

        # Fetch objects
        vacancy = Vacancy.objects.get(id=vacancy_id)
        manager = vacancy.manager
        candidate = Candidate.objects.filter(email=candidate_email).first()
        if not candidate:
            self.stdout.write(self.style.ERROR(f"Candidate with email {candidate_email} not found"))
            return

        # Find free slots
        start_date = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=days)

        cal = ZohoCalendarService(manager_email=username)
        cal.configure_basic_auth_caldav(caldav, username, password)
        slots = cal.get_available_slots(start_date, end_date, duration, manager_email=username)

        if not slots:
            self.stdout.write(self.style.WARNING("No free slots found"))
            return

        # Use earliest slot
        slot = slots[0]

        # Create InterviewSlot and Interview
        interview_slot = InterviewSlot.objects.create(
            vacancy=vacancy,
            manager=manager,
            start_time=slot['start_time'],
            end_time=slot['end_time'],
            is_available=False,
        )

        interview = Interview.objects.create(
            vacancy=vacancy,
            candidate=candidate,
            manager=manager,
            interview_slot=interview_slot,
            scheduled_at=slot['start_time'],
            duration_minutes=duration,
            status='scheduled',
        )

        # Email notifications via SMTP
        notify = InterviewSchedulingService()
        result = notify.send_interview_notifications([interview])

        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f"Interview scheduled and emails sent (Interview ID: {interview.id})"))
        else:
            self.stdout.write(self.style.WARNING(f"Interview scheduled but emails failed: {result.get('error')}"))


