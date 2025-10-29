"""
Django management command to manually schedule interviews for a vacancy
Usage: python manage.py schedule_interviews --vacancy-id 1
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import datetime, timedelta
from vacancies.models import Vacancy
from comms.automation_service import AutomatedInterviewScheduler


class Command(BaseCommand):
    help = 'Schedule interviews for a vacancy with shortlisted candidates'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vacancy-id',
            type=int,
            help='ID of the vacancy to schedule interviews for',
            required=True
        )
        parser.add_argument(
            '--start-days',
            type=int,
            default=7,
            help='Number of days from now to start scheduling (default: 7)'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=5,
            help='Number of days for scheduling window (default: 5)'
        )
        parser.add_argument(
            '--interview-duration',
            type=int,
            default=60,
            help='Duration of each interview in minutes (default: 60)'
        )

    def handle(self, *args, **options):
        vacancy_id = options['vacancy_id']
        start_days = options['start_days']
        duration_days = options['duration']
        interview_duration = options['interview_duration']

        try:
            # Get the vacancy
            vacancy = Vacancy.objects.get(id=vacancy_id)
            self.stdout.write(f"📋 Processing vacancy: {vacancy.title}")
            self.stdout.write(f"👤 Manager: {vacancy.manager.email}")
            self.stdout.write(f"🏢 Department: {vacancy.department}")

            # Check if vacancy is approved
            if vacancy.status != 'approved':
                raise CommandError(f"Vacancy {vacancy_id} is not approved. Current status: {vacancy.status}")

            # Check if shortlist exists
            shortlist_count = vacancy.shortlists.count()
            if shortlist_count == 0:
                self.stdout.write("⚠️ No shortlist found. Generating shortlist...")
                shortlist_count = vacancy.generate_shortlist()
                if shortlist_count == 0:
                    raise CommandError("No candidates available for shortlisting")
                self.stdout.write(f"✅ Generated shortlist with {shortlist_count} candidates")

            self.stdout.write(f"🎯 Found {shortlist_count} shortlisted candidates")

            # Initialize automation service
            automation_service = AutomatedInterviewScheduler()

            # Check manager availability
            start_date = timezone.now() + timedelta(days=start_days)
            end_date = start_date + timedelta(days=duration_days)

            self.stdout.write(f"📅 Checking availability from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

            availability_result = automation_service.check_manager_availability(
                vacancy.manager.email, start_date, end_date, interview_duration
            )

            if not availability_result['success']:
                raise CommandError(f"Failed to check availability: {availability_result['error']}")

            available_slots = availability_result['slots_count']
            self.stdout.write(f"✅ Found {available_slots} available slots")

            if available_slots < shortlist_count:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️ Only {available_slots} slots available for {shortlist_count} candidates"
                    )
                )

            # Schedule interviews
            self.stdout.write("📅 Scheduling interviews...")
            result = automation_service.schedule_interviews_for_approved_vacancy(vacancy)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Successfully scheduled {result['scheduled_count']} interviews"
                    )
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"📧 Sent {result['notifications_sent']} notifications"
                    )
                )
                self.stdout.write(f"💬 Message: {result['message']}")
            else:
                raise CommandError(f"Failed to schedule interviews: {result['error']}")

        except Vacancy.DoesNotExist:
            raise CommandError(f"Vacancy {vacancy_id} does not exist")
        except Exception as e:
            raise CommandError(f"Error: {str(e)}")
