# ai/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .services import AIService
from candidates.models import Application, Candidate, CV, CandidateProfile
from vacancies.models import Vacancy

class CVAnalysisView(APIView):
    """AI-powered CV analysis for applications"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, application_id):
        """Analyze a specific application's CV using AI"""
        try:
            application = get_object_or_404(Application, id=application_id)
            
            # Get the latest CV for the candidate
            latest_cv = CV.objects.filter(candidate=application.candidate).order_by('-created_at').first()
            if not latest_cv or not latest_cv.text:
                return Response(
                    {"detail": "No CV text found for this candidate"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Initialize AI service
            ai_service = AIService()
            
            # Analyze the CV
            analysis_result = ai_service.analyze_cv_for_vacancy(application, latest_cv.text)
            
            # Update the application with AI analysis
            application.score_out_of_10 = analysis_result.get('overall_score', 0)
            application.ai_analysis = analysis_result.get('reasoning', '')
            application.ai_score_breakdown = analysis_result.get('score_breakdown', {})
            application.save(update_fields=['score_out_of_10', 'ai_analysis', 'ai_score_breakdown'])
            
            return Response({
                "application_id": application.id,
                "candidate_name": application.candidate.full_name,
                "vacancy_title": application.vacancy.title,
                "ai_analysis": analysis_result,
                "message": "CV analysis completed successfully"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"detail": f"Analysis failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BulkCVAnalysisView(APIView):
    """Analyze all applications for a vacancy using AI"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request, vacancy_id):
        """Analyze all applications for a specific vacancy"""
        try:
            vacancy = get_object_or_404(Vacancy, id=vacancy_id)
            
            # Get all applications for this vacancy that have CVs
            applications = Application.objects.filter(
                vacancy=vacancy,
                cv__isnull=False
            ).distinct()
            
            if not applications.exists():
                return Response(
                    {"detail": "No applications with CVs found for this vacancy"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ai_service = AIService()
            analyzed_count = 0
            results = []
            
            for application in applications:
                try:
                    if not application.cv or not application.cv.raw_file or not application.cv.candidate:
                        continue
                    
                    # Analyze the CV
                    analysis_result = ai_service.analyze_cv_for_vacancy(application.cv, vacancy)
                    
                    # Update the candidate with AI scoring results
                    candidate = application.cv.candidate
                    candidate.ai_score_out_of_10 = analysis_result.get('overall_score', 0)
                    candidate.ai_analysis = analysis_result.get('reasoning', '')
                    candidate.ai_score_breakdown = analysis_result.get('score_breakdown', {})
                    candidate.ai_scoring_date = timezone.now()
                    candidate.latest_vacancy_scored = vacancy
                    candidate.save()
                    
                    analyzed_count += 1
                    results.append({
                        "application_id": application.id,
                        "candidate_name": candidate.full_name,
                        "score": candidate.ai_score_out_of_10,
                        "recommendation": "HIRE" if candidate.ai_score_out_of_10 >= 8 else "MAYBE" if candidate.ai_score_out_of_10 >= 6 else "REJECT"
                    })
                    
                except Exception as e:
                    print(f"Failed to analyze application {application.id}: {str(e)}")
                    continue
            
            return Response({
                "vacancy_id": vacancy.id,
                "vacancy_title": vacancy.title,
                "analyzed_count": analyzed_count,
                "total_applications": applications.count(),
                "results": results,
                "message": f"Successfully analyzed {analyzed_count} applications"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"detail": f"Bulk analysis failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class TopCandidatesView(APIView):
    """Get top 5 candidates for a vacancy based on AI scores"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, vacancy_id):
        """Get top 5 candidates for a vacancy"""
        try:
            vacancy = get_object_or_404(Vacancy, id=vacancy_id)
            
            # Get top 5 applications by AI score (from candidate model)
            top_applications = Application.objects.filter(
                vacancy=vacancy,
                cv__candidate__ai_score_out_of_10__isnull=False
            ).order_by('-cv__candidate__ai_score_out_of_10')[:5]
            
            results = []
            for app in top_applications:
                if app.cv and app.cv.candidate:
                    candidate = app.cv.candidate
                    results.append({
                        "application_id": app.id,
                        "candidate_name": candidate.full_name,
                        "candidate_email": candidate.email,
                        "score": float(candidate.ai_score_out_of_10),
                        "ai_analysis": candidate.ai_analysis,
                        "score_breakdown": candidate.ai_score_breakdown,
                        "status": app.status
                    })
            
            return Response({
                "vacancy_id": vacancy.id,
                "vacancy_title": vacancy.title,
                "top_candidates": results,
                "count": len(results)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"detail": f"Failed to get top candidates: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def post(self, request, vacancy_id):
        """Automatically select and shortlist top 5 candidates"""
        try:
            vacancy = get_object_or_404(Vacancy, id=vacancy_id)
            
            # Get top 5 applications by AI score
            top_applications = Application.objects.filter(
                vacancy=vacancy,
                score_out_of_10__isnull=False
            ).order_by('-score_out_of_10')[:5]
            
            if not top_applications.exists():
                return Response(
                    {"detail": "No scored applications found. Run AI analysis first."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Update status to shortlisted
            shortlisted_count = 0
            for app in top_applications:
                app.status = 'shortlisted'
                app.save(update_fields=['status'])
                shortlisted_count += 1
            
            # Vacancy remains in collecting_applications status
            # Status will be changed to 'closed' when ready for interviews
            
            return Response({
                "vacancy_id": vacancy.id,
                "vacancy_title": vacancy.title,
                "shortlisted_count": shortlisted_count,
                "message": f"Successfully shortlisted top {shortlisted_count} candidates"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"detail": f"Failed to shortlist candidates: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CVUploadView(APIView):
    """Upload and process CV files with AI extraction"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Upload CV file and extract data using AI"""
        try:
            # Get uploaded file
            cv_file = request.FILES.get('cv_file')
            vacancy_id = request.data.get('vacancy_id')
            candidate_name = request.data.get('candidate_name', '')
            candidate_email = request.data.get('candidate_email', '')
            candidate_phone = request.data.get('candidate_phone', '')
            
            if not cv_file:
                return Response(
                    {"detail": "CV file is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not vacancy_id:
                return Response(
                    {"detail": "vacancy_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate file type
            allowed_types = ['application/pdf', 'application/msword', 
                           'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                           'text/plain']
            if cv_file.content_type not in allowed_types:
                return Response(
                    {"detail": "Only PDF, DOC, DOCX, and TXT files are allowed"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get vacancy
            vacancy = get_object_or_404(Vacancy, id=vacancy_id)
            
            # Create CV record (candidate will be created automatically by signal)
            from candidates.models import Candidate, CV, Application
            
            cv_record = CV.objects.create(
                raw_file=cv_file
            )
            
            # Create application (AI scoring will be triggered automatically by signal)
            application, app_created = Application.objects.get_or_create(
                vacancy=vacancy,
                cv=cv_record,
                defaults={'status': 'applied'}
            )
            
            if not app_created:
                return Response(
                    {"detail": "Application already exists for this CV and vacancy"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                "message": "CV uploaded and processed successfully. Candidate will be created automatically from CV data.",
                "application_id": application.id,
                "cv_id": cv_record.id,
                "vacancy_title": vacancy.title
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {"detail": f"CV processing failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _extract_text_from_file(self, file):
        """Extract text from uploaded file"""
        try:
            # For now, we'll handle text files and basic extraction
            # In production, you'd want to use libraries like PyPDF2, python-docx, etc.
            
            if file.content_type == 'application/pdf':
                # For PDF files, you'd use PyPDF2 or similar
                # For now, return a placeholder
                return "PDF content extraction not implemented yet. Please provide text version."
            
            elif file.content_type in ['application/msword', 
                                     'application/vnd.openxmlformats-officedocument.wordprocessingml.document']:
                # For Word documents, you'd use python-docx
                # For now, return a placeholder
                return "Word document extraction not implemented yet. Please provide text version."
            
            else:
                # For text files
                file.seek(0)
                return file.read().decode('utf-8')
                
        except Exception as e:
            print(f"Error extracting text from file: {str(e)}")
            return None

class CVTextExtractionView(APIView):
    """Extract data from CV text using AI"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Extract structured data from CV text"""
        try:
            cv_text = request.data.get('cv_text')
            vacancy_id = request.data.get('vacancy_id')
            
            if not cv_text:
                return Response(
                    {"detail": "cv_text is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if not vacancy_id:
                return Response(
                    {"detail": "vacancy_id is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get vacancy
            vacancy = get_object_or_404(Vacancy, id=vacancy_id)
            
            # Initialize AI service
            ai_service = AIService()
            
            # Extract structured data using AI
            extracted_data = ai_service.extract_cv_data(cv_text)
            
            return Response({
                "extracted_data": extracted_data,
                "vacancy_title": vacancy.title,
                "message": "CV data extracted successfully"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response(
                {"detail": f"CV extraction failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )