from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import User
from .serializers import UserSerializer
from vacancies.models import Vacancy
from candidates.models import Candidate
from candidates.models import Application


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
