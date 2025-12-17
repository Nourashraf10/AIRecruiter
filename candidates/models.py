# candidates/models.py
from django.db import models
from vacancies.models import Vacancy

class Candidate(models.Model):
    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=50, blank=True)
    nationality = models.CharField(max_length=80, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # AI-extracted data fields
    ai_extracted_data = models.JSONField(null=True, blank=True, help_text='AI-extracted structured data from latest CV')
    ai_extraction_date = models.DateTimeField(null=True, blank=True, help_text='When the AI extraction was last performed')
    ai_summary = models.TextField(blank=True, null=True, default='', help_text='AI-generated candidate summary')
    
    # AI scoring fields (moved from Application)
    ai_score_out_of_10 = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text='AI score for latest vacancy application')
    ai_analysis = models.TextField(blank=True, help_text='AI analysis of the candidate for latest vacancy')
    ai_score_breakdown = models.JSONField(null=True, blank=True, help_text='Detailed AI scoring breakdown')
    ai_scoring_date = models.DateTimeField(null=True, blank=True, help_text='When the AI scoring was last performed')
    latest_vacancy_scored = models.ForeignKey('vacancies.Vacancy', on_delete=models.SET_NULL, null=True, blank=True, help_text='Latest vacancy this candidate was scored against')

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

class CV(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='cvs', null=True, blank=True)
    raw_file = models.FileField(upload_to='cvs/', null=True, blank=True, help_text='CV file (PDF, DOC, DOCX, TXT)')
    extracted_text = models.TextField(blank=True, help_text='Extracted text from CV file for AI processing')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        if self.candidate:
            return f"CV for {self.candidate.full_name} ({self.raw_file.name if self.raw_file else 'No file'})"
        else:
            return f"CV file: {self.raw_file.name if self.raw_file else 'No file'}"

class Application(models.Model):
    STATUS = (
        ('applied', 'Applied'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('shortlisted', 'Shortlisted Top5'),
        ('interview_scheduled', 'Interview Scheduled'),
        ('interview_done', 'Interview Done'),
    )
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='applications')
    cv = models.ForeignKey(CV, on_delete=models.CASCADE, related_name='applications', null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS, default='applied')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vacancy', 'cv')

class CandidateProfile(models.Model):
    """AI-generated detailed candidate profile"""
    candidate = models.OneToOneField(Candidate, on_delete=models.CASCADE, related_name='profile')
    summary = models.TextField(help_text='AI-generated candidate summary')
    skills_analysis = models.JSONField(help_text='Detailed skills analysis')
    experience_level = models.CharField(max_length=50, help_text='Experience level assessment')
    strengths = models.JSONField(help_text='Key strengths identified')
    areas_for_improvement = models.JSONField(help_text='Areas for improvement')
    cultural_fit_score = models.DecimalField(max_digits=4, decimal_places=1, help_text='Cultural fit score 1-10')
    technical_score = models.DecimalField(max_digits=4, decimal_places=1, help_text='Technical skills score 1-10')
    overall_recommendation = models.TextField(help_text='Overall AI recommendation')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CandidateVacancyProfile(models.Model):
    """
    Comprehensive candidate profile for each vacancy they applied to.
    Contains all information: applications, AI analysis, and manager feedback.
    """
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='vacancy_profiles')
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='candidate_profiles')
    
    # Application information
    application_status = models.CharField(max_length=30, blank=True, help_text='Current application status')
    application_date = models.DateTimeField(null=True, blank=True, help_text='When candidate applied')
    
    # CV and AI Analysis information
    cv_file_name = models.CharField(max_length=255, blank=True, help_text='Name of the CV file uploaded')
    ai_extracted_data = models.JSONField(null=True, blank=True, help_text='AI-extracted structured data from CV')
    ai_score = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text='AI score for this vacancy')
    ai_analysis = models.TextField(blank=True, help_text='AI analysis for this specific vacancy')
    ai_score_breakdown = models.JSONField(null=True, blank=True, help_text='Detailed AI scoring breakdown')
    ai_analysis_date = models.DateTimeField(null=True, blank=True, help_text='When AI analysis was performed')
    
    # Manager feedback information
    manager_feedback = models.TextField(blank=True, help_text='Manager feedback from interview (full email body)')
    manager_rating = models.IntegerField(
        choices=[(1, 'Poor'), (2, 'Fair'), (3, 'Good'), (4, 'Very Good'), (5, 'Excellent')],
        null=True, blank=True,
        help_text='Manager rating of the candidate'
    )
    manager_recommendation = models.BooleanField(
        null=True, blank=True,
        help_text='Whether manager recommends this candidate'
    )
    feedback_received_date = models.DateTimeField(null=True, blank=True, help_text='When manager feedback was received')
    recommendation_email_sent = models.BooleanField(default=False, help_text='Whether hiring recommendation email has been sent')
    recommendation_email_sent_at = models.DateTimeField(null=True, blank=True, help_text='When hiring recommendation email was sent')
    
    # Questionnaire response information
    questionnaire_response = models.TextField(blank=True, help_text='Candidate questionnaire response (full email body)')
    questionnaire_response_date = models.DateTimeField(null=True, blank=True, help_text='When questionnaire response was received')
    
    # Interview information
    interview_scheduled = models.BooleanField(default=False, help_text='Whether interview was scheduled')
    interview_date = models.DateTimeField(null=True, blank=True, help_text='Interview date and time')
    interview_duration = models.IntegerField(null=True, blank=True, help_text='Interview duration in minutes')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('candidate', 'vacancy')
        verbose_name = 'Candidate Vacancy Profile'
        verbose_name_plural = 'Candidate Vacancy Profiles'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.candidate.full_name} - {self.vacancy.title}"

class QuestionnaireResponse(models.Model):
    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name='questionnaire')
    answers = models.TextField()   # store JSON/text answers
    submitted_at = models.DateTimeField(null=True, blank=True)
