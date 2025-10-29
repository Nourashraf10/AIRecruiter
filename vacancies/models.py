# vacancies/models.py
from django.conf import settings
from django.db import models

class Vacancy(models.Model):
    STATUS = (
        ('awaiting_approval', 'Awaiting Approval'),
        ('approved', 'Approved'),
        ('collecting_applications', 'Collecting Applications'),
        ('closed', 'Closed'),
        ('rejected', 'Rejected'),
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_vacancies'
    )
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=120)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='managed_vacancies'
    )
    status = models.CharField(max_length=30, choices=STATUS, default='awaiting_approval')
    keywords = models.TextField(blank=True, help_text='Comma-separated keywords for CV scoring')
    require_dob_in_cv = models.BooleanField(default=True)
    require_egyptian = models.BooleanField(default=False)
    require_relevant_university = models.BooleanField(default=False)
    require_relevant_major = models.BooleanField(default=False)
    questionnaire_template = models.TextField(blank=True, help_text='Plain JSON or newline questions')
    meta = models.JSONField(null=True, blank=True, help_text='Additional metadata like approval tokens')
    linkedin_posted_at = models.DateTimeField(null=True, blank=True, help_text='When posted on LinkedIn')
    linkedin_url = models.URLField(blank=True, help_text='LinkedIn job posting URL')
    collection_ends_at = models.DateTimeField(null=True, blank=True, help_text='When to stop collecting applications')
    created_at = models.DateTimeField(auto_now_add=True)

    def keyword_list(self):
        return [k.strip().lower() for k in self.keywords.split(',') if k.strip()]

    def __str__(self):
        return f"{self.title} ({self.department})"

    def get_applied_candidates(self):
        """Get all candidates who applied to this vacancy"""
        from candidates.models import Application
        return Application.objects.filter(vacancy=self).select_related('cv__candidate')

    def get_shortlisted_candidates(self):
        """Get the top 5 shortlisted candidates for this vacancy"""
        return self.shortlists.all().order_by('rank')

    def generate_shortlist(self):
        """Generate shortlist of top 5 candidates based on AI scores"""
        from candidates.models import Application
        from django.utils import timezone
        
        # Get all applications for this vacancy with AI scores
        applications = Application.objects.filter(
            vacancy=self,
            cv__candidate__ai_score_out_of_10__isnull=False
        ).select_related('cv__candidate').order_by('-cv__candidate__ai_score_out_of_10')[:5]
        
        # Clear existing shortlist
        self.shortlists.all().delete()
        
        # Create new shortlist entries
        for rank, application in enumerate(applications, 1):
            Shortlist.objects.create(
                vacancy=self,
                candidate=application.cv.candidate,
                application=application,
                rank=rank,
                ai_score=application.cv.candidate.ai_score_out_of_10,
                generated_at=timezone.now()
            )
        
        return self.shortlists.count()


class Shortlist(models.Model):
    """Top 5 candidates shortlisted for a vacancy"""
    vacancy = models.ForeignKey(Vacancy, on_delete=models.CASCADE, related_name='shortlists')
    candidate = models.ForeignKey('candidates.Candidate', on_delete=models.CASCADE, related_name='shortlists')
    application = models.ForeignKey('candidates.Application', on_delete=models.CASCADE, related_name='shortlist_entries')
    rank = models.PositiveIntegerField(help_text='Rank in shortlist (1-5)')
    ai_score = models.DecimalField(max_digits=3, decimal_places=1, help_text='AI score out of 10')
    generated_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text='Additional notes about this candidate')
    
    class Meta:
        unique_together = ('vacancy', 'rank')
        ordering = ['vacancy', 'rank']
    
    def __str__(self):
        return f"{self.vacancy.title} - #{self.rank}: {self.candidate.full_name} ({self.ai_score}/10)"
