from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from datetime import datetime, timedelta
from .services import InterviewSchedulingService
from .models import Interview, InterviewSlot, CalendarIntegration
from .zoho_api_service import CalendarDiscoveryService


@method_decorator([staff_member_required, csrf_exempt], name='dispatch')
class ScheduleInterviewsView(View):
    """Admin view to schedule interviews for shortlisted candidates"""
    
    def post(self, request, vacancy_id):
        try:
            from vacancies.models import Vacancy
            
            vacancy = Vacancy.objects.get(id=vacancy_id)
            manager = vacancy.manager
            
            # Check if manager has calendar integration
            try:
                calendar_integration = CalendarIntegration.objects.get(manager=manager, is_active=True)
            except CalendarIntegration.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Manager {manager.email} does not have active calendar integration'
                })
            
            # Get scheduling parameters from request
            start_date_str = request.POST.get('start_date')
            end_date_str = request.POST.get('end_date')
            duration_minutes = int(request.POST.get('duration_minutes', 60))
            
            # Parse dates
            start_date = None
            end_date = None
            
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                start_date = timezone.make_aware(start_date)
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = timezone.make_aware(end_date)
            
            # Schedule interviews
            scheduling_service = InterviewSchedulingService()
            result = scheduling_service.schedule_interviews_for_vacancy(
                vacancy=vacancy,
                manager=manager,
                start_date=start_date,
                end_date=end_date,
                duration_minutes=duration_minutes
            )
            
            if result['success']:
                # Send email notifications
                notification_result = scheduling_service.send_interview_notifications(result['interviews'])
                
                return JsonResponse({
                    'success': True,
                    'scheduled_count': result['scheduled_count'],
                    'notifications_sent': notification_result.get('sent_count', 0),
                    'message': f"Successfully scheduled {result['scheduled_count']} interviews and sent {notification_result.get('sent_count', 0)} notifications"
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                })
                
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Vacancy not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@method_decorator([staff_member_required, csrf_exempt], name='dispatch')
class GetAvailableSlotsView(View):
    """Admin view to get available calendar slots for a manager"""
    
    def get(self, request, manager_id):
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            manager = User.objects.get(id=manager_id)
            
            # Check if manager has calendar integration
            try:
                calendar_integration = CalendarIntegration.objects.get(manager=manager, is_active=True)
            except CalendarIntegration.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': f'Manager {manager.email} does not have active calendar integration'
                })
            
            # Get date range from request
            start_date_str = request.GET.get('start_date')
            end_date_str = request.GET.get('end_date')
            duration_minutes = int(request.GET.get('duration_minutes', 60))
            
            # Parse dates
            start_date = None
            end_date = None
            
            if start_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                start_date = timezone.make_aware(start_date)
            else:
                start_date = timezone.now() + timedelta(days=1)
            
            if end_date_str:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                end_date = timezone.make_aware(end_date)
            else:
                end_date = start_date + timedelta(days=7)
            
            # Get available slots using manager's email for dynamic calendar discovery
            from .services import ZohoCalendarService
            calendar_service = ZohoCalendarService(manager_email=manager.email)
            available_slots = calendar_service.get_available_slots(
                start_date, end_date, duration_minutes, manager.email
            )
            
            # Format slots for JSON response
            formatted_slots = []
            for slot in available_slots:
                formatted_slots.append({
                    'start_time': slot['start_time'].strftime('%Y-%m-%d %H:%M'),
                    'end_time': slot['end_time'].strftime('%Y-%m-%d %H:%M'),
                    'duration_minutes': slot['duration_minutes'],
                    'is_available': slot['is_available']
                })
            
            return JsonResponse({
                'success': True,
                'slots': formatted_slots,
                'count': len(formatted_slots),
                'manager': manager.email
            })
            
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Manager not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@method_decorator([staff_member_required, csrf_exempt], name='dispatch')
class SendInterviewNotificationsView(View):
    """Admin view to resend interview notifications"""
    
    def post(self, request, vacancy_id):
        try:
            from vacancies.models import Vacancy
            
            vacancy = Vacancy.objects.get(id=vacancy_id)
            interviews = Interview.objects.filter(vacancy=vacancy, status='scheduled')
            
            if not interviews.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'No scheduled interviews found for this vacancy'
                })
            
            # Send notifications
            scheduling_service = InterviewSchedulingService()
            result = scheduling_service.send_interview_notifications(list(interviews))
            
            return JsonResponse({
                'success': result['success'],
                'sent_count': result.get('sent_count', 0),
                'message': result.get('message', 'Notifications sent successfully')
            })
            
        except Vacancy.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Vacancy not found'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })


@method_decorator([staff_member_required, csrf_exempt], name='dispatch')
class DiscoverCalendarView(View):
    """Admin view to discover calendar details for a manager by email"""
    
    def post(self, request):
        try:
            manager_email = request.POST.get('manager_email')
            
            if not manager_email:
                return JsonResponse({
                    'success': False,
                    'error': 'Manager email is required'
                })
            
            # Discover calendar details
            discovery_service = CalendarDiscoveryService()
            result = discovery_service.discover_manager_calendar(manager_email)
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'created': result['created'],
                    'calendar_details': result['calendar_details'],
                    'message': f"Calendar integration {'created' if result['created'] else 'updated'} for {manager_email}"
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    def get(self, request):
        """Get calendar details for a manager"""
        try:
            manager_email = request.GET.get('manager_email')
            
            if not manager_email:
                return JsonResponse({
                    'success': False,
                    'error': 'Manager email is required'
                })
            
            # Get calendar details
            discovery_service = CalendarDiscoveryService()
            result = discovery_service.discover_manager_calendar(manager_email)
            
            if result['success']:
                return JsonResponse({
                    'success': True,
                    'calendar_details': result['calendar_details'],
                    'manager_email': manager_email
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result['error']
                })
                
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })