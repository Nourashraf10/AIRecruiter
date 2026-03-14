from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import User
from .serializers import UserSerializer
from vacancies.models import Vacancy, Shortlist
from candidates.models import Candidate, Application, CandidateVacancyProfile
from interviews.models import Interview
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, View, DetailView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from django.db.models import Count, Q
from .forms import VacancyForm, InterviewEditForm, DailySchedulingScheduleForm


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        total_vacancies = Vacancy.objects.count()
        total_candidates = Candidate.objects.count()
        candidates_per_vacancy = {
            v.id: Application.objects.filter(vacancy=v).count() for v in Vacancy.objects.all()
        }

        return Response({
            "total_vacancies": total_vacancies,
            "total_candidates": total_candidates,
            "candidates_per_vacancy": candidates_per_vacancy,
        })


class RecruitmentDashboardView(TemplateView):
    template_name = 'dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Key Metrics
        context['total_vacancies'] = Vacancy.objects.count()
        context['active_vacancies'] = Vacancy.objects.filter(status='collecting_applications').count()
        context['total_candidates'] = Candidate.objects.count()
        context['total_interviews'] = Interview.objects.count()
        context['upcoming_interviews'] = Interview.objects.filter(status='scheduled').count()
        
        # Recent Activity
        context['recent_applications'] = Application.objects.select_related('vacancy', 'cv__candidate').order_by('-created_at')[:5]
        context['recent_interviews'] = Interview.objects.select_related('vacancy', 'candidate', 'manager').order_by('-scheduled_at')[:5]
        
        # Vacancy Overview
        context['vacancies'] = Vacancy.objects.all().annotate(
            app_count=Count('applications'),
            interview_count=Count('interviews')
        ).order_by('-created_at')[:10]

        # Candidate profiles (same as admin Candidate Vacancy Profiles)
        context['total_candidate_profiles'] = CandidateVacancyProfile.objects.count()
        context['recent_candidate_profiles'] = CandidateVacancyProfile.objects.select_related(
            'candidate', 'vacancy'
        ).order_by('-created_at')[:5]

        # Daily interview scheduling periodic task (for dashboard card + link to admin)
        context['daily_scheduling_task'] = None
        try:
            from django_celery_beat.models import PeriodicTask
            task = PeriodicTask.objects.filter(
                task='comms.tasks.daily_interview_scheduling_task'
            ).select_related('crontab', 'interval').first()
            if task:
                context['daily_scheduling_task'] = task
                if task.crontab:
                    c = task.crontab
                    try:
                        h = int(c.hour) if c.hour != '*' else 0
                        m = int(c.minute) if c.minute != '*' else 0
                        from datetime import time
                        t = time(h, m)
                        context['daily_scheduling_schedule'] = f'Daily at {t.strftime("%I:%M %p").lstrip("0")}'
                    except (ValueError, TypeError):
                        context['daily_scheduling_schedule'] = f'{c.hour}:{c.minute} (cron)'
                else:
                    context['daily_scheduling_schedule'] = getattr(task.interval, 'human', None) or 'Interval'
        except Exception:
            pass
        if not context.get('daily_scheduling_schedule'):
            context['daily_scheduling_schedule'] = '12:56 AM daily (from settings)'

        # Form to edit daily scheduling time (hour/minute)
        task = context.get('daily_scheduling_task')
        initial = {}
        if task and getattr(task, 'crontab', None):
            c = task.crontab
            try:
                initial['hour'] = int(c.hour) if c.hour != '*' else 0
                initial['minute'] = int(c.minute) if c.minute != '*' else 0
            except (ValueError, TypeError):
                initial = {'hour': 0, 'minute': 56}
        else:
            initial = {'hour': 0, 'minute': 56}
        context['daily_scheduling_form'] = DailySchedulingScheduleForm(initial=initial)

        return context


