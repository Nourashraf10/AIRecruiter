from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.views import View
from django.shortcuts import render, get_object_or_404

from vacancies.models import Vacancy
from .models import Candidate, Application, BlueCollarLead
from .serializers import CandidateSerializer, ApplicationSerializer

class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer


class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer

    @action(detail=True, methods=['post'])
    def score(self, request, pk=None):
        application = self.get_object()
        vacancy = application.vacancy
        candidate = application.candidate
        latest_cv = candidate.cvs.order_by('-created_at').first()
        if not latest_cv:
            return Response({"detail": "No CV found for candidate."}, status=status.HTTP_400_BAD_REQUEST)

        cv_text = (latest_cv.text or "").lower()
        keywords = vacancy.keyword_list()
        if not keywords:
            # If no keywords provided, neutral score
            application.score_out_of_10 = 0
            application.save(update_fields=['score_out_of_10'])
            return Response({"score_out_of_10": float(application.score_out_of_10), "matched_keywords": []})

        matched = 0
        matched_list = []
        for kw in keywords:
            if kw and kw in cv_text:
                matched += 1
                matched_list.append(kw)

        score = 10.0 * matched / max(1, len(keywords))
        application.score_out_of_10 = round(score, 1)
        application.save(update_fields=['score_out_of_10'])
        return Response({
            "score_out_of_10": float(application.score_out_of_10),
            "matched_count": matched,
            "total_keywords": len(keywords),
            "matched_keywords": matched_list,
        })


class BlueCollarApplyView(View):
    """Simple public form for blue-collar applicants (name + mobile only)."""
    template_name = 'blue_collar/apply.html'

    def get(self, request, vacancy_id: int):
        vacancy = get_object_or_404(Vacancy, id=vacancy_id)
        return render(request, self.template_name, {
            'vacancy': vacancy,
            'submitted': False,
            'errors': [],
            'name': '',
            'phone': '',
        })

    def post(self, request, vacancy_id: int):
        vacancy = get_object_or_404(Vacancy, id=vacancy_id)
        name = (request.POST.get('name') or '').strip()
        phone = (request.POST.get('phone') or '').strip()
        errors = []
        if not name:
            errors.append("Name is required.")
        if not phone:
            errors.append("Mobile number is required.")

        if errors:
            return render(request, self.template_name, {
                'vacancy': vacancy,
                'submitted': False,
                'errors': errors,
                'name': name,
                'phone': phone,
            })

        BlueCollarLead.objects.create(
            full_name=name,
            phone=phone,
            vacancy=vacancy,
        )
        return render(request, self.template_name, {
            'vacancy': vacancy,
            'submitted': True,
            'errors': [],
            'name': '',
            'phone': '',
        })
