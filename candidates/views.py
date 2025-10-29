from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Candidate, Application
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
