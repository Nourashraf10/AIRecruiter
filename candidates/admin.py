from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse
from django import forms
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Candidate, CV, Application, QuestionnaireResponse, CandidateProfile, CandidateVacancyProfile
from vacancies.models import Vacancy
from ai.services import AIService
from django.db import transaction
from .ai_sorting_service import CandidateSortingAIService


class CVUploadForm(forms.Form):
    cv_file = forms.FileField(
        label="CV File",
        help_text="Upload a PDF, DOC, DOCX, or TXT file",
        widget=forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.txt'})
    )
    vacancy = forms.ModelChoiceField(
        queryset=Vacancy.objects.filter(status='approved'),
        label="Vacancy",
        help_text="Select the vacancy this CV is applying for"
    )


class ApplicationAdminForm(forms.ModelForm):
    cv_file = forms.FileField(
        label="CV File",
        help_text="Upload a PDF, DOC, DOCX, or TXT file. AI will extract candidate information and create CV automatically.",
        widget=forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.txt'}),
        required=True
    )
    
    class Meta:
        model = Application
        fields = ['vacancy', 'status', 'cv_file']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # CV field will be created automatically from uploaded file


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "full_name", "email", "nationality", "ai_score_out_of_10", "ai_scoring_date", "created_at")
    search_fields = ("full_name", "email", "phone")
    actions = ['upload_cv_action']
    readonly_fields = ("ai_extraction_date", "ai_extracted_data", "ai_summary", "ai_scoring_date", "ai_score_out_of_10", "ai_analysis", "ai_score_breakdown", "latest_vacancy_scored")
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('full_name', 'email', 'phone', 'nationality', 'date_of_birth')
        }),
        ('AI Extracted Data', {
            'fields': ('ai_extraction_date', 'ai_summary', 'ai_extracted_data'),
            'classes': ('collapse',)
        }),
        ('AI Scoring Results', {
            'fields': ('ai_scoring_date', 'ai_score_out_of_10', 'ai_analysis', 'ai_score_breakdown', 'latest_vacancy_scored'),
            'classes': ('collapse',)
        }),
    )
    
    def upload_cv_action(self, request, queryset):
        """Custom admin action to upload CV"""
        return HttpResponseRedirect(reverse('admin:candidates_candidate_upload_cv'))
    upload_cv_action.short_description = "Upload CV File"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-cv/', self.admin_site.admin_view(self.upload_cv_view), name='candidates_candidate_upload_cv'),
        ]
        return custom_urls + urls
    
    def upload_cv_view(self, request):
        if request.method == 'POST':
            form = CVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    # Process the CV upload
                    cv_file = form.cleaned_data['cv_file']
                    vacancy = form.cleaned_data['vacancy']
                    
                    # Create CV record (candidate will be created automatically by signal)
                    cv_record = CV.objects.create(
                        raw_file=cv_file
                    )
                    
                    # Create application (AI scoring will be triggered automatically by signal)
                    application = Application.objects.create(
                        vacancy=vacancy,
                        cv=cv_record,
                        status='applied'
                    )
                    
                    messages.success(
                        request, 
                        f'CV uploaded successfully! Created application #{application.id}. Candidate will be created automatically from CV data.'
                    )
                    return redirect('admin:candidates_application_changelist')
                    
                except Exception as e:
                    messages.error(request, f'Error processing CV: {str(e)}')
        else:
            form = CVUploadForm()
        
        context = {
            'form': form,
            'title': 'Upload CV',
            'has_permission': True,
        }
        return render(request, 'admin/candidates/candidate/upload_cv.html', context)
    


@admin.register(CV)
class CVAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "raw_file", "created_at")
    search_fields = ("candidate__full_name", "candidate__email")
    readonly_fields = ("created_at",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    list_display = ("id", "vacancy", "cv", "candidate_name", "status", "created_at")
    list_filter = ("status", "vacancy")
    search_fields = ("vacancy__title", "cv__candidate__full_name", "cv__candidate__email")
    actions = ['upload_cv_action']
    
    def candidate_name(self, obj):
        return obj.cv.candidate.full_name if obj.cv and obj.cv.candidate else "No Candidate"
    candidate_name.short_description = "Candidate"
    
    def save_model(self, request, obj, form, change):
        """Handle CV file upload when saving application"""
        cv_file = form.cleaned_data.get('cv_file')
        
        if cv_file and not change:  # Only for new applications
            try:
                with transaction.atomic():
                    # Create CV record (candidate will be created automatically by signal)
                    cv_record = CV.objects.create(
                        raw_file=cv_file
                    )

                    # Link the CV to the application
                    obj.cv = cv_record

                    # Save the application (this will trigger the scoring signal)
                    super().save_model(request, obj, form, change)

                messages.success(
                    request,
                    'Application created successfully! CV uploaded, candidate created, and AI scoring completed automatically.'
                )
                # Prevent Django admin from attempting any further save operations in this request
                return
            except Exception as e:
                # Ensure the transaction is rolled back and do not proceed with further DB ops
                transaction.set_rollback(True)
                messages.error(request, f'Error processing CV: {str(e)}')
                return
        elif not cv_file and not change:
            # No CV file uploaded for new application
            messages.error(request, 'CV file is required to create an application.')
            return
        else:
            # For existing applications
            super().save_model(request, obj, form, change)
    
    def upload_cv_action(self, request, queryset):
        """Custom admin action to upload CV"""
        return HttpResponseRedirect(reverse('admin:candidates_application_upload_cv'))
    upload_cv_action.short_description = "Upload CV File"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-cv/', self.admin_site.admin_view(self.upload_cv_view), name='candidates_application_upload_cv'),
        ]
        return custom_urls + urls
    
    def upload_cv_view(self, request):
        """Upload CV file for an application"""
        if request.method == 'POST':
            form = CVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    # Process the CV upload
                    cv_file = form.cleaned_data['cv_file']
                    vacancy = form.cleaned_data['vacancy']
                    
                    # Create CV record (candidate will be created automatically by signal)
                    cv_record = CV.objects.create(
                        raw_file=cv_file
                    )
                    
                    # Create application (AI scoring will be triggered automatically by signal)
                    application = Application.objects.create(
                        vacancy=vacancy,
                        cv=cv_record,
                        status='applied'
                    )
                    
                    messages.success(
                        request, 
                        f'CV uploaded successfully! Created application #{application.id}. Candidate will be created automatically from CV data.'
                    )
                    return redirect('admin:candidates_application_changelist')
                    
                except Exception as e:
                    messages.error(request, f'Error processing CV: {str(e)}')
        else:
            form = CVUploadForm()
        
        context = {
            'form': form,
            'title': 'Upload CV for Application',
            'has_permission': True,
        }
        return render(request, 'admin/candidates/application/upload_cv.html', context)


