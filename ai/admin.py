from django.contrib import admin
from .models import Agent, AIAnalysis

# Register your models here.
@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "email", "active", "created_at")
    list_filter = ("active",)
    search_fields = ("name", "email")

@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "analysis_type", "tokens_used", "cost", "created_at")
    list_filter = ("analysis_type", "created_at")
    search_fields = ("application__candidate__full_name", "application__vacancy__title")