class UpdateDailySchedulingScheduleView(View):
    """Update the crontab hour/minute for the daily interview scheduling task from the dashboard."""
    def post(self, request):
        form = DailySchedulingScheduleForm(request.POST)
        if not form.is_valid():
            messages.error(request, 'Invalid time. Use hour 0–23 and minute 0–59.')
            return redirect('recruiter_dashboard')
        hour = form.cleaned_data['hour']
        minute = form.cleaned_data['minute']
        try:
            from django_celery_beat.models import PeriodicTask, CrontabSchedule
            from django.conf import settings as django_settings

            task = PeriodicTask.objects.filter(
                task='comms.tasks.daily_interview_scheduling_task'
            ).select_related('crontab').first()
            if not task:
                messages.error(request, 'Daily interview scheduling task not found in the database.')
                return redirect('recruiter_dashboard')

            # Use Celery/Django timezone so 11:00 means 11:00 local time, not UTC
            tz = getattr(django_settings, 'CELERY_TIMEZONE', None) or getattr(django_settings, 'TIME_ZONE', 'UTC')

            # Try to reuse an existing matching CrontabSchedule (including timezone) if possible
            schedule = CrontabSchedule.objects.filter(
                minute=str(minute),
                hour=str(hour),
                day_of_week='*',
                day_of_month='*',
                month_of_year='*',
                timezone=tz,
            ).first()
            if not schedule:
                schedule = CrontabSchedule.objects.create(
                    minute=str(minute),
                    hour=str(hour),
                    day_of_week='*',
                    day_of_month='*',
                    month_of_year='*',
                    timezone=tz,
                )

            task.crontab = schedule
            task.save()
            messages.success(
                request,
                f'Daily interview scheduling is now set to run at {hour:02d}:{minute:02d} ({tz}).'
            )
        except Exception as e:
            messages.error(request, f'Could not update schedule: {e}')
        return redirect('recruiter_dashboard')


class CandidateListView(ListView):
    model = Candidate
    template_name = 'candidates/list.html'
    context_object_name = 'candidates'
    ordering = ['-created_at']

    def get_queryset(self):
        return Candidate.objects.prefetch_related('cvs__applications__vacancy').order_by('-created_at')


class CandidateProfileListView(ListView):
    """List all candidate vacancy profiles with same data as admin: search and filters."""
    model = CandidateVacancyProfile
    template_name = 'candidate_profiles/list.html'
    context_object_name = 'profiles'
    paginate_by = 25

    def get_queryset(self):
        qs = CandidateVacancyProfile.objects.select_related('candidate', 'vacancy').order_by('-created_at')
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(candidate__full_name__icontains=q) |
                Q(candidate__email__icontains=q) |
                Q(vacancy__title__icontains=q) |
                Q(manager_feedback__icontains=q) |
                Q(ai_analysis__icontains=q)
            )
        application_status = self.request.GET.get('application_status', '')
        if application_status:
            qs = qs.filter(application_status=application_status)
        manager_rating = self.request.GET.get('manager_rating', '')
        if manager_rating and manager_rating.isdigit():
            qs = qs.filter(manager_rating=int(manager_rating))
        manager_recommendation = self.request.GET.get('manager_recommendation', '')
        if manager_recommendation == '1':
            qs = qs.filter(manager_recommendation=True)
        elif manager_recommendation == '0':
            qs = qs.filter(manager_recommendation=False)
        interview_scheduled = self.request.GET.get('interview_scheduled', '')
        if interview_scheduled == '1':
            qs = qs.filter(interview_scheduled=True)
        elif interview_scheduled == '0':
            qs = qs.filter(interview_scheduled=False)
        department = self.request.GET.get('department', '')
        if department:
            qs = qs.filter(vacancy__department=department)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['vacancies'] = list(
            Vacancy.objects.values_list('department', flat=True).distinct().order_by('department')
        )
        context['search_q'] = self.request.GET.get('q', '')
        context['filter_application_status'] = self.request.GET.get('application_status', '')
        context['filter_manager_rating'] = self.request.GET.get('manager_rating', '')
        context['filter_manager_recommendation'] = self.request.GET.get('manager_recommendation', '')
        context['filter_interview_scheduled'] = self.request.GET.get('interview_scheduled', '')
        context['filter_department'] = self.request.GET.get('department', '')
        return context


class CandidateProfileDetailView(DetailView):
    """Single candidate vacancy profile with all fields (same as admin fieldsets)."""
    model = CandidateVacancyProfile
    template_name = 'candidate_profiles/detail.html'
    context_object_name = 'profile'

    def get_queryset(self):
        return CandidateVacancyProfile.objects.select_related('candidate', 'vacancy')


class InterviewListView(ListView):
    model = Interview
    template_name = 'interviews/list.html'
    context_object_name = 'interviews'
    ordering = ['-scheduled_at']

    def get_queryset(self):
        # Show upcoming interviews first, then past ones
        return Interview.objects.all().select_related('candidate', 'vacancy', 'manager').order_by('-scheduled_at')


class InterviewUpdateView(UpdateView):
    """Edit interview date/time and duration from dashboard and portal."""
    model = Interview
    form_class = InterviewEditForm
    template_name = 'interviews/edit.html'
    context_object_name = 'interview'

    def get_success_url(self):
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        if next_url:
            return next_url
        return reverse_lazy('interview_list')


