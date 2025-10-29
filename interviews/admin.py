"""
Django Admin configuration for Interview models and OAuth functionality
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse, path
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils import timezone
from datetime import timedelta
from .models import CalendarIntegration, InterviewSlot, Interview, InterviewFeedback, ManagerFeedback
from .services import ZohoCalendarService, InterviewSchedulingService
import logging

logger = logging.getLogger(__name__)


@admin.register(CalendarIntegration)
class CalendarIntegrationAdmin(admin.ModelAdmin):
    """Admin interface for Calendar Integration management"""
    
    list_display = [
        'manager_email', 'calendar_id', 'is_active', 'has_valid_token', 
        'token_expires_at', 'created_at', 'oauth_actions'
    ]
    list_filter = ['is_active', 'created_at', 'updated_at']
    search_fields = ['manager__email', 'manager__username', 'calendar_id']
    readonly_fields = ['created_at', 'updated_at', 'token_info']
    
    fieldsets = (
        ('Manager Information', {
            'fields': ('manager',)
        }),
        ('Calendar Details', {
            'fields': ('calendar_id', 'calendar_uid', 'caldav_url', 'caldav_username', 'caldav_password', 'timezone')
        }),
        ('OAuth Tokens', {
            'fields': ('access_token', 'refresh_token', 'token_expires_at', 'token_info'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def manager_email(self, obj):
        return obj.manager.email
    manager_email.short_description = 'Manager Email'
    manager_email.admin_order_field = 'manager__email'
    
    def has_valid_token(self, obj):
        if not obj.access_token:
            return format_html('<span style="color: red;">❌ No Token</span>')
        
        if obj.token_expires_at and obj.token_expires_at > timezone.now() + timedelta(minutes=5):
            return format_html('<span style="color: green;">✅ Valid</span>')
        elif obj.refresh_token:
            return format_html('<span style="color: orange;">🔄 Needs Refresh</span>')
        else:
            return format_html('<span style="color: red;">❌ Expired</span>')
    has_valid_token.short_description = 'Token Status'
    
    def token_info(self, obj):
        if not obj.access_token:
            return "No OAuth tokens available"
        
        info = []
        if obj.access_token:
            info.append(f"Access Token: {obj.access_token[:20]}...")
        if obj.refresh_token:
            info.append(f"Refresh Token: {obj.refresh_token[:20]}...")
        if obj.token_expires_at:
            info.append(f"Expires: {obj.token_expires_at}")
        
        return format_html('<br>'.join(info))
    token_info.short_description = 'Token Information'
    
    def oauth_actions(self, obj):
        return format_html('<span style="color: #888;">OAuth removed</span>')
    oauth_actions.short_description = 'OAuth Actions'
    
    def get_urls(self):
        return super().get_urls()
    
    # OAuth admin views removed
    
    #
    
    #
    
    def response_change(self, request, obj):
        """Handle custom actions"""
        if 'action' in request.GET:
            # OAuth actions removed
            pass
        
        return super().response_change(request, obj)


@admin.register(InterviewSlot)
class InterviewSlotAdmin(admin.ModelAdmin):
    """Admin interface for Interview Slots"""
    
    list_display = [
        'vacancy_title', 'manager_email', 'start_time', 'end_time', 
        'is_available', 'duration', 'created_at'
    ]
    list_filter = ['is_available', 'start_time', 'created_at', 'vacancy__department']
    search_fields = ['vacancy__title', 'manager__email', 'manager__username']
    date_hierarchy = 'start_time'
    readonly_fields = ['created_at']
    
    def vacancy_title(self, obj):
        return obj.vacancy.title
    vacancy_title.short_description = 'Vacancy'
    vacancy_title.admin_order_field = 'vacancy__title'
    
    def manager_email(self, obj):
        return obj.manager.email
    manager_email.short_description = 'Manager'
    manager_email.admin_order_field = 'manager__email'
    
    def duration(self, obj):
        duration = obj.end_time - obj.start_time
        return f"{duration.total_seconds() / 60:.0f} min"
    duration.short_description = 'Duration'


@admin.register(Interview)
class InterviewAdmin(admin.ModelAdmin):
    """Admin interface for Interviews"""
    
    list_display = [
        'candidate_name', 'vacancy_title', 'manager_email', 'scheduled_at', 
        'status', 'duration_minutes', 'notifications_sent', 'has_manager_feedback', 'get_feedback_rating_display', 'interview_actions'
    ]
    list_filter = ['status', 'scheduled_at', 'created_at', 'vacancy__department']
    search_fields = ['candidate__full_name', 'candidate__email', 'vacancy__title', 'manager__email']
    date_hierarchy = 'scheduled_at'
    readonly_fields = ['created_at', 'updated_at', 'notification_status']
    
    fieldsets = (
        ('Interview Details', {
            'fields': ('vacancy', 'candidate', 'manager', 'interview_slot')
        }),
        ('Scheduling', {
            'fields': ('scheduled_at', 'duration_minutes', 'status')
        }),
        ('Notifications', {
            'fields': ('manager_notified', 'candidate_notified', 'manager_notification_sent_at', 'candidate_notification_sent_at', 'notification_status')
        }),
        ('Interview Information', {
            'fields': ('meeting_link', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def candidate_name(self, obj):
        return obj.candidate.full_name
    candidate_name.short_description = 'Candidate'
    candidate_name.admin_order_field = 'candidate__full_name'
    
    def vacancy_title(self, obj):
        return obj.vacancy.title
    vacancy_title.short_description = 'Vacancy'
    vacancy_title.admin_order_field = 'vacancy__title'
    
    def manager_email(self, obj):
        return obj.manager.email
    manager_email.short_description = 'Manager'
    manager_email.admin_order_field = 'manager__email'
    
    def notifications_sent(self, obj):
        manager_status = "✅" if obj.manager_notified else "❌"
        candidate_status = "✅" if obj.candidate_notified else "❌"
        return format_html(f"Manager: {manager_status} | Candidate: {candidate_status}")
    notifications_sent.short_description = 'Notifications'
    
    def notification_status(self, obj):
        status = []
        if obj.manager_notification_sent_at:
            status.append(f"Manager: {obj.manager_notification_sent_at}")
        if obj.candidate_notification_sent_at:
            status.append(f"Candidate: {obj.candidate_notification_sent_at}")
        return format_html('<br>'.join(status)) if status else "No notifications sent"
    notification_status.short_description = 'Notification Details'
    
    def interview_actions(self, obj):
        """Display interview action buttons"""
        actions = []
        
        if obj.status == 'scheduled':
            actions.append(
                f'<a href="?action=send_notifications&id={obj.id}" class="button">Send Notifications</a>'
            )
            actions.append(
                f'<a href="?action=mark_completed&id={obj.id}" class="button">Mark Completed</a>'
            )
        
        return format_html(' '.join(actions))
    interview_actions.short_description = 'Actions'
    
    def response_change(self, request, obj):
        """Handle custom actions"""
        if 'action' in request.GET:
            action = request.GET['action']
            interview_id = request.GET.get('id')
            
            if action == 'send_notifications':
                return self.send_notifications_view(request, interview_id)
            elif action == 'mark_completed':
                return self.mark_completed_view(request, interview_id)
        
        return super().response_change(request, obj)
    
    def send_notifications_view(self, request, interview_id):
        """Send interview notifications"""
        try:
            interview = Interview.objects.get(id=interview_id)
            scheduling_service = InterviewSchedulingService()
            
            result = scheduling_service.send_interview_notifications([interview])
            
            if result['success']:
                messages.success(request, f"Notifications sent successfully for interview with {interview.candidate.full_name}")
            else:
                messages.error(request, f"Failed to send notifications: {result['error']}")
                
        except Exception as e:
            messages.error(request, f"Failed to send notifications: {str(e)}")
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))
    
    def mark_completed_view(self, request, interview_id):
        """Mark interview as completed"""
        try:
            interview = Interview.objects.get(id=interview_id)
            interview.status = 'completed'
            interview.save()
            messages.success(request, f"Interview with {interview.candidate.full_name} marked as completed")
                
        except Exception as e:
            messages.error(request, f"Failed to mark interview as completed: {str(e)}")
        
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))


@admin.register(InterviewFeedback)
class InterviewFeedbackAdmin(admin.ModelAdmin):
    """Admin interface for Interview Feedback"""
    
    list_display = [
        'candidate_name', 'vacancy_title', 'manager_email', 'overall_rating', 
        'recommendation', 'created_at'
    ]
    list_filter = ['recommendation', 'overall_rating', 'created_at', 'interview__vacancy__department']
    search_fields = ['interview__candidate__full_name', 'interview__candidate__email', 'interview__vacancy__title', 'manager__email']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Interview Information', {
            'fields': ('interview', 'manager')
        }),
        ('Ratings (1-10)', {
            'fields': ('technical_skills', 'communication', 'problem_solving', 'cultural_fit', 'overall_rating')
        }),
        ('Feedback', {
            'fields': ('strengths', 'areas_for_improvement', 'additional_notes')
        }),
        ('Decision', {
            'fields': ('recommendation',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )
    
    def candidate_name(self, obj):
        return obj.interview.candidate.full_name
    candidate_name.short_description = 'Candidate'
    candidate_name.admin_order_field = 'interview__candidate__full_name'
    
    def vacancy_title(self, obj):
        return obj.interview.vacancy.title
    vacancy_title.short_description = 'Vacancy'
    vacancy_title.admin_order_field = 'interview__vacancy__title'
    
    def manager_email(self, obj):
        return obj.manager.email
    manager_email.short_description = 'Manager'
    manager_email.admin_order_field = 'manager__email'


# Custom Admin Actions
@admin.action(description='OAuth actions removed')
def check_oauth_status(modeladmin, request, queryset):
    messages.info(request, 'OAuth removed; no status to check.')

@admin.action(description='OAuth actions removed')
def refresh_oauth_tokens(modeladmin, request, queryset):
    messages.info(request, 'OAuth removed; no tokens to refresh.')

@admin.action(description='Send notifications for selected interviews')
def send_interview_notifications(modeladmin, request, queryset):
    """Bulk action to send interview notifications"""
    scheduling_service = InterviewSchedulingService()
    
    interviews = list(queryset.filter(status='scheduled'))
    if interviews:
        try:
            result = scheduling_service.send_interview_notifications(interviews)
            if result['success']:
                messages.success(request, f"✅ Notifications sent for {result['sent_count']} interviews")
            else:
                messages.error(request, f"❌ Failed to send notifications: {result['error']}")
        except Exception as e:
            messages.error(request, f"❌ Error sending notifications: {str(e)}")
    else:
        messages.warning(request, "⚠️ No scheduled interviews selected")

@admin.register(ManagerFeedback)
class ManagerFeedbackAdmin(admin.ModelAdmin):
    list_display = ('interview', 'rating', 'recommended', 'received_at')
    list_filter = ('rating', 'recommended', 'received_at')
    search_fields = ('interview__candidate__full_name', 'feedback_text')
    readonly_fields = ('received_at', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Interview Details', {
            'fields': ('interview',)
        }),
        ('Feedback', {
            'fields': ('feedback_text', 'rating', 'recommended')
        }),
        ('Timestamps', {
            'fields': ('received_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# Add actions to admin classes
CalendarIntegrationAdmin.actions = [check_oauth_status, refresh_oauth_tokens]
InterviewAdmin.actions = [send_interview_notifications]