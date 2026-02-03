"""
Signals for the interviews app.
"""
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Interview

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Interview)
def update_candidate_vacancy_profile_on_interview(sender, instance, created, **kwargs):
    """
    When an Interview is created or updated, set interview info on the candidate's
    CandidateVacancyProfile for this vacancy so the profile shows scheduled date/duration.
    """
    try:
        from candidates.models import CandidateVacancyProfile

        profile, _ = CandidateVacancyProfile.objects.get_or_create(
            candidate=instance.candidate,
            vacancy=instance.vacancy,
            defaults={
                'application_status': 'interview_scheduled',
                'interview_scheduled': True,
                'interview_date': instance.scheduled_at,
                'interview_duration': instance.duration_minutes,
            }
        )
        profile.interview_scheduled = True
        profile.interview_date = instance.scheduled_at
        profile.interview_duration = instance.duration_minutes
        profile.application_status = profile.application_status or 'interview_scheduled'
        profile.save(update_fields=['interview_scheduled', 'interview_date', 'interview_duration', 'application_status'])
        logger.info(f"Updated CandidateVacancyProfile interview info for {instance.candidate.full_name} - {instance.vacancy.title}")
    except Exception as e:
        logger.warning(f"Could not update CandidateVacancyProfile for interview: {e}")
