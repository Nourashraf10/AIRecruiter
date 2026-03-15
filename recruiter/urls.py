"""
URL configuration for recruiter project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from core.views import UserViewSet
from vacancies.views import VacancyViewSet, GenerateShortlistView, ClearShortlistView, PostToFacebookView
from candidates.views import CandidateViewSet, ApplicationViewSet, BlueCollarApplyView
from comms.views import InboundEmailView, ManagerApprovalView, ApplicationCollectionView, EmailApplicationView, ApprovalLandingView, LinkedInApplicationInboundView
from django.views.generic import TemplateView, RedirectView
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from ai.views import CVAnalysisView, BulkCVAnalysisView, TopCandidatesView, CVUploadView, CVTextExtractionView
from interviews.views import ScheduleInterviewsView, GetAvailableSlotsView, SendInterviewNotificationsView, DiscoverCalendarView
from core.views import (
    DashboardView, RecruitmentDashboardView, VacancyListView, VacancyCreateView,
    VacancyUpdateView, CandidateListView, InterviewListView, InterviewUpdateView,
    UpdateDailySchedulingScheduleView, CandidateProfileListView, CandidateProfileDetailView,
    VacancyStatusView, ApproveVacancyView, RejectVacancyView,
    UpdateDailySchedulingScheduleView, RunDailySchedulingManuallyView, CandidateProfileListView, CandidateProfileDetailView,
    SendInterviewNotificationsDashboardView, DeleteCandidateDashboardView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'vacancies', VacancyViewSet)
router.register(r'candidates', CandidateViewSet)
router.register(r'applications', ApplicationViewSet)

urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False), name='root_redirect'),
    path('admin/', admin.site.urls),
    path('admin/oauth-dashboard/', staff_member_required(TemplateView.as_view(template_name='admin/oauth_dashboard.html')), name='oauth_dashboard'),
    path('api/', include(router.urls)),
     path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/dashboard/', DashboardView.as_view(), name='dashboard'),
    path('dashboard/', RecruitmentDashboardView.as_view(), name='recruiter_dashboard'),
    path('dashboard/update-daily-scheduling/', UpdateDailySchedulingScheduleView.as_view(), name='update_daily_scheduling'),
    path('dashboard/run-daily-scheduling-now/', RunDailySchedulingManuallyView.as_view(), name='run_daily_scheduling_now'),
    path('dashboard/send-interview-notifications/', SendInterviewNotificationsDashboardView.as_view(), name='send_interview_notifications_dashboard'),
    path('dashboard/delete-candidate/<int:pk>/', staff_member_required(DeleteCandidateDashboardView.as_view()), name='dashboard_delete_candidate'),
    path('portal/vacancies/', VacancyListView.as_view(), name='vacancy_list'),
    path('portal/vacancies/create/', VacancyCreateView.as_view(), name='vacancy_create'),
    path('portal/vacancies/<int:pk>/edit/', VacancyUpdateView.as_view(), name='vacancy_update'),
    path('portal/vacancies/status/', VacancyStatusView.as_view(), name='vacancy_status'),
    path('portal/vacancies/<int:pk>/approve/', ApproveVacancyView.as_view(), name='approve_vacancy'),
    path('portal/vacancies/<int:pk>/reject/', RejectVacancyView.as_view(), name='reject_vacancy'),
    path('portal/candidates/', CandidateListView.as_view(), name='candidate_list'),
    path('portal/candidate-profiles/', CandidateProfileListView.as_view(), name='candidate_profile_list'),
    path('portal/candidate-profiles/<int:pk>/', CandidateProfileDetailView.as_view(), name='candidate_profile_detail'),
    path('portal/interviews/', InterviewListView.as_view(), name='interview_list'),
    path('portal/interviews/<int:pk>/edit/', InterviewUpdateView.as_view(), name='interview_edit'),
    # Public blue-collar application form (linked from Facebook posts)
    path('blue-collar/apply/<int:vacancy_id>/', BlueCollarApplyView.as_view(), name='blue_collar_apply'),
    path('api/inbound/email/', InboundEmailView.as_view(), name='inbound_email'),
    path('api/inbound/linkedin-application/', LinkedInApplicationInboundView.as_view(), name='linkedin_application_inbound'),
    path('api/approve-vacancy/<str:approval_token>/', ManagerApprovalView.as_view(), name='manager_approval'),
    # Nice local approval landing page
    path('approve/<str:approval_token>/', ApprovalLandingView.as_view(), name='approval_landing'),
    path('api/apply/', ApplicationCollectionView.as_view(), name='application_collection'),
    path('api/apply/email/', EmailApplicationView.as_view(), name='email_application'),
    # AI Analysis endpoints
    path('api/ai/analyze-cv/<int:application_id>/', CVAnalysisView.as_view(), name='cv_analysis'),
    path('api/ai/analyze-vacancy/<int:vacancy_id>/', BulkCVAnalysisView.as_view(), name='bulk_cv_analysis'),
    path('api/ai/top-candidates/<int:vacancy_id>/', TopCandidatesView.as_view(), name='top_candidates'),
    # CV Processing endpoints
    path('api/ai/upload-cv/', CVUploadView.as_view(), name='cv_upload'),
    path('api/ai/extract-cv-text/', CVTextExtractionView.as_view(), name='cv_text_extraction'),
    # Admin shortlist endpoints
    path('admin/vacancies/vacancy/<int:vacancy_id>/generate-shortlist/', GenerateShortlistView.as_view(), name='generate_shortlist'),
    path('admin/vacancies/vacancy/<int:vacancy_id>/clear-shortlist/', ClearShortlistView.as_view(), name='clear_shortlist'),
    path('admin/vacancies/vacancy/<int:vacancy_id>/post-to-facebook/', PostToFacebookView.as_view(), name='post_vacancy_to_facebook'),
    # Admin interview scheduling endpoints
    path('admin/vacancies/vacancy/<int:vacancy_id>/schedule-interviews/', ScheduleInterviewsView.as_view(), name='schedule_interviews'),
    path('admin/vacancies/vacancy/<int:vacancy_id>/send-notifications/', SendInterviewNotificationsView.as_view(), name='send_notifications'),
    path('admin/users/<int:manager_id>/check-availability/', GetAvailableSlotsView.as_view(), name='check_availability'),
    # Calendar discovery endpoint
    path('admin/calendar/discover/', DiscoverCalendarView.as_view(), name='discover_calendar'),
    # OAuth endpoints removed (switching to CalDAV-only read access)
]

# Serve static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

