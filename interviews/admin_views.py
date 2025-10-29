"""
Custom admin views for OAuth testing and management
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from .models import CalendarIntegration, Interview, InterviewSlot
from .zoho_oauth_service import ZohoOAuthService
from .services import ZohoCalendarService, InterviewSchedulingService
from core.models import User
from vacancies.models import Vacancy
import logging

logger = logging.getLogger(__name__)


@staff_member_required
def oauth_dashboard(request):
    """OAuth testing dashboard"""
    
    # Get all calendar integrations
    integrations = CalendarIntegration.objects.all().select_related('manager')
    
    # Get OAuth service
    oauth_service = ZohoOAuthService()
    
    # Check status for each integration
    integration_status = []
    for integration in integrations:
        has_valid_token = oauth_service.get_valid_access_token(integration.manager.email)
        integration_status.append({
            'integration': integration,
            'has_valid_token': has_valid_token,
            'needs_refresh': integration.refresh_token and not has_valid_token,
            'needs_setup': not integration.access_token
        })
    
    # Get recent interviews
    recent_interviews = Interview.objects.select_related(
        'candidate', 'vacancy', 'manager'
    ).order_by('-created_at')[:10]
    
    # Get vacancies with shortlists
    vacancies_with_shortlists = Vacancy.objects.filter(
        shortlists__isnull=False
    ).distinct().select_related('manager')
    
    context = {
        'integration_status': integration_status,
        'recent_interviews': recent_interviews,
        'vacancies_with_shortlists': vacancies_with_shortlists,
        'oauth_service_configured': bool(oauth_service.client_id and oauth_service.client_secret),
    }
    
    return render(request, 'admin/oauth_dashboard.html', context)


@staff_member_required
def test_oauth_flow(request):
    """Test OAuth flow for a specific manager"""
    
    if request.method == 'POST':
        manager_email = request.POST.get('manager_email')
        
        if not manager_email:
            messages.error(request, 'Manager email is required')
            return redirect('oauth_dashboard')
        
        try:
            # Get or create manager user
            manager, created = User.objects.get_or_create(
                email=manager_email,
                defaults={'username': manager_email.split('@')[0].replace('.', '')}
            )
            
            if created:
                messages.info(request, f'Created new user for manager: {manager_email}')
            
            # Setup OAuth
            oauth_service = ZohoOAuthService()
            setup_result = oauth_service.setup_calendar_integration(manager_email)
            
            if setup_result.get('requires_authorization'):
                messages.info(request, f'OAuth setup initiated for {manager_email}')
                messages.info(request, f'Authorization URL: {setup_result["authorization_url"]}')
                return redirect(setup_result['authorization_url'])
            elif setup_result['success']:
                messages.success(request, f'OAuth setup completed: {setup_result["message"]}')
            else:
                messages.error(request, f'OAuth setup failed: {setup_result["error"]}')
                
        except Exception as e:
            messages.error(request, f'Error setting up OAuth: {str(e)}')
            logger.error(f'OAuth setup error: {str(e)}')
    
    return redirect('oauth_dashboard')


@staff_member_required
def bulk_oauth_test(request):
    """Test OAuth for multiple managers"""
    
    if request.method == 'POST':
        manager_emails = request.POST.get('manager_emails', '').split('\n')
        manager_emails = [email.strip() for email in manager_emails if email.strip()]
        
        if not manager_emails:
            messages.error(request, 'Please provide manager emails')
            return redirect('oauth_dashboard')
        
        oauth_service = ZohoOAuthService()
        results = []
        
        for email in manager_emails:
            try:
                # Get or create manager user
                manager, created = User.objects.get_or_create(
                    email=email,
                    defaults={'username': email.split('@')[0].replace('.', '')}
                )
                
                # Check OAuth status
                setup_result = oauth_service.setup_calendar_integration(email)
                
                results.append({
                    'email': email,
                    'created': created,
                    'status': setup_result.get('success', False),
                    'requires_auth': setup_result.get('requires_authorization', False),
                    'message': setup_result.get('message', setup_result.get('error', 'Unknown'))
                })
                
            except Exception as e:
                results.append({
                    'email': email,
                    'created': False,
                    'status': False,
                    'requires_auth': False,
                    'message': str(e)
                })
        
        # Store results in session for display
        request.session['bulk_oauth_results'] = results
        messages.info(request, f'Processed OAuth setup for {len(manager_emails)} managers')
    
    return redirect('oauth_dashboard')


@staff_member_required
def calendar_availability_test(request):
    """Test calendar availability checking"""
    
    if request.method == 'POST':
        manager_email = request.POST.get('manager_email')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        duration_minutes = int(request.POST.get('duration_minutes', 60))
        
        try:
            # Get manager
            manager = User.objects.get(email=manager_email)
            
            # Check calendar integration
            try:
                calendar_integration = CalendarIntegration.objects.get(
                    manager=manager, is_active=True
                )
            except CalendarIntegration.DoesNotExist:
                messages.error(request, f'No calendar integration found for {manager_email}')
                return redirect('oauth_dashboard')
            
            # Test calendar service
            calendar_service = ZohoCalendarService()
            
            # Convert dates
            from datetime import datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Get available slots
            slots_result = calendar_service.get_available_slots(
                manager=manager,
                start_date=start_dt,
                end_date=end_dt,
                duration_minutes=duration_minutes
            )
            
            if slots_result['success']:
                messages.success(request, f'Found {len(slots_result["slots"])} available slots for {manager_email}')
                request.session['calendar_test_result'] = {
                    'manager_email': manager_email,
                    'slots': slots_result['slots'],
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration_minutes': duration_minutes
                }
            else:
                messages.error(request, f'Calendar check failed: {slots_result["error"]}')
                
        except Exception as e:
            messages.error(request, f'Error testing calendar: {str(e)}')
            logger.error(f'Calendar test error: {str(e)}')
    
    return redirect('oauth_dashboard')


@staff_member_required
def interview_scheduling_test(request):
    """Test interview scheduling for a vacancy"""
    
    if request.method == 'POST':
        vacancy_id = request.POST.get('vacancy_id')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        duration_minutes = int(request.POST.get('duration_minutes', 60))
        
        try:
            # Get vacancy
            vacancy = Vacancy.objects.get(id=vacancy_id)
            
            # Check if shortlist exists
            if not vacancy.shortlists.exists():
                messages.error(request, f'No shortlist found for vacancy: {vacancy.title}')
                return redirect('oauth_dashboard')
            
            # Test scheduling service
            scheduling_service = InterviewSchedulingService()
            
            # Convert dates
            from datetime import datetime
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Schedule interviews
            scheduling_result = scheduling_service.schedule_interviews_for_vacancy(
                vacancy=vacancy,
                manager=vacancy.manager,
                start_date=start_dt,
                end_date=end_dt,
                duration_minutes=duration_minutes
            )
            
            if scheduling_result['success']:
                messages.success(request, f'Scheduled {scheduling_result["scheduled_count"]} interviews for {vacancy.title}')
                
                # Send notifications
                notification_result = scheduling_service.send_interview_notifications(
                    scheduling_result['interviews']
                )
                
                if notification_result['success']:
                    messages.success(request, f'Sent {notification_result["sent_count"]} notifications')
                else:
                    messages.warning(request, f'Notification sending failed: {notification_result["error"]}')
                    
            else:
                messages.error(request, f'Interview scheduling failed: {scheduling_result["error"]}')
                
        except Exception as e:
            messages.error(request, f'Error testing interview scheduling: {str(e)}')
            logger.error(f'Interview scheduling test error: {str(e)}')
    
    return redirect('oauth_dashboard')
