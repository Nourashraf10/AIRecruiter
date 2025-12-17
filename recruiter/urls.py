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
from vacancies.views import VacancyViewSet, GenerateShortlistView, ClearShortlistView
from candidates.views import CandidateViewSet, ApplicationViewSet
from comms.views import InboundEmailView, ManagerApprovalView, ApplicationCollectionView, EmailApplicationView, ApprovalLandingView, LinkedInApplicationInboundView
from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from ai.views import CVAnalysisView, BulkCVAnalysisView, TopCandidatesView, CVUploadView, CVTextExtractionView
from interviews.views import ScheduleInterviewsView, GetAvailableSlotsView, SendInterviewNotificationsView, DiscoverCalendarView
from core.views import DashboardView

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'vacancies', VacancyViewSet)
router.register(r'candidates', CandidateViewSet)
router.register(r'applications', ApplicationViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin/oauth-dashboard/', staff_member_required(TemplateView.as_view(template_name='admin/oauth_dashboard.html')), name='oauth_dashboard'),
    path('api/', include(router.urls)),
     path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/dashboard/', DashboardView.as_view(), name='dashboard'),
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