@admin.register(QuestionnaireResponse)
class QuestionnaireResponseAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "submitted_at")


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "experience_level", "technical_score", "cultural_fit_score", "created_at")
    search_fields = ("candidate__full_name", "candidate__email")
    list_filter = ("experience_level",)

@admin.register(CandidateVacancyProfile)
class CandidateVacancyProfileAdmin(admin.ModelAdmin):
    list_display = (
        'candidate', 'vacancy', 'application_status', 'ai_score', 
        'manager_rating', 'manager_recommendation', 'recommendation_email_sent', 'interview_scheduled', 'created_at'
    )
    list_filter = (
        'application_status', 'manager_rating', 'manager_recommendation', 
        'interview_scheduled', 'vacancy__department', 'created_at'
    )
    search_fields = (
        'candidate__full_name', 'candidate__email', 'vacancy__title',
        'manager_feedback', 'ai_analysis'
    )
    readonly_fields = (
        'created_at', 'updated_at', 'ai_analysis_date', 'feedback_received_date',
        'recommendation_email_sent', 'recommendation_email_sent_at'
    )
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['fahmy_assistant_url'] = reverse('admin:candidates_fahmy_assistant')
        return super().changelist_view(request, extra_context)
    
    fieldsets = (
        ('Candidate & Vacancy', {
            'fields': ('candidate', 'vacancy')
        }),
        ('Application Information', {
            'fields': ('application_status', 'application_date', 'cv_file_name')
        }),
        ('AI Analysis', {
            'fields': (
                'ai_extracted_data', 'ai_score', 'ai_analysis', 
                'ai_score_breakdown', 'ai_analysis_date'
            ),
            'classes': ('collapse',)
        }),
        ('Interview Information', {
            'fields': ('interview_scheduled', 'interview_date', 'interview_duration')
        }),
        ('Manager Feedback', {
            'fields': (
                'manager_feedback', 'manager_rating', 'manager_recommendation', 
                'feedback_received_date', 'recommendation_email_sent', 'recommendation_email_sent_at'
            )
        }),
        ('Questionnaire Response', {
            'fields': (
                'questionnaire_response', 'questionnaire_response_date'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('candidate', 'vacancy')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('fahmy-assistant/', self.admin_site.admin_view(self.fahmy_assistant_view), name='candidates_fahmy_assistant'),
        ]
        return custom_urls + urls
    
    def fahmy_assistant_view(self, request):
        """
        Fahmy AI Assistant view for natural language candidate sorting
        """
        ai_service = CandidateSortingAIService()
        candidates = []
        query = request.GET.get('query', '')
        vacancy_id = request.GET.get('vacancy_id', '')
        filters_applied = {}
        explanation = ''
        
        if request.method == 'POST':
            query = request.POST.get('query', '')
            vacancy_id = request.POST.get('vacancy_id', '')
            
            if query:
                # Parse the query using AI
                parsed_result = ai_service.parse_query(query)
                
                if 'error' in parsed_result:
                    messages.error(request, f"Error: {parsed_result['error']}")
                else:
                    # Apply filters
                    filters = parsed_result.get('filters', {})
                    filters_applied = filters
                    explanation = parsed_result.get('explanation', '')
                    
                    # Get vacancy ID if provided
                    vac_id = int(vacancy_id) if vacancy_id and vacancy_id.isdigit() else None
                    
                    # Apply filters and get candidates
                    candidates_qs = ai_service.apply_filters(filters, vac_id)
                    candidates = list(candidates_qs[:100])  # Limit to 100 results
                    
                    messages.success(request, f"Found {len(candidates)} candidates matching your criteria.")
        
        # Get all vacancies for the dropdown
        vacancies = Vacancy.objects.all().order_by('-created_at')
        
        context = {
            'title': 'Fahmy AI Assistant - Candidate Sorting',
            'query': query,
            'vacancy_id': vacancy_id,
            'candidates': candidates,
            'vacancies': vacancies,
            'filters_applied': filters_applied,
            'explanation': explanation,
            'has_permission': True,
            'opts': CandidateVacancyProfile._meta,
        }
        
        return render(request, 'admin/candidates/fahmy_assistant.html', context)
