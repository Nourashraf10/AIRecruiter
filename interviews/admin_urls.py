"""
URL configuration for OAuth admin views
"""

from django.urls import path
from . import admin_views

app_name = 'oauth_admin'

urlpatterns = [
    path('oauth/dashboard/', admin_views.oauth_dashboard, name='oauth_dashboard'),
    path('oauth/test-flow/', admin_views.test_oauth_flow, name='test_oauth_flow'),
    path('oauth/bulk-test/', admin_views.bulk_oauth_test, name='bulk_oauth_test'),
    path('oauth/calendar-test/', admin_views.calendar_availability_test, name='calendar_availability_test'),
    path('oauth/interview-test/', admin_views.interview_scheduling_test, name='interview_scheduling_test'),
]
