# ai/models.py
from django.db import models

class Agent(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class AIAnalysis(models.Model):
    """Track AI analysis requests and results"""
    application = models.ForeignKey('candidates.Application', on_delete=models.CASCADE, related_name='ai_analyses')
    analysis_type = models.CharField(max_length=50, choices=[
        ('cv_scoring', 'CV Scoring'),
        ('profile_generation', 'Profile Generation'),
        ('questionnaire_analysis', 'Questionnaire Analysis'),
    ])
    prompt_used = models.TextField(help_text='The AI prompt that was used')
    response_received = models.TextField(help_text='The AI response received')
    tokens_used = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
