from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import User
from .serializers import UserSerializer
from vacancies.models import Vacancy, Shortlist
from candidates.models import Candidate, Application
from interviews.models import Interview
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.db.models import Count, Q
from .forms import VacancyForm


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
        
        return context


class CandidateListView(ListView):
    model = Candidate
    template_name = 'candidates/list.html'
    context_object_name = 'candidates'
    ordering = ['-created_at']

    def get_queryset(self):
        return Candidate.objects.all().order_by('-created_at')


class InterviewListView(ListView):
    model = Interview
    template_name = 'interviews/list.html'
    context_object_name = 'interviews'
    ordering = ['-scheduled_at']

    def get_queryset(self):
        # Show upcoming interviews first, then past ones
        return Interview.objects.all().select_related('candidate', 'vacancy', 'manager').order_by('-scheduled_at')


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
