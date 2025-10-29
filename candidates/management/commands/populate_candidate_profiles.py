from django.core.management.base import BaseCommand
from django.utils import timezone
from candidates.models import Candidate, Application, CandidateVacancyProfile
from interviews.models import Interview, ManagerFeedback

class Command(BaseCommand):
    help = 'Populate CandidateVacancyProfile for existing candidates and applications'

    def handle(self, *args, **options):
        self.stdout.write('Starting to populate candidate vacancy profiles...')
        
        created_count = 0
        updated_count = 0
        
        # Process all applications
        applications = Application.objects.select_related('vacancy', 'cv__candidate').all()
        
        for application in applications:
            if not application.cv or not application.cv.candidate:
                self.stdout.write(f'Skipping application {application.id} - no candidate')
                continue
                
            candidate = application.cv.candidate
            vacancy = application.vacancy
            
            # Get or create the profile
            profile, created = CandidateVacancyProfile.objects.get_or_create(
                candidate=candidate,
                vacancy=vacancy,
                defaults={
                    'application_status': application.status,
                    'application_date': application.created_at,
                    'cv_file_name': application.cv.raw_file.name if application.cv.raw_file else '',
                    'ai_extracted_data': candidate.ai_extracted_data,
                    'ai_score': candidate.ai_score_out_of_10,
                    'ai_analysis': candidate.ai_analysis,
                    'ai_score_breakdown': candidate.ai_score_breakdown,
                    'ai_analysis_date': candidate.ai_scoring_date,
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created profile for {candidate.full_name} - {vacancy.title}')
            else:
                # Update existing profile with latest data
                profile.application_status = application.status
                profile.application_date = application.created_at
                profile.cv_file_name = application.cv.raw_file.name if application.cv.raw_file else ''
                profile.ai_extracted_data = candidate.ai_extracted_data
                profile.ai_score = candidate.ai_score_out_of_10
                profile.ai_analysis = candidate.ai_analysis
                profile.ai_score_breakdown = candidate.ai_score_breakdown
                profile.ai_analysis_date = candidate.ai_scoring_date
                profile.save()
                updated_count += 1
                self.stdout.write(f'Updated profile for {candidate.full_name} - {vacancy.title}')
        
        # Process interviews and manager feedback
        interviews = Interview.objects.select_related('candidate', 'vacancy').all()
        
        for interview in interviews:
            try:
                profile = CandidateVacancyProfile.objects.get(
                    candidate=interview.candidate,
                    vacancy=interview.vacancy
                )
                
                # Update interview information
                profile.interview_scheduled = True
                profile.interview_date = interview.scheduled_at
                profile.interview_duration = interview.duration_minutes
                
                # Check for manager feedback
                try:
                    manager_feedback = ManagerFeedback.objects.get(interview=interview)
                    profile.manager_feedback = manager_feedback.feedback_text
                    profile.manager_rating = manager_feedback.rating
                    profile.manager_recommendation = manager_feedback.recommended
                    profile.feedback_received_date = manager_feedback.received_at
                    profile.application_status = 'interview_done'
                    
                    self.stdout.write(f'Added manager feedback for {interview.candidate.full_name} - {interview.vacancy.title}')
                except ManagerFeedback.DoesNotExist:
                    pass
                
                profile.save()
                
            except CandidateVacancyProfile.DoesNotExist:
                # Create profile for interview without application
                profile = CandidateVacancyProfile.objects.create(
                    candidate=interview.candidate,
                    vacancy=interview.vacancy,
                    application_status='interview_scheduled',
                    interview_scheduled=True,
                    interview_date=interview.scheduled_at,
                    interview_duration=interview.duration_minutes,
                    ai_extracted_data=interview.candidate.ai_extracted_data,
                    ai_score=interview.candidate.ai_score_out_of_10,
                    ai_analysis=interview.candidate.ai_analysis,
                    ai_score_breakdown=interview.candidate.ai_score_breakdown,
                    ai_analysis_date=interview.candidate.ai_scoring_date,
                )
                created_count += 1
                self.stdout.write(f'Created profile for interview {interview.candidate.full_name} - {interview.vacancy.title}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Completed! Created {created_count} profiles, updated {updated_count} profiles.'
            )
        )