class VacancyListView(ListView):
    model = Vacancy
    template_name = 'vacancies/list.html'
    context_object_name = 'vacancies'
    ordering = ['-created_at']

    def get_queryset(self):
        return Vacancy.objects.all().annotate(
            app_count=Count('applications')
        ).order_by('-created_at')


class VacancyCreateView(CreateView):
    model = Vacancy
    form_class = VacancyForm
    template_name = 'vacancies/form.html'
    success_url = reverse_lazy('vacancy_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.manager = self.request.user # Default to current user for simplicity in this portal
        return super().form_valid(form)


class VacancyUpdateView(UpdateView):
    model = Vacancy
    form_class = VacancyForm
    template_name = 'vacancies/form.html'
    success_url = reverse_lazy('vacancy_list')


class VacancyStatusView(TemplateView):
    """Show all vacancies grouped by status with approve/reject functionality."""
    template_name = 'vacancies/status.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group vacancies by status
        context['pending_vacancies'] = Vacancy.objects.filter(
            status='awaiting_approval'
        ).order_by('-created_at')
        
        context['approved_vacancies'] = Vacancy.objects.filter(
            status='approved'
        ).order_by('-created_at')[:10]
        
        context['rejected_vacancies'] = Vacancy.objects.filter(
            status='rejected'
        ).order_by('-created_at')[:10]
        
        context['active_vacancies'] = Vacancy.objects.filter(
            status='collecting_applications'
        ).order_by('-created_at')[:10]
        
        return context


class ApproveVacancyView(View):
    """Approve a vacancy and trigger LinkedIn automation."""
    
    def post(self, request, pk):
        try:
            vacancy = Vacancy.objects.get(pk=pk)
            # Set to 'approved' temporarily so the LinkedIn poster can validate status
            vacancy.status = 'approved'
            vacancy.save()
            
            # Trigger LinkedIn automation (same as email approval flow)
            from ai.linkedin_poster import LinkedInVacancyPoster
            from django.conf import settings
            
            if getattr(settings, 'LINKEDIN_POSTING_ENABLED', False):
                try:
                    print(f"🤖 Starting automated LinkedIn posting for: {vacancy.title}")
                    poster = LinkedInVacancyPoster(vacancy)
                    linkedin_result = poster.execute()
                    
                    if linkedin_result and linkedin_result.get('success'):
                        # poster.execute() already saved status = 'collecting_applications'
                        messages.success(
                            request,
                            f'Vacancy "{vacancy.title}" approved and posted to LinkedIn! '
                            f'Now collecting applications. URL: {linkedin_result.get("url", "N/A")}'
                        )
                    else:
                        error_msg = linkedin_result.get('error', 'Unknown error') if linkedin_result else 'No result returned'
                        # LinkedIn failed — still move to collecting_applications
                        vacancy.refresh_from_db()
                        if vacancy.status == 'approved':
                            vacancy.status = 'collecting_applications'
                            vacancy.save(update_fields=['status'])
                        messages.warning(
                            request,
                            f'Vacancy "{vacancy.title}" approved and set to collecting applications, '
                            f'but LinkedIn posting failed: {error_msg}'
                        )
                except Exception as e:
                    # LinkedIn error — still move to collecting_applications
                    vacancy.refresh_from_db()
                    if vacancy.status == 'approved':
                        vacancy.status = 'collecting_applications'
                        vacancy.save(update_fields=['status'])
                    messages.warning(
                        request,
                        f'Vacancy "{vacancy.title}" approved and set to collecting applications, '
                        f'but LinkedIn posting error: {str(e)}'
                    )
                    import traceback
                    traceback.print_exc()
            else:
                # LinkedIn disabled — go straight to collecting applications
                vacancy.status = 'collecting_applications'
                vacancy.save(update_fields=['status'])
                messages.success(
                    request,
                    f'Vacancy "{vacancy.title}" approved and is now collecting applications.'
                )

        except Vacancy.DoesNotExist:
            messages.error(request, 'Vacancy not found.')
        except Exception as e:
            messages.error(request, f'Error approving vacancy: {str(e)}')
        
        return redirect('vacancy_status')


class RejectVacancyView(View):
    """Reject a vacancy."""
    
    def post(self, request, pk):
        try:
            vacancy = Vacancy.objects.get(pk=pk)
            vacancy.status = 'rejected'
            vacancy.save()
            messages.success(request, f'Vacancy "{vacancy.title}" rejected.')
        except Vacancy.DoesNotExist:
            messages.error(request, 'Vacancy not found.')
        except Exception as e:
            messages.error(request, f'Error rejecting vacancy: {str(e)}')
        
        return redirect('vacancy_status')

