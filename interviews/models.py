from django.db import models
from django.conf import settings
from django.utils import timezone


class CalendarIntegration(models.Model):
    """Calendar integration settings for managers"""
    manager = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calendar_integration'
    )
    calendar_id = models.CharField(max_length=200, help_text='Zoho Calendar ID')
    calendar_uid = models.CharField(max_length=200, help_text='Zoho Calendar UID')
    caldav_url = models.URLField(help_text='CalDAV URL for calendar access')
    # Optional basic-auth for CalDAV
    caldav_username = models.CharField(max_length=255, blank=True, default='', help_text='CalDAV basic auth username')
    caldav_password = models.CharField(max_length=255, blank=True, default='', help_text='CalDAV basic auth password')
    
    # OAuth token fields
    access_token = models.TextField(blank=True, help_text='OAuth access token')
    refresh_token = models.TextField(blank=True, help_text='OAuth refresh token')
    token_expires_at = models.DateTimeField(null=True, blank=True, help_text='Token expiration time')
    
    # Integration settings
    is_active = models.BooleanField(default=True)
    timezone = models.CharField(max_length=50, default='UTC', help_text='Manager timezone')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Calendar Integration for {self.manager.email}"


class InterviewSlot(models.Model):
    """Available time slots for interviews"""
    vacancy = models.ForeignKey('vacancies.Vacancy', on_delete=models.CASCADE, related_name='interview_slots')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interview_slots')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['start_time']
    
    def __str__(self):
        return f"{self.vacancy.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"


class Interview(models.Model):
    """Scheduled interviews with candidates"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]
    
    vacancy = models.ForeignKey('vacancies.Vacancy', on_delete=models.CASCADE, related_name='interviews')
    candidate = models.ForeignKey('candidates.Candidate', on_delete=models.CASCADE, related_name='interviews')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interviews')
    interview_slot = models.ForeignKey(InterviewSlot, on_delete=models.CASCADE, related_name='interviews')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    scheduled_at = models.DateTimeField()
    duration_minutes = models.IntegerField(default=60)
    
    # Email notifications
    manager_notified = models.BooleanField(default=False)
    candidate_notified = models.BooleanField(default=False)
    manager_notification_sent_at = models.DateTimeField(null=True, blank=True)
    candidate_notification_sent_at = models.DateTimeField(null=True, blank=True)

    #Track feedback request email 
    feedback_request_sent = models.BooleanField(default=False)
    feedback_request_sent_at = models.DateTimeField(null=True, blank=True)


    
    # Interview details
    meeting_link = models.URLField(blank=True, help_text='Video call link if applicable')
    notes = models.TextField(blank=True, help_text='Interview notes')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['scheduled_at']
        unique_together = ('vacancy', 'candidate')
    
    def __str__(self):
        return f"{self.candidate.full_name} - {self.vacancy.title} ({self.scheduled_at.strftime('%Y-%m-%d %H:%M')})"
    
    def has_manager_feedback(self):
        """Check if manager has provided feedback"""
        return hasattr(self, 'manager_feedback') and self.manager_feedback is not None

    def get_feedback_rating_display(self):
        """Get feedback rating as string"""
        if self.has_manager_feedback():
            return self.manager_feedback.get_rating_display()
        return "No feedback yet"


class InterviewFeedback(models.Model):
    """Feedback from managers after interviews"""
    interview = models.OneToOneField(Interview, on_delete=models.CASCADE, related_name='feedback')
    manager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='interview_feedback')
    
    # Rating scores (1-10)
    technical_skills = models.IntegerField(help_text='Technical skills rating (1-10)')
    communication = models.IntegerField(help_text='Communication skills rating (1-10)')
    problem_solving = models.IntegerField(help_text='Problem solving rating (1-10)')
    cultural_fit = models.IntegerField(help_text='Cultural fit rating (1-10)')
    overall_rating = models.IntegerField(help_text='Overall rating (1-10)')
    
    # Feedback text
    strengths = models.TextField(help_text='Candidate strengths')
    areas_for_improvement = models.TextField(help_text='Areas for improvement')
    additional_notes = models.TextField(blank=True, help_text='Additional notes')
    
    # Decision
    recommendation = models.CharField(
        max_length=20,
        choices=[
            ('hire', 'Hire'),
            ('no_hire', 'No Hire'),
            ('maybe', 'Maybe'),
            ('strong_hire', 'Strong Hire'),
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Feedback for {self.interview.candidate.full_name} - {self.overall_rating}/10"


class ManagerFeedback(models.Model):
    interview = models.OneToOneField(Interview, on_delete=models.CASCADE, related_name='manager_feedback')   
    feedback_text = models.TextField(help_text='Manager feedback on the interview')
    rating = models.IntegerField(
        choices=[(1, 'Poor'), (2, 'Fair'), (3, 'Good'), (4, 'Very Good'), (5, 'Excellent')],
        null=True , blank=True,
        help_text='Manager rating of the candidate'
    )
    recommended = models.BooleanField(
        null=True, blank=True ,
        help_text='Wether manager recommends this candidate'
    )
    received_at = models.DateTimeField(auto_now_add=True) 
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)    

    class Meta:
        verbose_name = 'Manager Feedback'
        verbose_name_plural = 'Manager Feedback'

    def __str__(self):
        return f"Feedback for {self.interview.candidate.full_name} - {self.interview.scheduled_at.date()}"