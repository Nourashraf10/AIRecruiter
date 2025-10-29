from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from interviews.services import ZohoCalendarService


class Command(BaseCommand):
    help = "Test Zoho CalDAV free slots computation with provided credentials"

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--password', required=True)
        parser.add_argument('--caldav', required=True, help='CalDAV events collection URL')
        parser.add_argument('--days', type=int, default=7, help='Range in days from tomorrow')
        parser.add_argument('--duration', type=int, default=60, help='Slot duration minutes')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        caldav = options['caldav']
        days = options['days']
        duration = options['duration']

        start_date = (timezone.now() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=days)

        svc = ZohoCalendarService(manager_email=username)
        svc.configure_basic_auth_caldav(caldav, username, password)

        slots = svc.get_available_slots(start_date, end_date, duration, manager_email=username)

        self.stdout.write(self.style.SUCCESS(f"Found {len(slots)} free slots"))
        for s in slots[:10]:
            self.stdout.write(f"- {s['start_time'].astimezone(timezone.get_current_timezone())} -> {s['end_time'].astimezone(timezone.get_current_timezone())}")


