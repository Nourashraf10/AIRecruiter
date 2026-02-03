"""
Backfill CandidateVacancyProfile with interview info from existing Interview records.
Run: python manage.py backfill_interview_profiles
"""
from django.core.management.base import BaseCommand
from candidates.models import CandidateVacancyProfile
from interviews.models import Interview


class Command(BaseCommand):
    help = 'Backfill CandidateVacancyProfile with interview_scheduled, interview_date, interview_duration from Interview records'

    def handle(self, *args, **options):
        self.stdout.write('Backfilling interview info on CandidateVacancyProfile...')
        updated = 0
        created = 0
        for interview in Interview.objects.select_related('candidate', 'vacancy'):
            profile, created_profile = CandidateVacancyProfile.objects.get_or_create(
                candidate=interview.candidate,
                vacancy=interview.vacancy,
                defaults={
                    'application_status': 'interview_scheduled',
                    'interview_scheduled': True,
                    'interview_date': interview.scheduled_at,
                    'interview_duration': interview.duration_minutes,
                }
            )
            if created_profile:
                created += 1
                self.stdout.write(f'  Created profile for {interview.candidate.full_name} - {interview.vacancy.title}')
            else:
                profile.interview_scheduled = True
                profile.interview_date = interview.scheduled_at
                profile.interview_duration = interview.duration_minutes
                profile.application_status = profile.application_status or 'interview_scheduled'
                profile.save()
                updated += 1
                self.stdout.write(f'  Updated profile for {interview.candidate.full_name} - {interview.vacancy.title}')
        self.stdout.write(self.style.SUCCESS(f'Done: {created} created, {updated} updated.'))
